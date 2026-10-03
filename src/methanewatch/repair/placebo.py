"""Placebo repairs and power (docs/PLAN.md section 7; Gate 5).

Placebo: pseudo-repair dates at control sites where nothing changed. The share
of "drop" or "rise" calls is the test's false-positive rate. The pseudo-treated
site is removed from the control set in each fit. Pseudo-dates at the same few
sites have overlapping windows, so the Wilson interval is optimistic; a block
bootstrap over sites is reported alongside it.

Power: inject a known drop at one site after a date and record how often the
test calls "drop".
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta

import numpy as np
import pandas as pd

from methanewatch.config import RepairWindows
from methanewatch.repair.model import Repair, RepairResult

Verifier = Callable[[pd.DataFrame, Repair, list[str], int], RepairResult]


def pseudo_dates(
    detections: pd.DataFrame, windows: RepairWindows, n: int, rng: np.random.Generator
) -> list[pd.Timestamp]:
    """Dates whose before and after windows both fit inside the data span."""
    w = timedelta(days=round(windows.window_months * 30.4375))
    t0 = detections["acquired_utc"].min() + w
    t1 = detections["acquired_utc"].max() - w - timedelta(days=windows.gap_days)
    if t1 <= t0:
        raise ValueError("data span is shorter than two repair windows")
    span = (t1 - t0).total_seconds()
    return [t0 + timedelta(seconds=float(s)) for s in rng.uniform(0, span, n)]


def run_placebos(
    detections: pd.DataFrame,
    control_sites: list[str],
    n: int,
    verify: Verifier,
    windows: RepairWindows,
    rng: np.random.Generator,
) -> pd.DataFrame:
    dates = pseudo_dates(detections, windows, n, rng)
    rows = []
    for i, date in enumerate(dates):
        site = control_sites[int(rng.integers(len(control_sites)))]
        others = [c for c in control_sites if c != site]
        rep = Repair(site_id=site, date_start=date.to_pydatetime(), repair_id=f"placebo-{i:04d}")
        res = verify(detections, rep, others, int(rng.integers(2**31)))
        rows.append({**res.__dict__, "pseudo_date": date, "controls": ",".join(res.controls)})
    return pd.DataFrame(rows)


def false_positive_rate(placebos: pd.DataFrame) -> dict[str, float]:
    """FPR over usable placebo fits, with Wilson and site-block-bootstrap intervals."""
    from methanewatch.validate.synthetic import wilson

    usable = placebos[placebos["call"] != "insufficient_data"]
    hits = usable["call"].isin(["drop", "rise"])
    k, n = int(hits.sum()), len(usable)
    lo, hi = wilson(k, n)

    rng = np.random.default_rng(0)
    by_site = usable.assign(hit=hits).groupby("site_id")["hit"].agg(["sum", "size"])
    boots = []
    for _ in range(2000):
        pick = by_site.sample(len(by_site), replace=True, random_state=int(rng.integers(2**31)))
        boots.append(pick["sum"].sum() / max(pick["size"].sum(), 1))
    blo, bhi = np.quantile(boots, [0.025, 0.975]) if len(by_site) > 1 else (np.nan, np.nan)
    return {
        "fpr": k / n if n else float("nan"),
        "wilson_lo": lo,
        "wilson_hi": hi,
        "bootstrap_lo": float(blo),
        "bootstrap_hi": float(bhi),
        "n_usable": n,
        "n_insufficient": int(len(placebos) - n),
    }
