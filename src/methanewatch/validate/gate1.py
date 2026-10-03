"""Gate 1: plume and overpass table for the pilot sites (docs/PLAN.md section 5).

Pass when every pilot site has a boundary polygon and, for every instrument
with attributed plumes at that site, at least one usable overpass. A plume with
no overpass behind it means the denominator is missing for that instrument.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import pandas as pd

from methanewatch.provenance import new_id, run_manifest


@dataclass(frozen=True)
class Gate1Result:
    passed: bool
    problems: list[str] = field(default_factory=list)


def counts_by_year(
    plumes: pd.DataFrame, overpasses: pd.DataFrame, pilot_ids: list[str]
) -> pd.DataFrame:
    """Attributed plumes and usable overpasses per (site, instrument, year)."""
    pl = plumes[
        plumes["attribution"].isin(["inside", "buffer"]) & plumes["site_id"].isin(pilot_ids)
    ]
    pl = pl.assign(year=pd.to_datetime(pl["acquired_utc"], utc=True).dt.year)
    ov = overpasses[overpasses["usable"] & overpasses["site_id"].isin(pilot_ids)]
    ov = ov.assign(year=pd.to_datetime(ov["acquired_utc"], utc=True).dt.year)
    keys = ["site_id", "instrument", "year"]
    table = (
        pl.groupby(keys)
        .size()
        .rename("plumes")
        .to_frame()
        .join(ov.groupby(keys).size().rename("usable_overpasses"), how="outer")
        .fillna(0)
        .astype(int)
    )
    return table.reset_index()


def evaluate(table: pd.DataFrame, pilot_ids: list[str], missing_polygons: list[str]) -> Gate1Result:
    problems = [f"no boundary polygon: {s}" for s in missing_polygons if s in pilot_ids]
    per_inst = table.groupby(["site_id", "instrument"])[["plumes", "usable_overpasses"]].sum()
    for (site, inst), row in per_inst.iterrows():
        if row["plumes"] > 0 and row["usable_overpasses"] == 0:
            problems.append(
                f"{site}: {row['plumes']} {inst} plumes but no usable {inst} overpasses"
            )
    for site in pilot_ids:
        if site not in set(table["site_id"]):
            problems.append(f"{site}: no plumes or overpasses at all")
    return Gate1Result(passed=not problems, problems=problems)


def write_report(
    table: pd.DataFrame, result: Gate1Result, out_root: Path, *, unmatched: int = 0
) -> Path:
    run_id = new_id("gate1")
    out = out_root / "gate1"
    out.mkdir(parents=True, exist_ok=True)
    table.to_csv(out / f"{run_id}.csv", index=False)
    wide = table.pivot_table(
        index=["site_id", "year"],
        columns="instrument",
        values=["plumes", "usable_overpasses"],
        fill_value=0,
    )
    wide.columns = [f"{inst} {what.replace('_', ' ')}" for what, inst in wide.columns]
    lines = [
        f"# Gate 1: pilot plume and overpass table ({run_id})",
        "",
        f"**Result: {'PASS' if result.passed else 'FAIL'}**",
        "",
        *[f"- {p}" for p in result.problems],
        "",
        f"Attributed plumes with no matching usable overpass: {unmatched}.",
        "",
        wide.to_markdown(),
        "",
        "## Run manifest",
        "",
        "```json",
        json.dumps(run_manifest(run_id, extra={"gate": asdict(result)}), indent=2, default=str),
        "```",
        "",
    ]
    path = out / f"{run_id}.md"
    path.write_text("\n".join(lines))
    return path
