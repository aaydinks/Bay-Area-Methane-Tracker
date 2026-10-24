"""Synthetic sites with known truth (docs/PLAN.md section 8.1).

Site parameters are either drawn from the model's priors (the setting where
90% intervals should cover the truth 90% of the time) or set to fixed
scenarios. The detection process mirrors the model: each overpass finds the
site emitting with probability f; while emitting the rate is drawn from the
truncated log-normal; the instrument detects with probability r * POD(q); a
detection reports q * exp(N(0, tau)).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
from scipy.optimize import brentq
from scipy.special import expit
from scipy.stats import truncnorm

from methanewatch import features
from methanewatch.config import Priors, SyntheticConfig
from methanewatch.impact import HOURS_PER_YEAR, KG_PER_T
from methanewatch.model.grid import LogRateGrid, mean_rate, rate_density
from methanewatch.model.pod import pod

START = datetime(2024, 1, 1, tzinfo=UTC)


def fine_grid(syn: SyntheticConfig) -> LogRateGrid:
    """Dense grid for computing true means (independent of the model's grid size)."""
    return LogRateGrid.build(syn.q_min_kg_hr, syn.q_max_kg_hr, 4001)


def true_qbar(mu: float, sigma: float, grid: LogRateGrid) -> float:
    return mean_rate(grid, rate_density(grid, mu, sigma))


def mu_for_qbar(qbar: float, sigma: float, grid: LogRateGrid) -> float:
    """The mu that gives a truncated mean rate of ``qbar``."""
    lo, hi = grid.x[0] - 10 * sigma, grid.x[-1]
    return brentq(lambda m: true_qbar(m, sigma, grid) - qbar, lo, hi)


def sites_from_prior(
    n_sites: int,
    priors: Priors,
    syn: SyntheticConfig,
    rng: np.random.Generator,
    *,
    covariates: Sequence[str] = (),
    beta_sd: float = 0.5,
) -> tuple[pd.DataFrame, dict[str, float]]:
    """Draw hyperparameters, then site parameters, from the model's priors.

    With ``covariates``, each site also gets made-up covariate values (one column
    per name) and the coefficients are drawn from their Normal(0, beta_sd) prior,
    applied to the covariates as the model standardizes them (ADR 0008).
    """
    hyper = {
        "alpha_f": rng.normal(priors.alpha_f_mu, priors.alpha_f_sd),
        "tau_f": abs(rng.normal(0, priors.tau_f_sd)),
        "alpha_mu": rng.normal(priors.alpha_mu_mu, priors.alpha_mu_sd),
        "tau_mu": abs(rng.normal(0, priors.tau_mu_sd)),
        "sigma": float(np.exp(rng.normal(priors.sigma_log_mu, priors.sigma_log_sd))),
    }
    site_ids = [f"synth-{i:02d}" for i in range(n_sites)]
    shift_f = shift_mu = np.zeros(n_sites)
    cols = pd.DataFrame(index=range(n_sites))
    if covariates:
        cols = features.synthetic_columns(covariates, n_sites, rng)
        X = features.design_synthetic(cols.assign(site_id=site_ids), covariates).X
        beta_f = rng.normal(0, beta_sd, len(covariates))
        beta_mu = rng.normal(0, beta_sd, len(covariates))
        shift_f, shift_mu = X @ beta_f, X @ beta_mu
        hyper |= {f"beta_f_{n}": b for n, b in zip(covariates, beta_f, strict=True)}
        hyper |= {f"beta_mu_{n}": b for n, b in zip(covariates, beta_mu, strict=True)}
    f = expit(hyper["alpha_f"] + shift_f + hyper["tau_f"] * rng.normal(size=n_sites))
    mu = hyper["alpha_mu"] + shift_mu + hyper["tau_mu"] * rng.normal(size=n_sites)
    sites = pd.DataFrame({"site_id": site_ids, "f": f, "mu": mu, "sigma": hyper["sigma"]})
    sites = pd.concat([sites, cols], axis=1)
    return with_truth(sites, syn), hyper


def sites_from_scenarios(syn: SyntheticConfig, names: list[str] | None = None) -> pd.DataFrame:
    grid = fine_grid(syn)
    rows = []
    for name in names or list(syn.scenarios):
        sc = syn.scenarios[name]
        rows.append(
            {
                "site_id": name,
                "f": sc.f,
                "mu": mu_for_qbar(sc.qbar_kg_hr, sc.sigma, grid),
                "sigma": sc.sigma,
            }
        )
    return with_truth(pd.DataFrame(rows), syn)


def with_truth(sites: pd.DataFrame, syn: SyntheticConfig) -> pd.DataFrame:
    grid = fine_grid(syn)
    qbar = [true_qbar(m, s, grid) for m, s in zip(sites["mu"], sites["sigma"], strict=True)]
    return sites.assign(qbar=qbar, E_t_yr=lambda d: d["f"] * d["qbar"] * HOURS_PER_YEAR / KG_PER_T)


def poisson_schedule(
    site_ids: list[str], syn: SyntheticConfig, rng: np.random.Generator
) -> pd.DataFrame:
    """Overpass counts per (site, instrument) drawn from the configured rates."""
    rows = [
        {
            "site_id": s,
            "instrument": name,
            "n_overpasses": int(rng.poisson(inst.overpasses_per_year * syn.years)),
        }
        for s in site_ids
        for name, inst in syn.instruments.items()
    ]
    return pd.DataFrame(rows)


def simulate_detections(
    sites: pd.DataFrame,
    schedule: pd.DataFrame,
    syn: SyntheticConfig,
    rng: np.random.Generator,
    *,
    start: datetime = START,
) -> pd.DataFrame:
    """One row per overpass in the ``schemas.detections`` layout, plus ``acquired_utc``."""
    lo, hi = np.log(syn.q_min_kg_hr), np.log(syn.q_max_kg_hr)
    span_s = syn.years * 365.25 * 86400
    params = sites.set_index("site_id")
    frames = []
    for row in schedule.itertuples(index=False):
        n = row.n_overpasses
        if n == 0:
            continue
        p = params.loc[row.site_id]
        inst = syn.instruments[row.instrument]
        emitting = rng.random(n) < p["f"]
        a, b = (lo - p["mu"]) / p["sigma"], (hi - p["mu"]) / p["sigma"]
        log_q = truncnorm.rvs(a, b, loc=p["mu"], scale=p["sigma"], size=n, random_state=rng)
        q = np.exp(log_q)
        detected = emitting & (rng.random(n) < inst.release_prob * pod(q, inst.q50_kg_hr, inst.w))
        q_obs = np.where(detected, q * np.exp(rng.normal(0, inst.meas_sigma_log, n)), np.nan)
        times = sorted(start + timedelta(seconds=float(t)) for t in rng.uniform(0, span_s, n))
        frames.append(
            pd.DataFrame(
                {
                    "overpass_id": [f"{row.site_id}:{row.instrument}:{i:04d}" for i in range(n)],
                    "site_id": row.site_id,
                    "instrument": row.instrument,
                    "acquired_utc": pd.to_datetime(times, utc=True),
                    "detected": detected,
                    "q_obs_kg_hr": q_obs,
                    "q_sigma_log": np.where(detected, inst.meas_sigma_log, np.nan),
                }
            )
        )
    return pd.concat(frames, ignore_index=True)
