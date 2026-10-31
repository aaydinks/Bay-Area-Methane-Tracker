"""Fetch, train and run the one held-out evaluation of the Sentinel-2 cloud model.

``mw s2 cloud fetch`` caches CloudSEN12+ patches (held-out and validation patches with their
baseline masks, a subset of training sites without), ``mw s2 cloud train`` fits the model on
training sites and picks its settings on validation sites, and ``mw s2 cloud evaluate`` runs
the ADR 0013 test once and writes ``reports/validation/s2-cloud-model/``.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from methanewatch import provenance
from methanewatch.config import REPO_ROOT
from methanewatch.sentinel2 import cloudeval as ev
from methanewatch.sentinel2 import cloudsen12 as cs
from methanewatch.sentinel2.cloudmodel import (
    MODEL_DIR,
    CloudModel,
    features,
    fit,
    prior_weights,
    sample_pixels,
    to_classes,
)

ROLES = cs.CACHE / "roles.parquet"
TILES = cs.CACHE / "tile_cloud_cover.parquet"
MODEL_PATH = MODEL_DIR / "cloud-model.pkl"
RESULTS_DIR = REPO_ROOT / "reports" / "validation" / "s2-cloud-model"

# Settings tried on the validation sites (ADR 0013: chosen there, never on held-out sites)
GRID = [
    {"max_leaf_nodes": 31, "learning_rate": 0.1, "max_iter": 300, "l2_regularization": 1.0},
    {"max_leaf_nodes": 63, "learning_rate": 0.1, "max_iter": 300, "l2_regularization": 1.0},
    {"max_leaf_nodes": 127, "learning_rate": 0.1, "max_iter": 300, "l2_regularization": 1.0},
    {"max_leaf_nodes": 63, "learning_rate": 0.05, "max_iter": 600, "l2_regularization": 1.0},
]


def fetch(n_train_sites: int = 600, workers: int = 8, seed: int = 0) -> dict[str, int]:
    l1c = cs.load_index("l1c")
    extra = cs.load_index("extra")
    roles = cs.assign_roles(l1c)
    rng = np.random.default_rng(seed)
    train_sites = sorted(roles.loc[roles["role"] == "train", "roi_id"].unique())
    keep = set(rng.choice(train_sites, min(n_train_sites, len(train_sites)), replace=False))
    roles["fetch"] = roles["role"].isin(["heldout", "validation"]) | roles["roi_id"].isin(keep)
    cs.CACHE.mkdir(parents=True, exist_ok=True)
    roles.to_parquet(ROLES)

    held = roles[roles["role"] == "heldout"]
    if not TILES.exists():
        cs.tile_cloud_cover(held["s2_id"], workers=workers).to_parquet(TILES)
    with_baselines = roles[roles["fetch"] & roles["role"].isin(["heldout", "validation"])]
    train_rows = roles[roles["fetch"] & (roles["role"] == "train")]
    cs.fetch_samples(with_baselines, extra, with_baselines=True, workers=workers)
    cs.fetch_samples(train_rows, None, with_baselines=False, workers=workers)
    return {
        "heldout": int((roles["role"] == "heldout").sum()),
        "validation": int((roles["role"] == "validation").sum()),
        "train_fetched": len(train_rows),
        "dropped": int((roles["role"] == "dropped").sum()),
    }


def _load_roles() -> pd.DataFrame:
    if not ROLES.exists():
        raise FileNotFoundError(f"{ROLES} missing: run `mw s2 cloud fetch` first")
    return pd.read_parquet(ROLES)


def _pixels(
    rows: pd.DataFrame, per_patch: int, seed: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Sampled features and classes, and the count of every valid pixel per class."""
    rng = np.random.default_rng(seed)
    xs, ys = [], []
    counts = np.zeros(3, dtype=np.int64)
    for sid in rows["sample_id"]:
        s = cs.load_sample(cs.cache_path(sid))
        counts += np.bincount(to_classes(s["label"])[s["valid"]], minlength=3)
        x, y = sample_pixels(
            features(s["bands"]), to_classes(s["label"]), s["valid"], per_patch, rng
        )
        xs.append(x)
        ys.append(y)
    return np.concatenate(xs), np.concatenate(ys), counts


