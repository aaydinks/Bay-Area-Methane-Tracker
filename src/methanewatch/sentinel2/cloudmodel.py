"""Per-pixel clear / cloud / cloud-shadow classifier for Sentinel-2 L1C (ADR 0012, ADR 0013).

The smallest model that could beat the fixed thresholds in ``masks.py``: gradient-boosted
trees (scikit-learn ``HistGradientBoostingClassifier``) on each 20 m pixel's 13 top-of-
atmosphere reflectances, a few band ratios, and local means, spreads and maxima. The local
terms carry the context a single pixel lacks: thin cloud is smooth, and a cloud shadow is a
dark patch with something bright nearby.

Plumes are not a class. Methane changes only bands 11 and 12, so a mask that is right about
clouds should leave plumes alone; ADR 0013 tests that with injected plumes.

Trained only on CloudSEN12+ (CC0); weights live under ``data/processed/s2cloud/``
(git-ignored).
"""

from __future__ import annotations

import json
import pickle
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from scipy import ndimage

from methanewatch.config import REPO_ROOT

BANDS = ["B01", "B02", "B03", "B04", "B05", "B06", "B07", "B08", "B8A", "B09", "B10"]
BANDS += ["B11", "B12"]
B = {b: i for i, b in enumerate(BANDS)}
CLEAR, CLOUD, SHADOW = 0, 1, 2
CLASS_NAMES = ["clear", "cloud", "shadow"]
MODEL_DIR = REPO_ROOT / "data" / "processed" / "s2cloud"


def to_classes(label: np.ndarray) -> np.ndarray:
    """Expert CloudSEN12 labels (0 clear, 1 thick, 2 thin, 3 shadow) to clear/cloud/shadow."""
    out = np.full(label.shape, CLEAR, dtype=np.uint8)
    out[(label == 1) | (label == 2)] = CLOUD
    out[label == 3] = SHADOW
    return out


def _ratio(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    with np.errstate(divide="ignore", invalid="ignore"):
        return (a - b) / (a + b)


def _local(x: np.ndarray, size: int) -> tuple[np.ndarray, np.ndarray]:
    mean = ndimage.uniform_filter(x, size, mode="nearest")
    sq = ndimage.uniform_filter(x * x, size, mode="nearest")
    return mean, np.sqrt(np.clip(sq - mean * mean, 0, None))


def feature_names() -> list[str]:
    names = list(BANDS)
    names += ["ndvi", "ndwi", "ndsi", "vis_mean", "whiteness", "swir_ratio", "b10_over_b8a"]
    names += ["b09_over_b8a"]
    for band in ["vis_mean", "B08", "B11", "B10"]:
        for size in (3, 9):
            names += [f"{band}_mean{size}", f"{band}_sd{size}"]
    names += ["vis_max25", "vis_max75", "B08_min9", "B08_rel75"]
    return names


def features(bands: np.ndarray) -> np.ndarray:
    """(n_features, H, W) float32 from (13, H, W) reflectance; NaN where bands are missing."""
    r = bands.astype(np.float32)
    vis = r[[B["B02"], B["B03"], B["B04"]]]
    vis_mean = vis.mean(axis=0)
    with np.errstate(divide="ignore", invalid="ignore"):
        whiteness = np.abs(vis - vis_mean).sum(axis=0) / vis_mean
        swir_ratio = r[B["B12"]] / r[B["B11"]]
        b10_rel = r[B["B10"]] / r[B["B8A"]]
        b09_rel = r[B["B09"]] / r[B["B8A"]]
    layers = list(r)
    layers += [
        _ratio(r[B["B08"]], r[B["B04"]]),
        _ratio(r[B["B03"]], r[B["B08"]]),
        _ratio(r[B["B03"]], r[B["B11"]]),
        vis_mean,
        whiteness,
        swir_ratio,
        b10_rel,
        b09_rel,
    ]

    # Local context; missing values are filled with the patch median so filters stay finite
    def filled(x: np.ndarray) -> np.ndarray:
        med = np.nanmedian(x) if np.isfinite(x).any() else 0.0
        return np.where(np.isfinite(x), x, med)

    for x in [vis_mean, r[B["B08"]], r[B["B11"]], r[B["B10"]]]:
        x = filled(x)
        for size in (3, 9):
            layers += list(_local(x, size))
    v = filled(vis_mean)
    nir = filled(r[B["B08"]])
    layers += [
        ndimage.maximum_filter(v, 25, mode="nearest"),
        ndimage.maximum_filter(v, 75, mode="nearest"),
        ndimage.minimum_filter(nir, 9, mode="nearest"),
    ]
    with np.errstate(divide="ignore", invalid="ignore"):
        layers.append(nir / ndimage.uniform_filter(nir, 75, mode="nearest"))
    out = np.stack(layers).astype(np.float32)
    out[~np.isfinite(out)] = np.nan
    return out


def sample_pixels(
    feats: np.ndarray, classes: np.ndarray, valid: np.ndarray, n: int, rng: np.random.Generator
) -> tuple[np.ndarray, np.ndarray]:
    """Up to ``n`` valid pixels from a patch, a third per class where a class is present."""
    idx = []
    flat_cls = classes.ravel()
    flat_ok = valid.ravel()
    per_class = n // 3
    for c in (CLEAR, CLOUD, SHADOW):
        cand = np.flatnonzero(flat_ok & (flat_cls == c))
        if len(cand):
            idx.append(rng.choice(cand, min(per_class, len(cand)), replace=False))
    idx = np.concatenate(idx) if idx else np.array([], dtype=int)
    x = feats.reshape(feats.shape[0], -1)[:, idx].T
    return x, flat_cls[idx]


@dataclass
class CloudModel:
    """Fitted classifier plus what is needed to reproduce it."""

    estimator: object
    settings: dict
    trained_on: dict = field(default_factory=dict)

    def predict_proba(self, bands: np.ndarray) -> np.ndarray:
        """(3, H, W) class probabilities for one (13, H, W) reflectance patch."""
        f = features(bands)
        flat = f.reshape(f.shape[0], -1).T
        p = self.estimator.predict_proba(flat)
        full = np.zeros((flat.shape[0], len(CLASS_NAMES)), dtype=np.float32)
        full[:, self.estimator.classes_.astype(int)] = p  # a class absent in training stays 0
        return full.T.reshape(len(CLASS_NAMES), *bands.shape[1:])

    def predict(self, bands: np.ndarray) -> np.ndarray:
        return self.predict_proba(bands).argmax(axis=0).astype(np.uint8)

    def save(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as f:
            pickle.dump(self, f)
        meta = {"settings": self.settings, "trained_on": self.trained_on}
        path.with_suffix(".json").write_text(json.dumps(meta, indent=2, default=str))
        return path

    @staticmethod
    def load(path: Path) -> CloudModel:
        # Only ever loads a file this project wrote under data/processed/
        with path.open("rb") as f:
            return pickle.load(f)


def fit(x: np.ndarray, y: np.ndarray, settings: dict, seed: int = 0) -> CloudModel:
    from sklearn.ensemble import HistGradientBoostingClassifier

    est = HistGradientBoostingClassifier(
        learning_rate=settings.get("learning_rate", 0.1),
        max_iter=settings.get("max_iter", 300),
        max_leaf_nodes=settings.get("max_leaf_nodes", 63),
        l2_regularization=settings.get("l2_regularization", 1.0),
        early_stopping=False,
        random_state=seed,
    )
    est.fit(x, y)
    return CloudModel(estimator=est, settings=dict(settings))
