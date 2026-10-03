"""Plume-to-site attribution (docs/PLAN.md section 5, phase 2d).

All geometries are in the metric CRS (``crs_metric`` in project.yaml).
Only ``inside`` and ``buffer`` plumes feed the model; ``ambiguous`` plumes are
listed on the dashboard and never assigned.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

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