def train(per_patch: int = 900, seed: int = 0) -> dict:
    """Fit each setting in ``GRID`` on training sites; keep the best by validation macro-F1."""
    import sklearn
    from sklearn.metrics import f1_score

    roles = _load_roles()
    tr = roles[roles["fetch"] & (roles["role"] == "train")]
    va = roles[roles["role"] == "validation"]
    x, y, true_counts = _pixels(tr, per_patch, seed)
    xv, yv, _ = _pixels(va, per_patch, seed + 1)
    scores, best = [], None
    for settings in GRID:
        model = fit(x, y, settings, seed=seed)
        score = float(f1_score(yv, model.estimator.predict(xv), average="macro"))
        scores.append({**settings, "validation_macro_f1": score})
        if best is None or score > best[0]:
            best = (score, model)
    model = best[1]
    model.class_weights = prior_weights(true_counts, y)
    model.trained_on = {
        "class_shares_true": (true_counts / true_counts.sum()).round(4).tolist(),
        "class_weights": model.class_weights,
        "dataset": f"{cs.REPO}@{cs.REVISION}",
        "train_sites": int(tr["roi_id"].nunique()),
        "train_patches": len(tr),
        "train_pixels": len(y),
        "validation_sites": int(va["roi_id"].nunique()),
        "validation_patches": len(va),
        "grid": scores,
        "sklearn": sklearn.__version__,
        "git_sha": provenance.git_sha(),
    }
    model.save(MODEL_PATH)
    return model.trained_on


def _sites(rows: pd.DataFrame) -> list[ev.SitePatches]:
    """Sites whose patches are read from the cache only when used, one site at a time."""

    def loader(ids: list[str]):
        return lambda: [cs.load_sample(cs.cache_path(sid)) for sid in ids]

    return [
        ev.SitePatches(roi_id=roi, load=loader(sorted(g["sample_id"])))
        for roi, g in rows.groupby("roi_id")
    ]


REHEARSAL_DIR = MODEL_DIR / "rehearsal"


