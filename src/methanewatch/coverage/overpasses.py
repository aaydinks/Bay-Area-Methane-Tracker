"""The denominator (PLAN section 4.2 and 5 phase 2c).

One row per (site, instrument, observation day); same-day repeat passes collapse.
Fallback ladder when Carbon Mapper footprints are unavailable: ask for
acquisition lists, then use those instruments for rates only, then inferred
coverage (flagged).
"""

from __future__ import annotations

import geopandas as gpd
import pandas as pd


def from_emit_granules(granules: pd.DataFrame, sites: gpd.GeoDataFrame) -> pd.DataFrame:
    raise NotImplementedError("EMIT coverage: week 2")


def from_carbonmapper(scenes: pd.DataFrame, sites: gpd.GeoDataFrame) -> pd.DataFrame:
    raise NotImplementedError("Carbon Mapper coverage: week 2, depends on ADR 0001")


def from_sentinel2(scenes: pd.DataFrame, sites: gpd.GeoDataFrame) -> pd.DataFrame:
    raise NotImplementedError("Sentinel-2 coverage: week 3-4")


def build_detections(overpasses: pd.DataFrame, plumes: pd.DataFrame) -> pd.DataFrame:
    raise NotImplementedError("join to schemas.detections: week 2")
