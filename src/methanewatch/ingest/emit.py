"""NASA EMIT v2 methane products (docs/PLAN.md section 5, phase 2b).

Collections (LP DAAC, version 002; version 1 was decommissioned March 26, 2026):
- ``EMITL2BCH4ENH``: per-scene methane enhancement. Its granule footprints are
  EMIT's overpasses, available from CMR metadata without a login.
- ``EMITL2BCH4PLM``: reviewed plume complexes. The footprint and time are in CMR
  metadata; per-plume details are in a ``CH4PLMMETA`` JSON file that needs an
  Earthdata login (``~/.netrc``).

Plumes are manually reviewed before release, so a scene with no plume is not
proof of no leak. The model handles that through the detection curve and the
release probability.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Polygon

from methanewatch.provenance import PullManifest

ENH = "EMITL2BCH4ENH"
PLM = "EMITL2BCH4PLM"
VERSION = "002"


def _polygon(umm: dict) -> Polygon:
    geo = umm["SpatialExtent"]["HorizontalSpatialDomain"]["Geometry"]
    pts = geo["GPolygons"][0]["Boundary"]["Points"]
    return Polygon([(p["Longitude"], p["Latitude"]) for p in pts])


def _time(umm: dict) -> str:
    t = umm["TemporalExtent"]
    return t["RangeDateTime"]["BeginningDateTime"] if "RangeDateTime" in t else t["SingleDateTime"]


def _attr(umm: dict, name: str) -> str | None:
    for a in umm.get("AdditionalAttributes", []):
        if a["Name"] == name:
            return a["Values"][0]
    return None


def search_granules(
    short_name: str, bbox: tuple[float, float, float, float], start: date, end: date
) -> list[dict]:
    """CMR search; returns raw UMM-G records (metadata only, no login needed)."""
    import earthaccess

    results = earthaccess.search_data(
        short_name=short_name,
        version=VERSION,
        bounding_box=bbox,
        temporal=(start.isoformat(), end.isoformat()),
        count=-1,
    )
    return [dict(r) for r in results]


def pull(
    short_name: str,
    bbox: tuple[float, float, float, float],
    start: date,
    end: date,
    raw_root: Path,
) -> Path:
    records = search_granules(short_name, bbox, start, end)
    manifest = PullManifest.start(
        f"emit-{short_name.lower()}",
        "earthaccess.search_data",
        {
            "short_name": short_name,
            "version": VERSION,
            "bbox": bbox,
            "start": start.isoformat(),
            "end": end.isoformat(),
        },
    )
    pull_dir = raw_root / "emit" / manifest.pull_id
    pull_dir.mkdir(parents=True, exist_ok=True)
    path = pull_dir / "granules.json"
    path.write_text(json.dumps(records, indent=1, default=str))
    manifest.finish(pull_dir, [path], n_records=len(records))
    return pull_dir


def footprints(records: list[dict]) -> gpd.GeoDataFrame:
    """EMIT scene footprints in the layout ``coverage.overpasses.from_footprints`` expects.

    ``valid_frac`` comes from the scene-level ``CloudCover`` percentage. That is a
    scene average, not the cloud share over a site; replace it with the per-pixel
    mask once Earthdata access is set up.
    """
    rows = []
    for r in records:
        u = r["umm"]
        version = r["umm"]["CollectionReference"].get("Version", VERSION)
        if version != VERSION:
            raise ValueError(f"refusing EMIT granule version {version}: {u['GranuleUR']}")
        cloud = u.get("CloudCover")
        rows.append(
            {
                "scene_id": u["GranuleUR"],
                "instrument": "emit",
                "acquired_utc": _time(u),
                "valid_frac": 1 - cloud / 100 if cloud is not None else 1.0,
                "geometry": _polygon(u),
            }
        )
    gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")
    gdf["acquired_utc"] = pd.to_datetime(gdf["acquired_utc"], utc=True, format="ISO8601")
    return gdf


def plume_outlines(records: list[dict]) -> gpd.GeoDataFrame:
    """Plume-complex outlines and times from CMR metadata (no rates; see module doc)."""
    rows = []
    for r in records:
        u = r["umm"]
        rows.append(
            {
                "plume_id": f"emit-{_attr(u, 'PLUME_ID')}-{_time(u)[:10]}",
                "granule_ur": u["GranuleUR"],
                "acquired_utc": _time(u),
                "source_scenes": _attr(u, "SOURCE_SCENES"),
                "geometry": _polygon(u),
            }
        )
    gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")
    gdf["acquired_utc"] = pd.to_datetime(gdf["acquired_utc"], utc=True, format="ISO8601")
    return gdf


def load_pull(pull_dir: Path) -> list[dict]:
    return json.loads((pull_dir / "granules.json").read_text())


# --- Files behind an Earthdata login (~/.netrc) ------------------------------------

ENH_LAYERS = {
    "CH4ENH": "enhancement_ppm_m",
    "CH4UNCERT": "uncertainty_ppm_m",
    "CH4SENS": "sensitivity",
}


def data_urls(record: dict) -> dict[str, str]:
    """HTTPS links of a granule's protected files, keyed by product part (``CH4ENH``...)."""
    urls = {}
    for u in record["umm"].get("RelatedUrls", []):
        url = u["URL"]
        if u.get("Type") == "GET DATA" and url.startswith("https://"):
            name = url.rsplit("/", 1)[-1]
            part = name.split("_")[2]  # EMIT_L2B_<part>_002_...
            urls[part] = url
    return urls


