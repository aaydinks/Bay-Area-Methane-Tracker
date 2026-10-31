"""Carbon Mapper plumes and scenes (PLAN section 5, phase 2a).

Checked live against the API spec at ``api.carbonmapper.org/api/v1/openapi.json``
on 2026-10-17. The plume CSV and the STAC search are marked token-optional and
answer without a token; a token in ``CARBON_MAPPER_API_KEY`` is sent when set.

- ``/catalog/plume-csv``: one row per published plume, paged with ``limit`` and
  ``offset``. Pulled twice, once with ``sectors=6A`` (solid waste) and once
  with no sector filter, so plumes with a missing or wrong sector label are not
  lost before attribution.
- ``/stac/search`` on the scene-level ``l2b-ch4-*`` collections: footprint, time
  and the per-scene detection quantiles (``cm:pod``, kg/hr at 10, 50 and 90%).
  Each processing version has its own collection, and a plume's scene is in the
  collection of the plume's version (GAO v1 plumes are in ``l2b-ch4-mf-v1``), so
  the pass list is built from all of them.

Rates (``emission_auto`` and its uncertainty) are in kg/hr, the unit the API
spec gives for its emission filters.

Data are free for non-commercial use only. Raw pulls are never committed.
"""

from __future__ import annotations

import io
import json
import os
import warnings
from datetime import date
from pathlib import Path

import geopandas as gpd
import httpx
import pandas as pd
from shapely.geometry import shape
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from methanewatch.provenance import PullManifest

API = "https://api.carbonmapper.org/api/v1"
SCENE_COLLECTION = "l2b-ch4-mfa-v3e"  # newest version; carries the cm:pod quantiles
# Scene collections with Bay Area scenes, checked against /stac/collections on 2026-10-27.
SCENE_COLLECTIONS = (
    "l2b-ch4-mf-v1",
    "l2b-ch4-mfa-v1",
    "l2b-ch4-mfa-v3",
    "l2b-ch4-mfa-v3a",
    "l2b-ch4-mfa-v3b",
    "l2b-ch4-mfa-v3c",
    "l2b-ch4-mfa-v3d",
    SCENE_COLLECTION,
)
# Carbon Mapper instrument and platform codes -> keys in config/instruments.yaml
INSTRUMENTS = {
    "gao": "aircraft",
    "av3": "aircraft",
    "tan": "tanager1",
    "emi": "emit",
    "iss": "emit",
}
PAGE = 10_000
STAC_PAGE = 100  # the STAC search caps limit at 100

BBox = tuple[float, float, float, float]


def _headers() -> dict[str, str]:
    token = os.environ.get("CARBON_MAPPER_API_KEY")
    return {"Authorization": f"Bearer {token}"} if token else {}


def _transient(exc: BaseException) -> bool:
    """Server errors, rate limits and dropped connections are worth retrying."""
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500 or exc.response.status_code == 429
    return isinstance(exc, httpx.TransportError)


@retry(
    retry=retry_if_exception(_transient),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, max=60),
    reraise=True,
)
def _get(client: httpx.Client, path: str, params: list[tuple[str, str]]) -> httpx.Response:
    r = client.get(f"{API}{path}", params=params, timeout=180)
    if r.status_code == 401 and "Authorization" in client.headers:
        # Both endpoints answer without a token. An expired token in .env should not
        # stop a scheduled refresh, so drop it for the rest of this client's requests.
        warnings.warn(
            "Carbon Mapper rejected the token (expired?); continuing without it", stacklevel=2
        )
        del client.headers["Authorization"]
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
    """Write both plume pulls and every scene collection to one raw pull directory.

    Everything is downloaded before the directory is created, so a failed pull
    leaves nothing behind for the next build to trip on.
    """
    manifest = PullManifest.start(
        "carbonmapper",
        f"{API}/catalog/plume-csv; {API}/stac/search",
        {
            "bbox": bbox,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "plume_gas": "CH4",
            "plume_pulls": {"solid-waste": ["6A"], "all-sectors": None},
            "scene_collections": list(SCENE_COLLECTIONS),
        },
    )
    with httpx.Client(headers=_headers(), follow_redirects=True) as client:
        plume_tables = {
            name: plume_csv(client, bbox, start, sectors=sectors)
            for name, sectors in [("solid-waste", ["6A"]), ("all-sectors", None)]
        }
        scenes = {c: stac_scenes(client, bbox, start, end, c) for c in SCENE_COLLECTIONS}
        manifest.params["token_used"] = "Authorization" in client.headers
    pull_dir = raw_root / "carbonmapper" / manifest.pull_id
    pull_dir.mkdir(parents=True, exist_ok=True)
    files = []
    for name, table in plume_tables.items():
        path = pull_dir / f"plumes_{name}.csv"
        table.to_csv(path, index=False)
        files.append(path)
    for collection, items in scenes.items():
        path = pull_dir / f"scenes_{collection}.json"
        path.write_text(json.dumps(items))
        files.append(path)
    n = sum(len(t) for t in plume_tables.values()) + sum(len(v) for v in scenes.values())
    manifest.finish(pull_dir, files, n_records=n)
    return pull_dir


def finished_pulls(raw_root: Path) -> list[Path]:
    """Pull directories with a manifest, oldest first. Unfinished ones are ignored."""
    pulls = sorted((raw_root / "carbonmapper").glob("carbonmapper-*"))
    return [p for p in pulls if (p / "manifest.json").exists()]


