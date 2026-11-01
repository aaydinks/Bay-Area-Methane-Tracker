"""Clear-sky share over each pilot site on each Sentinel-2 pass (ADR 0013, ADR 0014).

For one (site, UTC day) of the overpass table, all 13 L1C bands are read for a 6 km window
centred on the site polygon's centroid. The window is snapped to the tile's 60 m grid, so 10 m
bands reduce to 20 m by an exact 2 x 2 mean and 60 m bands by exact 3 x 3 repeats, as in the
CloudSEN12+ patches the cloud model was trained on. Sen2Cor's scene classification (SCL) is
read for the same window from the matching L2A product.

Clear shares are taken over the central 254 x 254 pixels (5.08 km), the unit of the held-out
test; the outer ring only gives the model's local filters their context.

Pixels come from Google's public L1C mirror (``crops.py``) and Earth Search's L2A COGs, both
without a login. Windows are cached as digital numbers under ``data/raw/s2windows/``.
"""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import Window
from shapely.geometry import box
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from methanewatch.sentinel2 import crops
from methanewatch.sentinel2.cloudmodel import BANDS, CLEAR, CloudModel

WINDOW_M = 6000
RES_M = 20
GRID_M = 60  # coarsest band; snapping here keeps every band's pixels whole
WINDOW_PX = WINDOW_M // RES_M
SCORE_PX = 254  # 5.08 km, the held-out patch size
NATIVE_M = {"B01": 60, "B02": 10, "B03": 10, "B04": 10, "B05": 20, "B06": 20, "B07": 20}
NATIVE_M |= {"B08": 10, "B8A": 20, "B09": 60, "B10": 60, "B11": 20, "B12": 20}
SCL_UNUSABLE = (3, 8, 9, 10)  # cloud shadow, cloud medium, cloud high, thin cirrus (ADR 0013)
SCL_NODATA = 0
MIN_REFLECTANCE = 1e-4  # one digital number: the floor of the pre-04.00 baselines
MAX_NODATA_SHARE = 0.01  # ADR 0014: windows with more no data are listed, not scored
L2A_COLLECTIONS = ("sentinel-2-c1-l2a", "sentinel-2-l2a")  # c1 first; the older one fills 2022
METRIC_CRS = "EPSG:32610"
GDAL_ENV = {**crops.GDAL_ENV, "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".jp2,.xml,.tif"}
# A truncated range response surfaces as a JPEG 2000 decode error; Earth Search sometimes drops
# a connection under load. Both are retried a few times before the window is given up.
_retry = retry(
    stop=stop_after_attempt(4), wait=wait_exponential(multiplier=2, max=30), reraise=True
)


def scored_slice() -> tuple[slice, slice]:
    lo = (WINDOW_PX - SCORE_PX) // 2
    return slice(lo, lo + SCORE_PX), slice(lo, lo + SCORE_PX)


def site_centres(sites: gpd.GeoDataFrame) -> pd.DataFrame:
    """Polygon centroids in EPSG:32610 (the CRS of every pilot tile)."""
    c = sites.to_crs(METRIC_CRS).geometry.centroid
    return pd.DataFrame({"site_id": sites["site_id"].to_numpy(), "x": c.x, "y": c.y})


def snapped_bounds(ulx: float, uly: float, x: float, y: float) -> tuple[float, ...]:
    """6 km window around (x, y) whose edges lie on the tile's 60 m grid."""
    left = ulx + round((x - WINDOW_M / 2 - ulx) / GRID_M) * GRID_M
    top = uly - round((uly - (y + WINDOW_M / 2)) / GRID_M) * GRID_M
    return (left, top - WINDOW_M, left + WINDOW_M, top)


def _window(src, bounds: tuple[float, ...], res: int) -> Window:
    ulx, uly = src.transform.c, src.transform.f
    left, _, _, top = bounds
    n = WINDOW_M // res
    return Window(round((left - ulx) / res), round((uly - top) / res), n, n)


def _to_20m(a: np.ndarray, res: int) -> tuple[np.ndarray, np.ndarray]:
    """Digital numbers on the 20 m grid and where they hold data."""
    if res == 10:
        blocks = a.reshape(WINDOW_PX, 2, WINDOW_PX, 2)
        return blocks.mean(axis=(1, 3)), blocks.min(axis=(1, 3)) > 0
    if res == 60:
        a = np.repeat(np.repeat(a, 3, axis=0), 3, axis=1)
    return a.astype(np.float32), a > 0


def read_l1c(product_uri: str, x: float, y: float) -> dict:
    """All 13 bands of one window as digital numbers, plus what is needed to convert them."""
    urls = crops.band_urls(product_uri, BANDS)
    consts = crops.radiometric_constants(crops._get(urls["metadata"]).text, BANDS)
    with rasterio.Env(**GDAL_ENV), rasterio.open(crops._vsi(urls["B11"])) as ref:
        if ref.crs.to_epsg() != 32610:
            raise ValueError(f"{product_uri} is not in EPSG:32610")
        bounds = snapped_bounds(ref.transform.c, ref.transform.f, x, y)
        left, bottom, right, top = ref.bounds
        if bounds[0] < left or bounds[1] < bottom or bounds[2] > right or bounds[3] > top:
            raise ValueError(f"window not inside tile for {product_uri}")

    @_retry
    def one(b: str) -> tuple[np.ndarray, np.ndarray]:
        res = NATIVE_M[b]
        with rasterio.Env(**GDAL_ENV), rasterio.open(crops._vsi(urls[b])) as src:
            a = src.read(1, window=_window(src, bounds, res)).astype(np.float32)
        return _to_20m(a, res)

    # Thirteen files, each mostly waiting on range requests, so they are read at once
    with ThreadPoolExecutor(len(BANDS)) as pool:
        layers = list(pool.map(one, BANDS))
    return {
        "dn": np.rint(np.stack([d for d, _ in layers])).astype(np.uint16),
        "valid": np.logical_and.reduce([v for _, v in layers]),
        "bounds": np.asarray(bounds),
        "consts": consts,
    }


def reflectance(dn: np.ndarray, valid: np.ndarray, consts: dict) -> np.ndarray:
    """Top-of-atmosphere reflectance on the scale of the training patches; NaN where no data.

    Baselines from 04.00 add an offset (-1000) that the 2017 to 2020 training images lack.
    """
    q = consts["quantification"]
    offs = np.array([consts.get(f"offset_{b}", 0.0) for b in BANDS], np.float32)[:, None, None]
    r = np.maximum((dn.astype(np.float32) + offs) / q, MIN_REFLECTANCE)
    r[:, ~valid] = np.nan
    return r


def _sensing(product_uri: str) -> tuple[str, str, str]:
    m = re.match(r"(S2[ABC])_MSIL\w{2}_(\d{8}T\d{6})_N\d{4}_R\d{3}_T(\w{5})_", product_uri)
    if not m:
        raise ValueError(f"unexpected product name {product_uri}")
    return m.groups()


def find_scl(product_uri: str, client=None) -> dict | None:
    """The L2A scene classification of the same acquisition: platform, tile and sensing time."""
    from pystac_client import Client

    from methanewatch.sentinel2.search import EARTH_SEARCH

    platform, stamp, tile = _sensing(product_uri)
    day = f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]}"
    client = client or Client.open(EARTH_SEARCH)

    @_retry
    def search(coll: str) -> list:
        query = {"grid:code": {"eq": f"MGRS-{tile}"}}
        return list(
            client.search(
                collections=[coll], datetime=f"{day}/{day}", query=query, max_items=20
            ).items()
        )

    for coll in L2A_COLLECTIONS:
        for it in search(coll):
            uri = it.properties.get("s2:product_uri") or ""
            if uri.startswith(f"{platform}_MSIL2A_{stamp}_") and "scl" in it.assets:
                return {"collection": coll, "item": it.id, "href": it.assets["scl"].href}
    return None


