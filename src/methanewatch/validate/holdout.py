"""Hold-out prediction (docs/PLAN.md section 8.3; part of Gate 4).

Each site's usable overpasses are split into folds, stratified by instrument.
For each fold the model is fit on the other folds, and the posterior
predictive distribution of the number of detections in the held-out
overpasses is compared with what was observed. Pass when the observed count
falls inside the 90% predictive interval for at least ``TARGET`` of
site-folds (a proposed threshold, PLAN 8.3).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from methanewatch.config import ModelConfig, PodCurve, Sampler
from methanewatch.model import persistence
from methanewatch.model.grid import LogRateGrid
from methanewatch.model.pod import pod

TARGET = 0.80


def fold_assignments(det: pd.DataFrame, n_folds: int, rng: np.random.Generator) -> pd.Series:
    """Fold id per overpass, balanced within every (site, instrument) group."""
    folds = pd.Series(-1, index=det.index, dtype=int)
    for _, idx in det.groupby(["site_id", "instrument"]).groups.items():
        order = rng.permutation(np.asarray(idx))
        start = int(rng.integers(n_folds))
        folds.loc[order] = (start + np.arange(len(order))) % n_folds
    return folds


def detection_probability(
    f: np.ndarray,
    mu: np.ndarray,
    sigma: np.ndarray,
    grid: LogRateGrid,
    curves: dict[str, PodCurve],
    release: dict[str, float],
    instruments: list[str],
) -> np.ndarray:
    """P(detect) per draw, site and instrument: shape (draws, S, J). NumPy mirror of the model."""
    lp = -0.5 * ((grid.x[None, None, :] - mu[:, :, None]) / sigma[:, None, None]) ** 2
    lp = lp + np.log(grid.w)[None, None, :]
    lp -= lp.max(axis=2, keepdims=True)
    h = np.exp(lp)
    h /= h.sum(axis=2, keepdims=True)  # w_k h_s(x_k), normalized
    p = np.vstack([pod(grid.q, curves[j].q50_kg_hr, curves[j].w) for j in instruments])  # (J, K)
    r = np.array([release[j] for j in instruments])
    return f[:, :, None] * r[None, None, :] * (h @ p.T)


def predictive_counts(
    p_det: np.ndarray, n_heldout: np.ndarray, rng: np.random.Generator
) -> np.ndarray:
    """Posterior predictive detections per site: (draws, S), summing instruments."""
    return rng.binomial(n_heldout[None, :, :], p_det).sum(axis=2)


@dataclass(frozen=True)
class HoldoutResult:
    passed: bool
    share_inside: float
    n_site_folds: int
    target: float = TARGET


def run(
    det: pd.DataFrame,
    *,
    grid: LogRateGrid,
    curves: dict[str, PodCurve],
    release: dict[str, float],
    meas_sigma_log: dict[str, float | None],
    cfg: ModelConfig,
    sampler: Sampler,
    n_folds: int,
    rng: np.random.Generator,
    allow_unconfirmed: bool = False,
) -> pd.DataFrame:
    """One row per (fold, site): observed held-out detections and the predictive interval."""
    det = det.reset_index(drop=True)
    folds = fold_assignments(det, n_folds, rng)
    instruments = sorted(det["instrument"].unique())
    tail = (1 - cfg.interval_mass) / 2
    rows = []
    for k in range(n_folds):
        train, test = det[folds != k], det[folds == k]
        data = persistence.prepare(
            train,
            grid,
            curves,
            release=release,
            meas_sigma_log=meas_sigma_log,
            allow_unconfirmed=allow_unconfirmed,
        )
        idata = persistence.fit(
            persistence.build_model(data, cfg.priors), sampler, seed=int(rng.integers(2**31))
        )
        diag = persistence.diagnostics(idata, cfg)
        f = persistence.posterior_draws(idata, "f")
        mu = persistence.posterior_draws(idata, "mu")
        sigma = persistence.posterior_draws(idata, "sigma")
        p_det = detection_probability(f, mu, sigma, grid, curves, release, instruments)

        n_held = test.pivot_table(
            index="site_id",
            columns="instrument",
            values="overpass_id",
            aggfunc="count",
            fill_value=0,
        ).reindex(index=data.site_ids, columns=instruments, fill_value=0)
        draws = predictive_counts(p_det, n_held.to_numpy(), rng)
        observed = test.groupby("site_id")["detected"].sum().reindex(data.site_ids, fill_value=0)
        lo, hi = np.quantile(draws, [tail, 1 - tail], axis=0)
        for s, site in enumerate(data.site_ids):
            rows.append(
                {
                    "fold": k,
                    "site_id": site,
                    "n_heldout": int(n_held.loc[site].sum()),
                    "observed": int(observed[site]),
                    "pred_mean": float(draws[:, s].mean()),
                    "pred_lo": float(lo[s]),
                    "pred_hi": float(hi[s]),
                    "inside": bool(lo[s] <= observed[site] <= hi[s]),
                    "diag_ok": diag.ok,
                }
            )
    return pd.DataFrame(rows)


def evaluate(results: pd.DataFrame, target: float = TARGET) -> HoldoutResult:
    usable = results[results["n_heldout"] > 0]
    share = float(usable["inside"].mean()) if len(usable) else float("nan")
    return HoldoutResult(passed=bool(share >= target), share_inside=share, n_site_folds=len(usable))
