"""CloudSEN12+ expert cloud labels for the Sentinel-2 cloud model (ADR 0012, ADR 0013).

CloudSEN12+ v1.1 (Aybar et al. 2024, Data in Brief 56:110852; CC0) is stored on Hugging Face
as TACO files: an 18-byte header (2-byte magic, little-endian footer offset and length)
followed by the samples and a parquet footer that indexes them. Each sample is itself a
small container of the same kind holding GeoTIFFs: for the L1C collection the 13 bands and
the expert label, for the ``extra`` collection the baseline cloud masks. A sample is fetched
with one ranged request and read in memory.

Everything is reduced to the 20 m grid of the methane retrieval and cached as one ``.npz``
per patch under ``data/raw/cloudsen12/`` (git-ignored).

Splits follow ADR 0013: held-out sites are the official test split plus every site on the
US West Coast; training uses the other train and validation sites, minus any patch whose
tile also holds a held-out patch.
"""

from __future__ import annotations

import io
import re
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from rasterio.io import MemoryFile
from tenacity import retry, stop_after_attempt, wait_exponential

from methanewatch.config import REPO_ROOT

REPO = "tacofoundation/cloudsen12"
REVISION = "f9490f7de11b4f387f72ef800e73ccbb754711de"  # card says CC0-1.0, checked 2026-10-31
PARTS = {"l1c": 5, "extra": 3}
CACHE = REPO_ROOT / "data" / "raw" / "cloudsen12"

BANDS = ["B01", "B02", "B03", "B04", "B05", "B06", "B07", "B08", "B8A", "B09", "B10"]
BANDS += ["B11", "B12"]
# Expert label classes; cloud = thick or thin
CLEAR, THICK, THIN, SHADOW = 0, 1, 2, 3
BASELINE_MASKS = ["cloudmask_sen2cor", "cloudmask_s2cloudless", "cloudmask_unetmobv2_v2"]

# ADR 0013: held-out region, and the class order used when 2 x 2 label votes tie
WEST_COAST = {"lat": (32.0, 49.0), "lon": (-125.0, -114.0)}
TIE_ORDER = [THICK, THIN, SHADOW, CLEAR]  # ties go to the less clear class


def part_url(collection: str, part: int) -> str:
    return (
        f"https://huggingface.co/datasets/{REPO}/resolve/{REVISION}/"
        f"cloudsen12-{collection}.{part:04d}.part.taco"
    )


@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=2, max=60))
def _range(url: str, start: int, length: int) -> bytes:
    r = httpx.get(
        url,
        headers={"Range": f"bytes={start}-{start + length - 1}"},
        follow_redirects=True,
        timeout=180,
    )
    r.raise_for_status()
    if len(r.content) != length:
        raise OSError(f"short read from {url}: {len(r.content)} of {length} bytes")
    return r.content


def parse_header(head: bytes) -> tuple[int, int]:
    """Footer offset and length from a TACO or tortilla header."""
    if head[:2] not in {b"#y", b"WX"}:
        raise ValueError("not a TACO or tortilla container")
    return int.from_bytes(head[2:10], "little"), int.from_bytes(head[10:18], "little")


def read_footer(blob: bytes) -> pd.DataFrame:
    """Index table of an in-memory container; offsets are relative to ``blob``."""
    off, length = parse_header(blob[:18])
    return pq.read_table(io.BytesIO(blob[off : off + length])).to_pandas()


def load_part_index(collection: str, part: int) -> pd.DataFrame:
    url = part_url(collection, part)
    off, length = parse_header(_range(url, 0, 18))
    df = pq.read_table(io.BytesIO(_range(url, off, length))).to_pandas()
    return df.assign(collection=collection, part=part)


def load_index(collection: str = "l1c") -> pd.DataFrame:
    """Sample index of one collection: id, split, offsets, site, label shares, product name."""
    df = pd.concat([load_part_index(collection, p) for p in range(PARTS[collection])])
    keep = [
        "tortilla:id",
        "tortilla:data_split",
        "tortilla:offset",
        "tortilla:length",
        "stac:centroid",
        "stac:time_start",
        "roi_id",
        "label_type",
        "s2_id",
        "real_proj_shape",
        "clear_percentage",
        "thick_percentage",
        "thin_percentage",
        "cloud_shadow_percentage",
        "collection",
        "part",
    ]
    df = df[[c for c in keep if c in df.columns]].rename(
        columns={
            "tortilla:id": "sample_id",
            "tortilla:data_split": "split",
            "tortilla:offset": "offset",
            "tortilla:length": "length",
        }
    )
    xy = df["stac:centroid"].str.extract(r"POINT \(([-\d.]+) ([-\d.]+)\)").astype(float)
    df["lon"], df["lat"] = xy[0], xy[1]
    df["tile"] = df["s2_id"].str.extract(r"_T(\d{2}[A-Z]{3})_", expand=False)
    return df.drop(columns=["stac:centroid"]).reset_index(drop=True)


