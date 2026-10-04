import numpy as np
import pandas as pd
import pytensor.tensor as pt
import pytest

from methanewatch.config import load_model, load_synthetic
from methanewatch.model import persistence
from methanewatch.model.grid import LogRateGrid
from methanewatch.model.pod import pod
from methanewatch.validate import holdout, matched_pairs, operator

SYN = load_synthetic()
GRID = LogRateGrid.build(SYN.q_min_kg_hr, SYN.q_max_kg_hr, load_model().grid.n_points)
CURVES = {k: v.pod for k, v in SYN.instruments.items()}
RELEASE = {"tanager1": 0.9, "emit": 0.8, "aircraft": 1.0, "sentinel2": 1.0}


def test_fold_assignments_are_balanced_per_group():
    det = pd.DataFrame({"site_id": ["a"] * 10 + ["b"] * 7, "instrument": ["emit"] * 17})
    folds = holdout.fold_assignments(det, 5, np.random.default_rng(0))
    for _, g in folds.groupby(det["site_id"]):
        counts = g.value_counts()
        assert counts.max() - counts.min() <= 1
    assert set(folds) == set(range(5))


def test_detection_probability_matches_model():
    instruments = sorted(CURVES)
    f = np.array([[0.3, 0.6]])
    mu = np.array([[np.log(400), np.log(1500)]])
    sigma = np.array([0.8])
    got = holdout.detection_probability(f, mu, sigma, GRID, CURVES, RELEASE, instruments)[0]
    lw = persistence.log_rate_weights(pt.as_tensor(mu[0]), 0.8, GRID).eval()
    p = np.vstack([pod(GRID.q, CURVES[j].q50_kg_hr, CURVES[j].w) for j in instruments])
    r = np.array([RELEASE[j] for j in instruments])
    want = f[0][:, None] * r[None, :] * (np.exp(lw) @ p.T)
    np.testing.assert_allclose(got, want, rtol=1e-6)


def test_predictive_counts_shape_and_mean():
    p = np.full((4000, 2, 3), 0.25)
    n = np.array([[4, 0, 8], [0, 0, 0]])
    draws = holdout.predictive_counts(p, n, np.random.default_rng(1))
    assert draws.shape == (4000, 2)
    assert draws[:, 0].mean() == pytest.approx(3.0, abs=0.1)
    assert (draws[:, 1] == 0).all()


def test_holdout_evaluate_ignores_empty_site_folds():
    res = pd.DataFrame({"n_heldout": [5, 5, 5, 5, 0], "inside": [True, True, True, False, False]})
    out = holdout.evaluate(res)
    assert out.share_inside == pytest.approx(0.75)
    assert out.n_site_folds == 4 and not out.passed


def test_operator_compare_and_documentation_gate():
    est = pd.DataFrame(
        {
            "site_id": ["a", "b", "c"],
            "E_t_yr_med": [5000.0, 800.0, 3000.0],
            "E_t_yr_lo": [4000.0, 500.0, 1000.0],
            "E_t_yr_hi": [6000.0, 1200.0, 9000.0],
            "status": ["estimate", "estimate", "insufficient_data"],
        }
    )
    rep = pd.DataFrame(
        {
            "site_id": ["a", "a", "b", "c"],
            "year": [2022, 2019, 2023, 2023],
            "reported_ch4_t": [2000.0, 2000.0, 900.0, 100.0],
        }
    )
    table = operator.compare(est, rep, (2021, 2025))
    assert table[["site_id", "year", "direction"]].values.tolist() == [
        ["a", 2022, "model above"],
        ["b", 2023, "consistent"],
    ]
    res = operator.evaluate(table, None)
    assert not res.passed and res.undocumented == ["a 2022"]
    notes = pd.DataFrame(
        {"site_id": ["a"], "year": [2022], "explanation": ["floor and daytime bias"]}
    )
    assert operator.evaluate(table, notes).passed


def test_matched_pairs():
    t0 = pd.Timestamp("2025-06-01T18:00Z")
    det = pd.DataFrame(
        {
            "overpass_id": list("abcdefg"),
            "site_id": ["s"] * 6 + ["x"],
            "instrument": [
                "sentinel2",
                "emit",
                "sentinel2",
                "tanager1",
                "sentinel2",
                "emit",
                "emit",
            ],
            "acquired_utc": [
                t0,
                t0 + pd.Timedelta(hours=2),
                t0 + pd.Timedelta(days=10),
                t0 + pd.Timedelta(days=10, hours=5),
                t0 + pd.Timedelta(days=30),
                t0 + pd.Timedelta(days=35),
                t0,
            ],
            "detected": [True, True, True, False, False, True, True],
            "q_obs_kg_hr": [3000.0, 2500.0, 1500.0, np.nan, np.nan, 900.0, 4000.0],
        }
    )
    pairs = matched_pairs.pair(det, max_days=1)
    # The day-30 Sentinel-2 pass has no reference within a day; site x is never paired with s
    assert sorted(pairs["ref_overpass_id"]) == ["b", "d"]
    summary = matched_pairs.summarize(pairs).set_index("reference_rate_kg_hr")
    assert summary.loc["2000-5000", "pairs"] == 1 and summary.loc["2000-5000", "s2_detected"] == 1
    fp = summary.loc["no plume (false positives)"]
    assert fp["pairs"] == 1 and fp["s2_detected"] == 1
