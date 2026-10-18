"""Sentinel-2 scene search (docs/PLAN.md section 5, phase 3).

Scene metadata comes from the public Earth Search STAC catalog (no login).
Pixel access is a separate decision (ADR 0004): L1C bands on AWS are in a
requester-pays bucket, so L1C pixels come from Copernicus Data Space
(free account), or the retrieval uses the public L2A COGs if the method allows.
"""

from __future__ import annotations

from datetime import date

import geopandas as gpd
import pandas as pd
from shapely.geometry import shape

EARTH_SEARCH = "https://earth-search.aws.element84.com/v1"
COLLECTION = "sentinel-2-l1c"


def search_scenes(
    bbox: tuple[float, float, float, float],
    start: date,
    end: date,
    *,
    max_cloud: float = 100.0,
    collection: str = COLLECTION,
) -> list[dict]:
    from pystac_client import Client

    client = Client.open(EARTH_SEARCH)
    search = client.search(
        collections=[collection],
        bbox=list(bbox),
        datetime=f"{start.isoformat()}/{end.isoformat()}",
        query={"eo:cloud_cover": {"lte": max_cloud}},
    )
    return [item.to_dict() for item in search.items()]


def footprints(items: list[dict]) -> gpd.GeoDataFrame:
    """Scene footprints for ``coverage.overpasses.from_footprints``.

    ``valid_frac`` is the tile-level cloud share; the per-site share comes from the
    cloud mask during retrieval.
    """
    rows = [
        {
            "scene_id": it["id"],
            "instrument": "sentinel2",
            "acquired_utc": it["properties"]["datetime"],
            "valid_frac": 1 - it["properties"].get("eo:cloud_cover", 0.0) / 100,
            "platform": it["properties"].get("platform"),
            "relative_orbit": it["properties"].get("sat:relative_orbit"),
            "mgrs_tile": it["properties"].get("grid:code"),
            "geometry": shape(it["geometry"]),
        }
        for it in items
    ]
    gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")
    gdf["acquired_utc"] = pd.to_datetime(gdf["acquired_utc"], utc=True)
    return gdf
