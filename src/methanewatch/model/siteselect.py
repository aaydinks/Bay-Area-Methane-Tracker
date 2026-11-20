"""Which sites a fit covers.

The persistence model pools sites: every site in a fit moves the others' estimates a little.
So a fit says which sites it takes, by registry tier (``sites.csv``, ``tier``) or by id, and
its manifest records the choice. With neither given, a fit takes every site with detections,
as long as they are all of one tier. Once the registry holds sites of several tiers, a fit
with no choice stops and asks for one, so sites added later never join a fit unnoticed.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd


@dataclass
class SiteSelection:
    """The detections of the chosen sites, and how they were chosen."""

    detections: pd.DataFrame
    site_ids: list[str]
    tiers: list[str] = field(default_factory=list)  # as asked for
    sites: list[str] = field(default_factory=list)  # as asked for
    not_selected: list[str] = field(default_factory=list)  # sites with detections, left out

    @property
    def explicit(self) -> bool:
        return bool(self.tiers or self.sites)

    def manifest(self) -> dict:
        return {
            "site_selection": {"tiers": self.tiers, "sites": self.sites},
            "sites_not_selected": self.not_selected,
        }


def site_tiers(interim: Path) -> pd.Series | None:
    """Tier by ``site_id`` from ``interim/sites.parquet``; None when it cannot be read."""
    path = interim / "sites.parquet"
    if not path.exists():
        return None
    table = pd.read_parquet(path)
    if "tier" not in table or "site_id" not in table:
        return None
    return table.set_index("site_id")["tier"].fillna("").astype(str)


def _counts(tiers: pd.Series) -> str:
    counts = tiers.replace("", "(no tier)").value_counts().sort_index()
    return ", ".join(f"{name}: {n}" for name, n in counts.items())


def select(
    det: pd.DataFrame,
    tier_of: pd.Series | None,
    *,
    sites: Iterable[str] = (),
    tiers: Iterable[str] = (),
) -> SiteSelection:
    """Keep the detections of the sites named by ``sites`` (ids) or ``tiers``, or both.

    ``tier_of`` is ``site_tiers``' table. Raises ValueError for a tier or site that does not
    exist, for a tier choice when the tiers cannot be read, for a choice that leaves no
    detections, and, with no choice, when the sites with detections are of several tiers.
    """
    want_sites, want_tiers = sorted(set(sites)), sorted(set(tiers))
    with_det = sorted(det["site_id"].unique())
    if not want_sites and not want_tiers:
        if tier_of is not None:
            present = tier_of.reindex(with_det).dropna()
            if len(set(present)) > 1:
                raise ValueError(
                    f"the sites with detections are of several tiers ({_counts(present)}); "
                    "say which to fit with --tier or --site, so that sites added to the "
                    "registry do not join the fit unnoticed"
                )
        return SiteSelection(det, with_det)

    chosen: set[str] = set()
    if want_tiers:
        if tier_of is None:
            raise ValueError(
                "cannot choose sites by tier: data/interim/sites.parquet is missing or has no "
                "tier column; run `mw sites build` first"
            )
        unknown = sorted(set(want_tiers) - set(tier_of))
        if unknown:
            raise ValueError(f"no site of tier {unknown}; the registry has {_counts(tier_of)}")
        chosen |= set(tier_of.index[tier_of.isin(want_tiers)])
    if want_sites:
        known = set(with_det) | (set(tier_of.index) if tier_of is not None else set())
        unknown = sorted(set(want_sites) - known)
        if unknown:
            raise ValueError(f"sites not in the registry or the detections: {unknown}")
        chosen |= set(want_sites)

    kept = det[det["site_id"].isin(chosen)].reset_index(drop=True)
    if kept.empty:
        raise ValueError("the chosen sites have no detections to fit")
    return SiteSelection(
        kept,
        sorted(kept["site_id"].unique()),
        tiers=want_tiers,
        sites=want_sites,
        not_selected=sorted(set(with_det) - chosen),
    )
