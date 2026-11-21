"""CARB's air district outlines for every district that touches the project's regions, used
to say which air district each site sits in (ADR 0018).

Checked live on 2026-11-20. The same public layer as the Bay Area outline in
``boundaries.py`` (``CaAirDistrict_PublicWeb``, no login), asked for every district whose
outline meets a box instead of for district codes, so no code has to be known in advance.
Over the Bay Area region's box it returns ten districts.

Two cautions:

- CARB's metadata dates these outlines to March 2004. A district read from them is a first
  answer, not a confirmed one; the registry marks it unconfirmed until a person has checked
  it against the district itself.
- The service publishes no terms of use (check).
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlencode

import geopandas as gpd
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from methanewatch.ingest.boundaries import CARB_LAYER, DISTRICT_AS_OF
from methanewatch.provenance import PullManifest

SOURCE = "air-districts"
FILE = "carb_air_districts.geojson"


def query(bbox: tuple[float, float, float, float]) -> dict[str, str]:
    """Layer query for every district whose outline meets ``bbox`` (west, south, east, north)."""
    return {
        "where": "1=1",
        "geometry": ",".join(f"{v:g}" for v in bbox),
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "NAME,DIS",
        "outSR": "4326",
        "f": "geojson",
    }


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=2, max=30))
def _get(client: httpx.Client, url: str) -> bytes:
    r = client.get(url, timeout=300)
    r.raise_for_status()
    return r.content


def pull(
    raw_root: Path, bbox: tuple[float, float, float, float], client: httpx.Client | None = None
) -> Path:
    """Download the outlines into ``raw_root/air-districts/<pull_id>/`` (about 3 MB)."""
    params = query(bbox)
    url = f"{CARB_LAYER}/query?{urlencode(params, safe=',')}"
    manifest = PullManifest.start(
        SOURCE, f"{CARB_LAYER}/query", {**params, "district_as_of": DISTRICT_AS_OF}
    )
    pull_dir = raw_root / SOURCE / manifest.pull_id
    pull_dir.mkdir(parents=True, exist_ok=True)
    path = pull_dir / FILE
    with client or httpx.Client(follow_redirects=True) as c:
        path.write_bytes(_get(c, url))
    n = len(outlines(path))  # fail here, before a manifest exists, if the answer is unusable
    manifest.finish(pull_dir, [path], n_records=n)
    return pull_dir


def latest(raw_root: Path) -> Path | None:
    """The newest finished pull's outline file, if any."""
    pulls = sorted((raw_root / SOURCE).glob(f"{SOURCE}-*/manifest.json"))
    return pulls[-1].parent / FILE if pulls else None


def outlines(path: Path) -> gpd.GeoDataFrame:
    """One valid outline per district, in EPSG:4326, with the date of the outlines."""
    fc = json.loads(path.read_text())
    if fc.get("error") or not fc.get("features"):
        raise ValueError(f"CARB query returned no district: {fc.get('error') or 'no features'}")
    if fc.get("exceededTransferLimit") or fc.get("properties", {}).get("exceededTransferLimit"):
        raise ValueError("CARB answer was cut short; the query needs paging")
    gdf = gpd.GeoDataFrame.from_features(fc["features"], crs="EPSG:4326")
    gdf = gdf[gdf["DIS"].notna() & gdf["NAME"].notna() & gdf.geometry.notna()]
    gdf["geometry"] = gdf.geometry.make_valid()
    out = gdf.dissolve(by="DIS", aggfunc="first").reset_index()
    out["boundary_as_of"] = DISTRICT_AS_OF
    return out[["NAME", "DIS", "boundary_as_of", "geometry"]].sort_values("DIS", ignore_index=True)
