"""Sen2Cor's clear share over each pilot site on each Sentinel-2 pass (ADR 0014).

ADR 0014's check of the cloud model did not hold, so the share that decides whether a
Sentinel-2 pass counts comes from Sen2Cor, not from the model. Only Sen2Cor's scene
classification (SCL) is read, never the 13 L1C bands:

- **Window.** The same 6 km window as ``sitecloud``, around the site polygon's centroid and
  snapped to the tile's 60 m grid. The grid comes from the SCL file's own transform, which is
  the tile's.
- **Scored area.** The central 254 x 254 pixels (5.08 km), as in ADR 0013 and ADR 0014.
- **Clear share.** One minus the share of SCL classes 3, 8, 9 and 10 among pixels with data.
  Class 0 is no data.

A pass has no Sen2Cor share when Earth Search holds no matching L2A granule, or when more than
1% of the scored area has no data (ADR 0014's rule for partial windows). Such a pass keeps the
tile figure, and that is marked.

Windows are cached under ``data/raw/s2scl/<pull>/``. The 13-band windows already under
``data/raw/s2windows/`` are reused when their SCL covers the scored area. A pass with no L2A
match is not cached, so a later run asks Earth Search again.
"""

from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from methanewatch import schemas
from methanewatch.sentinel2 import sitecloud as sc

SOURCE = "s2scl"
ENDPOINT = "earth-search sentinel-2-c1-l2a / sentinel-2-l2a (SCL)"
TABLE = "s2_site_clear.parquet"
# Why a pass has (or lacks) a Sen2Cor share
SITE = schemas.VALID_FRAC_SITE
NO_L2A = "no-l2a"
PARTIAL = "partial"
ERROR = "error"


@dataclass
class SclWindow:
    """One cached SCL window and its place on the ground."""

    scl: np.ndarray
    bounds: np.ndarray
    source: dict

    def save(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp.npz")
        np.savez_compressed(tmp, scl=self.scl, bounds=self.bounds, meta=json.dumps(self.source))
        tmp.rename(path)
        return path

    @staticmethod
    def load(path: Path) -> SclWindow:
        with np.load(path) as z:
            return SclWindow(z["scl"], z["bounds"], json.loads(str(z["meta"])))


def _vsi(href: str) -> str:
    return f"/vsicurl/{href}"


def cache_file(root: Path, site_id: str, product_uri: str) -> Path:
    return root / site_id / f"{product_uri.removesuffix('.SAFE')}.npz"


def share(scl: np.ndarray) -> dict:
    """Sen2Cor's clear share and its no-data share over the scored area."""
    rs, cs = sc.scored_slice()
    s = scl[rs, cs]
    ok = s != sc.SCL_NODATA
    return {
        "clear_scl": float(1 - np.isin(s[ok], sc.SCL_UNUSABLE).mean()) if ok.any() else np.nan,
        "scl_nodata_share": float(1 - ok.mean()),
    }


@retry(
    retry=retry_if_exception_type(rasterio.errors.RasterioError),
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=2, max=30),
    reraise=True,
)
def scl_bounds(href: str, x: float, y: float) -> np.ndarray:
    """The 6 km window around (x, y), on the grid of the SCL file's tile."""
    with rasterio.Env(**sc.GDAL_ENV), rasterio.open(_vsi(href)) as src:
        if src.crs.to_epsg() != 32610:
            raise ValueError(f"{href} is not in EPSG:32610")
        if tuple(src.res) != (sc.RES_M, sc.RES_M):
            raise ValueError(f"{href} is not on a {sc.RES_M} m grid")
        return np.asarray(sc.snapped_bounds(src.transform.c, src.transform.f, x, y))


def fetch(product_uri: str, x: float, y: float, client=None) -> SclWindow | None:
    """The fullest SCL window of the pass, or None when Earth Search has no L2A match."""
    cands = sc.scl_candidates(product_uri, client)
    if not cands:
        return None
    bounds = scl_bounds(cands[0]["href"], x, y)
    scl, src = sc.fullest_scl(cands, bounds)
    return SclWindow(scl, bounds, src)


def _from_window13(path: Path) -> SclWindow | None:
    """The SCL part of a cached 13-band window, if it has one."""
    with np.load(path) as z:
        if not z["scl"].size:
            return None
        meta = json.loads(str(z["meta"]))
        return SclWindow(z["scl"], z["bounds"], meta["scl_source"])


