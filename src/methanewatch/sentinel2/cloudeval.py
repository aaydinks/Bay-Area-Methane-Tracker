"""The pre-registered held-out test of the Sentinel-2 cloud model (ADR 0013).

Every constant here is fixed by ADR 0013 and must not be tuned on held-out data:

- Claim 1 (usable windows): a 5 km patch is usable when at least 70% of its pixels are
  clear; a method calls it usable when its predicted clear share is at least 0.7 (the tile
  rule: tile cloud cover of 30% or less). Primary measure: false-usable rate; paired:
  false-unusable rate.
- Claim 2 (false detections): multi-band multi-pass absorption between the clearest date of
  a site (at least 99% clear) and each other date; candidates from ``detect.py``; a
  candidate is cloud-caused when at least half its pixels are labelled cloud or shadow on
  either date. Three Gaussian plumes are injected per target to check that a mask leaves
  plumes detectable.
- Intervals: 90% percentile bootstrap over sites, 2,000 replicates, seed 20261031.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd
import xarray as xr

from methanewatch.config import load_sentinel2
from methanewatch.sentinel2 import detect, retrieval
from methanewatch.sentinel2.cloudmodel import CLEAR, B, CloudModel

USABLE_CLEAR_SHARE = 0.7
TILE_RULE_MAX_CLOUD = 30.0
REFERENCE_MIN_CLEAR = 0.99
CLOUD_CAUSED_SHARE = 0.5
N_PLUMES = 3
PLUME_LENGTH_M = (600.0, 2000.0)
PLUME_CORE = 0.5
PLUME_HIT_SHARE = 0.3
AMPLITUDES = (0.02, 0.03, 0.05, 0.08, 0.12)
AMPLITUDE_TARGET = 0.8
N_BOOT = 2000
SEED = 20261031
CLAIM1_MAX_FNR_LOSS = 0.05
CLAIM2_MAX_DETECTION_LOSS = 0.02
PX_M = 20.0

CLAIM1_BASELINES = ["tile_rule", "threshold", "sen2cor", "s2cloudless"]
CLAIM2_BASELINES = ["threshold", "sen2cor", "s2cloudless"]


# --- what each method calls unusable (cloud or shadow) -----------------------------------


def labelled_unusable(s: dict) -> np.ndarray:
    return s["label"] != 0


def threshold_unusable(s: dict) -> np.ndarray:
    m = load_sentinel2().masks
    b = s["bands"]
    with np.errstate(divide="ignore", invalid="ignore"):
        ndwi = (b[B["B03"]] - b[B["B08"]]) / (b[B["B03"]] + b[B["B08"]])
    cloud = (b[B["B02"]] > m.max_b02_reflectance) | (b[B["B12"]] > m.max_b12_reflectance)
    shadow = (b[B["B12"]] < m.min_b12_reflectance) & (ndwi <= m.max_ndwi)
    return cloud | shadow


def sen2cor_unusable(s: dict) -> np.ndarray:
    return np.isin(s["sen2cor"], [3, 8, 9, 10])


def s2cloudless_unusable(s: dict) -> np.ndarray:
    return s["s2cloudless"] >= 40


def unet_unusable(s: dict) -> np.ndarray:
    return s["unetmobv2_v2"] != 0


def no_mask(s: dict) -> np.ndarray:
    return np.zeros(s["label"].shape, bool)


def model_unusable(model: CloudModel) -> Callable[[dict], np.ndarray]:
    def f(s: dict) -> np.ndarray:
        return model.predict(s["bands"]) != CLEAR

    return f


def pixel_methods(model: CloudModel | None) -> dict[str, Callable[[dict], np.ndarray]]:
    out = {
        "threshold": threshold_unusable,
        "sen2cor": sen2cor_unusable,
        "s2cloudless": s2cloudless_unusable,
        "unetmobv2_v2": unet_unusable,
    }
    if model is not None:
        out["model"] = model_unusable(model)
    return out


def artifact_valid(s: dict) -> np.ndarray:
    """The non-cloud parts of ``masks.py`` (band 12 range, water), applied to every method."""
    m = load_sentinel2().masks
    b = s["bands"]
    with np.errstate(divide="ignore", invalid="ignore"):
        ndwi = (b[B["B03"]] - b[B["B08"]]) / (b[B["B03"]] + b[B["B08"]])
    ok = (b[B["B12"]] >= m.min_b12_reflectance) & (b[B["B12"]] <= m.max_b12_reflectance)
    ok &= np.isfinite(b[B["B11"]]) & np.isfinite(b[B["B12"]])
    return ok & ~(ndwi > m.max_ndwi) & s["valid"]


# --- bootstrap over sites ----------------------------------------------------------------


def bootstrap(
    per_site: pd.DataFrame, stat: Callable[[pd.DataFrame], dict[str, float]], seed: int = SEED
) -> pd.DataFrame:
    """``stat`` over ``N_BOOT`` resamples of the rows of ``per_site`` (one row per site)."""
    rng = np.random.default_rng(seed)
    n = len(per_site)
    rows = []
    for _ in range(N_BOOT):
        take = per_site.iloc[rng.integers(0, n, n)]
        rows.append(stat(take))
    return pd.DataFrame(rows)


def interval(x: pd.Series) -> list[float]:
    return [float(np.nanpercentile(x, 5)), float(np.nanpercentile(x, 95))]


# --- Claim 1 -------------------------------------------------------------------------------


def window_row(s: dict, masks: dict[str, np.ndarray]) -> dict[str, float]:
    """True clear share and each method's predicted clear share for one patch.

    ``masks`` holds each method's unusable pixels for this patch.
    """
    ok = s["valid"]
    out = {"true_clear": float((~labelled_unusable(s))[ok].mean())}
    for name, unusable in masks.items():
        out[f"clear_{name}"] = float((~unusable)[ok].mean())
    return out


def usable_calls(windows: pd.DataFrame, methods: list[str]) -> pd.DataFrame:
    df = windows.copy()
    for m in methods:
        if m == "tile_rule":
            df["usable_tile_rule"] = df["tile_cloud_cover"] <= TILE_RULE_MAX_CLOUD
        else:
            df[f"usable_{m}"] = df[f"clear_{m}"] >= USABLE_CLEAR_SHARE
    return df


def site_error_counts(windows: pd.DataFrame, methods: list[str]) -> pd.DataFrame:
    """Per site: truly unusable and usable patches, and each method's errors on them.

    The tile rule is scored on patches with a tile figure only, and so is the model when it
    is compared with the tile rule (columns ``model@tile_rule:*``).
    """
    df = usable_calls(windows, methods)
    truth = df["true_clear"] >= USABLE_CLEAR_SHARE
    cols = {}
    for m in methods:
        keep = df["tile_cloud_cover"].notna() if m == "tile_rule" else pd.Series(True, df.index)
        scored = [m] + (["model"] if m != "model" and "model" in methods else [])
        for who in scored:
            tag = m if who == m else f"model@{m}"
            called = df[f"usable_{who}"]
            cols[f"{tag}:bad"] = keep & ~truth
            cols[f"{tag}:good"] = keep & truth
            cols[f"{tag}:fu"] = keep & ~truth & called
            cols[f"{tag}:fnu"] = keep & truth & ~called
    counts = pd.DataFrame(cols).astype(int)
    counts["roi_id"] = df["roi_id"].to_numpy()
    return counts.groupby("roi_id").sum().reset_index()


def _ratio_of_sums(num: float, den: float) -> float:
    return float(num / den) if den else np.nan


def claim1(windows: pd.DataFrame, methods: list[str]) -> dict:
    """Rates per method, differences from the model, 90% site-bootstrap intervals, pass flag.

    ``windows`` has one row per patch: ``roi_id``, ``true_clear``, ``clear_<method>``,
    ``tile_cloud_cover``. Patches with no tile figure are left out of the tile rule only.
    """
    sites = site_error_counts(windows, methods)

    def stat(take: pd.DataFrame) -> dict[str, float]:
        t = take.drop(columns="roi_id").sum()
        out = {}
        for m in methods:
            out[f"{m}:false_usable"] = _ratio_of_sums(t[f"{m}:fu"], t[f"{m}:bad"])
            out[f"{m}:false_unusable"] = _ratio_of_sums(t[f"{m}:fnu"], t[f"{m}:good"])
            if m != "model" and "model" in methods:
                mfu = _ratio_of_sums(t[f"model@{m}:fu"], t[f"model@{m}:bad"])
                mfnu = _ratio_of_sums(t[f"model@{m}:fnu"], t[f"model@{m}:good"])
                out[f"diff_{m}:false_usable"] = mfu - out[f"{m}:false_usable"]
                out[f"diff_{m}:false_unusable"] = mfnu - out[f"{m}:false_unusable"]
        return out

    point = stat(sites)
    boot = bootstrap(sites, stat)
    result = {
        "n_patches": len(windows),
        "n_sites": len(sites),
        "n_truly_unusable": int((windows["true_clear"] < USABLE_CLEAR_SHARE).sum()),
        "n_tile_rule_scored": int(windows["tile_cloud_cover"].notna().sum()),
        "rates": {
            m: {
                k: {"value": point[f"{m}:{k}"], "interval": interval(boot[f"{m}:{k}"])}
                for k in ("false_usable", "false_unusable")
            }
            for m in methods
        },
    }
    if "model" in methods:
        comparisons = {}
        for m in methods:
            if m == "model":
                continue
            fu_iv = interval(boot[f"diff_{m}:false_usable"])
            fnu_iv = interval(boot[f"diff_{m}:false_unusable"])
            comparisons[m] = {
                "false_usable_diff": {"value": point[f"diff_{m}:false_usable"], "interval": fu_iv},
                "false_unusable_diff": {
                    "value": point[f"diff_{m}:false_unusable"],
                    "interval": fnu_iv,
                },
                "passed": bool(fu_iv[1] < 0 and fnu_iv[1] <= CLAIM1_MAX_FNR_LOSS),
            }
        result["comparisons"] = comparisons
        result["passed"] = all(
            comparisons[m]["passed"] for m in CLAIM1_BASELINES if m in comparisons
        )
    return result


# --- Claim 2 -------------------------------------------------------------------------------


def plume_shape(h: int, w: int, x0: float, y0: float, theta: float, length_px: float) -> np.ndarray:
    """Gaussian plume from (x0, y0) blowing towards ``theta``; peak 1, zero beyond its length."""
    yy, xx = np.mgrid[0:h, 0:w].astype(float)
    dx, dy = xx - x0, yy - y0
    s = dx * np.cos(theta) + dy * np.sin(theta)
    n = -dx * np.sin(theta) + dy * np.cos(theta)
    sigma = 1.5 + 0.15 * np.clip(s, 0, None)
    along = np.where(s >= 0, np.exp(-2 * s / length_px), np.exp(-(s**2) / 2))
    shape = along * np.exp(-(n**2) / (2 * sigma**2))
    shape[s > length_px] = 0
    return shape / shape.max()


def place_plumes(clear: np.ndarray, rng: np.random.Generator) -> list[np.ndarray]:
    """``N_PLUMES`` plume shapes with sources on pixels clear on both dates, 40 px apart."""
    h, w = clear.shape
    margin = 8
    cand = np.argwhere(clear[margin:-margin, margin:-margin]) + margin
    shapes, sources = [], []
    for _ in range(200):
        if len(shapes) == N_PLUMES or not len(cand):
            break
        y0, x0 = cand[rng.integers(len(cand))]
        if any(np.hypot(y0 - y, x0 - x) < 40 for y, x in sources):
            continue
        length = rng.uniform(*PLUME_LENGTH_M) / PX_M
        shapes.append(plume_shape(h, w, x0, y0, rng.uniform(0, 2 * np.pi), length))
        sources.append((y0, x0))
    return shapes


def inject(bands: np.ndarray, shapes: list[np.ndarray], a: float) -> np.ndarray:
    """Band 12 times (1 - a * shape); band 11 unchanged (ADR 0013)."""
    out = bands.copy()
    total = np.clip(np.sum(shapes, axis=0), 0, 1) if shapes else 0
    out[B["B12"]] = out[B["B12"]] * (1 - a * total)
    return out


def _ds(bands: np.ndarray) -> xr.Dataset:
    h, w = bands.shape[1:]
    coords = {"y": np.arange(h) * PX_M, "x": np.arange(w) * PX_M}
    return xr.Dataset(
        {"B11": (("y", "x"), bands[B["B11"]]), "B12": (("y", "x"), bands[B["B12"]])}, coords
    )


def absorption(target: np.ndarray, reference: np.ndarray, valid: np.ndarray) -> np.ndarray:
    t, r = _ds(target), _ds(reference)
    v = xr.DataArray(valid, coords=t.coords, dims=("y", "x"))
    return retrieval.fractional_absorption(retrieval.mbmp(t, r, v, v)).values


def pair_counts(
    target: dict,
    reference: dict,
    methods: dict[str, Callable[[dict], np.ndarray]],
    a: float,
    rng: np.random.Generator,
    ref_masks: dict[str, np.ndarray] | None = None,
) -> dict[str, dict[str, int]]:
    """Cloud-caused candidates and injected-plume hits for one target/reference pair."""
    labelled_bad = labelled_unusable(target) | labelled_unusable(reference)
    base_ok = artifact_valid(target) & artifact_valid(reference)
    shapes = place_plumes(~labelled_bad & base_ok, rng)
    injected = dict(target, bands=inject(target["bands"], shapes, a))
    cores = [sh >= PLUME_CORE for sh in shapes]
    ref_masks = ref_masks or {m: f(reference) for m, f in methods.items()}
    out = {}
    for m, f in methods.items():
        res = {"plumes": len(shapes)}
        # False candidates on the target as observed
        ok = base_ok & ~f(target) & ~ref_masks[m]
        comps, _ = detect.candidate_components(
            np.where(ok, absorption(target["bands"], reference["bands"], ok), np.nan)
        )
        res["candidates"] = len(comps)
        res["cloud_caused"] = sum(int(labelled_bad[c].mean() >= CLOUD_CAUSED_SHARE) for c in comps)
        # Plume detection on the same target with plumes added (the mask sees them too)
        ok_i = base_ok & ~f(injected) & ~ref_masks[m]
        vals = absorption(injected["bands"], reference["bands"], ok_i)
        comps_i, _ = detect.candidate_components(np.where(ok_i, vals, np.nan))
        res["hits"] = sum(
            int(any((c & core).sum() >= PLUME_HIT_SHARE * core.sum() for c in comps_i))
            for core in cores
        )
        out[m] = res
    return out


@dataclass
class SitePatches:
    """One site's dates; ``load`` returns their arrays (from ``cloudsen12.load_sample``)."""

    roi_id: str
    load: Callable[[], list[dict]]


