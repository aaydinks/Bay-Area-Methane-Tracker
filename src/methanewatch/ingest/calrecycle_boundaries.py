"""CalRecycle's landfill boundary polygons, for site outlines (ADR 0018).

Checked live on 2026-11-19. A public ArcGIS layer with no login: 153 polygons keyed by SWIS
number, drawn by CalRecycle staff from each landfill's most recent permit map and aerial
imagery. OEHHA publishes it as CalEnviroScreen 4.0 indicator data and credits CalRecycle.

Two cautions:

- The layer reports its data as last edited on 2021-09-30, so an outline can be older than
  the site's current permit.
- No terms of reuse were found on the layer. Check them before an outline from it is
  committed to the registry.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlencode

import geopandas as gpd
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from methanewatch.provenance import PullManifest

SOURCE = "calrecycle-boundaries"
LAYER = (
    "https://services1.arcgis.com/PCHfdHz4GlDNAhBb/ArcGIS/rest/services/"
    "CalEnviroScreen_4_Indicator_Facility_Data/FeatureServer/9"
)
QUERY = {"where": "1=1", "outFields": "SWIS_NO,SiteName", "outSR": "4326", "f": "geojson"}
FILE = "landfill_boundaries.geojson"
DATA_AS_OF = "2021-09"


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=2, max=30))
def _get(client: httpx.Client, url: str) -> bytes:
    r = client.get(url, timeout=120)
    r.raise_for_status()
    return r.content


def pull(raw_root: Path, client: httpx.Client | None = None) -> Path:
    """Download every polygon in the layer into ``raw_root/calrecycle-boundaries/<pull_id>/``."""
    url = f"{LAYER}/query?{urlencode(QUERY, safe=',')}"
    manifest = PullManifest.start(SOURCE, f"{LAYER}/query", {**QUERY, "data_as_of": DATA_AS_OF})
    pull_dir = raw_root / SOURCE / manifest.pull_id
    pull_dir.mkdir(parents=True, exist_ok=True)
    path = pull_dir / FILE
    with client or httpx.Client(follow_redirects=True) as c:
        path.write_bytes(_get(c, url))
    n = len(outlines(path))  # fail here, before a manifest exists, if the answer is unusable
    manifest.finish(pull_dir, [path], n_records=n)
    return pull_dir


def latest(raw_root: Path) -> Path | None:
    """The newest finished pull's polygon file, if any."""
    pulls = sorted((raw_root / SOURCE).glob(f"{SOURCE}-*/manifest.json"))
    return pulls[-1].parent / FILE if pulls else None


def outlines(path: Path) -> gpd.GeoDataFrame:
    """One valid outline per SWIS number, in EPSG:4326, from a saved layer query."""
    fc = json.loads(path.read_text())
    if fc.get("error") or not fc.get("features"):
        raise ValueError(f"boundary layer returned no polygons: {fc.get('error') or 'no features'}")
    if fc.get("exceededTransferLimit") or fc.get("properties", {}).get("exceededTransferLimit"):
        raise ValueError("boundary layer answer was cut short; the query needs paging")
    gdf = gpd.GeoDataFrame.from_features(fc["features"], crs="EPSG:4326")
    gdf = gdf.rename(columns={"SWIS_NO": "swis_number", "SiteName": "layer_name"})
    gdf["swis_number"] = gdf["swis_number"].fillna("").str.strip()
    gdf = gdf[(gdf["swis_number"] != "") & gdf.geometry.notna()]
    gdf["geometry"] = gdf.geometry.make_valid()
    out = gdf.dissolve(by="swis_number", aggfunc="first").reset_index()
    return out[["swis_number", "layer_name", "geometry"]].sort_values(
        "swis_number", ignore_index=True
    )
