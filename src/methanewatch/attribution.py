"""Plume-to-site attribution (docs/PLAN.md section 5, phase 2d).

All geometries are in the metric CRS (``crs_metric`` in project.yaml).
Only ``inside`` and ``buffer`` plumes feed the model; ``ambiguous`` plumes are
listed on the dashboard and never assigned. A plume is ambiguous when another
source lies as close as the landfill, or when its own source tagged it with a
sector other than waste (decision record 0022).
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from typing import Literal

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry

Label = Literal["inside", "buffer", "ambiguous", "nearby", "none"]


@dataclass(frozen=True)
class Attribution:
    site_id: str | None  # nearest landfill, kept for listing even when ambiguous
    label: Label
    distance_m: float | None

    @property
    def feeds_model(self) -> bool:
        return self.label in ("inside", "buffer")


def classify(
    origin: Point,
    sites: dict[str, BaseGeometry],
    neighbors: dict[str, BaseGeometry],
    *,
    buffer_m: float,
    search_radius_m: float,
) -> Attribution:
    """Classify one plume origin against landfill polygons and known neighbor sources."""
    if not sites:
        return Attribution(None, "none", None)

    site_d = {k: origin.distance(g) for k, g in sites.items()}
    nearest = min(site_d, key=site_d.get)
    d = site_d[nearest]

    if d == 0:
        return Attribution(nearest, "inside", 0.0)
    if d <= buffer_m:
        others = [v for k, v in site_d.items() if k != nearest]
        others += [origin.distance(g) for g in neighbors.values()]
        if any(o <= buffer_m for o in others):
            return Attribution(nearest, "ambiguous", d)
        return Attribution(nearest, "buffer", d)
    if d <= search_radius_m:
        return Attribution(nearest, "nearby", d)
    return Attribution(None, "none", d)


def attribute_plumes(
    plumes: pd.DataFrame,
    sites: gpd.GeoDataFrame,
    neighbors: gpd.GeoDataFrame,
    *,
    buffer_m: float,
    search_radius_m: float,
    metric_crs: str,
    waste_sectors: Collection[str] | None = None,
) -> pd.DataFrame:
    """Fill ``site_id``, ``attribution`` and ``distance_m`` for every plume origin.

    With ``waste_sectors``, a plume on or beside a landfill whose ``ipcc_sector`` names another
    sector is marked ``ambiguous`` (decision record 0022). A plume with no sector tag, or from a
    source that gives none, follows the distance rule alone.
    """
    site_geoms = dict(zip(sites["site_id"], sites.to_crs(metric_crs).geometry, strict=True))
    nb = neighbors.to_crs(metric_crs) if len(neighbors) else neighbors
    key = "name" if "name" in nb else "site_id"
    neighbor_geoms = dict(zip(nb[key], nb.geometry, strict=True)) if len(nb) else {}
    origins = gpd.GeoSeries(
        gpd.points_from_xy(plumes["origin_lon"], plumes["origin_lat"]), crs="EPSG:4326"
    ).to_crs(metric_crs)
    res = [
        classify(o, site_geoms, neighbor_geoms, buffer_m=buffer_m, search_radius_m=search_radius_m)
        for o in origins
    ]
    out = plumes.assign(
        site_id=[r.site_id for r in res],
        attribution=[r.label for r in res],
        distance_m=[r.distance_m for r in res],
    )
    if waste_sectors is not None and "ipcc_sector" in out:
        tag = out["ipcc_sector"].fillna("").astype(str).str.strip()
        other = (tag != "") & ~tag.isin(list(waste_sectors))
        counted = out["attribution"].isin(["inside", "buffer"])
        out.loc[other & counted, "attribution"] = "ambiguous"
    return out
