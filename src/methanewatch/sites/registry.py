"""Build and QA the site registry (PLAN section 5, phase 1).

Input: ``data/registry/sites.csv`` (attributes) and ``data/registry/sites.geojson``
(polygons drawn over imagery and permit maps). Output: ``data/interim/sites.parquet``.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd


def build_registry(registry_dir: Path, out_path: Path) -> gpd.GeoDataFrame:
    raise NotImplementedError("site registry: week 1-2, PLAN section 5 phase 1")


def qa_checks(sites: gpd.GeoDataFrame) -> list[str]:
    raise NotImplementedError(
        "registry QA (valid, in Bay Area counties, non-overlapping): week 1-2"
    )


def screening_polygons(points: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    raise NotImplementedError("OSM landuse=landfill polygons with buffer fallback: week 2")