def earthdata_session():
    """Requests session logged in through ~/.netrc; raises if the login is missing."""
    import earthaccess

    auth = earthaccess.login(strategy="netrc")
    if not auth or not auth.authenticated:
        raise PermissionError("Earthdata login failed; add urs.earthdata.nasa.gov to ~/.netrc")
    return earthaccess.get_requests_https_session()


def plume_metadata(record: dict, session) -> dict:
    """The CH4PLMMETA JSON of a plume complex: rate, uncertainty, maximum enhancement."""
    r = session.get(data_urls(record)["CH4PLMMETA"], timeout=120)
    r.raise_for_status()
    return r.json()


def gdal_env(cookie_file: Path) -> dict[str, str]:
    """GDAL settings for windowed reads of LP DAAC files through the Earthdata redirect."""
    return {
        "GDAL_HTTP_NETRC": "YES",
        "GDAL_HTTP_COOKIEFILE": str(cookie_file),
        "GDAL_HTTP_COOKIEJAR": str(cookie_file),
        "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
        "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif",
        "GDAL_HTTP_UNSAFESSL": "NO",
    }


def site_window(
    record: dict, lon: float, lat: float, half_m: float, out: Path, cookie_file: Path
) -> Path:
    """Write enhancement, uncertainty and sensitivity around (lon, lat) as one 3-band GeoTIFF."""
    import numpy as np
    import rasterio
    from pyproj import Transformer
    from rasterio.windows import from_bounds

    urls = data_urls(record)
    to_ll = Transformer.from_crs("EPSG:32610", "EPSG:4326", always_xy=True)
    x, y = Transformer.from_crs("EPSG:4326", "EPSG:32610", always_xy=True).transform(lon, lat)
    xs, ys = to_ll.transform([x - half_m, x + half_m], [y - half_m, y + half_m])
    layers, profile = [], None
    with rasterio.Env(**gdal_env(cookie_file)):
        for part in ENH_LAYERS:
            with rasterio.open(f"/vsicurl/{urls[part]}") as src:
                if src.crs.to_epsg() != 4326:
                    raise ValueError(f"unexpected CRS {src.crs} for {urls[part]}")
                w = from_bounds(xs[0], ys[0], xs[1], ys[1], src.transform).round_offsets()
                w = w.round_lengths()
                data = src.read(1, window=w, boundless=True, fill_value=src.nodata)
                layers.append(data.astype("float32"))
                if profile is None:
                    profile = {
                        "transform": src.window_transform(w),
                        "crs": src.crs,
                        "nodata": src.nodata,
                    }
    stack = np.stack(layers)
    out.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        out,
        "w",
        driver="GTiff",
        height=stack.shape[1],
        width=stack.shape[2],
        count=len(layers),
        dtype="float32",
        compress="deflate",
        predictor=3,
        **profile,
    ) as dst:
        dst.write(stack)
        for i, name in enumerate(ENH_LAYERS.values(), start=1):
            dst.set_band_description(i, name)
        dst.update_tags(granule_ur=record["umm"]["GranuleUR"], source=urls["CH4ENH"])
    return out
