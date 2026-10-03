"""Plume segmentation and origin finding. A Sentinel-2 detection never supports a
site-specific claim unless a Carbon Mapper or EMIT plume coincides.
"""

from __future__ import annotations

import xarray as xr


def detect_plume(
    enhancement: xr.DataArray, mask: xr.DataArray, k_sigma: float = 2.0
) -> dict | None:
    raise NotImplementedError("S2 detection: week 4")
