"""Multi-band multi-pass (MBMP) retrieval (Varon et al. 2021 method; docs/PLAN.md phase 3).

Methane absorbs more in band 12 (~2.2 um) than in band 11 (~1.6 um). For one
scene, the band-ratio signal is

  dR = (c * B12 - B11) / B11,   c fitted by least squares so that c * B12 ~ B11

which removes most of the surface brightness. MBMP subtracts the same quantity
from a clean reference scene of the same site (same relative orbit), which
removes surface features that persist between passes:

  dR_MBMP = dR_target - dR_reference

Methane makes dR negative, so ``fractional_absorption = -dR_MBMP`` is positive
inside a plume. Turning that into a column enhancement (ppb) needs a lookup
table from the radiative transfer of the chosen pipeline (ADR 0004); until one
is configured, retrieval stops at fractional absorption.

Before vendoring anything from the open MIT-licensed pipeline, read it and
keep its license notice on the copied code.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr


class MissingLookupTableError(RuntimeError):
    pass


def band_ratio_scale(b11: xr.DataArray, b12: xr.DataArray, valid: xr.DataArray) -> float:
    """Least-squares c (through the origin) such that c * B12 ~ B11 over valid pixels."""
    x = b12.values[valid.values]
    y = b11.values[valid.values]
    ok = np.isfinite(x) & np.isfinite(y)
    return float(np.sum(x[ok] * y[ok]) / np.sum(x[ok] ** 2))


def single_pass(scene: xr.Dataset, valid: xr.DataArray) -> xr.DataArray:
    """dR = (c * B12 - B11) / B11 for one scene."""
    c = band_ratio_scale(scene["B11"], scene["B12"], valid)
    dr = (c * scene["B12"] - scene["B11"]) / scene["B11"]
    return dr.where(valid).rename("dR").assign_attrs(c=c)


def mbmp(
    target: xr.Dataset,
    reference: xr.Dataset,
    target_valid: xr.DataArray,
    reference_valid: xr.DataArray,
) -> xr.DataArray:
    """dR_MBMP on the target grid; pixels invalid in either scene are NaN."""
    valid = target_valid & reference_valid
    out = single_pass(target, valid) - single_pass(reference, valid)
    return out.rename("dR_mbmp")


def fractional_absorption(dr_mbmp: xr.DataArray) -> xr.DataArray:
    return (-dr_mbmp).rename("fractional_absorption")


def to_ppb(absorption: xr.DataArray, lookup_table: Path | None) -> xr.DataArray:
    """Column enhancement from fractional absorption via a monotonic lookup table.

    The table is a CSV with columns ``fractional_absorption`` and ``delta_xch4_ppb``.
    """
    if lookup_table is None:
        raise MissingLookupTableError(
            "set ppb_lookup_table in config/sentinel2.yaml once ADR 0004 picks the pipeline"
        )
    table = pd.read_csv(lookup_table).sort_values("fractional_absorption")
    ppb = np.interp(
        absorption.values,
        table["fractional_absorption"].to_numpy(),
        table["delta_xch4_ppb"].to_numpy(),
    )
    ppb = np.where(np.isfinite(absorption.values), ppb, np.nan)
    return absorption.copy(data=ppb).rename("delta_xch4_ppb")