def evaluate(*, rehearsal: bool = False) -> Path:
    """The ADR 0013 test. Runs once: refuses to overwrite an existing result.

    ``rehearsal=True`` runs the same code with the validation sites standing in for the
    held-out sites and writes under ``data/processed/s2cloud/rehearsal/``. It never reads a
    held-out patch, so bugs can be found before the one real run.
    """
    out_dir = REHEARSAL_DIR if rehearsal else RESULTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    if not rehearsal and any(out_dir.glob("*.json")):
        raise FileExistsError(
            f"a held-out result already exists in {out_dir}; ADR 0013 allows one run"
        )
    roles = _load_roles()
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"{MODEL_PATH} missing: run `mw s2 cloud train` first")
    model = CloudModel.load(MODEL_PATH)
    methods = ev.pixel_methods(model)

    # Plume strength is fixed on validation sites before any held-out pair is scored
    amplitude = ev.choose_amplitude(_sites(roles[roles["role"] == "validation"]))

    role = "validation" if rehearsal else "heldout"
    held = roles[roles["role"] == role].merge(pd.read_parquet(TILES), on="s2_id", how="left")
    rows, pixel = [], {m: np.zeros((2, 2), int) for m in methods}
    band_sum = np.zeros((3, len(cs.BANDS)))
    band_n = np.zeros(3)
    for r in held.itertuples():
        s = cs.load_sample(cs.cache_path(r.sample_id))
        cls = to_classes(s["label"])
        for c in range(3):
            pick = s["valid"] & (cls == c)
            band_sum[c] += s["bands"][:, pick].sum(axis=1)
            band_n[c] += pick.sum()
        masks = {m: f(s) for m, f in methods.items()}
        rows.append({"roi_id": r.roi_id, "sample_id": r.sample_id, **ev.window_row(s, masks)})
        truth = ev.labelled_unusable(s)[s["valid"]]
        for m, unusable in masks.items():
            pred = unusable[s["valid"]]
            for i, t in enumerate((False, True)):
                for j, p in enumerate((False, True)):
                    pixel[m][i, j] += int(((truth == t) & (pred == p)).sum())
    windows = pd.DataFrame(rows).merge(
        held[["sample_id", "split", "regional", "tile_cloud_cover", "lat", "lon"]], on="sample_id"
    )

    c1_methods = ["tile_rule", "threshold", "sen2cor", "s2cloudless", "model"]
    official = windows["split"] == ("validation" if rehearsal else "test")
    claim1 = {
        "all_heldout": ev.claim1(windows, c1_methods),
        "west_coast": ev.claim1(windows[windows["regional"]], c1_methods),
        "official_test_with_reference": ev.claim1(windows[official], [*c1_methods, "unetmobv2_v2"]),
    }

    c2_methods = {"none": ev.no_mask, **methods}
    counts = ev.claim2_counts(_sites(held), c2_methods, amplitude["amplitude"])
    test_sites = set(windows.loc[official, "roi_id"])
    names = ["none", "threshold", "sen2cor", "s2cloudless", "model"]
    claim2 = {
        "all_heldout": ev.claim2(counts[counts["method"].isin(names)], names),
        "official_test_with_reference": ev.claim2(
            counts[counts["roi_id"].isin(test_sites)], [*names, "unetmobv2_v2"]
        ),
    }

    bay_area = windows[windows["lat"].between(37.0, 38.6) & windows["lon"].between(-123.0, -121.5)]
    result = {
        "adr": "0013",
        **provenance.run_manifest(provenance.new_id("s2-cloud-model")),
        "dataset": f"{cs.REPO}@{cs.REVISION}",
        "model": {"settings": model.settings, "trained_on": model.trained_on},
        "amplitude": amplitude,
        "claim1": claim1,
        "claim2": claim2,
        "pixel_confusion": {
            m: {"rows_truth_cols_pred_[clear,unusable]": c.tolist()} for m, c in pixel.items()
        },
        "bay_area_patches": bay_area.drop(columns=["lat", "lon"]).to_dict(orient="records"),
        # Mean top-of-atmosphere reflectance per band of labelled pixels (descriptive only)
        "band_means": {
            "bands": cs.BANDS,
            **{
                name: (band_sum[c] / max(band_n[c], 1)).round(4).tolist()
                for c, name in enumerate(["clear", "cloud", "shadow"])
            },
            "pixels": dict(
                zip(["clear", "cloud", "shadow"], band_n.astype(int).tolist(), strict=True)
            ),
        },
        "published": {
            "claim1_passed": claim1["all_heldout"]["passed"],
            "claim2_passed": claim2["all_heldout"]["passed"],
        },
    }
    result["rehearsal"] = rehearsal
    out = out_dir / f"{result['run_id']}.json"
    out.write_text(json.dumps(_finite(result), indent=2, default=_json_default, allow_nan=False))
    windows.to_csv(out.with_suffix(".windows.csv"), index=False)
    counts.to_csv(out.with_suffix(".pairs.csv"), index=False)
    out.with_suffix(".md").write_text(report_markdown(_finite(result)))
    return out


NAMES = {
    "tile_rule": "Tile cloud rule (current valid_frac)",
    "threshold": "Threshold mask (masks.py)",
    "sen2cor": "Sen2Cor scene classification",
    "s2cloudless": "s2cloudless",
    "model": "Cloud model",
    "unetmobv2_v2": "UNetMobV2-V2 (reference)",
    "none": "No cloud mask (reference)",
}


