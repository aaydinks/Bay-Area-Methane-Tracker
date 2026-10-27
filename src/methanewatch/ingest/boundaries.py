"""Boundary files for maps and descriptive site context: counties, places, tracts, roads,
water, and the Bay Area air district.

Checked live on 2026-10-27, all public with no key:

- US Census 2025 cartographic boundaries (1:500,000): US counties, California places.
- US Census TIGER/Line 2025: California tracts, primary and secondary roads, and area
  water for each of the nine Bay Area counties.
- CARB air districts, layer ``CaAirDistrict_PublicWeb``, filtered to ``DIS='BA'``. CARB's
  metadata dates these boundaries to March 2004, so the outline carries
  ``DISTRICT_CAVEAT`` wherever it is written.

The air district is descriptive only; it is never a model covariate.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlencode

import geopandas as gpd
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from methanewatch.provenance import PullManifest

CENSUS = "https://www2.census.gov/geo/tiger"
VINTAGE = 2025
CARB_LAYER = (
    "https://gis.carb.arb.ca.gov/hosting/rest/services/"
    "California_Air_Resources_Board_Air_Districts_MIL1/MapServer/0"
)
CARB_QUERY = {"where": "DIS='BA'", "outFields": "NAME,DIS", "outSR": "4326", "f": "geojson"}
DISTRICT_AS_OF = "2004-03"
DISTRICT_CAVEAT = "check against current BAAQMD"

COUNTY_FIPS = ("001", "013", "041", "055", "075", "081", "085", "095", "097")
COUNTY_FILE = f"cb_{VINTAGE}_us_county_500k.zip"
DISTRICT_FILE = "carb_air_district_ba.geojson"
# Simplification tolerance for the committed county outlines, in metres.
COUNTY_SIMPLIFY_M = 100.0


def sources() -> dict[str, str]:
    """File name in the pull directory -> URL. The CARB query comes first: it is small and
    is checked before the large Census files are fetched."""
    gen, tiger = f"{CENSUS}/GENZ{VINTAGE}/shp", f"{CENSUS}/TIGER{VINTAGE}"
    files = {DISTRICT_FILE: f"{CARB_LAYER}/query?{urlencode(CARB_QUERY, safe=',')}"}
    files[COUNTY_FILE] = f"{gen}/{COUNTY_FILE}"
    files[f"cb_{VINTAGE}_06_place_500k.zip"] = f"{gen}/cb_{VINTAGE}_06_place_500k.zip"
    files[f"tl_{VINTAGE}_06_tract.zip"] = f"{tiger}/TRACT/tl_{VINTAGE}_06_tract.zip"
    roads = f"tl_{VINTAGE}_06_prisecroads.zip"
    files[roads] = f"{tiger}/PRISECROADS/{roads}"
    for fips in COUNTY_FIPS:
        water = f"tl_{VINTAGE}_06{fips}_areawater.zip"
        files[water] = f"{tiger}/AREAWATER/{water}"
    return files


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=2, max=30))
def _download(client: httpx.Client, url: str, path: Path) -> None:
    with client.stream("GET", url, timeout=300) as r:
        r.raise_for_status()
        with path.open("wb") as fh:
            for block in r.iter_bytes():
                fh.write(block)


def pull(raw_root: Path, client: httpx.Client | None = None) -> Path:
    """Download every boundary file into ``raw_root/boundaries/<pull_id>/`` (about 60 MB)."""
    urls = sources()
    manifest = PullManifest.start(
        "boundaries",
        f"{CENSUS}/GENZ{VINTAGE}; {CENSUS}/TIGER{VINTAGE}; {CARB_LAYER}/query",
        {"vintage": VINTAGE, "files": urls, "district_as_of": DISTRICT_AS_OF},
    )
    pull_dir = raw_root / "boundaries" / manifest.pull_id
    pull_dir.mkdir(parents=True, exist_ok=True)
    files = []
    with client or httpx.Client(follow_redirects=True) as c:
        for name, url in urls.items():
            path = pull_dir / name
            _download(c, url, path)
            if name == DISTRICT_FILE:
                district(path)  # fail before the large files if the service sent an error
            files.append(path)
    manifest.finish(pull_dir, files, n_records=len(files))
    return pull_dir


def district(path: Path) -> gpd.GeoDataFrame:
    """The Bay Area air district outline from a saved CARB query, with its date and caveat."""
    fc = json.loads(path.read_text())
    if fc.get("error") or not fc.get("features"):
        raise ValueError(f"CARB query returned no district: {fc.get('error') or 'no features'}")
    gdf = gpd.GeoDataFrame.from_features(fc["features"], crs="EPSG:4326")
    if set(gdf["DIS"]) != {"BA"}:
        raise ValueError(f"expected only DIS='BA', got {sorted(set(gdf['DIS']))}")
    gdf["boundary_as_of"] = DISTRICT_AS_OF
    gdf["caveat"] = DISTRICT_CAVEAT
    return gdf[["NAME", "DIS", "boundary_as_of", "caveat", "geometry"]]


def counties(zip_path: Path, metric_crs: str) -> gpd.GeoDataFrame:
    """The nine Bay Area counties, simplified so shared edges stay shared."""
    fips = ",".join(f"'{c}'" for c in COUNTY_FIPS)
    gdf = gpd.read_file(f"zip://{zip_path}", where=f"STATEFP = '06' AND COUNTYFP IN ({fips})")
    gdf = gdf.to_crs(metric_crs)
    gdf["geometry"] = gdf.geometry.simplify_coverage(COUNTY_SIMPLIFY_M)
    gdf = gdf[["GEOID", "COUNTYFP", "NAME", "geometry"]].to_crs("EPSG:4326")
    return gdf.sort_values("COUNTYFP").reset_index(drop=True)
