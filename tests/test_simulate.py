import numpy as np
import pandas as pd
import pytest

from methanewatch import schemas
from methanewatch.config import load_model, load_synthetic
from methanewatch.model import simulate
from methanewatch.validate.synthetic import evaluate, wilson

SYN = load_synthetic()


def test_simulated_detections_match_schema_and_rates():
    rng = np.random.default_rng(0)
    sites = pd.DataFrame({"site_id": ["x"], "f": [0.4], "mu": [np.log(3000)], "sigma": [0.3]})
    schedule = pd.DataFrame([{"site_id": "x", "instrument": "aircraft", "n_overpasses": 4000}])
    det = simulate.simulate_detections(sites, schedule, SYN, rng)
    schemas.detections.validate(det)
    # aircraft POD is ~1 at 3,000 kg/hr, so the detection share should be close to f
    assert det["detected"].mean() == pytest.approx(0.4, abs=0.03)
    q = det.loc[det["detected"], "q_obs_kg_hr"]
    assert np.log(q).std() == pytest.approx(np.hypot(0.3, 0.3), rel=0.1)


def test_prior_sites_have_truth_columns():
    sites, hyper = simulate.sites_from_prior(5, load_model().priors, SYN, np.random.default_rng(1))
    assert set(hyper) == {"alpha_f", "tau_f", "alpha_mu", "tau_mu", "sigma"}
    assert {"f", "mu", "sigma", "qbar", "E_t_yr"} <= set(sites.columns)
    assert (sites["qbar"] >= SYN.q_min_kg_hr).all()


def test_wilson_interval():
    lo, hi = wilson(90, 100)
    assert lo < 0.9 < hi
    assert wilson(0, 0) == (0.0, 1.0)


def test_gate_evaluation():
    rows = 100
    res = pd.DataFrame(
        {
            "replicate": np.arange(rows) // 10,
            "site_id": "s",
            "diag_ok": True,
            "f_covered": np.arange(rows) % 10 != 0,  # 90%
            "qbar_covered": np.arange(rows) % 10 != 0,
            "E_t_yr_covered": np.arange(rows) % 5 != 0,  # 80% -> fail
        }
    )
    gate = evaluate(res, SYN)
    assert gate.coverage["f"] == pytest.approx(0.9)
    assert not gate.passed
