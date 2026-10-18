"""Carbon Mapper plumes and scenes (PLAN section 5, phase 2a).

Checked live against the API spec at ``api.carbonmapper.org/api/v1/openapi.json``
on 2026-10-17. The plume CSV and the STAC search are marked token-optional and
answer without a token; a token in ``CARBON_MAPPER_API_KEY`` is sent when set.

- ``/catalog/plume-csv``: one row per published plume, paged with ``limit`` and
  ``offset``. Pulled twice, once with ``sectors=6A`` (solid waste) and once
  with no sector filter, so plumes with a missing or wrong sector label are not
  lost before attribution.
- ``/stac/search`` on a scene-level ``l2b-ch4-*`` collection: footprint, time
  and the per-scene detection quantiles (``cm:pod``, kg/hr at 10, 50 and 90%).

Data are free for non-commercial use only. Raw pulls are never committed.
"""

from __future__ import annotations

import io
import json
import os
from datetime import date
from pathlib import Path

import geopandas as gpd
import httpx
import pandas as pd
from shapely.geometry import shape
from tenacity import retry, stop_after_attempt, wait_exponential

from methanewatch.provenance import PullManifest

API = "https://api.carbonmapper.org/api/v1"
SCENE_COLLECTION = "l2b-ch4-mfa-v3e"
PAGE = 10_000
STAC_PAGE = 100  # the STAC search caps limit at 100

BBox = tuple[float, float, float, float]


def _headers() -> dict[str, str]:
    token = os.environ.get("CARBON_MAPPER_API_KEY")
    return {"Authorization": f"Bearer {token}"} if token else {}


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=2, max=30))
def _get(client: httpx.Client, path: str, params: list[tuple[str, str]]) -> httpx.Response:
    r = client.get(f"{API}{path}", params=params, timeout=180)
    r.raise_for_status()
    return r


def plume_csv(
    client: httpx.Client, bbox: BBox, start: date, *, sectors: list[str] | None = None
) -> pd.DataFrame:
    """Every CH4 plume in ``bbox`` observed on or after ``start``, all instruments."""
    base = [("plume_gas", "CH4"), ("datetime", f"{start.isoformat()}T00:00:00Z/..")]
    base += [("bbox", str(b)) for b in bbox]
    base += [("sectors", s) for s in sectors or []]
    pages, offset = [], 0
    while True:
        params = [*base, ("limit", str(PAGE)), ("offset", str(offset))]
        text = _get(client, "/catalog/plume-csv", params).text
        page = pd.read_csv(io.StringIO(text)) if text.strip() else pd.DataFrame()
        pages.append(page)
        if len(page) < PAGE:
            break
        offset += PAGE
    return pd.concat(pages, ignore_index=True)


def stac_scenes(
    client: httpx.Client, bbox: BBox, start: date, end: date, collection: str = SCENE_COLLECTION
) -> list[dict]:
    """Scene-level STAC items touching ``bbox`` between ``start`` and ``end``."""
    items: list[dict] = []
    while True:
        params = [
            ("collections", collection),
            ("bbox", ",".join(str(b) for b in bbox)),
            ("datetime", f"{start.isoformat()}T00:00:00Z/{end.isoformat()}T23:59:59Z"),
            ("limit", str(STAC_PAGE)),
            ("offset", str(len(items))),
        ]
        page = _get(client, "/stac/search", params).json()
        items += page["features"]
        if not page["features"] or len(items) >= page["numberMatched"]:
            return items


def pull(bbox: BBox, start: date, end: date, raw_root: Path) -> Path:
    """Write both plume pulls and the scene search to one raw pull directory."""
    manifest = PullManifest.start(
        "carbonmapper",
        f"{API}/catalog/plume-csv; {API}/stac/search",
        {
            "bbox": bbox,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "plume_gas": "CH4",
            "plume_pulls": {"solid-waste": ["6A"], "all-sectors": None},
            "scene_collection": SCENE_COLLECTION,
            "token_used": bool(_headers()),
        },
    )
    pull_dir = raw_root / "carbonmapper" / manifest.pull_id
    pull_dir.mkdir(parents=True, exist_ok=True)
    files = []
    with httpx.Client(headers=_headers(), follow_redirects=True) as client:
        for name, sectors in [("solid-waste", ["6A"]), ("all-sectors", None)]:
            path = pull_dir / f"plumes_{name}.csv"
            plume_csv(client, bbox, start, sectors=sectors).to_csv(path, index=False)
            files.append(path)
        scenes = stac_scenes(client, bbox, start, end)
    path = pull_dir / f"scenes_{SCENE_COLLECTION}.json"
    path.write_text(json.dumps(scenes))
    files.append(path)
    n = sum(len(pd.read_csv(f)) for f in files[:2]) + len(scenes)
    manifest.finish(pull_dir, files, n_records=n)
    return pull_dir


def latest_pull(raw_root: Path) -> Path:
    pulls = sorted((raw_root / "carbonmapper").glob("carbonmapper-*"))
    if not pulls:
        raise FileNotFoundError("no Carbon Mapper pull yet; run `mw ingest carbonmapper`")
    return pulls[-1]


# Columns that carry signed or account-specific asset links are left out of tables.
_ASSET_COLUMNS = ("plume_tif", "plume_png", "con_tif", "rgb_tif", "rgb_png")


def plumes_table(csv: Path) -> pd.DataFrame:
    """Plume rows with UTC times and without asset links."""
    df = pd.read_csv(csv).drop(columns=list(_ASSET_COLUMNS), errors="ignore")
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True, format="ISO8601")
    return df.sort_values(["datetime", "plume_id"]).reset_index(drop=True)


def scenes_table(items: list[dict]) -> gpd.GeoDataFrame:
    """Scene footprints, times and Carbon Mapper's per-scene detection quantiles (kg/hr)."""
    rows = []
    for it in items:
        p = it["properties"]
        pod = p.get("cm:pod") or {}
        rows.append(
            {
                "scene_id": it["id"],
                "acquired_utc": p["datetime"],
                "platform": p.get("platform"),
                "version": p.get("version"),
                "gsd_m": p.get("gsd"),
                "pod10_kg_hr": pod.get("0.1"),
                "pod50_kg_hr": pod.get("0.5"),
                "pod90_kg_hr": pod.get("0.9"),
                "geometry": shape(it["geometry"]),
            }
        )
    gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")
    gdf["acquired_utc"] = pd.to_datetime(gdf["acquired_utc"], utc=True, format="ISO8601")
    return gdf.sort_values("acquired_utc").reset_index(drop=True)
