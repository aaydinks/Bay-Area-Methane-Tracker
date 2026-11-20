"""Build and QA the site registry (docs/PLAN.md section 5, phase 1).

Inputs in ``data/registry/``:
- ``sites.csv``: one row per landfill (attributes, tier, neighbors). ``region`` must be the
  region its county belongs to, ``swis_number`` is CalRecycle's site number, and
  ``air_district`` is filled in only once a person has checked it (ADR 0018).
- ``sites.geojson``: polygons keyed by ``site_id`` with a ``part`` property:
  ``boundary`` (required to use a site), ``working_face`` or ``closed``
  (pilot sites). Neighbor sources use ``part = neighbor`` and a ``name``.

Output: ``data/interim/sites.parquet`` (GeoParquet, EPSG:4326) and
``neighbors.parquet``. Each site carries ``air_district``: the checked value from
``sites.csv`` when there is one (``air_district_confirmed`` is then true), otherwise the
district whose CARB outline holds most of the site, which stays unconfirmed.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING

import geopandas as gpd
import pandas as pd
from shapely.geometry import box

if TYPE_CHECKING:
    from methanewatch.config import ProjectConfig

# Margin in degrees around the project's regions. The box is a coarse check for swapped
# coordinates or a wrong CRS; it is not a county-boundary test.
REGION_PAD_DEG = 0.05
# East edge of UTM zone 10N (see config.UTM10_EAST_LON); only enforced for EPSG:32610
UTM10_EAST_LON = -120.0
PARTS = {"boundary", "working_face", "closed", "neighbor"}
SCREEN_BUFFER_M = 750
# CalRecycle's SWIS number: county number, enforcement agency, serial (43-AN-0003)
SWIS_NUMBER = re.compile(r"\d{2}-[A-Z]{2}-\d{4}")
# Columns every built registry has, blank when sites.csv does not hold them
ID_COLUMNS = ("region", "swis_number", "air_district", "district_facility_id")
# A site this close to a district's edge needs its district checked by hand first
DISTRICT_EDGE_M = 500.0
# CARB's district outlines, under the datasets folder (`mw datasets build --only air-districts`)
DISTRICTS_FILE = Path("boundaries") / "air_districts.geojson"


def read_polygons(path: Path) -> gpd.GeoDataFrame:
    if not path.exists():
        return gpd.GeoDataFrame({"site_id": [], "part": []}, geometry=[], crs="EPSG:4326")
    gdf = gpd.read_file(path)
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    return gdf.to_crs("EPSG:4326")


def build_project_registry(project: ProjectConfig) -> gpd.GeoDataFrame:
    """Build the registry the way every command does: the project's regions, its counties'
    regions, and the committed air district outlines."""
    return build_registry(
        project.resolve(project.paths.registry),
        project.resolve(project.paths.interim),
        region_bbox=project.bbox,
        metric_crs=project.crs_metric,
        county_region=project.county_region,
        districts=read_districts(project.resolve(project.paths.datasets) / DISTRICTS_FILE),
    )


def build_registry(
    registry_dir: Path,
    out_dir: Path,
    *,
    region_bbox: tuple[float, float, float, float],
    metric_crs: str = "EPSG:32610",
    county_region: Mapping[str, str] | None = None,
    districts: gpd.GeoDataFrame | None = None,
) -> gpd.GeoDataFrame:
    """``region_bbox`` is the box covering the project's regions (``ProjectConfig.bbox``).

    ``county_region`` maps a county name to its region id; with it, every site gets its
    region from its county, and a different value in ``sites.csv`` is an error.
    ``districts`` are CARB's air district outlines (``read_districts``); with them, a site
    whose ``air_district`` is blank gets the district that holds most of its outline.
    """
    attrs = pd.read_csv(registry_dir / "sites.csv", dtype=str).fillna("")
    for col in ID_COLUMNS:
        if col not in attrs:
            attrs[col] = ""
    polys = read_polygons(registry_dir / "sites.geojson")

    problems = qa_inputs(attrs, polys, region_bbox)
    problems += qa_ids(attrs, county_region, districts)
    if metric_crs == "EPSG:32610":
        east = polys[polys.geometry.bounds["maxx"] > UTM10_EAST_LON]
        if len(east):
            problems.append(
                f"geometries east of 120°W, outside UTM zone 10N: {east['site_id'].tolist()}"
            )
    if problems:
        raise ValueError("registry QA failed:\n  " + "\n  ".join(problems))

    parts = {}
    for part in ("boundary", "working_face", "closed"):
        sel = polys[polys["part"] == part].dissolve(by="site_id")
        parts[part] = sel.geometry
    sites = gpd.GeoDataFrame(
        attrs.set_index("site_id")
        .assign(
            working_face_geom=parts["working_face"].to_wkt(),
            closed_geom=parts["closed"].to_wkt(),
        )
        .join(parts["boundary"].rename("geometry"), how="inner"),
        geometry="geometry",
        crs="EPSG:4326",
    ).reset_index()

    overlaps = qa_overlaps(sites, metric_crs)
    if overlaps:
        raise ValueError("registry QA failed:\n  " + "\n  ".join(overlaps))

    if county_region is not None:
        sites["region"] = sites["county"].map(county_region)
    sites["air_district_confirmed"] = sites["air_district"] != ""
    sites["air_district_edge_m"] = float("nan")
    if districts is not None and len(sites):
        found = district_overlay(sites, districts, metric_crs)
        open_ = ~sites["air_district_confirmed"]
        sites.loc[open_, "air_district"] = sites.loc[open_, "site_id"].map(found["name"]).fillna("")
        sites["air_district_edge_m"] = sites["site_id"].map(found["edge_m"]).astype(float)

    out_dir.mkdir(parents=True, exist_ok=True)
    sites.to_parquet(out_dir / "sites.parquet")
    neighbors = polys[polys["part"] == "neighbor"]
    neighbors.to_parquet(out_dir / "neighbors.parquet")
    return sites


def qa_inputs(
    attrs: pd.DataFrame, polys: gpd.GeoDataFrame, region_bbox: tuple[float, float, float, float]
) -> list[str]:
    problems = []
    dupes = attrs.loc[attrs["site_id"].duplicated(), "site_id"].tolist()
    if dupes:
        problems.append(f"duplicate site_id in sites.csv: {dupes}")
    bad_parts = set(polys["part"]) - PARTS
    if bad_parts:
        problems.append(f"unknown part values: {sorted(bad_parts)}")
    site_polys = polys[polys["part"] != "neighbor"]
    unknown = set(site_polys["site_id"]) - set(attrs["site_id"])
    if unknown:
        problems.append(f"polygons for sites not in sites.csv: {sorted(unknown)}")
    invalid = polys[~polys.geometry.is_valid]
    if len(invalid):
        problems.append(f"invalid geometries: {invalid['site_id'].tolist()}")
    west, south, east, north = region_bbox
    pad = REGION_PAD_DEG
    outside = polys[~polys.geometry.within(box(west - pad, south - pad, east + pad, north + pad))]
    if len(outside):
        problems.append(f"geometries outside the project's regions: {outside['site_id'].tolist()}")
    return problems


def qa_ids(
    attrs: pd.DataFrame,
    county_region: Mapping[str, str] | None,
    districts: gpd.GeoDataFrame | None,
) -> list[str]:
    """Checks on the identifying columns of ``sites.csv``: region, SWIS number, air district."""
    problems = []
    if "baaqmd_facility_id" in attrs:
        problems.append("sites.csv: rename column baaqmd_facility_id to district_facility_id")
    if county_region is not None:
        county = attrs["county"] if "county" in attrs else pd.Series("", index=attrs.index)
        for site, c, given in zip(attrs["site_id"], county, attrs["region"], strict=True):
            region = county_region.get(c)
            if region is None:
                problems.append(f"{site}: county {c or '(blank)'} is in no region")
            elif given and given != region:
                problems.append(f"{site}: region {given} but {c} County is in {region}")
    swis = attrs.loc[attrs["swis_number"] != "", ["site_id", "swis_number"]]
    for site, s in zip(swis["site_id"], swis["swis_number"], strict=True):
        if not SWIS_NUMBER.fullmatch(s):
            problems.append(f"{site}: swis_number {s} is not of the form 43-AN-0003")
    shared = sorted(set(swis.loc[swis["swis_number"].duplicated(), "swis_number"]))
    if shared:
        problems.append(f"swis_number used by more than one site: {shared}")
    if districts is not None:
        known = set(districts["NAME"])
        named = attrs[attrs["air_district"] != ""]
        for site, d in zip(named["site_id"], named["air_district"], strict=True):
            if d not in known:
                problems.append(
                    f"{site}: air_district {d} is not a CARB district name ({sorted(known)})"
                )
    return problems


def read_districts(path: Path) -> gpd.GeoDataFrame | None:
    """CARB's air district outlines (``NAME``, ``DIS``, outline) from the committed dataset
    file, or ``None`` when the file is not there."""
    if not path.exists():
        return None
    return gpd.read_file(path)[["NAME", "DIS", "geometry"]]


def district_overlay(
    sites: gpd.GeoDataFrame, districts: gpd.GeoDataFrame, metric_crs: str
) -> pd.DataFrame:
    """For each site: ``name``, the district holding the largest share of its outline (absent
    when no district meets it), and ``edge_m``, how far the outline is from the nearest
    district edge (0 when an edge crosses it)."""
    s = sites[["site_id", "geometry"]].to_crs(metric_crs)
    d = districts[["NAME", "geometry"]].to_crs(metric_crs)
    parts = gpd.overlay(s, d, how="intersection", keep_geom_type=True)
    parts["area"] = parts.geometry.area
    best = parts.sort_values("area", ascending=False).drop_duplicates("site_id")
    edges = d.geometry.boundary.union_all()
    return pd.DataFrame(
        {
            "name": s["site_id"].map(best.set_index("site_id")["NAME"]).to_numpy(),
            "edge_m": s.geometry.distance(edges).to_numpy(),
        },
        index=s["site_id"].to_numpy(),
    )


def district_notes(sites: pd.DataFrame, *, edge_m: float = DISTRICT_EDGE_M) -> list[str]:
    """What a person should check about the air districts of a built registry."""
    notes = []
    open_ = sites[~sites["air_district_confirmed"]]
    none = sorted(open_.loc[open_["air_district"] == "", "site_id"])
    if none:
        notes.append(f"no air district found for: {', '.join(none)}")
    near = open_[open_["air_district_edge_m"] < edge_m]
    for site, d, m in zip(
        near["site_id"], near["air_district"], near["air_district_edge_m"], strict=True
    ):
        where = f"read as {d}" if d else "outside every outline"
        notes.append(f"{site}: {m:.0f} m from an air district edge ({where}); check it first")
    n = int((open_["air_district"] != "").sum())
    if n:
        notes.append(f"air district of {n} site(s) is read from CARB's 2004 outlines, unconfirmed")
    return notes


def qa_overlaps(sites: gpd.GeoDataFrame, metric_crs: str) -> list[str]:
    m = sites[["site_id", "geometry"]].to_crs(metric_crs)
    pairs = gpd.sjoin(m, m, predicate="intersects")
    pairs = pairs[pairs["site_id_left"] < pairs["site_id_right"]]
    problems = []
    for a, b in zip(pairs["site_id_left"], pairs["site_id_right"], strict=True):
        ga = m.set_index("site_id").geometry[a]
        gb = m.set_index("site_id").geometry[b]
        if ga.intersection(gb).area > 1.0:  # m^2; touching edges are fine
            problems.append(f"boundaries overlap: {a} and {b}")
    return problems


def missing_polygons(registry_dir: Path) -> list[str]:
    """Sites in sites.csv with no boundary polygon yet."""
    attrs = pd.read_csv(registry_dir / "sites.csv", dtype=str)
    polys = read_polygons(registry_dir / "sites.geojson")
    have = set(polys.loc[polys["part"] == "boundary", "site_id"])
    return sorted(set(attrs["site_id"]) - have)


def screening_polygons(
    points: gpd.GeoDataFrame, *, metric_crs: str = "EPSG:32610", buffer_m: float = SCREEN_BUFFER_M
) -> gpd.GeoDataFrame:
    """Fallback boundary for screening-tier sites: a buffer around the site point.

    OpenStreetMap ``landuse=landfill`` polygons replace these where they exist.
    """
    out = points.to_crs(metric_crs)
    out = out.assign(geometry=out.geometry.buffer(buffer_m), part="boundary")
    return out.to_crs("EPSG:4326")
