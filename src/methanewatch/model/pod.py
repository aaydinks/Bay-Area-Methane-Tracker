"""Instrument detection-probability curves (docs/PLAN.md section 6.2)."""

from __future__ import annotations

import numpy as np
from scipy.stats import norm

from methanewatch.config import PodCurve
from methanewatch.model.grid import LogRateGrid


class UnsetPodCurveError(ValueError):
    pass


def pod(q: np.ndarray | float, q50_kg_hr: float, w: float) -> np.ndarray:
    """POD(q) = Phi((ln q - ln q50) / w)."""
    q = np.asarray(q, dtype=float)
    return norm.cdf((np.log(q) - np.log(q50_kg_hr)) / w)


def pod_matrix(
    grid: LogRateGrid, curves: dict[str, PodCurve], *, allow_unconfirmed: bool = False
) -> tuple[list[str], np.ndarray]:
    """Instruments x grid matrix of detection probabilities, plus the row order."""
    names = sorted(curves)
    rows = []
    for name in names:
        c = curves[name]
        if not c.is_set:
            raise UnsetPodCurveError(f"POD curve for {name!r} has no values in instruments.yaml")
        if not c.confirmed and not allow_unconfirmed:
            raise UnsetPodCurveError(
                f"POD curve for {name!r} is unconfirmed; pass allow_unconfirmed=True "
                "and stamp outputs provisional"
            )
        rows.append(pod(grid.q, c.q50_kg_hr, c.w))
    return names, np.vstack(rows)
