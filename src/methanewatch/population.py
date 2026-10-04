"""Residents near a site, for context only (docs/PLAN.md section 9.3).

Population is the ACS 5-year total (table B01003) for each census block group,
split by the share of the block group's area inside the buffer around the
site (areal interpolation; assumes people are spread evenly within a block
group). This is context, not a health effect.

- Block-group boundaries: Census TIGERweb REST, no key.
- Population: Census Data API, which needs a free key in ``CENSUS_API_KEY``.
"""

from __future__ import annotations

import os

import geopandas as gpd
import httpx
import pandas as pd
from shapely.geometry.base import BaseGeometry
from tenacity import retry, stop_after_attempt, wait_exponential

TIGERWEB = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_ACS{year}/MapServer/10/query"
ACS = "https://api.census.gov/data/{year}/acs/acs5"
ACS_YEAR = 2023
TIGER_YEAR = 2024  # 2020-decade block-group boundaries, shared by ACS 2020-2029 releases
LABEL = "residents nearby (context, not a health effect)"


class MissingCensusKeyError(RuntimeError):
    pass


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=2, max=30))
def _get(url: str, params: dict) -> httpx.Response:
    r = httpx.get(url, params=params, timeout=120, follow_redirects=True)
    r.raise_for_status()
    return r


def block_groups(
    bounds: tuple[float, float, float, float], year: int = TIGER_YEAR
) -> gpd.GeoDataFrame:
    """Block groups intersecting a lon/lat bounding box."""
    params = {
        "geometry": ",".join(f"{b:.5f}" for b in bounds),
        "geometryType": "esriGeometryEnvelope",
        "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "GEOID,STATE,COUNTY,TRACT,BLKGRP",
        "returnGeometry": "true",
        "outSR": 4326,
        "geometryPrecision": 5,
        "f": "geojson",
    }
    return from_geojson(_get(TIGERWEB.format(year=year), params).json())


def from_geojson(fc: dict) -> gpd.GeoDataFrame:
    gdf = gpd.GeoDataFrame.from_features(fc["features"], crs="EPSG:4326")
    return gdf[["GEOID", "STATE", "COUNTY", "geometry"]]


def acs_population(state: str, counties: list[str], year: int = ACS_YEAR) -> pd.DataFrame:
    """Block-group population (B01003_001E) for the given counties."""
    key = os.environ.get("CENSUS_API_KEY")
    if not key:
        raise MissingCensusKeyError(
            "set CENSUS_API_KEY in .env (free key from the Census Data API) for population context"
        )
    frames = []
    for county in counties:
        params = {
            "get": "B01003_001E",
            "for": "block group:*",
            "in": f"state:{state} county:{county}",
            "key": key,
        }
        rows = _get(ACS.format(year=year), params).json()
        df = pd.DataFrame(rows[1:], columns=rows[0])
        df["GEOID"] = df["state"] + df["county"] + df["tract"] + df["block group"]
        frames.append(df[["GEOID", "B01003_001E"]].rename(columns={"B01003_001E": "population"}))
    out = pd.concat(frames, ignore_index=True)
    out["population"] = pd.to_numeric(out["population"])
    return out


def areal_population(
    area: BaseGeometry, groups: gpd.GeoDataFrame, population: pd.DataFrame, metric_crs: str
) -> float:
    """Sum of block-group population weighted by the share of each group inside ``area``."""
    g = groups.merge(population, on="GEOID", how="inner").to_crs(metric_crs)
    a = gpd.GeoSeries([area], crs="EPSG:4326").to_crs(metric_crs).iloc[0]
    share = g.geometry.intersection(a).area / g.geometry.area
    return float((g["population"] * share).sum())


def residents_within(
    site_geometry: BaseGeometry,
    radii_km: list[float],
    metric_crs: str,
    *,
    groups: gpd.GeoDataFrame | None = None,
    population: pd.DataFrame | None = None,
) -> dict[float, int]:
    """Residents within each radius of the site boundary (the boundary itself included)."""
    site = gpd.GeoSeries([site_geometry], crs="EPSG:4326").to_crs(metric_crs)
    buffers = {r: site.buffer(r * 1000).to_crs("EPSG:4326").iloc[0] for r in radii_km}
    if groups is None:
        groups = block_groups(buffers[max(radii_km)].bounds)
    if population is None:
        counties = sorted(groups["COUNTY"].unique())
        population = acs_population(groups["STATE"].iloc[0], counties)
    return {
        r: round(areal_population(b, groups, population, metric_crs)) for r, b in buffers.items()
    }
