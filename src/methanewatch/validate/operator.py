"""Operator comparison (docs/PLAN.md section 8.4; part of Gate 4).

Compares each site's model annual-emissions interval with operator-reported
methane (EPA GHGRP) for the reporting years the fit covers. A gap is a finding
to explain, not proof of error on either side: the model counts only emissions
above the detection floor during observable conditions, and operators'
estimates rest mostly on waste-in-place models.

The gate is a documentation gate. It passes when every gap has a written
explanation in ``data/registry/operator_gap_notes.csv`` (site_id, year,
explanation).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

GAP_NOTES = "operator_gap_notes.csv"
STANDING_CAVEATS = (
    "model counts emissions above the detection floor during daytime clear-sky overpasses",
    "GHGRP subpart HH figures are mostly modelled from waste in place and collection efficiency",
)


def compare(estimates: pd.DataFrame, reports: pd.DataFrame, years: tuple[int, int]) -> pd.DataFrame:
    """One row per (site, reporting year) inside ``years``, with a direction label."""
    rep = reports[(reports["year"] >= years[0]) & (reports["year"] <= years[1])]
    est = estimates[estimates["status"] != "insufficient_data"]
    out = rep.merge(
        est[["site_id", "E_t_yr_med", "E_t_yr_lo", "E_t_yr_hi", "status"]], on="site_id"
    )
    out["direction"] = np.select(
        [out["E_t_yr_lo"] > out["reported_ch4_t"], out["E_t_yr_hi"] < out["reported_ch4_t"]],
        ["model above", "model below"],
        default="consistent",
    )
    out["ratio_med"] = out["E_t_yr_med"] / out["reported_ch4_t"]
    cols = [
        "site_id",
        "year",
        "reported_ch4_t",
        "E_t_yr_med",
        "E_t_yr_lo",
        "E_t_yr_hi",
        "ratio_med",
        "direction",
        "status",
    ]
    return out[cols].sort_values(["site_id", "year"]).reset_index(drop=True)


@dataclass(frozen=True)
class OperatorResult:
    passed: bool
    n_compared: int
    n_gaps: int
    undocumented: list[str] = field(default_factory=list)


def evaluate(table: pd.DataFrame, notes: pd.DataFrame | None) -> OperatorResult:
    gaps = table[table["direction"] != "consistent"]
    documented = set()
    if notes is not None and len(notes):
        filled = notes[notes["explanation"].fillna("").str.strip() != ""]
        documented = {(r.site_id, int(r.year)) for r in filled.itertuples()}
    missing = [
        f"{r.site_id} {r.year}"
        for r in gaps.itertuples()
        if (r.site_id, int(r.year)) not in documented
    ]
    return OperatorResult(
        passed=not missing, n_compared=len(table), n_gaps=len(gaps), undocumented=missing
    )