def site_pairs(patches: list[dict]) -> tuple[dict, list[dict]] | None:
    """The clearest date as reference (at least 99% clear by label), and the other dates."""
    shares = [float((~labelled_unusable(p))[p["valid"]].mean()) for p in patches]
    i = int(np.argmax(shares))
    if shares[i] < REFERENCE_MIN_CLEAR:
        return None
    return patches[i], [p for j, p in enumerate(patches) if j != i]


def claim2_counts(
    sites: list[SitePatches],
    methods: dict[str, Callable[[dict], np.ndarray]],
    a: float,
    *,
    only_clear_targets: bool = False,
    seed: int = SEED,
) -> pd.DataFrame:
    """One row per (site, method): targets, candidates, cloud-caused, plumes and hits."""
    rng = np.random.default_rng(seed)
    rows = []
    for site in sites:
        pr = site_pairs(site.load())
        if pr is None:
            continue
        ref, targets = pr
        if only_clear_targets:
            targets = [
                t
                for t in targets
                if (~labelled_unusable(t))[t["valid"]].mean() >= REFERENCE_MIN_CLEAR
            ]
        if not targets:
            continue
        ref_masks = {m: f(ref) for m, f in methods.items()}
        acc = {
            m: {"targets": 0, "candidates": 0, "cloud_caused": 0, "plumes": 0, "hits": 0}
            for m in methods
        }
        for t in targets:
            counts = pair_counts(t, ref, methods, a, rng, ref_masks)
            for m, c in counts.items():
                acc[m]["targets"] += 1
                for k, v in c.items():
                    acc[m][k] += v
        for m, c in acc.items():
            rows.append({"roi_id": site.roi_id, "method": m, **c})
    return pd.DataFrame(rows)


