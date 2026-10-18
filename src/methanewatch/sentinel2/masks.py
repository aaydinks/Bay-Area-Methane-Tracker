"""Artifact masks for Sentinel-2 methane retrieval (docs/PLAN.md phase 3).

Dark surfaces (water, shadows, dark roofs) and very bright surfaces produce
band-ratio artifacts that look like plumes. ``artifact_mask`` returns True where
a pixel is usable. Bands are top-of-atmosphere reflectance (0-1); B02, B03 and
B08 are optional and add the cloud and water screens when present.
"""

from __future__ import annotations

import xarray as xr

from methanewatch.config import S2Masks, load_sentinel2


def artifact_mask(scene: xr.Dataset, cfg: S2Masks | None = None) -> xr.DataArray:
    cfg = cfg or load_sentinel2().masks
    b12 = scene["B12"]
    valid = (b12 >= cfg.min_b12_reflectance) & (b12 <= cfg.max_b12_reflectance)
    valid &= scene["B11"].notnull() & b12.notnull()
    if "B03" in scene and "B08" in scene:
        ndwi = (scene["B03"] - scene["B08"]) / (scene["B03"] + scene["B08"])
        valid &= ndwi <= cfg.max_ndwi
    if "B02" in scene:
        valid &= scene["B02"] <= cfg.max_b02_reflectance
    return valid.rename("valid")
