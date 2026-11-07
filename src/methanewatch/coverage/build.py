"""Pipeline step: footprints + attributed plumes -> overpasses and detections.

Ingest steps write scene footprints to ``data/interim/footprints/<source>.parquet``
(GeoParquet with ``scene_id, instrument, acquired_utc, valid_frac, geometry``)
and normalized plumes to ``data/interim/plumes/<source>.parquet``. This step
writes ``overpasses.parquet``, ``detections.parquet`` and
``unmatched_plumes.parquet`` to ``data/interim``.

Sentinel-2 passes take Sen2Cor's clear share over each site from
``data/interim/s2_site_clear.parquet`` (``mw s2 site-clear``, ADR 0014) before
detections are joined, so both tables count the same passes. This step reads
that table only; it never goes to the network.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd

from methanewatch import schemas
from methanewatch.attribution import attribute_plumes
from methanewatch.config import ProjectConfig
from methanewatch.coverage.overpasses import apply_site_clear, build_detections, from_footprints

# Footprint file stem -> coverage_source label
SOURCES = {"emit": "cmr-granule", "sentinel2": "s2-scene", "carbonmapper": "stac-footprint"}
SITE_CLEAR = "s2_site_clear.parquet"  # sentinel2/siteclear.TABLE, without its imports


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
    site_clear_path = interim / SITE_CLEAR
    site_clear = pd.read_parquet(site_clear_path) if site_clear_path.exists() else None
    overpasses = apply_site_clear(overpasses, site_clear, project.coverage)

    plume_files = sorted((interim / "plumes").glob("*.parquet"))
    plumes = (
        pd.concat([pd.read_parquet(p) for p in plume_files], ignore_index=True)
        if plume_files
        else None
    )
    if plumes is None or plumes.empty:
        plumes = no_plumes()
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
    s2 = overpasses["instrument"] == "sentinel2"
    source = overpasses["valid_frac_source"]
    return {
        "overpasses": len(overpasses),
        "usable": int(overpasses["usable"].sum()),
        "s2_site_share": int((source == schemas.VALID_FRAC_SITE).sum()),
        "s2_tile_fallback": int((s2 & (source == schemas.VALID_FRAC_TILE)).sum()),
        "detections": int(detections["detected"].sum()),
        "unmatched_plumes": len(unmatched),
    }


def no_plumes() -> pd.DataFrame:
    """An attributed plume table with no rows, typed by the plume schema.

    Untyped empty columns are object dtype, and the detection join then cannot take the log of
    the rates. The full column set also lets later steps read ``plumes_attributed.parquet``
    (the snapshot filters on ``source``).
    """
    return schemas.plumes.validate(pd.DataFrame(columns=list(schemas.plumes.columns)))


def latest(path: Path) -> Path:
    dirs = sorted(p for p in path.iterdir() if p.is_dir())
    if not dirs:
        raise FileNotFoundError(f"no pulls under {path}")
    return dirs[-1]