def _pct(x: dict | None) -> str:
    if not x or x.get("value") is None:
        return "n/a"
    lo, hi = x["interval"]
    if lo is None or hi is None:
        return f"{100 * x['value']:.1f}%"
    return f"{100 * x['value']:.1f}% ({100 * lo:.1f} to {100 * hi:.1f})"


def _num(x: dict | None) -> str:
    if not x or x.get("value") is None:
        return "n/a"
    lo, hi = x["interval"]
    return f"{x['value']:.2f} ({lo:.2f} to {hi:.2f})"


def report_markdown(r: dict) -> str:
    """The human-readable report beside the results file (read by ``mw publish``)."""
    c1, c2 = r["claim1"]["all_heldout"], r["claim2"]["all_heldout"]
    verdict = {True: "PASS", False: "FAIL"}
    lines = [
        f"# Sentinel-2 cloud model, held-out test ({r['run_id']})",
        "",
        "Pre-registered in ADR 0013. 90% ranges are site-bootstrap percentile intervals.",
        "Patches are CloudSEN12+ expert-labelled windows of about 5 km; nothing here uses"
        " Bay Area landfill data or Carbon Mapper data.",
        "",
        f"**Claim 1 (usable windows): {verdict[bool(c1.get('passed'))]}**",
        "",
        f"{c1['n_patches']} patches at {c1['n_sites']} sites; {c1['n_truly_unusable']} truly"
        f" unusable. Tile rule scored on {c1['n_tile_rule_scored']} patches.",
        "",
        "| Method | False-usable rate | False-unusable rate |",
        "|---|---|---|",
    ]
    for m, v in c1["rates"].items():
        lines.append(f"| {NAMES[m]} | {_pct(v['false_usable'])} | {_pct(v['false_unusable'])} |")
    lines += ["", "| Model minus | False-usable | False-unusable | Passed |", "|---|---|---|---|"]
    for m, v in c1.get("comparisons", {}).items():
        lines.append(
            f"| {NAMES[m]} | {_pct(v['false_usable_diff'])} | {_pct(v['false_unusable_diff'])}"
            f" | {'yes' if v['passed'] else 'no'} |"
        )
    lines += [
        "",
        f"**Claim 2 (cloud-caused detections): {verdict[bool(c2.get('passed'))]}**",
        "",
        f"{c2['n_targets']} target dates at {c2['n_sites']} sites; {c2['n_plumes']} injected"
        f" plumes at peak absorption {r['amplitude']['amplitude']} (fixed on validation sites).",
        "",
        "| Method | Cloud-caused candidates per target | Injected plumes found |",
        "|---|---|---|",
    ]
    for m, v in c2["rates"].items():
        lines.append(
            f"| {NAMES[m]} | {_num(v['cloud_caused_per_target'])} | {_pct(v['detection_share'])} |"
        )
    lines += ["", "| Model minus | Cloud-caused per target | Plumes found | Passed |"]
    lines += ["|---|---|---|---|"]
    for m, v in c2.get("comparisons", {}).items():
        lines.append(
            f"| {NAMES[m]} | {_num(v['cloud_caused_diff'])} | {_pct(v['detection_share_diff'])}"
            f" | {'yes' if v['passed'] else 'no'} |"
        )
    manifest = {k: r[k] for k in ("run_id", "created_at", "git_sha", "git_dirty", "dataset")}
    lines += ["", "```json", json.dumps(manifest, indent=2), "```", ""]
    return "\n".join(lines)


def _finite(o):
    """NaN and infinities become null so the website can parse the file."""
    if isinstance(o, dict):
        return {k: _finite(v) for k, v in o.items()}
    if isinstance(o, list | tuple):
        return [_finite(v) for v in o]
    if isinstance(o, float | np.floating) and not np.isfinite(o):
        return None
    if isinstance(o, np.generic):
        return o.item()
    return o


def _json_default(o):
    if isinstance(o, np.generic):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    return str(o)
