"""Small Sentinel-2 L1C crops around the pilot sites (docs/PLAN.md phase 3, ADR 0004).

Sentinel-2 is a check on large events, not a detector, so only two kinds of dates
are cropped: days with a Carbon Mapper or EMIT plume near a site and a same-day
Sentinel-2 pass, and a few clear earlier no-plume days as MBMP references
(same relative orbit where possible).

Pixels come from Google's public copy of the ESA L1C archive
(``gcp-public-data-sentinel-2``), which needs no login; the AWS copy is
requester-pays. The band files are tiled JPEG 2000, so a window is read without
downloading the tile. Crops keep the original digital numbers; reflectance is
``(DN + RADIO_ADD_OFFSET) / QUANTIFICATION_VALUE``, both read from the product
metadata and written into each crop's tags.
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path

import geopandas as gpd
import httpx
import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer
from rasterio.enums import Resampling
from rasterio.windows import from_bounds
from tenacity import retry, stop_after_attempt, wait_exponential

GCS = "https://storage.googleapis.com"
BUCKET = "gcp-public-data-sentinel-2"
BANDS = ["B02", "B03", "B08", "B11", "B12"]  # B02/B03/B08 feed the artifact masks
RES_M = 20
GDAL_ENV = {
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".jp2,.xml",
    "GDAL_HTTP_MULTIRANGE": "YES",
}


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=2, max=30))
def _get(url: str, params: dict | None = None) -> httpx.Response:
    r = httpx.get(url, params=params, timeout=120)
    r.raise_for_status()
    return r


def product_prefix(product_uri: str) -> str:
    """Bucket prefix ``tiles/10/S/EG/<product>.SAFE/`` for a product named ``..._T10SEG_...``."""
    m = re.search(r"_T(\d{2})([A-Z])([A-Z]{2})_", product_uri)
    if not m:
        raise ValueError(f"no MGRS tile in {product_uri}")
    zone, band, square = m.groups()
    return f"tiles/{zone}/{band}/{square}/{product_uri}/"


def band_urls(product_uri: str) -> dict[str, str]:
    """Public URLs of the band files and product metadata on Google's mirror."""
    prefix = product_prefix(product_uri)
    params = {"prefix": prefix, "fields": "items(name),nextPageToken", "maxResults": 1000}
    names = [i["name"] for i in _get(f"{GCS}/storage/v1/b/{BUCKET}/o", params).json()["items"]]
    urls = {}
    for b in BANDS:
        hit = [n for n in names if "/IMG_DATA/" in n and n.endswith(f"_{b}.jp2")]
        if len(hit) != 1:
            raise FileNotFoundError(f"{b} not found once under {prefix}")
        urls[b] = f"{GCS}/{BUCKET}/{hit[0]}"
    urls["metadata"] = f"{GCS}/{BUCKET}/{prefix}MTD_MSIL1C.xml"
    return urls


def radiometric_constants(metadata_xml: str) -> dict[str, float]:
    """Quantification value and per-band additive offset (0 before baseline 04.00)."""
    quant = float(re.search(r"<QUANTIFICATION_VALUE[^>]*>([\d.]+)<", metadata_xml).group(1))
    offsets = {
        int(i): float(v)
        for i, v in re.findall(
            r'<RADIO_ADD_OFFSET band_id="(\d+)">(-?[\d.]+)</RADIO_ADD_OFFSET>', metadata_xml
        )
    }
    # band_id order in the metadata: B01 B02 B03 B04 B05 B06 B07 B08 B8A B09 B10 B11 B12
    order = ["B01", "B02", "B03", "B04", "B05", "B06", "B07", "B08", "B8A", "B09", "B10"]
    order += ["B11", "B12"]
    out = {"quantification": quant}
    for b in BANDS:
        out[f"offset_{b}"] = offsets.get(order.index(b), 0.0)
    return out


def _vsi(url: str) -> str:
    return f"/vsicurl/{url}"


def _read_band(url: str, bounds: tuple[float, float, float, float], size: int) -> np.ndarray:
    """One band's window on the crop grid. Each call opens its own file, so calls can run in
    parallel threads."""
    with rasterio.Env(**GDAL_ENV), rasterio.open(_vsi(url)) as src:
        w = from_bounds(*bounds, src.transform)
        return src.read(1, window=w, out_shape=(size, size), resampling=Resampling.average)


