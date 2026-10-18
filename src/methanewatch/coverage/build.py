"""Pipeline step: footprints + attributed plumes -> overpasses and detections.

Ingest steps write scene footprints to ``data/interim/footprints/<source>.parquet``
(GeoParquet with ``scene_id, instrument, acquired_utc, valid_frac, geometry``)
and normalized plumes to ``data/interim/plumes/<source>.parquet``. This step
writes ``overpasses.parquet``, ``detections.parquet`` and
``unmatched_plumes.parquet`` to ``data/interim``.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd

from methanewatch.attribution import attribute_plumes
from methanewatch.config import ProjectConfig
from methanewatch.coverage.overpasses import build_detections, from_footprints

# Footprint file stem -> coverage_source label
SOURCES = {"emit": "cmr-granule", "sentinel2": "s2-scene", "carbonmapper": "stac-footprint"}


def build(project: ProjectConfig) -> dict[str, int]:
    interim = project.resolve(project.paths.interim)
    sites = gpd.read_parquet(interim / "sites.parquet")
    nb_path = interim / "neighbors.parquet"
    neighbors = gpd.read_parquet(nb_path) if nb_path.exists() else sites.iloc[0:0]

    frames = []
    for path in sorted((interim / "footprints").glob("*.parquet")):
        if path.stem not in SOURCES:
            raise ValueError(f"unknown footprint source {path.stem!r}")
        fp = gpd.read_parquet(path)
        frames.append(
            from_footprints(
                fp,
                sites,
                project.coverage,
                source=SOURCES[path.stem],
                metric_crs=project.crs_metric,
            )
        )
    if not frames:
        raise FileNotFoundError(f"no footprint files in {interim / 'footprints'}")
    overpasses = pd.concat(frames, ignore_index=True)

    plume_files = sorted((interim / "plumes").glob("*.parquet"))
    plumes = (
        pd.concat([pd.read_parquet(p) for p in plume_files], ignore_index=True)
        if plume_files
        else None
    )
    if plumes is None or plumes.empty:
        plumes = pd.DataFrame(
            columns=[
                "plume_id",
                "instrument",
                "acquired_utc",
                "q_kg_hr",
                "q_sigma_kg_hr",
                "site_id",
                "attribution",
                "origin_lon",
                "origin_lat",
            ]
        )
    else:
        plumes = attribute_plumes(
            plumes,
            sites,
            neighbors,
            buffer_m=project.attribution.buffer_m,
            search_radius_m=project.attribution.search_radius_km * 1000,
            metric_crs=project.crs_metric,
        )
    detections, unmatched = build_detections(overpasses, plumes)

    overpasses.to_parquet(interim / "overpasses.parquet")
    plumes.to_parquet(interim / "plumes_attributed.parquet")
    detections.to_parquet(interim / "detections.parquet")
    unmatched.to_parquet(interim / "unmatched_plumes.parquet")
    return {
        "overpasses": len(overpasses),
        "usable": int(overpasses["usable"].sum()),
        "detections": int(detections["detected"].sum()),
        "unmatched_plumes": len(unmatched),
    }


def latest(path: Path) -> Path:
    dirs = sorted(p for p in path.iterdir() if p.is_dir())
    if not dirs:
        raise FileNotFoundError(f"no pulls under {path}")
    return dirs[-1]
