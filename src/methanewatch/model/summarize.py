"""Posterior draws -> ``site_estimates`` rows, with the insufficient-data rule (PLAN 6.6)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import xarray as xr

from methanewatch import schemas
from methanewatch.config import ModelConfig
from methanewatch.model.persistence import Diagnostics, ModelData, posterior_draws


def quantiles(draws: np.ndarray, mass: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Median and equal-tailed interval along the sample axis."""
    tail = (1 - mass) / 2
    lo, med, hi = np.quantile(draws, [tail, 0.5, 1 - tail], axis=0)
    return med, lo, hi


def summarize(
    idata: xr.DataTree,
    data: ModelData,
    diag: Diagnostics,
    cfg: ModelConfig,
    *,
    run_id: str,
    period: str = "all",
    provisional: bool = False,
) -> pd.DataFrame:
    mass = cfg.interval_mass
    out = pd.DataFrame(
        {
            "site_id": data.site_ids,
            "period": period,
            "run_id": run_id,
            "n_usable_overpasses": data.n_overpasses.sum(axis=1),
            "n_detections": data.n_overpasses.sum(axis=1) - data.n_nondetect.sum(axis=1),
        }
    )
    for name, col in [("f", "f"), ("qbar", "qbar_kg_hr"), ("E_t_yr", "E_t_yr")]:
        med, lo, hi = quantiles(posterior_draws(idata, name), mass)
        out[f"{col}_med"], out[f"{col}_lo"], out[f"{col}_hi"] = med, lo, hi

    rule = cfg.insufficient_data
    width = np.log10(out["E_t_yr_hi"] / out["E_t_yr_lo"].clip(lower=1e-12))
    insufficient = (
        (out["n_usable_overpasses"] < rule.min_usable_overpasses)
        | (width > rule.max_interval_orders_of_magnitude)
        | (not diag.ok)
    )
    ok_status = "provisional" if provisional else "estimate"
    out["status"] = np.where(insufficient, "insufficient_data", ok_status)
    out["rhat_max"] = diag.rhat_max
    out["ess_bulk_min"] = diag.ess_bulk_min
    out["divergences"] = diag.divergences
    return schemas.site_estimates.validate(out)
