"""Hierarchical persistence model in PyMC (docs/PLAN.md section 6).

For site s and instrument j, with x = ln q on the grid and h_s the rate density
while emitting (Normal(mu_s, sigma) in x, truncated to the grid):

  A_sj        = sum_k w_k h_s(x_k) POD_j(q_k)            (P(detect | emitting))
  non-detect: log(1 - f_s r_j A_sj)
  detect:     log f_s + log r_j
              + log sum_k w_k h_s(x_k) POD_j(q_k) LogNormal(q_obs | x_k, tau_i)

Non-detections enter as counts per (site, instrument), so the cost scales with
the number of detections, not overpasses.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import pymc as pm
import pytensor.tensor as pt
import xarray as xr

from methanewatch.config import ModelConfig, PodCurve, Priors, Sampler
from methanewatch.impact import HOURS_PER_YEAR, KG_PER_T
from methanewatch.model.grid import LogRateGrid
from methanewatch.model.pod import pod_matrix

LOG_2PI = np.log(2 * np.pi)
HYPER = ("alpha_f", "tau_f", "alpha_mu", "tau_mu", "sigma")


@dataclass(frozen=True)
class ModelData:
    """Arrays the likelihood needs, built from a detections table."""

    site_ids: list[str]
    instruments: list[str]
    grid: LogRateGrid
    log_pod: np.ndarray  # (J, K)
    release: np.ndarray  # (J,)
    n_overpasses: np.ndarray  # (S, J)
    n_nondetect: np.ndarray  # (S, J)
    det_site: np.ndarray  # (D,) site index of each detection
    det_inst: np.ndarray  # (D,) instrument index of each detection
    log_meas: np.ndarray  # (D, K) log LogNormal(q_obs | x_k, tau)

    @property
    def n_sites(self) -> int:
        return len(self.site_ids)


def prepare(
    detections: pd.DataFrame,
    grid: LogRateGrid,
    curves: dict[str, PodCurve],
    *,
    release: dict[str, float],
    meas_sigma_log: dict[str, float | None],
    allow_unconfirmed: bool = False,
) -> ModelData:
    """Turn a ``schemas.detections`` table into model arrays.

    ``q_sigma_log`` on a detection overrides the instrument's default
    measurement error.
    """
    site_ids = sorted(detections["site_id"].unique())
    instruments = sorted(detections["instrument"].unique())
    missing = set(instruments) - set(curves)
    if missing:
        raise ValueError(f"no POD curve for: {sorted(missing)}")
    _, pod = pod_matrix(
        grid, {k: curves[k] for k in instruments}, allow_unconfirmed=allow_unconfirmed
    )
    log_pod = np.log(np.clip(pod, 1e-300, None))

    si = pd.Index(site_ids).get_indexer(detections["site_id"])
    ji = pd.Index(instruments).get_indexer(detections["instrument"])
    detected = detections["detected"].to_numpy(bool)

    n_over = np.zeros((len(site_ids), len(instruments)), dtype=int)
    n_nd = np.zeros_like(n_over)
    np.add.at(n_over, (si, ji), 1)
    np.add.at(n_nd, (si[~detected], ji[~detected]), 1)

    det = detections.loc[detected]
    tau = det["q_sigma_log"].astype(float).to_numpy()
    default_tau = det["instrument"].map(meas_sigma_log).astype(float).to_numpy()
    tau = np.where(np.isnan(tau), default_tau, tau)
    if np.isnan(tau).any():
        raise ValueError("detections without q_sigma_log and no instrument default")
    log_q = np.log(det["q_obs_kg_hr"].to_numpy(float))
    z = (log_q[:, None] - grid.x[None, :]) / tau[:, None]
    log_meas = -0.5 * z**2 - np.log(tau)[:, None] - log_q[:, None] - 0.5 * LOG_2PI

    return ModelData(
        site_ids=site_ids,
        instruments=instruments,
        grid=grid,
        log_pod=log_pod,
        release=np.array([release[j] for j in instruments], dtype=float),
        n_overpasses=n_over,
        n_nondetect=n_nd,
        det_site=si[detected],
        det_inst=ji[detected],
        log_meas=log_meas,
    )


def log_rate_weights(mu, sigma, grid: LogRateGrid):
    """log(w_k h_s(x_k)) per site, shape (S, K), normalized over k."""
    x = pt.as_tensor(grid.x)[None, :]
    lp = -0.5 * ((x - pt.shape_padright(mu)) / sigma) ** 2 + np.log(grid.w)[None, :]
    return lp - pt.logsumexp(lp, axis=1, keepdims=True)


def loglik(f, mu, sigma, data: ModelData):
    """Total log-likelihood of all overpasses given site parameters."""
    f = pt.as_tensor(f)
    lw = log_rate_weights(mu, sigma, data.grid)  # (S, K)
    pod = pt.as_tensor(np.exp(data.log_pod))  # (J, K)
    p_det = pt.shape_padright(f) * data.release[None, :] * (pt.exp(lw) @ pod.T)  # (S, J)
    ll = pt.sum(pt.as_tensor(data.n_nondetect) * pt.log1p(-p_det))

    if len(data.det_site):
        s, j = data.det_site, data.det_inst
        terms = lw[s] + data.log_pod[j] + data.log_meas  # (D, K)
        ll = ll + pt.sum(pt.log(f[s]) + np.log(data.release[j]) + pt.logsumexp(terms, axis=1))
    return ll


def mean_rate(mu, sigma, grid: LogRateGrid):
    """Qbar_s = E[q | emitting] in kg/hr."""
    return pt.exp(log_rate_weights(mu, sigma, grid)) @ pt.as_tensor(grid.q)


def build_model(data: ModelData, priors: Priors) -> pm.Model:
    with pm.Model(coords={"site": data.site_ids}) as model:
        alpha_f = pm.Normal("alpha_f", priors.alpha_f_mu, priors.alpha_f_sd)
        tau_f = pm.HalfNormal("tau_f", priors.tau_f_sd)
        alpha_mu = pm.Normal("alpha_mu", priors.alpha_mu_mu, priors.alpha_mu_sd)
        tau_mu = pm.HalfNormal("tau_mu", priors.tau_mu_sd)
        sigma = pm.LogNormal("sigma", priors.sigma_log_mu, priors.sigma_log_sd)
        z_f = pm.Normal("z_f", 0, 1, dims="site")
        z_mu = pm.Normal("z_mu", 0, 1, dims="site")

        f = pm.Deterministic("f", pm.math.sigmoid(alpha_f + tau_f * z_f), dims="site")
        mu = pm.Deterministic("mu", alpha_mu + tau_mu * z_mu, dims="site")
        qbar = pm.Deterministic("qbar", mean_rate(mu, sigma, data.grid), dims="site")
        pm.Deterministic("E_t_yr", f * qbar * HOURS_PER_YEAR / KG_PER_T, dims="site")
        pm.Potential("loglik", loglik(f, mu, sigma, data))
    return model


def fit(model: pm.Model, sampler: Sampler, *, seed: int | None = None, quiet: bool = True):
    """Sample with NUTS (nutpie when installed). Returns an xarray DataTree."""
    with model:
        return pm.sample(
            draws=sampler.draws,
            tune=sampler.tune,
            chains=sampler.chains,
            target_accept=sampler.target_accept,
            random_seed=sampler.seed if seed is None else seed,
            progressbar=not quiet,
            quiet=quiet,
            compute_convergence_checks=False,
        )


@dataclass(frozen=True)
class Diagnostics:
    rhat_max: float
    ess_bulk_min: float
    divergences: int
    ok: bool


def diagnostics(
    idata: xr.DataTree, cfg: ModelConfig, var_names: list[str] | None = None
) -> Diagnostics:
    import arviz as az

    names = var_names or [*HYPER, "f", "mu"]
    rhat = az.rhat(idata, var_names=names).to_dataset()
    ess = az.ess(idata, var_names=names, method="bulk").to_dataset()
    rhat_max = max(float(v.max()) for v in rhat.data_vars.values())
    ess_min = min(float(v.min()) for v in ess.data_vars.values())
    div = int(idata["sample_stats"]["diverging"].values.sum())
    lim = cfg.diagnostics
    ok = rhat_max <= lim.rhat_max and ess_min >= lim.ess_bulk_min and div <= lim.max_divergences
    return Diagnostics(rhat_max=rhat_max, ess_bulk_min=ess_min, divergences=div, ok=ok)


def posterior_draws(idata: xr.DataTree, name: str) -> np.ndarray:
    """Draws with chains stacked: shape (n_samples, ...)."""
    da = idata["posterior"][name].stack(sample=("chain", "draw")).transpose("sample", ...)
    return np.asarray(da.values)