def crop(product_uri: str, lon: float, lat: float, half_m: float, out: Path, tags: dict) -> Path:
    """Write a 20 m GeoTIFF of ``BANDS`` centred on (lon, lat); 10 m bands are averaged."""
    urls = band_urls(product_uri)
    consts = radiometric_constants(_get(urls["metadata"]).text)
    with rasterio.Env(**GDAL_ENV), rasterio.open(_vsi(urls["B11"])) as ref:
        crs = ref.crs
        x, y = Transformer.from_crs(4326, crs, always_xy=True).transform(lon, lat)
        bounds = (x - half_m, y - half_m, x + half_m, y + half_m)
        left, bottom, right, top = ref.bounds
        if bounds[0] < left or bounds[1] < bottom or bounds[2] > right or bounds[3] > top:
            raise ValueError(f"window not inside tile for {product_uri}")
    size = round(2 * half_m / RES_M)
    transform = rasterio.transform.from_bounds(*bounds, size, size)
    # Each band is its own file and a read is mostly waiting on many small range requests, so the
    # five bands are fetched at once: about 20 s a crop instead of 85 s, same pixels (ADR 0011).
    with ThreadPoolExecutor(len(BANDS)) as pool:
        layers = list(pool.map(lambda b: _read_band(urls[b], bounds, size), BANDS))
    data = np.stack(layers).astype("uint16")
    out.parent.mkdir(parents=True, exist_ok=True)
    profile = {
        "driver": "GTiff",
        "height": size,
        "width": size,
        "count": len(BANDS),
        "dtype": "uint16",
        "crs": crs,
        "transform": transform,
        "nodata": 0,
        "compress": "deflate",
        "predictor": 2,
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
    }
    with rasterio.open(out, "w", **profile) as dst:
        dst.write(data)
        for i, b in enumerate(BANDS, start=1):
            dst.set_band_description(i, b)
        dst.update_tags(
            product_uri=product_uri,
            source=f"{GCS}/{BUCKET}/{product_prefix(product_uri)}",
            reflectance="(DN + offset_<band>) / quantification",
            **{k: str(v) for k, v in {**consts, **tags}.items()},
        )
    return out


def choose_targets(
    sites: gpd.GeoDataFrame,
    plumes: pd.DataFrame,
    scenes: gpd.GeoDataFrame,
    *,
    plume_radius_m: float = 3000,
    half_m: float = 3000,
    max_cloud: float = 20,
    n_reference: int = 3,
    quiet_days: int = 3,
) -> pd.DataFrame:
    """Plume days with a clear same-day pass, plus clear earlier no-plume reference days.

    ``plumes`` needs ``plume_id``, ``acquired_utc``, ``lon``, ``lat`` and ``source``;
    ``scenes`` is the Sentinel-2 footprint table with ``product_uri``. A plume
    counts for a site when it lies within ``plume_radius_m`` of the site's
    reference point (no boundaries yet, so this is a search radius, not
    attribution). Only scenes whose footprint holds the whole crop window are used.
    """
    metric = "EPSG:32610"
    pts = sites.to_crs(metric)
    pl = gpd.GeoDataFrame(
        plumes, geometry=gpd.points_from_xy(plumes["lon"], plumes["lat"]), crs="EPSG:4326"
    ).to_crs(metric)
    near = gpd.sjoin_nearest(pl, pts[["site_id", "geometry"]], distance_col="distance_m")
    near = near[near["distance_m"] <= plume_radius_m].copy()
    near["day"] = near["acquired_utc"].dt.tz_convert("UTC").dt.date
    sc = scenes.copy()
    sc["day"] = sc["acquired_utc"].dt.tz_convert("UTC").dt.date
    sc = sc[sc["cloud_cover_pct"] <= max_cloud]

    rows = []
    for site in pts.itertuples():
        window = gpd.GeoSeries([site.geometry.buffer(half_m, cap_style="square")], crs=metric)
        covering = sc[sc.contains(window.to_crs("EPSG:4326").iloc[0])]
        site_plumes = near[near["site_id"] == site.site_id]
        plume_days = set(site_plumes["day"])
        span = range(-quiet_days, quiet_days + 1)
        busy = {d + timedelta(days=k) for d in plume_days for k in span}
        targets = covering[covering["day"].isin(plume_days)].sort_values("cloud_cover_pct")
        targets = targets.drop_duplicates("day")
        for t in targets.itertuples():
            on_day = site_plumes[site_plumes["day"] == t.day]
            rows.append(
                {
                    "site_id": site.site_id,
                    "role": "plume_day",
                    "day": t.day,
                    "product_uri": t.product_uri,
                    "relative_orbit": t.relative_orbit,
                    "cloud_cover_pct": t.cloud_cover_pct,
                    "plume_ids": ";".join(sorted(on_day["plume_id"])),
                    "for_day": None,
                }
            )
        quiet = covering[~covering["day"].isin(busy)]
        anchors = list(targets.itertuples()) or [None]
        for anchor in anchors:
            pool = quiet if anchor is None else quiet[quiet["day"] < anchor.day]
            if anchor is not None:
                same = pool[pool["relative_orbit"] == anchor.relative_orbit]
                pool = same if len(same) >= n_reference else pool
            refs = pool.sort_values(["day", "cloud_cover_pct"], ascending=[False, True])
            refs = refs.drop_duplicates("day").head(n_reference)
            for r in refs.itertuples():
                rows.append(
                    {
                        "site_id": site.site_id,
                        "role": "reference",
                        "day": r.day,
                        "product_uri": r.product_uri,
                        "relative_orbit": r.relative_orbit,
                        "cloud_cover_pct": r.cloud_cover_pct,
                        "plume_ids": "",
                        "for_day": None if anchor is None else anchor.day,
                    }
                )
    out = pd.DataFrame(rows)
    return out.drop_duplicates(["site_id", "product_uri", "role", "for_day"]).reset_index(drop=True)
