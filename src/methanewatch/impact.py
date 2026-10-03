"""Impact accounting (docs/PLAN.md section 9).

Functions take posterior draws and return draws; summarize them with
``interval``. Methane is only "avoided" after a repair test calls a drop.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

from methanewatch.config import ImpactConfig, load_impact

HOURS_PER_YEAR = 8760
KG_PER_T = 1000

RepairCall = Literal["drop", "rise", "inconclusive", "insufficient_data"]


@dataclass(frozen=True)
class Interval:
    median: float
    lo: float
    hi: float
    mass: float


@dataclass(frozen=True)
class Converted:
    values: np.ndarray
    confirmed: bool  # False when the conversion factor is still unconfirmed
    source: str | None


def interval(draws: np.ndarray, mass: float = 0.90) -> Interval:
    tail = (1 - mass) / 2 * 100
    lo, med, hi = np.percentile(draws, [tail, 50, 100 - tail])
    return Interval(median=float(med), lo=float(lo), hi=float(hi), mass=mass)


def annual_t(f: np.ndarray, qbar_kg_hr: np.ndarray) -> np.ndarray:
    """E_s = f_s * Qbar_s * 8760 h, in t/yr."""
    return np.asarray(f) * np.asarray(qbar_kg_hr) * HOURS_PER_YEAR / KG_PER_T


def ch4_from_rate(rate_kg_hr: np.ndarray | float, hours: float) -> np.ndarray:
    return np.asarray(rate_kg_hr, dtype=float) * hours / KG_PER_T


def ch4_avoided_t(
    e_before_t_yr: np.ndarray,
    e_after_t_yr: np.ndarray,
    years_held: float,
    call: RepairCall,
) -> np.ndarray | None:
    """(E_before - E_after) * years the drop holds; None unless the call is "drop"."""
    if call != "drop":
        return None
    return (np.asarray(e_before_t_yr) - np.asarray(e_after_t_yr)) * years_held


def to_co2e(
    ch4_t: np.ndarray | float,
    horizon: Literal["gwp20", "gwp100"],
    cfg: ImpactConfig | None = None,
) -> Converted:
    factor = getattr(cfg or load_impact(), horizon)
    return Converted(np.asarray(ch4_t, dtype=float) * factor.value, factor.confirmed, factor.source)


def to_usd(co2e_t: np.ndarray | float, cfg: ImpactConfig | None = None) -> Converted:
    price = (cfg or load_impact()).usd_per_t_co2e
    return Converted(np.asarray(co2e_t, dtype=float) * price.value, price.confirmed, price.source)


def population_within(site_id: str, radius_km: float) -> int:
    """ACS block-group population inside the site buffer (context, not a health effect)."""
    raise NotImplementedError("population context: week 10, PLAN section 9.3")
