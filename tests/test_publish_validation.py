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
