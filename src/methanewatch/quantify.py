"""Integrated mass enhancement (IME) quantification with Monte Carlo uncertainty.

Q = U_eff * IME / L, with L = sqrt(plume area) and U_eff = a * U10 + b from the
method's published calibration (cite it in ADR 0002).
"""

from __future__ import annotations

import xarray as xr


def ime_kg(enhancement: xr.DataArray, plume_mask: xr.DataArray) -> float:
    raise NotImplementedError("IME: week 4")


def rate_kg_hr(
    ime_kg: float, plume_len_m: float, u10_ms: float, n_draws: int = 1000
) -> tuple[float, float, float]:
    raise NotImplementedError("rate with MC interval: week 4")
