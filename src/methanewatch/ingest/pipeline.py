"""Ingest steps that write raw pulls and the interim tables ``coverage build`` reads.

- EMIT: scene footprints -> ``interim/footprints/emit.parquet``; plume-complex
  outlines (no rates yet) -> ``interim/emit_plume_outlines.parquet``.
- Sentinel-2: scene footprints -> ``interim/footprints/sentinel2.parquet``.
- Carbon Mapper: aircraft and Tanager scene footprints ->
  ``interim/footprints/carbonmapper.parquet``; plumes with rates ->
  ``interim/plumes/carbonmapper.parquet``. Built from every finished pull: one
  row per scene, and one row per plume at its most recently modified version.
- GHGRP: Bay Area subpart HH facilities -> ``interim/ghgrp_facilities_<year>.csv``;
  reports for crosswalked sites -> ``interim/operator_reports.parquet``.

Footprint tables are rebuilt from every raw pull of that source, deduplicated by
scene, so repeated or overlapping pulls are safe.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import geopandas as gpd
import pandas as pd

from methanewatch.config import ProjectConfig, load_impact
from methanewatch.ingest import carbonmapper, emit, ghgrp
from methanewatch.provenance import PullManifest
from methanewatch.sentinel2 import search as s2

BBox = tuple[float, float, float, float]


def registry_bbox(project: ProjectConfig) -> BBox | None:
    """Bounds of all site polygons plus the plume search radius, or None if no sites yet."""
    path = project.resolve(project.paths.interim) / "sites.parquet"
    if not path.exists():
        return None
    sites = gpd.read_parquet(path)
    if sites.empty:
        return None
    buffered = sites.to_crs(project.crs_metric).buffer(project.attribution.search_radius_km * 1000)
    minx, miny, maxx, maxy = buffered.to_crs("EPSG:4326").total_bounds
    return (float(minx), float(miny), float(maxx), float(maxy))


def _write_footprints(frames: list[gpd.GeoDataFrame], out: Path) -> int:
    fp = pd.concat(frames, ignore_index=True).drop_duplicates("scene_id")
    out.parent.mkdir(parents=True, exist_ok=True)
    gpd.GeoDataFrame(fp, geometry="geometry", crs="EPSG:4326").to_parquet(out)
    return len(fp)


def ingest_emit(project: ProjectConfig, bbox: BBox, start: date, end: date) -> dict[str, int]:
    raw = project.resolve(project.paths.raw)
    interim = project.resolve(project.paths.interim)
    emit.pull(emit.ENH, bbox, start, end, raw)
    emit.pull(emit.PLM, bbox, start, end, raw)

    def records(prefix: str) -> list[dict]:
        pulls = sorted((raw / "emit").glob(f"emit-{prefix.lower()}-*"))
        return [r for p in pulls for r in emit.load_pull(p)]

    n_fp = _write_footprints(
        [emit.footprints(records(emit.ENH))], interim / "footprints" / "emit.parquet"
    )
    outlines = emit.plume_outlines(records(emit.PLM)).drop_duplicates("granule_ur")
    outlines.to_parquet(interim / "emit_plume_outlines.parquet")
    return {"emit_scenes": n_fp, "emit_plume_complexes": len(outlines)}


def ingest_carbonmapper(project: ProjectConfig, bbox: BBox, start: date, end: date) -> dict:
    carbonmapper.pull(bbox, start, end, project.resolve(project.paths.raw))
    return write_carbonmapper(project)


def write_carbonmapper(project: ProjectConfig) -> dict:
    """Interim footprint and plume tables merged from every finished Carbon Mapper pull."""
    pulls = carbonmapper.finished_pulls(project.resolve(project.paths.raw))
    if not pulls:
        raise FileNotFoundError("no Carbon Mapper pull yet; run `mw ingest carbonmapper`")
    interim = project.resolve(project.paths.interim)
    fp = carbonmapper.footprints(carbonmapper.merged_scenes(pulls))
    n_fp = _write_footprints([fp], interim / "footprints" / "carbonmapper.parquet")
    plumes = carbonmapper.plumes(carbonmapper.merged_plumes(pulls))
    out = interim / "plumes" / "carbonmapper.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    plumes.to_parquet(out)
    return {
        "pulls": len(pulls),
        "newest_pull": pulls[-1].name,
        "scenes": n_fp,
        "scenes_by_instrument": fp["instrument"].value_counts().to_dict(),
        "plumes": len(plumes),
        "plumes_with_rate": int(plumes["q_kg_hr"].notna().sum()),
        "plume_versions": plumes["data_version"].value_counts().to_dict(),
    }


def ingest_sentinel2(
    project: ProjectConfig, bbox: BBox, start: date, end: date, max_cloud: float = 100.0
) -> dict[str, int]:
    raw = project.resolve(project.paths.raw)
    interim = project.resolve(project.paths.interim)
    items = s2.search_scenes(bbox, start, end, max_cloud=max_cloud)
    manifest = PullManifest.start(
        "sentinel2",
        f"{s2.EARTH_SEARCH} {s2.COLLECTION}",
        {"bbox": bbox, "start": start.isoformat(), "end": end.isoformat(), "max_cloud": max_cloud},
    )
    pull_dir = raw / "sentinel2" / manifest.pull_id
    pull_dir.mkdir(parents=True, exist_ok=True)
    path = pull_dir / "items.json"
    path.write_text(json.dumps(items))
    manifest.finish(pull_dir, [path], n_records=len(items))

    frames = [
        s2.footprints(json.loads((p / "items.json").read_text()))
        for p in sorted((raw / "sentinel2").iterdir())
        if (p / "items.json").exists()
    ]
    n = _write_footprints(frames, interim / "footprints" / "sentinel2.parquet")
    return {"sentinel2_scenes_this_pull": len(items), "sentinel2_scenes_total": n}


def ingest_ghgrp(project: ProjectConfig, year: int) -> dict[str, int]:
    raw = project.resolve(project.paths.raw)
    interim = project.resolve(project.paths.interim)
    registry = project.resolve(project.paths.registry)
    interim.mkdir(parents=True, exist_ok=True)

    facilities = ghgrp.bay_area_facilities(year)
    facilities.to_csv(interim / f"ghgrp_facilities_{year}.csv", index=False)

    crosswalk = pd.read_csv(registry / "operator_crosswalk.csv", dtype=str)
    ids = crosswalk["ghgrp_facility_id"].dropna().tolist()
    if not ids:
        return {"bay_area_facilities": len(facilities), "operator_rows": 0}
    pull_dir = ghgrp.pull_reports(ids, raw)
    reports = ghgrp.normalize(pull_dir, crosswalk, load_impact().ghgrp_gwp_ch4.by_year())
    reports.to_parquet(interim / "operator_reports.parquet")
    return {"bay_area_facilities": len(facilities), "operator_rows": len(reports)}
