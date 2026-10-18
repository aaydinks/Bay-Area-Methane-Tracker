"""Plume segmentation and origin finding (docs/PLAN.md phase 3).

Candidates are valid pixels above median + k * robust sigma of the scene's
enhancement. Connected components (8-neighbour) smaller than ``min_pixels``
are dropped. A component counts for a site only if its origin lies inside
the site's attribution area (polygon plus buffer, rasterized to
``site_area``). The origin is the most upwind pixel of the component when a
wind vector is given, otherwise its peak.

A Sentinel-2 detection never supports a site-specific claim on its own; it
must coincide with a Carbon Mapper or EMIT plume (PLAN risk table).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import xarray as xr
from scipy import ndimage

from methanewatch.config import S2Detection, load_sentinel2


@dataclass(frozen=True)
class Detection:
    mask: xr.DataArray
    origin_x: float
    origin_y: float
    n_pixels: int
    enhancement_sum: float
    background_sigma: float


def robust_sigma(values: np.ndarray) -> float:
    v = values[np.isfinite(values)]
    return float(1.4826 * np.median(np.abs(v - np.median(v))))


def detect_plume(
    enhancement: xr.DataArray,
    valid: xr.DataArray,
    site_area: xr.DataArray,
    *,
    wind_uv: tuple[float, float] | None = None,
    cfg: S2Detection | None = None,
) -> Detection | None:
    """Largest qualifying plume whose origin falls in ``site_area``, or None."""
    cfg = cfg or load_sentinel2().detection
    vals = np.where(valid.values, enhancement.values, np.nan)
    sigma = robust_sigma(vals)
    if not np.isfinite(sigma) or sigma == 0:
        return None
    threshold = np.nanmedian(vals) + cfg.k_sigma * sigma
    candidates = np.nan_to_num(vals, nan=-np.inf) > threshold
    labels, n = ndimage.label(candidates, structure=np.ones((3, 3), dtype=int))

    ys, xs = enhancement["y"].values, enhancement["x"].values
    best = None
    for lab in range(1, n + 1):
        comp = labels == lab
        size = int(comp.sum())
        if size < cfg.min_pixels:
            continue
        iy, ix = np.nonzero(comp)
        if wind_uv is not None:
            u, v = wind_uv
            # Most upwind pixel: smallest projection onto the wind direction
            k = int(np.argmin(xs[ix] * u + ys[iy] * v))
        else:
            k = int(np.argmax(vals[iy, ix]))
        oy, ox = iy[k], ix[k]
        if not bool(site_area.values[oy, ox]):
            continue
        total = float(np.nansum(vals[comp]))
        if best is None or total > best.enhancement_sum:
            best = Detection(
                mask=enhancement.copy(data=comp).rename("plume"),
                origin_x=float(xs[ox]),
                origin_y=float(ys[oy]),
                n_pixels=size,
                enhancement_sum=total,
                background_sigma=sigma,
            )
    return best