def run(
    passes: pd.DataFrame,
    cache_roots: list[Path],
    window_roots: list[Path],
    pull_dir: Path,
    *,
    workers: int = 8,
    client=None,
) -> tuple[pd.DataFrame, list[Path]]:
    """Sen2Cor's share for every pass of ``sitecloud.pass_table``.

    SCL windows under ``pull_dir`` or ``cache_roots`` (newest pull first) are not read again,
    nor are 13-band windows under ``window_roots`` whose SCL covers the scored area. New
    windows are written under ``pull_dir``. Earth Search is opened only if a pass needs it.
    Returns one row per pass and the new files.
    """
    lock = threading.Lock()
    opened = [client]

    def catalogue():
        with lock:
            if opened[0] is None:
                from pystac_client import Client

                from methanewatch.sentinel2.search import EARTH_SEARCH

                opened[0] = Client.open(EARTH_SEARCH)
            return opened[0]

    def get(r) -> tuple[SclWindow | None, Path | None, str, str | None]:
        for root in [pull_dir, *sorted(cache_roots, reverse=True)]:
            p = cache_file(root, r.site_id, r.product_uri)
            if p.exists():
                return SclWindow.load(p), p, "cached", None
        for root in sorted(window_roots, reverse=True):
            p = sc.cache_file(root, r.site_id, r.product_uri)
            if p.exists():
                w = _from_window13(p)
                if w is not None and share(w.scl)["scl_nodata_share"] <= sc.MAX_NODATA_SHARE:
                    return w, p, "window", None
        try:
            w = fetch(r.product_uri, r.x, r.y, catalogue())
        except Exception as exc:  # one pass failing must not stop the others; it is listed
            return None, None, ERROR, f"{type(exc).__name__}: {exc}"
        if w is None:
            return None, None, NO_L2A, None
        return w, w.save(cache_file(pull_dir, r.site_id, r.product_uri)), "new", None

    keep = ["overpass_id", "site_id", "day", "acquired_utc", "scene_id", "product_uri"]
    keep += ["platform", "baseline", "valid_frac"]
    rows, new = [], []
    with ThreadPoolExecutor(workers) as pool:
        got = pool.map(get, passes.itertuples())
        for r, (w, path, status, error) in zip(passes.itertuples(), got, strict=True):
            row = {k: getattr(r, k) for k in keep}
            row |= {"clear_scl": np.nan, "scl_nodata_share": np.nan, "scl_collection": None}
            row |= {"scl_item": None, "fetch": status, "error": error, "file": None}
            if w is not None:
                row |= share(w.scl)
                row |= {"scl_collection": w.source.get("collection")}
                row |= {"scl_item": w.source.get("item"), "file": str(path)}
            if status == "new":
                new.append(path)
            rows.append(row)
    return site_shares(pd.DataFrame(rows, columns=[*keep, *_ROW])), new


_ROW = ["clear_scl", "scl_nodata_share", "scl_collection", "scl_item", "fetch", "error", "file"]


def site_shares(df: pd.DataFrame) -> pd.DataFrame:
    """Add ``site_source`` and ``valid_frac_site`` (NaN where there is no Sen2Cor share)."""
    df = df.copy()
    full = df["scl_nodata_share"] <= sc.MAX_NODATA_SHARE
    df["site_source"] = np.select(
        [df["fetch"] == ERROR, df["fetch"] == NO_L2A, ~full],
        [ERROR, NO_L2A, PARTIAL],
        default=SITE,
    )
    df["valid_frac_site"] = df["clear_scl"].where(df["site_source"] == SITE)
    return df


def passes_from_footprints(project) -> pd.DataFrame:
    """Every Sentinel-2 site-day the coverage step will build, with its scene and window centre.

    Built from the footprints and sites, not from ``overpasses.parquet``, because the coverage
    step reads this module's table to build that file.
    """
    import geopandas as gpd

    from methanewatch.coverage.overpasses import from_footprints

    interim = project.resolve(project.paths.interim)
    fp_path = interim / "footprints" / "sentinel2.parquet"
    if not fp_path.exists():
        return pd.DataFrame()
    fp = gpd.read_parquet(fp_path)
    sites = gpd.read_parquet(interim / "sites.parquet")
    ov = from_footprints(
        fp, sites, project.coverage, source="s2-scene", metric_crs=project.crs_metric
    )
    if ov.empty:
        return pd.DataFrame()
    return sc.pass_table(ov, fp, sites)


def pull(project, *, workers: int = 8, client=None) -> dict:
    """Sen2Cor's share for every Sentinel-2 site-day, written to ``data/interim``.

    New SCL windows go to ``data/raw/s2scl/<pull_id>/`` with a manifest; a run that reads
    nothing new writes no pull. The table ``data/interim/s2_site_clear.parquet`` holds every
    pass, with ``valid_frac_site`` where Sen2Cor gives a share and the reason where it does
    not. Passes already cached take about a second in all, so every run covers every pass.
    """
    from methanewatch import provenance

    interim = project.resolve(project.paths.interim)
    raw = project.resolve(project.paths.raw)
    passes = passes_from_footprints(project)
    if passes.empty:
        return {"passes": 0}

    root = raw / SOURCE
    params = {"window_m": sc.WINDOW_M, "score_px": sc.SCORE_PX, "n_passes": len(passes)}
    man = provenance.PullManifest.start(SOURCE, ENDPOINT, params | {"workers": workers})
    pull_dir = root / man.pull_id
    prior = [p for p in root.glob(f"{SOURCE}-*") if p.is_dir()]
    window_roots = [p for p in (raw / "s2windows").glob("s2windows-*") if p.is_dir()]
    df, new = run(passes, prior, window_roots, pull_dir, workers=workers, client=client)
    if new:
        man.finish(pull_dir, new, len(new))
    df.to_parquet(interim / TABLE)
    counts = df["site_source"].value_counts().to_dict()
    pull_id = man.pull_id if new else None
    return {"passes": len(df), "new_windows": len(new), "pull_id": pull_id, **counts}


def refresh_step(project) -> dict:
    """``pull`` for ``mw refresh``. Passes Earth Search could not serve keep the tile figure;
    the step then fails, so the refresh is not reported as complete."""
    counts = pull(project)
    if counts.get(ERROR):
        raise RuntimeError(
            f"{counts[ERROR]} of {counts['passes']} Sentinel-2 passes could not be read from "
            "Earth Search; they keep the tile figure until a later refresh"
        )
    return counts
