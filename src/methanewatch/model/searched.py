"""Which instruments' passes a real fit may take (decision record 0016).

A usable pass with no attributed plume enters the persistence model as a non-detection:
"looked and saw nothing". That holds only if a plume search ran on the pass. So an
instrument enters a real fit only when ``data/interim/plumes/<source>.parquet`` exists for
at least one of its ``plume_sources`` (config/instruments.yaml).

A search step writes its plume table even when it finds nothing, as the Carbon Mapper
ingest does: an empty table means the search ran and found no plume, a missing one means
no search has run. Sentinel-2's own search (source ``s2-local``) has not run yet, so its
passes stay out of a default fit.

The rule is per instrument, not per pass: a search that covered only some of an
instrument's passes still lets every pass in. The plume tables are read when the fit runs,
so ``mw coverage build`` must have run after the newest one (``mw refresh`` runs the steps
in that order).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from methanewatch.config import InstrumentsConfig

NOT_SEARCHED = "plume search not run"


@dataclass(frozen=True)
class Selection:
    """The detections a fit may use, and what was left out and why."""

    detections: pd.DataFrame
    used: list[str]
    left_out: dict[str, dict] = field(default_factory=dict)
    included_unsearched: list[str] = field(default_factory=list)
    sites_left_out: list[str] = field(default_factory=list)
    plume_tables: dict[str, int] = field(default_factory=dict)

    def manifest(self) -> dict:
        return {
            "instruments_left_out": self.left_out,
            "included_unsearched": self.included_unsearched,
            "sites_left_out": self.sites_left_out,
            "plume_tables": self.plume_tables,
        }


def plume_tables(interim: Path) -> dict[str, int]:
    """Rows in each plume table under ``interim/plumes``, by source (the file name)."""
    folder = interim / "plumes"
    if not folder.exists():
        return {}
    return {p.stem: len(pd.read_parquet(p)) for p in sorted(folder.glob("*.parquet"))}


def select(
    det: pd.DataFrame,
    instruments: InstrumentsConfig,
    tables: dict[str, int],
    *,
    include_unsearched: Iterable[str] = (),
) -> Selection:
    """Keep the rows of instruments whose plume search has run.

    ``include_unsearched`` names instruments to keep anyway; the selection records them.
    """
    include = set(include_unsearched)
    unknown = sorted((include | set(det["instrument"])) - set(instruments.instruments))
    if unknown:
        raise ValueError(f"instruments not in config/instruments.yaml: {unknown}")

    used, left_out, forced = [], {}, []
    for name in sorted(det["instrument"].unique()):
        sources = list(instruments.instruments[name].plume_sources)
        if any(s in tables for s in sources):
            used.append(name)
        elif name in include:
            used.append(name)
            forced.append(name)
        else:
            rows = det[det["instrument"] == name]
            left_out[name] = {
                "reason": NOT_SEARCHED,
                "plume_sources": sources,
                "n_passes": len(rows),
                "n_detections": int(rows["detected"].sum()),
                "detail": (
                    f"no plume table from {' or '.join(sources) or 'any source'} under "
                    "data/interim/plumes, so its usable passes would count as searched "
                    "passes with no plume"
                ),
            }

    kept = det[det["instrument"].isin(used)].reset_index(drop=True)
    sites_left_out = sorted(set(det["site_id"]) - set(kept["site_id"]))
    return Selection(kept, used, left_out, forced, sites_left_out, dict(tables))
