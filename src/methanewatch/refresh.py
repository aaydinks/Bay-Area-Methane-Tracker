"""One refresh: pull every source again, then rebuild the interim tables.

The tracker is retrospective, and its sources publish late: Carbon Mapper plumes
appear about 30 days after the flight, and older plumes are sometimes reprocessed
at a newer version. So the data are refreshed on a schedule, and a refresh must
give the same tables whenever it runs on the same downloads:

- Every pull asks the same question: the window and areas in
  ``config/project.yaml`` (``ingest``), from the fixed start date up to today.
- Pulls are never overwritten. The interim tables are rebuilt from all finished
  pulls of a source, so a failed or partial pull never removes earlier data.
- A source that is down is recorded and skipped. The tables are then rebuilt
  from that source's earlier pulls, and the run exits non-zero.
- Each refresh writes a manifest (code version, config hashes, every step's
  result and row counts) to ``interim/refresh/``.

Raw downloads are in ``data/raw/`` and the tables in ``data/interim/``; both are
git-ignored. Annual sources (EPA GHGRP, CalRecycle) are not part of a refresh.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable, Sequence
from datetime import date
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd

from methanewatch import features
from methanewatch.config import ProjectConfig
from methanewatch.coverage import build as coverage
from methanewatch.ingest import pipeline
from methanewatch.provenance import new_id, run_manifest, utcnow
from methanewatch.sites import registry

SOURCES = ("emit", "sentinel2", "carbonmapper")
# Tables copied to interim/csv/ for opening in a spreadsheet
CSV_TABLES = ("overpasses", "detections", "plumes_attributed", "unmatched_plumes", "site_features")


def _sites(project: ProjectConfig) -> dict[str, Any]:
    registry_dir = project.resolve(project.paths.registry)
    sites = registry.build_registry(
        registry_dir, project.resolve(project.paths.interim), metric_crs=project.crs_metric
    )
    if sites.empty:
        raise FileNotFoundError("no site boundary polygons in data/registry/sites.geojson")
    sources = sites.get("polygon_source", pd.Series("", index=sites.index)).fillna("").str.lower()
    return {
        "sites": len(sites),
        "missing_polygons": registry.missing_polygons(registry_dir),
        "provisional_outlines": sorted(sites.loc[sources.str.contains("provisional"), "site_id"]),
    }


def _features(project: ProjectConfig) -> dict[str, Any]:
    return {"sites": len(features.write_site_features(project))}


def export_csv(interim: Path) -> dict[str, Any]:
    """CSV copies of the main tables, without geometry, in ``interim/csv/``."""
    out = interim / "csv"
    out.mkdir(exist_ok=True)
    written = []
    for name in CSV_TABLES:
        path = interim / f"{name}.parquet"
        if not path.exists():
            continue
        df = pd.read_parquet(path)
        if "scene_ids" in df:
            df["scene_ids"] = df["scene_ids"].map(";".join)
        df.drop(columns=["geometry"], errors="ignore").to_csv(out / f"{name}.csv", index=False)
        written.append(name)
    sites_path = interim / "sites.parquet"
    if sites_path.exists():
        sites = gpd.read_parquet(sites_path)
        sites.drop(columns="geometry").assign(wkt=sites.geometry.to_wkt()).to_csv(
            out / "sites.csv", index=False
        )
        written.append("sites")
    return {"files": written}


def run(
    project: ProjectConfig,
    *,
    end: date | None = None,
    skip: Sequence[str] = (),
    csv: bool = True,
) -> dict[str, Any]:
    """Pull, rebuild and record. ``manifest["ok"]`` is False if any step failed."""
    unknown = sorted(set(skip) - set(SOURCES))
    if unknown:
        raise ValueError(f"unknown sources to skip: {unknown}; choose from {list(SOURCES)}")
    started = utcnow()
    out = project.resolve(project.paths.interim) / "refresh"
    out.mkdir(parents=True, exist_ok=True)
    refresh_id, n = new_id("refresh", started), 1
    while (out / f"{refresh_id}.json").exists():  # ids are per second; never overwrite one
        n += 1
        refresh_id = f"{new_id('refresh', started)}-{n}"
    end = end or started.date()
    ing = project.ingest
    steps: dict[str, dict[str, Any]] = {}

    def step(name: str, fn: Callable[..., dict[str, Any]], *args: Any) -> bool:
        try:
            steps[name] = {"ok": True, **fn(*args)}
        except Exception as exc:  # one source being down must not stop the others
            steps[name] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        return steps[name]["ok"]

    pulls = {
        "emit": (pipeline.ingest_emit, ing.bbox),
        "sentinel2": (pipeline.ingest_sentinel2, ing.sentinel2_bbox),
        "carbonmapper": (pipeline.ingest_carbonmapper, ing.bbox),
    }
    for name, (fn, bbox) in pulls.items():
        if name in skip:
            steps[name] = {"ok": True, "skipped": True}
            continue
        if not step(name, fn, project, bbox, ing.start, end) and name == "carbonmapper":
            # Rebuild from the pulls already on disk so the tables stay complete
            step("carbonmapper_rebuild", pipeline.write_carbonmapper, project)

    interim = project.resolve(project.paths.interim)
    built = (
        step("sites", _sites, project)
        and step("coverage", coverage.build, project)
        and step("features", _features, project)
    )
    if built and csv:
        step("csv", export_csv, interim)

    manifest = run_manifest(
        refresh_id,
        extra={
            "kind": "refresh",
            "started_at": started.isoformat(),
            "window": {"start": ing.start.isoformat(), "end": end.isoformat()},
            "ingest": ing.model_dump(mode="json"),
            "skipped": sorted(skip),
            "steps": steps,
            "ok": all(s["ok"] for s in steps.values()) and built,
        },
    )
    path = out / f"{refresh_id}.json"
    path.write_text(json.dumps(manifest, indent=2, default=str))
    shutil.copyfile(path, out / "latest.json")
    return manifest
