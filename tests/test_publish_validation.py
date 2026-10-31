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
