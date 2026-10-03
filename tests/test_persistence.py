"""Model likelihood checked against an independent loop-based implementation."""

import numpy as np
import pandas as pd
import pytest
from scipy.integrate import quad
from scipy.stats import lognorm, norm

from methanewatch.config import PodCurve, load_model, load_synthetic
from methanewatch.model import persistence, simulate
from methanewatch.model.grid import LogRateGrid

SYN = load_synthetic()
GRID = LogRateGrid.build(SYN.q_min_kg_hr, SYN.q_max_kg_hr, load_model().grid.n_points)
CURVES = {k: v.pod for k, v in SYN.instruments.items()}
RELEASE = {"tanager1": 0.9, "emit": 0.8, "aircraft": 1.0, "sentinel2": 1.0}
TAU = {k: v.meas_sigma_log for k, v in SYN.instruments.items()}


def reference_loglik(df, f, mu, sigma):
    """Direct quadrature in q for each overpass; no grid, no vectorization."""
    lo, hi = SYN.q_min_kg_hr, SYN.q_max_kg_hr
    total = 0.0
    for row in df.itertuples():
        s = row.site_id
        inst = SYN.instruments[row.instrument]
        r = RELEASE[row.instrument]
        # truncated log-normal density of q on [lo, hi]
        mass = norm.cdf((np.log(hi) - mu[s]) / sigma) - norm.cdf((np.log(lo) - mu[s]) / sigma)

        def g(q, s=s, mass=mass):
            return lognorm.pdf(q, sigma, scale=np.exp(mu[s])) / mass

        def p(q, inst=inst):
            return norm.cdf((np.log(q) - np.log(inst.q50_kg_hr)) / inst.w)

        if not row.detected:
            a, _ = quad(lambda q, g=g, p=p: g(q) * p(q), lo, hi, limit=200, points=[inst.q50_kg_hr])
            total += np.log1p(-f[s] * r * a)
        else:
            tau = row.q_sigma_log

            def integrand(q, g=g, p=p, tau=tau, qo=row.q_obs_kg_hr):
                return g(q) * p(q) * lognorm.pdf(qo, tau, scale=q)

            b, _ = quad(integrand, lo, hi, limit=400, points=[row.q_obs_kg_hr])
            total += np.log(f[s] * r * b)
    return total


@pytest.fixture(scope="module")
def small_dataset():
    rng = np.random.default_rng(3)
    sites = pd.DataFrame(
        {
            "site_id": ["a", "b", "c"],
            "f": [0.2, 0.5, 0.05],
            "mu": [np.log(300), np.log(900), np.log(150)],
            "sigma": 0.8,
        }
    )
    schedule = pd.DataFrame(
        [
            {"site_id": s, "instrument": i, "n_overpasses": n}
            for s in ["a", "b", "c"]
            for i, n in [("tanager1", 12), ("emit", 6), ("sentinel2", 20)]
        ]
    )
    df = simulate.simulate_detections(sites, schedule, SYN, rng)
    assert df["detected"].sum() >= 3
    return df


def test_loglik_matches_reference(small_dataset):
    df = small_dataset
    data = persistence.prepare(df, GRID, CURVES, release=RELEASE, meas_sigma_log=TAU)
    f = {"a": 0.3, "b": 0.4, "c": 0.1}
    mu = {"a": np.log(250), "b": np.log(1200), "c": np.log(100)}
    sigma = 0.9
    got = persistence.loglik(
        np.array([f[s] for s in data.site_ids]),
        np.array([mu[s] for s in data.site_ids]),
        sigma,
        data,
    ).eval()
    want = reference_loglik(df, f, mu, sigma)
    assert got == pytest.approx(want, abs=0.05, rel=1e-3)


def test_mean_rate_matches_fine_grid():
    mu = np.array([np.log(300), np.log(2000)])
    got = persistence.mean_rate(mu, 0.8, GRID).eval()
    fine = simulate.fine_grid(SYN)
    want = [simulate.true_qbar(m, 0.8, fine) for m in mu]
    assert got == pytest.approx(want, rel=0.005)


def test_prepare_counts(small_dataset):
    data = persistence.prepare(small_dataset, GRID, CURVES, release=RELEASE, meas_sigma_log=TAU)
    assert data.n_overpasses.sum() == len(small_dataset)
    assert len(data.det_site) == small_dataset["detected"].sum()
    assert data.log_meas.shape == (len(data.det_site), GRID.x.size)


def test_prepare_refuses_unconfirmed_curves(small_dataset):
    unconfirmed = {k: PodCurve(q50_kg_hr=v.q50_kg_hr, w=v.w) for k, v in CURVES.items()}
    with pytest.raises(ValueError, match="unconfirmed"):
        persistence.prepare(small_dataset, GRID, unconfirmed, release=RELEASE, meas_sigma_log=TAU)


def test_scenario_mu_hits_requested_mean():
    sites = simulate.sites_from_scenarios(SYN)
    for name, sc in SYN.scenarios.items():
        row = sites.set_index("site_id").loc[name]
        assert row["qbar"] == pytest.approx(sc.qbar_kg_hr, rel=1e-4)


def test_summarize_applies_insufficient_data_rule(small_dataset):
    from methanewatch.model.persistence import Diagnostics
    from methanewatch.model.summarize import summarize

    data = persistence.prepare(small_dataset, GRID, CURVES, release=RELEASE, meas_sigma_log=TAU)
    rng = np.random.default_rng(0)
    n, s = 400, data.n_sites
    # Fake posterior: site 0 tight, site 1 spanning several orders of magnitude.
    E = np.column_stack(
        [rng.lognormal(np.log(100), 0.1, n), rng.lognormal(np.log(100), 3.0, n)]
        + [rng.lognormal(np.log(100), 0.1, n) for _ in range(s - 2)]
    )
    import xarray as xr

    def da(x):
        return (("chain", "draw", "site"), x.reshape(1, n, s))

    post = xr.Dataset(
        {"f": da(np.full((n, s), 0.3)), "qbar": da(E / 2.628), "E_t_yr": da(E)},
        coords={"site": data.site_ids},
    )
    idata = xr.DataTree.from_dict({"posterior": post})
    ok = Diagnostics(rhat_max=1.0, ess_bulk_min=1000, divergences=0, ok=True)
    out = summarize(idata, data, ok, load_model(), run_id="test")
    assert out.loc[0, "status"] == "estimate"
    assert out.loc[1, "status"] == "insufficient_data"
    bad = Diagnostics(rhat_max=1.2, ess_bulk_min=50, divergences=3, ok=False)
    out = summarize(idata, data, bad, load_model(), run_id="test")
    assert (out["status"] == "insufficient_data").all()


@pytest.mark.slow
def test_single_fit_recovers_scenarios():
    from methanewatch.validate.synthetic import fit_replicate

    cfg = load_model()
    sites = simulate.sites_from_scenarios(SYN)
    out = fit_replicate(sites, SYN, cfg, np.random.default_rng(5), seed=5)
    assert out["diag_ok"].all()
    assert out["E_t_yr_covered"].sum() >= 2
