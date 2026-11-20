"""Propose screening-tier sites and outlines from CalRecycle's records (ADR 0018).

Nothing here writes to ``data/registry``. ``propose`` returns rows, outlines and a review
table for a person to check; the reviewed result is committed to the registry by hand.

Which sites: every SWIS site with a "Solid Waste Landfill" activity whose regulatory status
is Permitted, open or closed. Unpermitted and exempt units are left out. A row in the
optional ``screening_overrides.csv`` (``swis_number, include, reason``) overrules that for
one site, in either direction, and its reason is carried into the review table.

Which outline, in order of preference: the site's polygon in CalRecycle's boundary layer,
else a 750 m buffer around its SWIS point, marked provisional. A buffer never overlaps
another site: it gives way to any real outline, and two buffers that would overlap are cut
along the line halfway between their points.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, Polygon
from shapely.geometry.base import BaseGeometry

from methanewatch.report.lint import find_banned
from methanewatch.sites.registry import SCREEN_BUFFER_M

INCLUDED_STATUS = "Permitted"
LAYER_SOURCE = "CalRecycle LandfillBoundaries layer (drawn from permit maps; data as of {as_of})"
BUFFER_SOURCE = "provisional {buffer_m:g} m buffer around CalRecycle SWIS point"
STATUS = {"Active": "active", "Closed": "closed"}  # anything else is left blank for a person
SITE_COLUMNS = (
    "site_id",
    "name",
    "county",
    "region",
    "tier",
    "status",
    "swis_number",
    "polygon_source",
    "notes",
)


@dataclass(frozen=True)
class Proposal:
    sites: pd.DataFrame  # proposed registry rows, tier ``screen``
    outlines: gpd.GeoDataFrame  # site_id, part = boundary, source, geometry (EPSG:4326)
    review: pd.DataFrame  # every landfill considered, with the decision and why
    problems: list[str] = field(default_factory=list)  # things a person must settle


def site_slug(name: str) -> str:
    """A registry id from a site name: lower case, words joined by hyphens."""
    s = name.lower().replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def select(landfills: pd.DataFrame, overrides: pd.DataFrame | None = None) -> pd.DataFrame:
    """Add ``included`` and ``reason`` to the SWIS landfill list."""
    out = landfills.copy()
    permitted = out["regulatory_status"].fillna("") == INCLUDED_STATUS
    out["included"] = permitted
    out["reason"] = [
        "permitted landfill" if ok else f"regulatory status: {status or 'unknown'}"
        for ok, status in zip(permitted, out["regulatory_status"].fillna(""), strict=True)
    ]
    if overrides is not None and len(overrides):
        unknown = set(overrides["swis_number"]) - set(out["swis_number"])
        if unknown:
            raise ValueError(f"overrides name SWIS numbers not in the list: {sorted(unknown)}")
        for row in overrides.itertuples():
            include = str(row.include).strip().lower()
            if include not in {"yes", "no"}:
                raise ValueError(f"override for {row.swis_number}: include must be yes or no")
            hit = out["swis_number"] == row.swis_number
            out.loc[hit, "included"] = include == "yes"
            out.loc[hit, "reason"] = f"override: {row.reason}"
    return out


def _half_plane(own: Point, other: Point, reach: float) -> Polygon:
    """The side of the line halfway between two points that holds ``own``."""
    d = own.distance(other)
    ux, uy = (other.x - own.x) / d, (other.y - own.y) / d
    mx, my = (own.x + other.x) / 2, (own.y + other.y) / 2
    nx, ny = -uy, ux
    a = (mx + nx * reach, my + ny * reach)
    b = (mx - nx * reach, my - ny * reach)
    return Polygon(
        [a, b, (b[0] - ux * reach, b[1] - uy * reach), (a[0] - ux * reach, a[1] - uy * reach)]
    )


def outline_geometries(
    points: gpd.GeoSeries,
    real: dict[str, BaseGeometry],
    fixed: list[BaseGeometry],
    *,
    buffer_m: float = SCREEN_BUFFER_M,
) -> tuple[dict[str, BaseGeometry], list[str]]:
    """Outline per site in a metric CRS. ``points`` is indexed by site id; ``real`` holds the
    sites that have a drawn outline; ``fixed`` are outlines already in the registry."""
    problems: list[str] = []
    out: dict[str, BaseGeometry] = dict(real)
    buffered = [s for s in points.index if s not in real]
    for site in buffered:
        own = points[site]
        geom = own.buffer(buffer_m)
        for other in buffered:
            if other == site:
                continue
            d = own.distance(points[other])
            if d == 0:
                problems.append(
                    f"{site} and {other} share one SWIS point; no outline can separate them"
                )
            elif d < 2 * buffer_m:
                geom = geom.intersection(_half_plane(own, points[other], 10 * buffer_m))
        for other, poly in real.items():
            if poly.contains(own):
                problems.append(f"{site}: its SWIS point lies inside the outline of {other}")
            geom = geom.difference(poly)
        for poly in fixed:
            if poly.contains(own):
                problems.append(
                    f"{site}: its SWIS point lies inside an outline already in the registry"
                )
            geom = geom.difference(poly)
        if geom.is_empty:
            problems.append(f"{site}: nothing is left of its buffer after giving way to neighbours")
            continue
        out[site] = geom
    ids = list(real)
    for i, a in enumerate(ids):
        for b in ids[i + 1 :]:
            if real[a].intersection(real[b]).area > 1.0:  # m^2, the registry's own tolerance
                problems.append(f"drawn outlines overlap: {a} and {b}")
    return out, problems


def propose(
    landfills: pd.DataFrame,
    boundaries: gpd.GeoDataFrame,
    *,
    county_region: dict[str, str],
    existing: gpd.GeoDataFrame,
    existing_swis: dict[str, str],
    boundaries_as_of: str,
    overrides: pd.DataFrame | None = None,
    metric_crs: str = "EPSG:32610",
    buffer_m: float = SCREEN_BUFFER_M,
) -> Proposal:
    """Screening rows and outlines for every selected landfill not already in the registry.

    ``county_region`` maps a county name to its region id; ``existing`` is the built registry
    (``site_id``, geometry); ``existing_swis`` maps a SWIS number to the registry site that
    already covers it, so pilots are not proposed twice.
    """
    review = select(landfills, overrides)
    review["site_id"] = [
        existing_swis.get(s) or site_slug(n)
        for s, n in zip(review["swis_number"], review["name"], strict=True)
    ]
    review["region"] = review["county"].map(county_region)
    review["in_registry"] = review["swis_number"].isin(existing_swis)
    review["wording"] = review["name"].map(lambda n: "; ".join(find_banned(n)))
    has_point = review["latitude"].notna() & review["longitude"].notna()
    problems = [
        f"{r.swis_number} {r.name}: county {r.county} is in no region"
        for r in review[review["included"] & review["region"].isna()].itertuples()
    ]
    problems += [
        f"{r.swis_number} {r.name}: no coordinates in SWIS"
        for r in review[review["included"] & ~has_point].itertuples()
    ]
    problems += [
        f"{r.swis_number} {r.name}: name contains {r.wording}"
        for r in review[review["included"] & (review["wording"] != "")].itertuples()
    ]

    new = review[review["included"] & ~review["in_registry"] & review["region"].notna() & has_point]
    dupes = sorted(
        set(new.loc[new["site_id"].duplicated(keep=False), "site_id"])
        | (set(new["site_id"]) & set(existing["site_id"]))
    )
    if dupes:
        problems.append(f"site ids not unique, rename by hand: {dupes}")
        new = new[~new["site_id"].isin(dupes)]

    points = gpd.GeoSeries(
        gpd.points_from_xy(new["longitude"].astype(float), new["latitude"].astype(float)),
        index=new["site_id"],
        crs="EPSG:4326",
    ).to_crs(metric_crs)
    layer = boundaries.to_crs(metric_crs).set_index("swis_number").geometry
    swis = dict(zip(new["site_id"], new["swis_number"], strict=True))
    real = {site: layer[s] for site, s in swis.items() if s in layer.index}
    fixed = list(existing.to_crs(metric_crs).geometry)
    geoms, more = outline_geometries(points, real, fixed, buffer_m=buffer_m)
    problems += more

    sources = {
        site: (
            LAYER_SOURCE.format(as_of=boundaries_as_of)
            if site in real
            else BUFFER_SOURCE.format(buffer_m=buffer_m)
        )
        for site in geoms
    }
    kept = new[new["site_id"].isin(geoms)]
    sites = pd.DataFrame(
        {
            "site_id": kept["site_id"],
            "name": kept["name"],
            "county": kept["county"],
            "region": kept["region"],
            "tier": "screen",
            "status": kept["landfill_status"].map(STATUS).fillna(""),
            "swis_number": kept["swis_number"],
            "polygon_source": kept["site_id"].map(sources),
            "notes": [
                f"SWIS landfill status: {s}" if s not in STATUS else ""
                for s in kept["landfill_status"]
            ],
        },
        columns=list(SITE_COLUMNS),
    ).sort_values("site_id", ignore_index=True)
    outlines = gpd.GeoDataFrame(
        {"site_id": list(geoms), "part": "boundary", "source": [sources[s] for s in geoms]},
        geometry=list(geoms.values()),
        crs=metric_crs,
    ).to_crs("EPSG:4326")
    outlines = outlines.sort_values("site_id", ignore_index=True)
    review["outline"] = (
        review["site_id"]
        .map(sources)
        .where(~review["in_registry"], "already in the registry")
        .fillna("")
    )
    cols = [
        "swis_number",
        "name",
        "county",
        "region",
        "landfill_status",
        "regulatory_status",
        "included",
        "reason",
        "in_registry",
        "site_id",
        "outline",
        "wording",
    ]
    return Proposal(
        sites,
        outlines,
        review[cols].sort_values(["county", "swis_number"], ignore_index=True),
        problems,
    )
