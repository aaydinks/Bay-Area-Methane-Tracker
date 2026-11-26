"""Carbon Mapper's CO2 plumes, as counts per landfill and year (PLAN section 16.3, ADR 0024).

No instrument used here measures a landfill's CO2, and CO2 is never modelled. This step answers
one narrow question: in the passes Carbon Mapper searched for CO2, how many CO2 plumes did it
publish on or beside each landfill? The answer is two counts per landfill and year, written as
``site_metrics`` rows.

Checked live against the API on 2026-11-25:

- ``/catalog/plume-csv`` with ``plume_gas=CO2`` returns the same columns as the methane list,
  with ``gas`` set to ``CO2``.
- CO2 scenes are in scene-level collections named ``l2b-co2-<filter>-<version>``. New versions
  get new collections, so the list is read from ``/stac/collections`` at each pull and recorded
  in the pull manifest.

A CO2 pull is kept apart from the methane pulls. It lives under ``data/raw/carbonmapper-co2/``,
which no methane step reads, and its only output is ``interim/site_metrics/carbonmapper-co2
.parquet``. Nothing here writes a plume, pass or detection table.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import geopandas as gpd
import httpx
import pandas as pd

from methanewatch import schemas
from methanewatch.ingest import carbonmapper
from methanewatch.ingest.carbonmapper import API, BBox
from methanewatch.provenance import PullManifest

SOURCE = "carbonmapper-co2"  # the raw folder, the pull-id prefix and the key in data_terms.yaml
GAS = "CO2"
SCENE_PREFIX = "l2b-co2-"
PLUME_FILE = "plumes_co2.csv"
UNIT = "count"
PASSES = "cm_co2_passes"
PLUMES = "cm_co2_plumes"


def scene_collections(client: httpx.Client) -> list[str]:
    """The scene-level CO2 collections Carbon Mapper lists today."""
    listed = carbonmapper._get(client, "/stac/collections", []).json()["collections"]
    ids = sorted(c["id"] for c in listed if c["id"].startswith(SCENE_PREFIX))
    if not ids:
        raise RuntimeError(f"Carbon Mapper lists no collection named {SCENE_PREFIX}*")
    return ids


def pull(bbox: BBox, start: date, end: date, raw_root: Path) -> Path:
    """Write the CO2 plume list and every CO2 scene collection to one raw pull directory.

    Everything is downloaded before the directory is created, as the methane pull does.
    """
    manifest = PullManifest.start(
        SOURCE,
        f"{API}/catalog/plume-csv; {API}/stac/search",
        {"bbox": bbox, "start": start.isoformat(), "end": end.isoformat(), "plume_gas": GAS},
    )
    with httpx.Client(headers=carbonmapper._headers(), follow_redirects=True) as client:
        plumes = carbonmapper.plume_csv(client, bbox, start, gas=GAS)
        collections = scene_collections(client)
        scenes = {c: carbonmapper.stac_scenes(client, bbox, start, end, c) for c in collections}
        manifest.params["scene_collections"] = collections
        manifest.params["token_used"] = "Authorization" in client.headers
    _only_co2(plumes)
    pull_dir = raw_root / SOURCE / manifest.pull_id
    pull_dir.mkdir(parents=True, exist_ok=True)
    files = [pull_dir / PLUME_FILE]
    plumes.to_csv(files[0], index=False)
    for collection, items in scenes.items():
        path = pull_dir / f"scenes_{collection}.json"
        path.write_text(json.dumps(items))
        files.append(path)
    manifest.finish(pull_dir, files, n_records=len(plumes) + sum(len(v) for v in scenes.values()))
    return pull_dir


def _only_co2(plumes: pd.DataFrame) -> None:
    """Stop if the list holds any other gas: a methane plume must never be counted as CO2."""
    if len(plumes) and not (plumes["gas"] == GAS).all():
        raise ValueError(f"the CO2 plume list holds other gases: {sorted(set(plumes['gas']))}")


def finished_pulls(raw_root: Path) -> list[Path]:
    """CO2 pull directories with a manifest, oldest first."""
    pulls = sorted((raw_root / SOURCE).glob(f"{SOURCE}-*"))
    return [p for p in pulls if (p / "manifest.json").exists()]


def merged_plumes(pulls: list[Path]) -> pd.DataFrame:
    """One row per CO2 plume across pulls, at its most recently modified version."""
    try:
        table = carbonmapper.merged_plumes(pulls, PLUME_FILE)
    except FileNotFoundError:
        raise FileNotFoundError(
            "no Carbon Mapper CO2 pull yet; run `mw ingest carbonmapper-co2`"
        ) from None
    _only_co2(table)
    return table


def merged_scenes(pulls: list[Path]) -> gpd.GeoDataFrame:
    """One row per CO2 scene across pulls and processing versions; empty if none was pulled."""
    try:
        return carbonmapper.merged_scenes(pulls)
    except FileNotFoundError:
        empty = pd.DataFrame({"scene_id": [], "acquired_utc": pd.to_datetime([], utc=True)})
        return gpd.GeoDataFrame(empty, geometry=gpd.GeoSeries([], crs="EPSG:4326"))


def plumes_near(
    plumes: pd.DataFrame, sites: gpd.GeoDataFrame, *, buffer_m: float, metric_crs: str
) -> pd.DataFrame:
    """One row per (plume, landfill) whose plume origin is on the outline or within ``buffer_m``.

    This is nearness, not attribution: a plume beside two landfills is listed for both, and its
    sector tag is kept so the step can report what Carbon Mapper says the source is.
    """
    columns = ["plume_id", "site_id", "year", "ipcc_sector"]
    if plumes.empty:
        return pd.DataFrame(columns=columns)
    origins = gpd.GeoDataFrame(
        {
            "plume_id": plumes["plume_id"].astype(str).to_numpy(),
            "year": pd.to_datetime(plumes["datetime"], utc=True).dt.year.to_numpy(),
            "ipcc_sector": plumes["ipcc_sector"].to_numpy(),
        },
        geometry=gpd.points_from_xy(plumes["plume_longitude"], plumes["plume_latitude"]),
        crs="EPSG:4326",
    ).to_crs(metric_crs)
    outlines = sites[["site_id", "geometry"]].to_crs(metric_crs)
    near = gpd.sjoin(origins, outlines, predicate="dwithin", distance=buffer_m, how="inner")
    return (
        pd.DataFrame(near[columns])
        .sort_values(["site_id", "year", "plume_id"])
        .reset_index(drop=True)
    )


def passes_over(
    scenes: gpd.GeoDataFrame, sites: gpd.GeoDataFrame, *, min_coverage_frac: float, metric_crs: str
) -> pd.DataFrame:
    """One row per (landfill, UTC day) on which a CO2 scene covered the landfill.

    A scene covers a landfill when it holds at least ``min_coverage_frac`` of the outline, the
    rule the methane passes use. Scenes on the same day count once.
    """
    columns = ["site_id", "day", "year"]
    if scenes.empty:
        return pd.DataFrame(columns=columns)
    fp = scenes[["scene_id", "acquired_utc", "geometry"]].to_crs(metric_crs)
    outlines = sites[["site_id", "geometry"]].to_crs(metric_crs)
    pairs = gpd.sjoin(fp, outlines, predicate="intersects", how="inner")
    if pairs.empty:
        return pd.DataFrame(columns=columns)
    outline = outlines.set_index("site_id").geometry
    covered = [
        g.intersection(outline[s]).area / outline[s].area
        for g, s in zip(pairs.geometry, pairs["site_id"], strict=True)
    ]
    pairs = pairs[[c >= min_coverage_frac for c in covered]]
    day = pd.to_datetime(pairs["acquired_utc"], utc=True).dt.floor("D")
    out = pd.DataFrame({"site_id": pairs["site_id"].to_numpy(), "day": day.to_numpy()})
    out = out.drop_duplicates().sort_values(["site_id", "day"]).reset_index(drop=True)
    return out.assign(year=pd.DatetimeIndex(out["day"]).year)[columns]


def yearly_counts(near: pd.DataFrame, passes: pd.DataFrame, pull_id: str) -> pd.DataFrame:
    """``site_metrics`` rows: passes searched for CO2 and CO2 plumes found, per landfill and year.

    A year in which a pass covered the landfill gets both counts, so a zero there means
    "searched, none found". A year with no pass gets no row, which the pages read as "not
    searched". A plume found in a year with no listed pass still gets its count, without a pass
    count beside it.
    """
    n_pass = passes.groupby(["site_id", "year"]).size().rename("n").reset_index()
    n_plume = near.groupby(["site_id", "year"])["plume_id"].nunique().rename("n").reset_index()
    searched = n_pass[["site_id", "year"]].merge(n_plume, how="left", on=["site_id", "year"])
    unsearched = n_plume.merge(n_pass[["site_id", "year"]], how="left", indicator=True)
    unsearched = unsearched[unsearched["_merge"] == "left_only"].drop(columns="_merge")
    found = pd.concat([searched.fillna({"n": 0}), unsearched], ignore_index=True)
    rows = pd.concat(
        [n_pass.assign(metric_id=PASSES), found.assign(metric_id=PLUMES)], ignore_index=True
    )
    out = pd.DataFrame(
        {
            "site_id": rows["site_id"].astype(str),
            "metric_id": rows["metric_id"],
            "period": rows["year"].astype(int).astype(str),
            "source": SOURCE,
            "value": rows["n"].astype(float),
            "value_text": None,
            "unit": UNIT,
            "kind": "observed",
            # counted by a fixed rule from Carbon Mapper's own lists
            "confirmed": True,
            "source_id": None,
            "url": None,
            "pull_id": pull_id,
        }
    ).sort_values(["site_id", "period", "metric_id"])
    return schemas.site_metrics.validate(out.reset_index(drop=True))