@retry(
    retry=retry_if_exception_type(rasterio.errors.RasterioError),
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=2, max=30),
    reraise=True,
)
def read_scl(href: str, bounds: np.ndarray) -> np.ndarray:
    with rasterio.Env(**GDAL_ENV), rasterio.open(f"/vsicurl/{href}") as src:
        return src.read(1, window=_window(src, tuple(bounds), RES_M), boundless=True, fill_value=0)


def choose_scene(scene_ids: list[str], footprints: pd.DataFrame, x: float, y: float) -> str:
    """The first scene (by id) whose footprint holds the whole window, else the most overlap."""
    half = WINDOW_M / 2
    win = gpd.GeoSeries([box(x - half, y - half, x + half, y + half)], crs=METRIC_CRS)
    fp = footprints.loc[sorted(scene_ids)]
    inside = fp[fp.geometry.contains(win.to_crs("EPSG:4326").iloc[0])]
    if len(inside):
        return inside.index[0]
    return fp.geometry.to_crs(METRIC_CRS).intersection(win.iloc[0]).area.idxmax()


@dataclass
class Window13:
    """One cached window: digital numbers, data mask, SCL, and its place on the ground."""

    dn: np.ndarray
    valid: np.ndarray
    scl: np.ndarray | None
    bounds: np.ndarray
    consts: dict
    scl_source: dict | None

    def save(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp.npz")
        np.savez_compressed(
            tmp,
            dn=self.dn,
            valid=self.valid,
            scl=self.scl if self.scl is not None else np.zeros(0, np.uint8),
            bounds=self.bounds,
            meta=json.dumps({"consts": self.consts, "scl_source": self.scl_source}),
        )
        tmp.rename(path)
        return path

    @staticmethod
    def load(path: Path) -> Window13:
        with np.load(path) as z:
            meta = json.loads(str(z["meta"]))
            scl = z["scl"] if z["scl"].size else None
            src = meta["scl_source"]
            return Window13(z["dn"], z["valid"], scl, z["bounds"], meta["consts"], src)


def fetch_window(product_uri: str, x: float, y: float, client=None) -> Window13:
    w = read_l1c(product_uri, x, y)
    src = find_scl(product_uri, client)
    scl = read_scl(src["href"], w["bounds"]) if src else None
    return Window13(w["dn"], w["valid"], scl, w["bounds"], w["consts"], src)


def score(win: Window13, model: CloudModel) -> tuple[dict, np.ndarray]:
    """Clear shares over the scored area, and the model's class map for the whole window."""
    refl = reflectance(win.dn, win.valid, win.consts)
    classes = model.predict(refl)
    rs, cs = scored_slice()
    ok = win.valid[rs, cs]
    row = {
        "nodata_share": float(1 - ok.mean()),
        "clear_model": float((classes[rs, cs][ok] == CLEAR).mean()) if ok.any() else np.nan,
        "clear_scl": np.nan,
        "scl_nodata_share": np.nan,
    }
    if win.scl is not None:
        scl = win.scl[rs, cs]
        scl_ok = ok & (scl != SCL_NODATA)
        row["scl_nodata_share"] = float(1 - scl_ok.mean())
        if scl_ok.any():
            row["clear_scl"] = float(1 - np.isin(scl[scl_ok], SCL_UNUSABLE).mean())
    row["scored"] = row["nodata_share"] <= MAX_NODATA_SHARE
    return row, classes


def pass_table(
    overpasses: pd.DataFrame, footprints: gpd.GeoDataFrame, sites: gpd.GeoDataFrame
) -> pd.DataFrame:
    """Sentinel-2 site-days with the chosen scene and window centre."""
    s2 = overpasses[overpasses["instrument"] == "sentinel2"].copy()
    centres = site_centres(sites).set_index("site_id")
    fp = footprints.set_index("scene_id")
    s2 = s2.join(centres, on="site_id")
    s2["scene_id"] = [
        choose_scene(list(ids), fp, x, y)
        for ids, x, y in zip(s2["scene_ids"], s2["x"], s2["y"], strict=True)
    ]
    s2 = s2.join(fp[["product_uri", "platform"]], on="scene_id")
    s2["baseline"] = s2["product_uri"].str.extract(r"_(N\d{4})_", expand=False)
    s2["day"] = pd.to_datetime(s2["acquired_utc"], utc=True).dt.strftime("%Y-%m-%d")
    cols = ["overpass_id", "site_id", "day", "acquired_utc", "scene_id", "product_uri"]
    cols += ["platform", "baseline", "valid_frac", "x", "y"]
    return s2[cols].sort_values(["day", "site_id"]).reset_index(drop=True)


def cache_file(root: Path, site_id: str, product_uri: str) -> Path:
    return root / site_id / f"{product_uri.removesuffix('.SAFE')}.npz"


def run(
    passes: pd.DataFrame,
    model: CloudModel,
    cache_roots: list[Path],
    pull_dir: Path,
    *,
    workers: int = 6,
    keep_classes: bool = False,
) -> tuple[pd.DataFrame, dict[str, np.ndarray], list[Path]]:
    """Score every pass. Windows already cached under any of ``cache_roots`` are not read again;
    new ones are written under ``pull_dir``. Returns the scores, the class maps (when asked)
    and the new files."""
    from pystac_client import Client

    from methanewatch.sentinel2.search import EARTH_SEARCH

    client = Client.open(EARTH_SEARCH)

    def get(r) -> tuple[Path | None, str | None]:
        for root in [*cache_roots, pull_dir]:
            p = cache_file(root, r.site_id, r.product_uri)
            if p.exists():
                return p, None
        try:
            win = fetch_window(r.product_uri, r.x, r.y, client)
        except Exception as exc:  # one window failing must not stop the others; it is listed
            return None, f"{type(exc).__name__}: {exc}"
        return win.save(cache_file(pull_dir, r.site_id, r.product_uri)), "new"

    rows, classes, new = [], {}, []
    with ThreadPoolExecutor(workers) as pool:
        # Reads run in threads; the model scores each window in this thread as it arrives
        for r, (path, status) in zip(
            passes.itertuples(), pool.map(get, passes.itertuples()), strict=True
        ):
            base = r._asdict()
            base.pop("Index")
            if path is None:
                rows.append({**base, "error": status, "scored": False})
                continue
            if status == "new":
                new.append(path)
            win = Window13.load(path)
            row, cls = score(win, model)
            src = win.scl_source or {}
            rows.append(
                {
                    **base,
                    **row,
                    "scl_collection": src.get("collection"),
                    "scl_item": src.get("item"),
                    "window_left": float(win.bounds[0]),
                    "window_top": float(win.bounds[3]),
                    "file": str(path),
                    "error": None,
                }
            )
            if keep_classes:
                classes[r.overpass_id] = cls
    return pd.DataFrame(rows), classes, new
