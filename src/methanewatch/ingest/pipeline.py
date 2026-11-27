"""Ingest steps that write raw pulls and the interim tables ``coverage build`` reads.

- EMIT: scene footprints -> ``interim/footprints/emit.parquet``; plume-complex
  outlines (no rates yet) -> ``interim/emit_plume_outlines.parquet``.
- Sentinel-2: scene footprints -> ``interim/footprints/sentinel2.parquet``.
- Carbon Mapper: aircraft and Tanager scene footprints ->
  ``interim/footprints/carbonmapper.parquet``; plumes with rates ->
  ``interim/plumes/carbonmapper.parquet``. Built from every finished pull: one
  row per scene, and one row per plume at its most recently modified version.
- GHGRP: subpart HH facilities in the project's counties ->
  ``interim/ghgrp_facilities_<year>.csv``; reports for crosswalked sites ->
  ``interim/operator_reports.parquet``, and every gas they reported ->
  ``interim/site_metrics/ghgrp.parquet``.

- Carbon Mapper CO2: plumes and scenes from their own raw folder -> counts per landfill and
  year in ``interim/site_metrics/carbonmapper-co2.parquet``, and nothing else (ADR 0024).
- EPA landfill gas program (LMOP): EPA's California workbook -> how each matched landfill is
  run, in ``interim/site_metrics/epa-lmop.parquet``, and the EPA landfills in the project's
  counties that no site is matched to in ``interim/lmop_unmatched.csv`` (ADR 0025).

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
from methanewatch.ingest import carbonmapper, carbonmapper_co2, emit, ghgrp, lmop
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


def ingest_carbonmapper_co2(project: ProjectConfig, bbox: BBox, start: date, end: date) -> dict:
    carbonmapper_co2.pull(bbox, start, end, project.resolve(project.paths.raw))
    return write_carbonmapper_co2(project)


def write_carbonmapper_co2(project: ProjectConfig) -> dict:
    """CO2 plume and pass counts per landfill and year, from every finished CO2 pull.

    Rerun this after the registry changes: the counts depend on each landfill's outline.
    """
    pulls = carbonmapper_co2.finished_pulls(project.resolve(project.paths.raw))
    if not pulls:
        raise FileNotFoundError("no Carbon Mapper CO2 pull yet; run `mw ingest carbonmapper-co2`")
    interim = project.resolve(project.paths.interim)
    if not (interim / "sites.parquet").exists():
        raise FileNotFoundError("no site table yet; run `mw sites build`")
    sites = gpd.read_parquet(interim / "sites.parquet")
    plumes = carbonmapper_co2.merged_plumes(pulls)
    scenes = carbonmapper_co2.merged_scenes(pulls)
    near = carbonmapper_co2.plumes_near(
        plumes, sites, buffer_m=project.attribution.buffer_m, metric_crs=project.crs_metric
    )
    passes = carbonmapper_co2.passes_over(
        scenes,
        sites,
        min_coverage_frac=project.coverage.min_coverage_frac,
        metric_crs=project.crs_metric,
    )
    rows = carbonmapper_co2.yearly_counts(near, passes, pulls[-1].name)
    (interim / "site_metrics").mkdir(parents=True, exist_ok=True)
    rows.to_parquet(interim / "site_metrics" / f"{carbonmapper_co2.SOURCE}.parquet")
    return {
        "pulls": len(pulls),
        "newest_pull": pulls[-1].name,
        "co2_plumes": len(plumes),
        "co2_plumes_by_sector": plumes["ipcc_sector"].fillna("no tag").value_counts().to_dict(),
        "co2_scenes": len(scenes),
        "sites_with_a_pass": int(passes["site_id"].nunique()),
        "site_days_searched": len(passes),
        "plumes_near_a_site": int(near["plume_id"].nunique()),
        "near_plumes_by_sector": near.drop_duplicates("plume_id")["ipcc_sector"]
        .fillna("no tag")
        .value_counts()
        .to_dict(),
        "rows": len(rows),
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

    facilities = ghgrp.facilities_in([c.name for c in project.counties], year)
    facilities.to_csv(interim / f"ghgrp_facilities_{year}.csv", index=False)

    crosswalk = pd.read_csv(registry / "operator_crosswalk.csv", dtype=str)
    ids = crosswalk["ghgrp_facility_id"].dropna().tolist()
    if not ids:
        return {"facilities_in_regions": len(facilities), "operator_rows": 0}
    pull_dir = ghgrp.pull_reports(ids, raw)
    reports = ghgrp.normalize(pull_dir, crosswalk, load_impact().ghgrp_gwp_ch4.by_year())
    reports.to_parquet(interim / "operator_reports.parquet")
    # Every gas the matched facilities reported, for the measures table (ADR 0019)
    gases, left_out = ghgrp.normalize_gases(pull_dir, crosswalk)
    (interim / "site_metrics").mkdir(exist_ok=True)
    gases.to_parquet(interim / "site_metrics" / "ghgrp.parquet")
    return {
        "facilities_in_regions": len(facilities),
        "operator_rows": len(reports),
        "gas_rows": len(gases),
        "gas_rows_left_out": int(left_out["rows"].sum()),
    }


def ingest_lmop(project: ProjectConfig) -> dict:
    lmop.pull(project.resolve(project.paths.raw))
    return write_lmop(project)


def write_lmop(project: ProjectConfig) -> dict:
    """How each matched landfill is run, from the newest pull of EPA's landfill gas file.

    Rerun this after ``data/registry/lmop_crosswalk.csv`` changes: no download is needed.
    """
    pulls = lmop.finished_pulls(project.resolve(project.paths.raw))
    if not pulls:
        raise FileNotFoundError("no EPA landfill gas file yet; run `mw ingest lmop`")
    newest = pulls[-1]
    details = lmop.pull_details(newest)
    table = lmop.read_workbook(newest / lmop.FILE)
    crosswalk = lmop.read_crosswalk(project.resolve(project.paths.registry) / "lmop_crosswalk.csv")
    rows, gone = lmop.measures(
        table, crosswalk, edition=details["edition"], url=details["file_url"], pull_id=newest.name
    )
    interim = project.resolve(project.paths.interim)
    (interim / "site_metrics").mkdir(parents=True, exist_ok=True)
    rows.to_parquet(interim / "site_metrics" / f"{lmop.SOURCE}.parquet")
    # EPA landfills in the project's counties that no site is matched to, for a hand check
    listed = lmop.landfills(table)
    in_counties = listed[listed[lmop.C_COUNTY].isin([c.name for c in project.counties])]
    matched = set(crosswalk["lmop_landfill_id"].dropna().astype(int))
    unmatched = in_counties[~in_counties.index.isin(matched)]
    unmatched[[lmop.C_NAME, lmop.C_COUNTY, lmop.C_GHGRP]].to_csv(interim / "lmop_unmatched.csv")
    return {
        "newest_pull": newest.name,
        "edition": details["edition"],
        "epa_landfills_in_file": len(listed),
        "epa_landfills_in_counties": len(in_counties),
        "sites_matched": int(rows["site_id"].nunique()),
        "matches_checked_by_hand": int(rows.loc[rows["confirmed"], "site_id"].nunique()),
        "epa_landfills_unmatched": len(unmatched),
        "matched_but_no_longer_listed": len(gone),
        "rows": len(rows),
    }