def choose_amplitude(validation_sites: list[SitePatches]) -> dict:
    """Smallest amplitude at which 80% of plumes are found with no cloud mask on clear pairs."""
    shares = {}
    for a in AMPLITUDES:
        df = claim2_counts(validation_sites, {"none": no_mask}, a, only_clear_targets=True)
        shares[a] = float(df["hits"].sum() / df["plumes"].sum()) if len(df) else np.nan
        if shares[a] >= AMPLITUDE_TARGET:
            return {"amplitude": a, "detection_share": shares, "reached_target": True}
    return {"amplitude": AMPLITUDES[-1], "detection_share": shares, "reached_target": False}


def claim2(counts: pd.DataFrame, methods: list[str]) -> dict:
    wide = counts.pivot_table(index="roi_id", columns="method", aggfunc="sum")
    sites = pd.DataFrame({"roi_id": wide.index})
    wide = wide.loc[sites["roi_id"]]

    def stat(take: pd.DataFrame) -> dict[str, float]:
        w = wide.loc[take["roi_id"]].sum()
        out = {}
        for m in methods:
            out[f"{m}:cloud_caused_per_target"] = w[("cloud_caused", m)] / w[("targets", m)]
            out[f"{m}:detection_share"] = w[("hits", m)] / w[("plumes", m)]
        if "model" in methods:
            for m in methods:
                if m == "model":
                    continue
                out[f"diff_{m}:cloud_caused_per_target"] = (
                    out["model:cloud_caused_per_target"] - out[f"{m}:cloud_caused_per_target"]
                )
                out[f"diff_{m}:detection_share"] = (
                    out["model:detection_share"] - out[f"{m}:detection_share"]
                )
        return out

    point = stat(sites)
    boot = bootstrap(sites, stat)
    keys = ("cloud_caused_per_target", "detection_share")
    result = {
        "n_sites": len(sites),
        "n_targets": int(wide[("targets", methods[0])].sum()),
        "n_plumes": int(wide[("plumes", methods[0])].sum()),
        "rates": {
            m: {
                k: {"value": point[f"{m}:{k}"], "interval": interval(boot[f"{m}:{k}"])}
                for k in keys
            }
            for m in methods
        },
    }
    if "model" in methods:
        comparisons = {}
        for m in methods:
            if m == "model":
                continue
            cc = interval(boot[f"diff_{m}:cloud_caused_per_target"])
            ds = interval(boot[f"diff_{m}:detection_share"])
            comparisons[m] = {
                "cloud_caused_diff": {
                    "value": point[f"diff_{m}:cloud_caused_per_target"],
                    "interval": cc,
                },
                "detection_share_diff": {
                    "value": point[f"diff_{m}:detection_share"],
                    "interval": ds,
                },
                "passed": bool(cc[1] < 0 and ds[0] >= -CLAIM2_MAX_DETECTION_LOSS),
            }
        result["comparisons"] = comparisons
        result["passed"] = all(
            comparisons[m]["passed"] for m in CLAIM2_BASELINES if m in comparisons
        )
    return result
