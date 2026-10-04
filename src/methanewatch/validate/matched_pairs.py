"""Sentinel-2 vs reference instruments on matched days (docs/PLAN.md section 8.2).

Each usable Sentinel-2 overpass is paired with a usable reference overpass
(Carbon Mapper instruments or EMIT) at the same site within ``max_days``,
preferring the closest in time. Results are binned by the reference rate:

- hit rate: Sentinel-2 detected when the reference saw a plume;
- false-positive rate: Sentinel-2 detected when the reference had a usable
  overpass and saw nothing.

Counts come with Wilson intervals. There is no pass threshold (PLAN, Goal and
success metrics).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from methanewatch.validate.synthetic import wilson

RATE_BINS = [0, 500, 1000, 2000, 5000, np.inf]
RATE_LABELS = ["<500", "500-1000", "1000-2000", "2000-5000", ">5000"]
REFERENCE = ("tanager1", "aircraft", "emit")


def pair(det: pd.DataFrame, max_days: float = 1.0) -> pd.DataFrame:
    """Nearest reference overpass for each Sentinel-2 overpass, within ``max_days``."""
    t = pd.to_datetime(det["acquired_utc"], utc=True)
    d = det.assign(t=t)
    s2 = d[d["instrument"] == "sentinel2"].sort_values("t")
    ref = d[d["instrument"].isin(REFERENCE)].sort_values("t")
    cols = ["site_id", "t", "detected", "q_obs_kg_hr", "instrument", "overpass_id"]
    merged = pd.merge_asof(
        s2[cols],
        ref[cols].rename(columns=lambda c: c if c in ("site_id", "t") else f"ref_{c}"),
        on="t",
        by="site_id",
        direction="nearest",
        tolerance=pd.Timedelta(days=max_days),
    )
    return merged.dropna(subset=["ref_overpass_id"]).reset_index(drop=True)


def summarize(pairs: pd.DataFrame) -> pd.DataFrame:
    """Hit and false-positive rates by reference-rate bin."""
    hits = pairs[pairs["ref_detected"].astype(bool)].copy()
    hits["bin"] = pd.cut(hits["ref_q_obs_kg_hr"], RATE_BINS, labels=RATE_LABELS, right=False)
    rows = []
    for label in RATE_LABELS:
        g = hits[hits["bin"] == label]
        k, n = int(g["detected"].sum()), len(g)
        lo, hi = wilson(k, n)
        rows.append(
            {
                "reference_rate_kg_hr": label,
                "pairs": n,
                "s2_detected": k,
                "hit_rate": k / n if n else np.nan,
                "ci_lo": lo,
                "ci_hi": hi,
            }
        )
    quiet = pairs[~pairs["ref_detected"].astype(bool)]
    k, n = int(quiet["detected"].sum()), len(quiet)
    lo, hi = wilson(k, n)
    rows.append(
        {
            "reference_rate_kg_hr": "no plume (false positives)",
            "pairs": n,
            "s2_detected": k,
            "hit_rate": k / n if n else np.nan,
            "ci_lo": lo,
            "ci_hi": hi,
        }
    )
    return pd.DataFrame(rows)
