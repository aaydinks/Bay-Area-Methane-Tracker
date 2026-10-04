"""Plume-rate quantification by integrated mass enhancement (docs/PLAN.md section 5, phase 4).

  Q = U_eff * IME / L,  with L = sqrt(plume area) and U_eff = a * U10 + b.

Enhancements arrive as column-averaged dry-air mole fraction (ppb). They are
converted to mass per area with the dry-air column from surface pressure:

  dOmega [kg/m^2] = dX [ppb] * 1e-9 * P / (g * M_air) * M_CH4

The rate interval comes from a Monte Carlo over the 10 m wind, the U_eff
calibration, and background noise in the IME. The U_eff coefficients are in
``config/quantify.yaml`` and stay unconfirmed until checked (ADR 0002).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import xarray as xr

from methanewatch.config import QuantifyConfig, load_quantify

G = 9.80665  # m/s^2
M_AIR = 0.0289644  # kg/mol, dry air
M_CH4 = 0.01604246  # kg/mol


def ppb_to_kg_m2(ppb: np.ndarray | float, surface_pressure_pa: float) -> np.ndarray:
    """Column mass of a methane enhancement given in ppb."""
    dry_air_mol_m2 = surface_pressure_pa / (G * M_AIR)
    return np.asarray(ppb) * 1e-9 * dry_air_mol_m2 * M_CH4


def pixel_area_m2(da: xr.DataArray) -> float:
    """Area of one pixel; ``da`` needs regular ``x`` and ``y`` coordinates in metres."""
    dx = float(np.abs(np.diff(da["x"].values[:2]))[0])
    dy = float(np.abs(np.diff(da["y"].values[:2]))[0])
    return dx * dy


@dataclass(frozen=True)
class Plume:
    ime_kg: float
    area_m2: float
    n_pixels: int
    background_sigma_ppb: float

    @property
    def length_m(self) -> float:
        return float(np.sqrt(self.area_m2))


def measure_plume(
    enhancement_ppb: xr.DataArray,
    plume_mask: xr.DataArray,
    valid_mask: xr.DataArray | None = None,
    surface_pressure_pa: float | None = None,
) -> Plume:
    """IME and size of a masked plume, plus the background noise outside it.

    ``valid_mask`` marks pixels usable as background (False for masked artifacts).
    """
    p = surface_pressure_pa or load_quantify().surface_pressure_pa
    area = pixel_area_m2(enhancement_ppb)
    inside = plume_mask.values.astype(bool)
    vals = enhancement_ppb.values
    ime = float(np.nansum(ppb_to_kg_m2(vals[inside], p)) * area)
    bg = ~inside & np.isfinite(vals)
    if valid_mask is not None:
        bg &= valid_mask.values.astype(bool)
    sigma = float(np.nanstd(vals[bg])) if bg.any() else float("nan")
    return Plume(
        ime_kg=ime,
        area_m2=float(inside.sum() * area),
        n_pixels=int(inside.sum()),
        background_sigma_ppb=sigma,
    )


@dataclass(frozen=True)
class Rate:
    median_kg_hr: float
    lo_kg_hr: float
    hi_kg_hr: float
    confirmed_calibration: bool


def rate_kg_hr(
    plume: Plume,
    u10_ms: float,
    *,
    u10_sigma_ms: float | None = None,
    surface_pressure_pa: float | None = None,
    cfg: QuantifyConfig | None = None,
    rng: np.random.Generator | None = None,
    mass: float = 0.90,
) -> Rate:
    """Emission rate with a Monte Carlo interval over wind, U_eff and IME noise."""
    cfg = cfg or load_quantify()
    rng = rng or np.random.default_rng(0)
    n = cfg.n_draws
    p = surface_pressure_pa or cfg.surface_pressure_pa

    u10 = rng.normal(u10_ms, u10_sigma_ms or cfg.u10_sigma_ms, n).clip(min=cfg.min_u10_ms)
    ueff = (cfg.ueff.a.value * u10 + cfg.ueff.b.value) * rng.lognormal(
        0, cfg.ueff.relative_sigma, n
    )
    # Independent pixel noise: the IME error grows with sqrt(plume pixels)
    pixel_area = plume.area_m2 / max(plume.n_pixels, 1)
    noise_kg = ppb_to_kg_m2(plume.background_sigma_ppb, p) * pixel_area * np.sqrt(plume.n_pixels)
    ime = plume.ime_kg + rng.normal(0, float(noise_kg) if np.isfinite(noise_kg) else 0.0, n)
    q = ueff * ime / plume.length_m * 3600
    tail = (1 - mass) / 2
    lo, med, hi = np.quantile(q, [tail, 0.5, 1 - tail])
    confirmed = cfg.ueff.a.confirmed and cfg.ueff.b.confirmed
    return Rate(float(med), float(lo), float(hi), confirmed)
