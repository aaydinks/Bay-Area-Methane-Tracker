from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from methanewatch.config import RepairWindows, load_synthetic
from methanewatch.repair import placebo
from methanewatch.repair.model import Repair, RepairResult, assign_periods, window_counts

WINDOWS = RepairWindows(window_months=6, gap_days=14, min_overpasses_per_window=3)
T0 = datetime(2025, 1, 1, tzinfo=UTC)


def overpasses(site: str, days: list[int]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "overpass_id": [f"{site}:emit:{d}" for d in days],
            "site_id": site,
            "instrument": "emit",
            "acquired_utc": [T0 + timedelta(days=d) for d in days],
            "detected": False,
            "q_obs_kg_hr": np.nan,
            "q_sigma_log": np.nan,
        }
    )


def test_assign_periods_excludes_repair_and_gap():
    det = overpasses("a", [-400, -100, -1, 0, 5, 10, 20, 100, 400])
    rep = Repair("a", T0, T0 + timedelta(days=4))
    out = assign_periods(det, rep, WINDOWS).set_index("overpass_id")["period"]
    assert out.to_dict() == {
        "a:emit:-100": "before",
        "a:emit:-1": "before",
        "a:emit:20": "after",
        "a:emit:100": "after",
    }


def test_window_counts():
    det = pd.concat([overpasses("a", [-30, -20, 30]), overpasses("b", [-10, 40, 50])])
    counts = window_counts(assign_periods(det, Repair("a", T0), WINDOWS))
    assert counts.loc[("a", "before"), "total"] == 2
    assert counts.loc[("b", "after"), "total"] == 2


def test_pseudo_dates_leave_room_for_both_windows():
    det = overpasses("a", list(range(0, 800, 5)))
    dates = placebo.pseudo_dates(det, WINDOWS, 50, np.random.default_rng(0))
    w = timedelta(days=round(6 * 30.4375))
    assert min(dates) >= det["acquired_utc"].min() + w
    assert max(dates) <= det["acquired_utc"].max() - w


def _result(site: str, call: str) -> RepairResult:
    return RepairResult("r", site, [], call, *([None] * 7), 10, 10, True)


def test_false_positive_rate_ignores_insufficient_fits():
    calls = ["drop"] + ["inconclusive"] * 9 + ["insufficient_data"] * 5
    df = pd.DataFrame([{**_result(f"s{i % 3}", c).__dict__} for i, c in enumerate(calls)])
    out = placebo.false_positive_rate(df)
    assert out["fpr"] == pytest.approx(0.1)
    assert out["n_usable"] == 10 and out["n_insufficient"] == 5


def test_placebo_drops_pseudo_treated_site_from_controls():
    det = pd.concat([overpasses(s, list(range(0, 800, 7))) for s in "abc"])
    seen = []

    def verify(d, rep, controls, seed):
        seen.append((rep.site_id, tuple(controls)))
        return _result(rep.site_id, "inconclusive")

    placebo.run_placebos(det, ["a", "b", "c"], 20, verify, WINDOWS, np.random.default_rng(1))
    assert all(site not in controls for site, controls in seen)


def test_with_drop_only_changes_treated_site_after_date():
    from methanewatch.validate import repair_synthetic as rs

    syn = rs.repair_world(load_synthetic())
    sites = pd.DataFrame(
        {"site_id": ["t", "c"], "f": [0.9, 0.9], "mu": [np.log(5000)] * 2, "sigma": [0.3] * 2}
    )
    date = pd.Timestamp(rs.simulate.START + timedelta(days=500))
    det = rs.with_drop(sites, syn, np.random.default_rng(2), "t", date, factor=0.01)
    late = det[(det["site_id"] == "t") & (det["acquired_utc"] >= date)]
    early = det[(det["site_id"] == "t") & (det["acquired_utc"] < date)]
    ctrl = det[det["site_id"] == "c"]
    assert late["detected"].mean() < 0.05
    assert early["detected"].mean() > 0.3
    assert ctrl["detected"].mean() > 0.3


@pytest.mark.slow
def test_repair_model_sees_a_large_drop():
    from methanewatch.validate import repair_synthetic as rs

    syn = rs.repair_world(load_synthetic())
    rng = np.random.default_rng(4)
    ctrl = rs.control_sites(syn, 5, rng)
    world = pd.concat([rs.simulate.sites_from_scenarios(syn, ["frequent-small"]), ctrl])
    date = pd.Timestamp(rs.simulate.START + timedelta(days=548))
    det = rs.with_drop(world, syn, rng, "frequent-small", date, factor=0.1)
    res = rs.make_verifier(syn)(
        det, Repair("frequent-small", date.to_pydatetime()), ctrl["site_id"].tolist(), 4
    )
    assert res.call == "drop"
