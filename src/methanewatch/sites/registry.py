"""Build and QA the site registry (docs/PLAN.md section 5, phase 1).

Inputs in ``data/registry/``:
- ``sites.csv``: one row per landfill (attributes, tier, neighbors).
- ``sites.geojson``: polygons keyed by ``site_id`` with a ``part`` property:
  ``boundary`` (required to use a site), ``working_face`` or ``closed``
  (pilot sites). Neighbor sources use ``part = neighbor`` and a ``name``.

Output: ``data/interim/sites.parquet`` (GeoParquet, EPSG:4326) and
``neighbors.parquet``.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import box

# Loose bounding box around the nine Bay Area counties (lon/lat). A coarse check
# for swapped coordinates or wrong CRS; not a county-boundary test.
BAY_AREA_BBOX = box(-123.65, 36.85, -121.2, 38.9)
PARTS = {"boundary", "working_face", "closed", "neighbor"}
SCREEN_BUFFER_M = 750


def read_polygons(path: Path) -> gpd.GeoDataFrame:
    if not path.exists():
        return gpd.GeoDataFrame({"site_id": [], "part": []}, geometry=[], crs="EPSG:4326")
    gdf = gpd.read_file(path)
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    return gdf.to_crs("EPSG:4326")


def build_registry(
    registry_dir: Path, out_dir: Path, *, metric_crs: str = "EPSG:32610"
) -> gpd.GeoDataFrame:
    attrs = pd.read_csv(registry_dir / "sites.csv", dtype=str).fillna("")
    polys = read_polygons(registry_dir / "sites.geojson")

    problems = qa_inputs(attrs, polys)
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

    out_dir.mkdir(parents=True, exist_ok=True)
    sites.to_parquet(out_dir / "sites.parquet")
    neighbors = polys[polys["part"] == "neighbor"]
    neighbors.to_parquet(out_dir / "neighbors.parquet")
    return sites


def qa_inputs(attrs: pd.DataFrame, polys: gpd.GeoDataFrame) -> list[str]:
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
    outside = polys[~polys.geometry.within(BAY_AREA_BBOX)]
    if len(outside):
        problems.append(f"geometries outside the Bay Area box: {outside['site_id'].tolist()}")
    return problems


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