def assign_roles(index: pd.DataFrame) -> pd.DataFrame:
    """ADR 0013 roles for expert-labelled 509 px patches: heldout, validation, train or dropped.

    ``regional`` marks held-out West Coast sites, reported as a subset.
    """
    df = index[(index["label_type"] == "high") & (index["real_proj_shape"] == 509)].copy()
    lat, lon = WEST_COAST["lat"], WEST_COAST["lon"]
    west = df["lat"].between(*lat) & df["lon"].between(*lon)
    west_sites = set(df.loc[west, "roi_id"])
    test_sites = set(df.loc[df["split"] == "test", "roi_id"])
    held_sites = west_sites | test_sites
    df["regional"] = df["roi_id"].isin(west_sites)
    df["role"] = np.where(df["roi_id"].isin(held_sites), "heldout", df["split"])
    held_tiles = set(df.loc[df["role"] == "heldout", "tile"])
    leak = (df["role"] != "heldout") & df["tile"].isin(held_tiles)
    df.loc[leak, "role"] = "dropped"
    return df


# --- reading one sample --------------------------------------------------------------------


def _read_tif(blob: bytes) -> tuple[np.ndarray, dict]:
    with MemoryFile(blob) as mem, mem.open() as src:
        return src.read(), {"crs": str(src.crs), "transform": tuple(src.transform)[:6]}


def sample_files(collection: str, part: int, offset: int, length: int) -> dict[str, bytes]:
    """The GeoTIFFs inside one sample, keyed by their id (e.g. ``s2l1c``, ``target``)."""
    blob = _range(part_url(collection, part), offset, length)
    inner = read_footer(blob)
    return {
        r["tortilla:id"]: blob[r["tortilla:offset"] : r["tortilla:offset"] + r["tortilla:length"]]
        for _, r in inner.iterrows()
    }