def latest_pull(raw_root: Path) -> Path:
    pulls = finished_pulls(raw_root)
    if not pulls:
        raise FileNotFoundError("no Carbon Mapper pull yet; run `mw ingest carbonmapper`")
    return pulls[-1]


def merged_plumes(pulls: list[Path]) -> pd.DataFrame:
    """One row per plume across pulls: the most recently modified version wins.

    Merging, rather than reading only the newest pull, keeps plumes from earlier
    pulls when a later pull covers a shorter window. When Carbon Mapper reprocesses
    a plume, its ``modified`` time moves forward, so the newer version is kept.
    """
    frames = [
        plumes_table(p / "plumes_all-sectors.csv").assign(pull_id=p.name)
        for p in pulls
        if (p / "plumes_all-sectors.csv").exists()
    ]
    if not frames:
        raise FileNotFoundError("no Carbon Mapper plume pull yet; run `mw ingest carbonmapper`")
    table = pd.concat(frames, ignore_index=True)
    table["_modified"] = pd.to_datetime(table["modified"], utc=True, format="ISO8601")
    table = table.sort_values(["_modified", "pull_id"], kind="stable")
    table = table.drop_duplicates("plume_id", keep="last").drop(columns="_modified")
    return table.sort_values(["datetime", "plume_id"]).reset_index(drop=True)


def merged_scenes(pulls: list[Path]) -> gpd.GeoDataFrame:
    """One row per scene across pulls, taken from the newest pull that has it."""
    frames = []
    for p in pulls:
        try:
            frames.append(load_scenes(p).assign(pull_id=p.name))
        except FileNotFoundError:  # a pull with no scenes in the window
            continue
    if not frames:
        raise FileNotFoundError("no Carbon Mapper scene pull yet; run `mw ingest carbonmapper`")
    gdf = pd.concat(frames, ignore_index=True).drop_duplicates("scene_id", keep="last")
    gdf = gdf.sort_values(["acquired_utc", "scene_id"]).reset_index(drop=True)
    return gpd.GeoDataFrame(gdf, geometry="geometry", crs="EPSG:4326")


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


def load_scenes(pull_dir: Path) -> gpd.GeoDataFrame:
    """Every scene in a pull, from all collections, one row per scene id."""
    frames = [
        scenes_table(json.loads(p.read_text())) for p in sorted(pull_dir.glob("scenes_*.json"))
    ]
    frames = [f for f in frames if len(f)]
    if not frames:
        raise FileNotFoundError(f"no scenes in {pull_dir}")
    gdf = pd.concat(frames, ignore_index=True).drop_duplicates("scene_id")
    return gpd.GeoDataFrame(gdf, geometry="geometry", crs="EPSG:4326")


def footprints(scenes: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Scene footprints in the layout ``coverage.overpasses.from_footprints`` expects.

    EMIT scenes (platform ``iss``) are left out: EMIT passes come from NASA's own
    scene list, and counting them twice would double EMIT's looks. The scenes have
    no cloud mask, so ``valid_frac`` is 1 and every covered pass counts as usable.
    """
    platform = scenes["platform"].str.lower()
    keep = scenes[(platform != "iss") & platform.isin(list(INSTRUMENTS))]
    out = keep.assign(
        instrument=platform[keep.index].map(INSTRUMENTS),
        valid_frac=1.0,
        data_version=keep["version"].astype(str),
    )
    cols = ["scene_id", "instrument", "acquired_utc", "valid_frac", "data_version", "geometry"]
    return gpd.GeoDataFrame(out[cols], geometry="geometry", crs="EPSG:4326").reset_index(drop=True)


def plumes(table: pd.DataFrame, pull_id: str | None = None) -> pd.DataFrame:
    """Plumes in the layout ``coverage build`` reads, before attribution.

    The plume list has one row per plume, at the newest processing version Carbon
    Mapper has published for it; ``data_version`` records which. A plume with no
    published rate keeps a missing rate and is reported, not modelled. ``pull_id``
    defaults to the table's own ``pull_id`` column (set by ``merged_plumes``).
    """
    code = table["instrument"].str.lower()
    unknown = sorted(set(code) - set(INSTRUMENTS))
    if unknown:
        raise ValueError(f"unknown Carbon Mapper instrument codes: {unknown}")
    if table["plume_id"].duplicated().any():
        raise ValueError("a plume appears more than once; keep its newest version only")
    out = pd.DataFrame(
        {
            "plume_id": table["plume_id"].astype(str),
            "source": "carbonmapper",
            "instrument": code.map(INSTRUMENTS),
            "acquired_utc": pd.to_datetime(table["datetime"], utc=True, format="ISO8601"),
            "origin_lon": table["plume_longitude"].astype(float),
            "origin_lat": table["plume_latitude"].astype(float),
            "q_kg_hr": table["emission_auto"].astype(float),
            "q_sigma_kg_hr": table["emission_uncertainty_auto"].astype(float),
            "data_version": table["emission_version"].astype(str),
            "platform": table["platform"],
            "ipcc_sector": table["ipcc_sector"],
            "pull_id": table["pull_id"] if pull_id is None else pull_id,
        }
    )
    return out.sort_values(["acquired_utc", "plume_id"]).reset_index(drop=True)
