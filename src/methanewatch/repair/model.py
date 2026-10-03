"""Repair verification: before/after with control sites (docs/PLAN.md section 7).

The repair date is known, so this is a before/after comparison, not a search
for an unknown change point. Each (site, period) is a unit in the persistence
likelihood:

  logit f[s, after] = logit f[s, before] + gamma_f + delta_f * treated_s
  mu[s, after]      = mu[s, before]      + gamma_mu + delta_mu * treated_s

Control sites (same instruments, same windows) identify the common shifts
gamma, which absorb instrument changes and seasonality. The reported effect is
the treated site's after-period emissions relative to its counterfactual
(delta = 0), on the log scale:

  effect = log E[s, after] - log E_cf[s, after]

Call: "drop" if P(effect < 0) >= call_probability (0.975 by default), "rise" if
P(effect < 0) <= 1 - call_probability, "inconclusive" otherwise, and
"insufficient_data" if a window has too few usable overpasses or the fit fails
diagnostics. The call threshold is stricter than the reported 90% interval so the
nominal false-positive rate (5%) sits under the 10% placebo gate (ADR 0006).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

import numpy as np
import pandas as pd
import pymc as pm
import pytensor.tensor as pt

from methanewatch.config import ModelConfig, PodCurve, Priors, RepairWindows, Sampler
from methanewatch.impact import HOURS_PER_YEAR, KG_PER_T
from methanewatch.model import persistence
from methanewatch.model.grid import LogRateGrid

Call = Literal["drop", "rise", "inconclusive", "insufficient_data"]
PERIODS = ("before", "after")
REPAIR_PARAMS = ("alpha_f", "alpha_mu", "sigma", "gamma_f", "gamma_mu", "delta_f", "delta_mu")


@dataclass(frozen=True)
class Repair:
    site_id: str
    date_start: datetime
    date_end: datetime | None = None
    repair_id: str = "repair"


def _utc(t: datetime) -> pd.Timestamp:
    ts = pd.Timestamp(t)
    return ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")


def assign_periods(
    detections: pd.DataFrame, repair: Repair, windows: RepairWindows
) -> pd.DataFrame:
    """Label each overpass ``before`` / ``after`` and drop those outside both windows.

    before = [start - W, start), after = (end + gap, end + gap + W]. Overpasses
    during the repair and the gap that follows are excluded.
    """
    w = timedelta(days=round(windows.window_months * 30.4375))
    start = _utc(repair.date_start)
    end = _utc(repair.date_end or repair.date_start)
    after_start = end + timedelta(days=windows.gap_days)
    t = detections["acquired_utc"]
    period = np.select(
        [(t >= start - w) & (t < start), (t > after_start) & (t <= after_start + w)],
        ["before", "after"],
        default="",
    )
    out = detections.assign(period=period)
    return out[out["period"] != ""].reset_index(drop=True)


def call_from_probability(p_decrease: float, call_probability: float) -> Call:
    if p_decrease >= call_probability:
        return "drop"
    if p_decrease <= 1 - call_probability:
        return "rise"
    return "inconclusive"


def window_counts(labelled: pd.DataFrame) -> pd.DataFrame:
    """Usable overpasses per (site, period, instrument)."""
    counts = labelled.pivot_table(
        index=["site_id", "period"],
        columns="instrument",
        values="overpass_id",
        aggfunc="count",
        fill_value=0,
    )
    return counts.assign(total=counts.sum(axis=1))


@dataclass(frozen=True)
class RepairResult:
    repair_id: str
    site_id: str
    controls: list[str]
    call: Call
    effect_med: float | None
    effect_lo: float | None
    effect_hi: float | None
    p_decrease: float | None
    dE_t_yr_med: float | None
    dE_t_yr_lo: float | None
    dE_t_yr_hi: float | None
    n_before: int
    n_after: int
    diag_ok: bool | None
    reason: str = ""


def build_model(
    data: persistence.ModelData, units: pd.DataFrame, treated: str, priors: Priors
) -> pm.Model:
    """``units`` has one row per data.site_ids entry with columns site_id, period."""
    sites = sorted(units["site_id"].unique())
    s_idx = pd.Index(sites).get_indexer(units["site_id"])
    after = (units["period"] == "after").to_numpy(float)
    is_treated = (units["site_id"] == treated).to_numpy(float)
    t_site = sites.index(treated)

    with pm.Model(coords={"site": sites, "unit": data.site_ids}) as model:
        alpha_f = pm.Normal("alpha_f", priors.alpha_f_mu, priors.alpha_f_sd)
        tau_f = pm.HalfNormal("tau_f", priors.tau_f_sd)
        alpha_mu = pm.Normal("alpha_mu", priors.alpha_mu_mu, priors.alpha_mu_sd)
        tau_mu = pm.HalfNormal("tau_mu", priors.tau_mu_sd)
        sigma = pm.LogNormal("sigma", priors.sigma_log_mu, priors.sigma_log_sd)
        z_f = pm.Normal("z_f", 0, 1, dims="site")
        z_mu = pm.Normal("z_mu", 0, 1, dims="site")
        gamma_f = pm.Normal("gamma_f", 0, 1)
        gamma_mu = pm.Normal("gamma_mu", 0, 0.5)
        delta_f = pm.Normal("delta_f", 0, 1.5)
        delta_mu = pm.Normal("delta_mu", 0, 1)

        base_f = alpha_f + tau_f * z_f
        base_mu = alpha_mu + tau_mu * z_mu
        logit_f = base_f[s_idx] + after * (gamma_f + delta_f * is_treated)
        mu = base_mu[s_idx] + after * (gamma_mu + delta_mu * is_treated)
        f = pm.math.sigmoid(logit_f)
        pm.Potential("loglik", persistence.loglik(f, mu, sigma, data))

        # Treated site after the repair, actual vs counterfactual (delta = 0)
        def annual(lf, m):
            q = persistence.mean_rate(pt.stack([m]), sigma, data.grid)[0]
            return pm.math.sigmoid(lf) * q * HOURS_PER_YEAR / KG_PER_T

        lf_cf = base_f[t_site] + gamma_f
        mu_cf = base_mu[t_site] + gamma_mu
        e_after = pm.Deterministic("E_after", annual(lf_cf + delta_f, mu_cf + delta_mu))
        e_cf = pm.Deterministic("E_counterfactual", annual(lf_cf, mu_cf))
        pm.Deterministic("E_before", annual(base_f[t_site], base_mu[t_site]))
        pm.Deterministic("effect", pt.log(e_after) - pt.log(e_cf))
    return model


def verify_repair(
    detections: pd.DataFrame,
    repair: Repair,
    controls: list[str],
    *,
    grid: LogRateGrid,
    curves: dict[str, PodCurve],
    release: dict[str, float],
    meas_sigma_log: dict[str, float | None],
    cfg: ModelConfig,
    windows: RepairWindows,
    sampler: Sampler,
    seed: int | None = None,
    allow_unconfirmed: bool = False,
) -> RepairResult:
    controls = [c for c in controls if c != repair.site_id]
    sub = detections[detections["site_id"].isin([repair.site_id, *controls])]
    labelled = assign_periods(sub, repair, windows)
    counts = labelled[labelled["site_id"] == repair.site_id].groupby("period").size()
    n_before, n_after = int(counts.get("before", 0)), int(counts.get("after", 0))

    def empty(reason: str, diag_ok: bool | None = None) -> RepairResult:
        return RepairResult(
            repair.repair_id,
            repair.site_id,
            controls,
            "insufficient_data",
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            n_before,
            n_after,
            diag_ok,
            reason,
        )

    if min(n_before, n_after) < windows.min_overpasses_per_window:
        return empty(f"fewer than {windows.min_overpasses_per_window} overpasses in a window")
    if not controls:
        return empty("no control sites")

    unit_df = labelled.assign(site_id=labelled["site_id"] + "|" + labelled["period"])
    data = persistence.prepare(
        unit_df,
        grid,
        curves,
        release=release,
        meas_sigma_log=meas_sigma_log,
        allow_unconfirmed=allow_unconfirmed,
    )
    units = pd.DataFrame([u.split("|") for u in data.site_ids], columns=["site_id", "period"])
    model = build_model(data, units, repair.site_id, cfg.priors)
    idata = persistence.fit(model, sampler, seed=seed)
    diag = persistence.diagnostics(idata, cfg, list(REPAIR_PARAMS))
    if not diag.ok:
        return empty("fit failed diagnostics", diag_ok=False)

    eff = persistence.posterior_draws(idata, "effect")
    e_cf = persistence.posterior_draws(idata, "E_counterfactual")
    d_e = e_cf - persistence.posterior_draws(idata, "E_after")
    tail = (1 - cfg.interval_mass) / 2
    lo, med, hi = np.quantile(eff, [tail, 0.5, 1 - tail])
    dlo, dmed, dhi = np.quantile(d_e, [tail, 0.5, 1 - tail])
    p_dec = float((eff < 0).mean())
    call = call_from_probability(p_dec, windows.call_probability)
    return RepairResult(
        repair.repair_id,
        repair.site_id,
        controls,
        call,
        float(med),
        float(lo),
        float(hi),
        p_dec,
        float(dmed),
        float(dlo),
        float(dhi),
        n_before,
        n_after,
        True,
    )