def to_20m_mean(a: np.ndarray) -> np.ndarray:
    """2 x 2 block mean of a (..., 512, 512) array at 10 m."""
    *lead, h, w = a.shape
    return a.reshape(*lead, h // 2, 2, w // 2, 2).mean(axis=(-3, -1))


def to_20m_labels(
    lab: np.ndarray, classes: Iterable[int] = (CLEAR, THICK, THIN, SHADOW)
) -> np.ndarray:
    """2 x 2 majority vote; ties go to the class earliest in ``TIE_ORDER``."""
    h, w = lab.shape
    blocks = lab.reshape(h // 2, 2, w // 2, 2).transpose(0, 2, 1, 3).reshape(h // 2, w // 2, 4)
    classes = list(classes)
    counts = np.stack([(blocks == c).sum(axis=-1) for c in classes], axis=-1)
    rank = np.array([TIE_ORDER.index(c) if c in TIE_ORDER else len(TIE_ORDER) for c in classes])
    # Highest count wins; among equal counts, the lowest TIE_ORDER rank wins
    score = counts * 10 - rank[None, None, :]
    return np.asarray(classes, dtype=lab.dtype)[score.argmax(axis=-1)]


def l1c_arrays(files: dict[str, bytes]) -> dict[str, np.ndarray]:
    """20 m bands (13, digital numbers), expert label (uint8) and a padding mask."""
    img_key = next(k for k in files if "l1c" in k.lower())
    lab_key = next(k for k in files if k != img_key)
    img, meta = _read_tif(files[img_key])
    lab, _ = _read_tif(files[lab_key])
    pad = (img == 0).all(axis=0)
    # Kept as digital numbers (reflectance x 10000) to halve the cache; see ``load_sample``
    dn = np.rint(to_20m_mean(img.astype(np.float32)))
    valid = ~(to_20m_mean(pad.astype(np.float32)) > 0)
    return {
        "bands": dn.astype(np.uint16),
        "label": to_20m_labels(lab[0]),
        "valid": valid,
        "transform": np.asarray(meta["transform"]),
    }


def extra_arrays(files: dict[str, bytes]) -> dict[str, np.ndarray]:
    """Baseline masks at 20 m: Sen2Cor scene classes and UNet classes by majority vote,
    s2cloudless probability (0-100) by mean."""
    out = {}
    sen2cor, _ = _read_tif(files["cloudmask_sen2cor"])
    scl_classes = range(12)
    out["sen2cor"] = to_20m_labels(sen2cor[0].astype(np.uint8), scl_classes)
    prob, _ = _read_tif(files["cloudmask_s2cloudless"])
    out["s2cloudless"] = to_20m_mean(prob[0].astype(np.float32))
    unet, _ = _read_tif(files["cloudmask_unetmobv2_v2"])
    out["unetmobv2_v2"] = to_20m_labels(unet[0].astype(np.uint8))
    return out


def cache_path(sample_id: str, root: Path = CACHE) -> Path:
    return root / "samples" / f"{re.sub(r'[^A-Za-z0-9_.-]', '_', sample_id)}.npz"


def fetch_sample(row: pd.Series, extra_row: pd.Series | None, root: Path = CACHE) -> Path:
    """Download one patch (and its baseline masks) and cache it at 20 m."""
    out = cache_path(row["sample_id"], root)
    if out.exists():
        return out
    arrays = l1c_arrays(sample_files("l1c", row["part"], row["offset"], row["length"]))
    if extra_row is not None:
        files = sample_files("extra", extra_row["part"], extra_row["offset"], extra_row["length"])
        arrays.update(extra_arrays(files))
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp.npz")
    np.savez_compressed(tmp, **arrays)
    tmp.rename(out)
    return out


def fetch_samples(
    rows: pd.DataFrame,
    extra_index: pd.DataFrame | None,
    *,
    with_baselines: bool,
    root: Path = CACHE,
    workers: int = 8,
) -> list[Path]:
    extra_by_id = extra_index.set_index("sample_id") if extra_index is not None else None

    def one(row: pd.Series) -> Path:
        extra_row = None
        if with_baselines and extra_by_id is not None:
            extra_row = extra_by_id.loc[row["sample_id"]]
        return fetch_sample(row, extra_row, root)

    with ThreadPoolExecutor(workers) as pool:
        return list(pool.map(one, (r for _, r in rows.iterrows())))


def load_sample(path: Path) -> dict[str, np.ndarray]:
    """A cached patch, with ``bands`` as float32 top-of-atmosphere reflectance."""
    with np.load(path) as z:
        out = {k: z[k] for k in z.files}
    out["bands"] = out["bands"].astype(np.float32) / 10000.0
    return out


# --- tile cloud cover for the tile rule (the current valid_frac) ----------------------------


def tile_cloud_cover(product_ids: Iterable[str], workers: int = 8) -> pd.DataFrame:
    """``eo:cloud_cover`` of each L1C product from Earth Search, the pipeline's own source.

    Matched by product name; when the archive holds a reprocessed copy under another name,
    the same platform, tile and sensing time is used instead. Unmatched products get NaN.
    """
    from pystac_client import Client

    from methanewatch.sentinel2.search import COLLECTION, EARTH_SEARCH

    client = Client.open(EARTH_SEARCH)

    def one(pid: str) -> dict:
        items = list(
            client.search(
                collections=[COLLECTION],
                query={"s2:product_uri": {"eq": f"{pid}.SAFE"}},
                max_items=2,
            ).items()
        )
        how = "name"
        if not items:
            m = re.match(r"(S2[ABC])_MSIL1C_(\d{8})T(\d{6})_N\d{4}_R\d{3}_T(\w{5})_", pid)
            if m:
                platform, day, hms, tile = m.groups()
                stamp = f"{day[:4]}-{day[4:6]}-{day[6:]}"
                items = [
                    it
                    for it in client.search(
                        collections=[COLLECTION],
                        datetime=f"{stamp}/{stamp}",
                        query={"grid:code": {"eq": f"MGRS-{tile}"}},
                        max_items=10,
                    ).items()
                    if f"{day}T{hms}" in (it.properties.get("s2:product_uri") or "")
                    and (it.properties.get("platform") or "").lower().endswith(platform[-1].lower())
                ]
                how = "tile_and_time"
        if not items:
            return {"s2_id": pid, "tile_cloud_cover": np.nan, "matched_by": "none"}
        return {
            "s2_id": pid,
            "tile_cloud_cover": float(items[0].properties.get("eo:cloud_cover", np.nan)),
            "matched_by": how,
        }

    with ThreadPoolExecutor(workers) as pool:
        return pd.DataFrame(list(pool.map(one, sorted(set(product_ids)))))
