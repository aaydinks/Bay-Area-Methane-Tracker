"""Low-reflectance, shadow, water and bright-surface masks."""

from __future__ import annotations

import xarray as xr


def artifact_mask(scene: xr.Dataset) -> xr.DataArray:
    raise NotImplementedError("S2 masks: week 4")
