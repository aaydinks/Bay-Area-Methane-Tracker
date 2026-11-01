"""The method checks are read from the committed reports, never typed in."""

from pathlib import Path

import pytest

from methanewatch.publish.validation import validation_rows

REPORTS = Path(__file__).parents[1] / "reports"


@pytest.fixture(scope="module")
def rows():
    return {r["report_id"]: r for r in validation_rows(REPORTS)}


def test_gate3_coverage_numbers_come_from_the_report(rows):
    r = rows["synthetic-20261003T223204Z"]
    assert r["gate"] == "gate3" and r["result"] == "pass"
    assert r["metrics"]["coverage_f"] == 0.910
    assert r["metrics"]["coverage_qbar"] == 0.900
    assert r["metrics"]["coverage_e"] == 0.895
    assert r["metrics"]["diag_fail_frac"] == pytest.approx(0.07)
    assert r["metrics"]["replicates"] == 200 and r["metrics"]["sites"] == 10
    assert r["created_at"].startswith("2026-10-03")


def test_covariate_gate3_runs_are_marked(rows):
    passed = rows["synthetic-20261024T013708Z"]
    failed = rows["synthetic-20261024T010329Z"]
    assert passed["result"] == "pass" and failed["result"] == "fail"
    assert passed["metrics"]["covariates"] == ["closed", "log_area"]
    assert failed["metrics"]["diag_fail_frac"] == pytest.approx(0.115)


def test_holdout_share_inside(rows):
    r = rows["holdout-synthetic-20261004T001513Z"]
    assert r["gate"] == "holdout" and r["result"] == "pass"
    assert r["metrics"] == {"share_inside": 0.98, "folds": 50, "target": 0.8}


def test_placebo_and_power_rows(rows):
    placebo = rows["repair-synthetic-20261003T234738Z-placebo"]
    assert placebo["result"] == "dry-run" and not placebo["superseded"]
    assert placebo["metrics"]["false_positive_rate"] == 0.020
    assert placebo["metrics"]["wilson"] == [0.007, 0.056]
    assert placebo["metrics"]["fits"] == 153 and placebo["metrics"]["worlds"] == 40
    assert placebo["metrics"]["call_probability"] == 0.975
    power = rows["repair-synthetic-20261003T234738Z-power"]
    assert power["metrics"]["p_drop_by_factor"] == {
        "0.100": 0.214,
        "0.250": 0.429,
        "0.500": 0.143,
        "0.750": 0.0,
    }
    assert "none of the tested drops reached 80% power" in power["note"]
    old = rows["repair-synthetic-20261003T232115Z-placebo"]
    assert old["superseded"] and old["metrics"]["false_positive_rate"] == 0.129


def _cloud_result(passed1: bool, rehearsal: bool = False) -> dict:
    def r(v):
        return {"value": v, "interval": [v - 0.01, v + 0.01]}

    def rates(keys):
        return {m: {k: r(0.1) for k in keys} for m in ("tile_rule", "sen2cor", "model")}

    c1_keys = ("false_usable", "false_unusable")
    claim1 = {
        "n_patches": 10,
        "n_sites": 4,
        "rates": rates(c1_keys),
        "comparisons": {
            "sen2cor": {
                "false_usable_diff": r(-0.05),
                "false_unusable_diff": r(0.0),
                "passed": passed1,
            }
        },
        "passed": passed1,
    }
    c2_keys = ("cloud_caused_per_target", "detection_share")
    claim2 = {
        "n_sites": 3,
        "n_targets": 6,
        "n_plumes": 18,
        "rates": rates(c2_keys),
        "comparisons": {
            "sen2cor": {
                "cloud_caused_diff": r(0.2),
                "detection_share_diff": r(0.0),
                "passed": False,
            }
        },
        "passed": False,
    }
    ref1 = {
        "n_patches": 5,
        "rates": {**rates(c1_keys), "unetmobv2_v2": {k: r(0.05) for k in c1_keys}},
    }
    ref2 = {"rates": {**rates(c2_keys), "unetmobv2_v2": {k: r(0.05) for k in c2_keys}}}
    return {
        "rehearsal": rehearsal,
        "amplitude": {"amplitude": 0.05},
        "claim1": {
            "all_heldout": claim1,
            "west_coast": claim1,
            "official_test_with_reference": ref1,
        },
        "claim2": {"all_heldout": claim2, "official_test_with_reference": ref2},
    }


def _write_cloud_report(root: Path, result: dict, run_id: str) -> None:
    import json

    folder = root / "validation" / "s2-cloud-model"
    folder.mkdir(parents=True)
    manifest = json.dumps({"run_id": run_id, "created_at": "2026-11-01T00:00:00+00:00"}, indent=2)
    (folder / f"{run_id}.md").write_text(f"# Cloud model ({run_id})\n\n```json\n{manifest}\n```\n")
    (folder / f"{run_id}.json").write_text(json.dumps(result))


def test_cloud_model_rows_come_from_the_results_file(tmp_path):
    _write_cloud_report(tmp_path, _cloud_result(passed1=True), "s2-cloud-model-x")
    rows = {r["gate"]: r for r in validation_rows(tmp_path)}
    usable, detections = rows["s2_cloud_usable"], rows["s2_cloud_detections"]
    assert usable["result"] == "pass" and detections["result"] == "fail"
    assert usable["report_id"] == "s2-cloud-model-x-claim1"
    assert usable["metrics"]["rates"]["model"]["false_usable"] == pytest.approx([0.1, 0.09, 0.11])
    assert usable["metrics"]["comparisons"]["sen2cor"]["passed"] is True
    assert set(usable["metrics"]["reference"]["rates"]) == {"model", "unetmobv2_v2"}
    assert detections["metrics"]["amplitude"] == 0.05
    assert usable["created_at"] == "2026-11-01T00:00:00+00:00"


def test_a_cloud_model_rehearsal_is_never_published(tmp_path):
    _write_cloud_report(tmp_path, _cloud_result(passed1=True, rehearsal=True), "s2-cloud-model-r")
    assert validation_rows(tmp_path) == []


def test_the_committed_cloud_model_test_gives_one_row_per_claim(rows):
    cloud = {r["gate"]: r for r in rows.values() if r["gate"].startswith("s2_cloud")}
    assert set(cloud) == {"s2_cloud_usable", "s2_cloud_detections"}
    usable = cloud["s2_cloud_usable"]["metrics"]
    # Every compared method has a rate with its 90% range, and every comparison a verdict
    assert {"tile_rule", "threshold", "sen2cor", "s2cloudless", "model"} <= set(usable["rates"])
    assert all(len(v["false_usable"]) == 3 for v in usable["rates"].values())
    assert all(isinstance(c["passed"], bool) for c in usable["comparisons"].values())
    assert len(usable["bay_area"]) == 15


def _write_recent_report(root: Path, holds: bool | None) -> None:
    import json

    folder = root / "validation" / "s2-cloud-recent"
    folder.mkdir(parents=True)
    run_id = "s2-cloud-recent-x"
    eye = {"status": "scored", "passed": holds, "thumbnails": [{"thumb": 1}]}
    result = {
        "windows": {"site_days": 10},
        "reference": {"R1": 0.058, "R2": 0.087},
        "criteria": {"2_clear_kept": {"value": 0.05, "passed": True}, "6_eye": eye},
        "per_site": {"a": {"usable_model": 3}},
    }
    if holds is not None:
        result["verdict"] = {"holds": holds, "model_sites": ["a"] if holds else []}
    manifest = json.dumps({"run_id": run_id, "created_at": "2026-11-01T00:00:00+00:00"}, indent=2)
    (folder / f"{run_id}.md").write_text(f"# Recent ({run_id})\n\n```json\n{manifest}\n```\n")
    (folder / f"{run_id}.json").write_text(json.dumps(result))


def test_the_recent_pass_check_is_one_row_with_counts_only_when_it_holds(tmp_path):
    _write_recent_report(tmp_path, holds=True)
    (row,) = validation_rows(tmp_path)
    assert row["gate"] == "s2_cloud_recent" and row["result"] == "pass"
    assert row["metrics"]["per_site_2025"] == {"a": {"usable_model": 3}}
    assert "thumbnails" not in row["metrics"]["criteria"]["6_eye"]


def test_a_failed_recent_pass_check_publishes_no_counts(tmp_path):
    _write_recent_report(tmp_path, holds=False)
    (row,) = validation_rows(tmp_path)
    assert row["result"] == "fail" and "per_site_2025" not in row["metrics"]


def test_an_unfinished_recent_pass_check_is_not_published(tmp_path):
    _write_recent_report(tmp_path, holds=None)
    assert validation_rows(tmp_path) == []
