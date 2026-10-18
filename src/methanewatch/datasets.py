"""The committed copy of each source dataset, one folder per source under ``datasets/``.

``data/raw`` stays the local download cache (git-ignored). ``mw datasets build``
writes tidy, openly licensed tables from those pulls into ``datasets/<source>/``,
with a copy of each pull manifest, so the repository carries the data and its
provenance. Carbon Mapper tables are written too, but its folder is git-ignored
except for the README: the data are non-commercial and not for redistribution.
"""

from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path

import geopandas as gpd
import pandas as pd

from methanewatch.ingest import carbonmapper, emit
from methanewatch.sentinel2 import search as s2

# EMIT was paused by a power issue outside the instrument. These days are "no data",
# not "no leak"; the coverage build must not create overpasses inside the gap.
EMIT_OUTAGE = (date(2022, 9, 13), date(2023, 1, 6))

BAY_AREA_COUNTY_FIPS = {
    "001": "Alameda",
    "013": "Contra Costa",
    "041": "Marin",
    "055": "Napa",
    "075": "San Francisco",
    "081": "San Mateo",
    "085": "Santa Clara",
    "095": "Solano",
    "097": "Sonoma",
}


def _copy_manifests(pulls: list[Path], out: Path) -> None:
    dest = out / "pulls"
    dest.mkdir(parents=True, exist_ok=True)
    for p in pulls:
        shutil.copyfile(p / "manifest.json", dest / f"{p.name}.json")


def _geojson(gdf: gpd.GeoDataFrame, path: Path) -> None:
    gdf = gdf.copy()
    for col in gdf.columns:
        if isinstance(gdf[col].dtype, pd.DatetimeTZDtype):
            gdf[col] = gdf[col].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    path.unlink(missing_ok=True)
    gdf.to_file(path, driver="GeoJSON", layer_options={"COORDINATE_PRECISION": 6})


def in_emit_outage(t: pd.Series) -> pd.Series:
    day = t.dt.tz_convert("UTC").dt.date
    return (day >= EMIT_OUTAGE[0]) & (day <= EMIT_OUTAGE[1])


def build_emit(raw: Path, out: Path) -> dict[str, int]:
    out.mkdir(parents=True, exist_ok=True)
    counts = {}
    for short, name in [(emit.ENH, "scenes"), (emit.PLM, "plume_complexes")]:
        pulls = sorted((raw / "emit").glob(f"emit-{short.lower()}-*"))
        records = {r["umm"]["GranuleUR"]: r for p in pulls for r in emit.load_pull(p)}
        recs = list(records.values())
        if short == emit.ENH:
            gdf = emit.footprints(recs).drop(columns=["valid_frac"])
            gdf["cloud_cover_pct"] = [r["umm"].get("CloudCover") for r in recs]
            gdf["in_outage"] = in_emit_outage(gdf["acquired_utc"])
        else:
            gdf = emit.plume_outlines(recs)
        gdf = gdf.sort_values("acquired_utc").reset_index(drop=True)
        _geojson(gdf, out / f"{name}.geojson")
        _copy_manifests(pulls, out)
        counts[f"emit_{name}"] = len(gdf)
    return counts


def build_sentinel2(raw: Path, out: Path) -> dict[str, int]:
    out.mkdir(parents=True, exist_ok=True)
    pulls = sorted(p for p in (raw / "sentinel2").iterdir() if (p / "items.json").exists())
    items = {it["id"]: it for p in pulls for it in json.loads((p / "items.json").read_text())}
    gdf = s2.footprints(list(items.values())).drop(columns=["valid_frac", "instrument"])
    gdf["cloud_cover_pct"] = [it["properties"].get("eo:cloud_cover") for it in items.values()]
    gdf = gdf.sort_values("acquired_utc").reset_index(drop=True)
    _geojson(gdf, out / "scenes.geojson")
    _copy_manifests(pulls, out)
    return {"sentinel2_scenes": len(gdf)}


def build_carbonmapper(raw: Path, out: Path) -> dict[str, int]:
    out.mkdir(parents=True, exist_ok=True)
    pull = carbonmapper.latest_pull(raw)
    counts = {}
    for name in ["solid-waste", "all-sectors"]:
        df = carbonmapper.plumes_table(pull / f"plumes_{name}.csv")
        df["datetime"] = df["datetime"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        df.to_csv(out / f"plumes_{name}.csv", index=False)
        counts[f"carbonmapper_plumes_{name}"] = len(df)
    items = json.loads((pull / f"scenes_{carbonmapper.SCENE_COLLECTION}.json").read_text())
    scenes = carbonmapper.scenes_table(items)
    _geojson(scenes, out / f"scenes_{carbonmapper.SCENE_COLLECTION}.geojson")
    _copy_manifests([pull], out)
    counts["carbonmapper_scenes"] = len(scenes)
    return counts


def build_ghgrp(raw: Path, interim: Path, out: Path) -> dict[str, int]:
    out.mkdir(parents=True, exist_ok=True)
    pull = sorted((raw / "ghgrp").glob("ghgrp-*"))[-1]
    files = [p for p in sorted(pull.glob("*.json")) if p.name != "manifest.json"]
    rows = pd.DataFrame([r for p in files for r in json.loads(p.read_text())])
    # As published: t CO2e by facility, year, subpart and gas. Converting to CH4 needs the
    # GWP EPA used, which is a config value, not data.
    rows = rows.sort_values(["facility_id", "year", "sub_part_id", "gas_id"])
    rows.to_csv(out / "emissions_by_subpart_gas.csv", index=False)
    facilities = sorted(interim.glob("ghgrp_facilities_*.csv"))
    for f in facilities:
        shutil.copyfile(f, out / f.name.replace("ghgrp_", ""))
    _copy_manifests([pull], out)
    return {"ghgrp_rows": len(rows), "ghgrp_facility_lists": len(facilities)}


def build_census(raw: Path, out: Path, sites: gpd.GeoDataFrame, radius_km: float) -> dict[str, int]:
    """2020 block population for the nine counties, and block outlines near the pilot sites."""
    zip_path = raw / "census" / "tiger2020-tabblock20" / "tl_2020_06_tabblock20.zip"
    if not zip_path.exists():
        raise FileNotFoundError(f"missing {zip_path}; see datasets/census/README.md")
    out.mkdir(parents=True, exist_ok=True)
    fips = ",".join(f"'{c}'" for c in BAY_AREA_COUNTY_FIPS)
    blocks = gpd.read_file(f"zip://{zip_path}", where=f"COUNTYFP20 IN ({fips})")
    cols = ["GEOID20", "COUNTYFP20", "TRACTCE20", "BLOCKCE20", "POP20", "HOUSING20"]
    cols += ["ALAND20", "AWATER20", "INTPTLAT20", "INTPTLON20", "UR20"]
    table = blocks[cols].assign(county=blocks["COUNTYFP20"].map(BAY_AREA_COUNTY_FIPS))
    table.sort_values("GEOID20").to_csv(out / "blocks_2020_population.csv", index=False)
    near = sites.to_crs("EPSG:32610").buffer(radius_km * 1000).to_crs(blocks.crs).union_all()
    nearby = blocks[blocks.intersects(near)][["GEOID20", "POP20", "HOUSING20", "geometry"]]
    nearby.to_crs("EPSG:4326").sort_values("GEOID20").to_parquet(
        out / f"blocks_2020_within_{radius_km:g}km_of_pilots.parquet"
    )
    return {"census_blocks": len(table), "census_blocks_near_pilots": len(nearby)}


def reference_points(path: Path) -> gpd.GeoDataFrame:
    df = pd.read_csv(path)
    return gpd.GeoDataFrame(
        df, geometry=gpd.points_from_xy(df["longitude"], df["latitude"]), crs="EPSG:4326"
    )


def build_sentinel2_crops(
    root: Path, interim: Path, sites: gpd.GeoDataFrame, half_m: float = 3000
) -> dict[str, int]:
    """Crop Sentinel-2 L1C around each pilot site on plume days and reference days.

    The full target list, with Carbon Mapper plume ids, stays local in
    ``data/interim/s2_targets.csv``; the committed index names only the trigger.
    """
    from methanewatch.sentinel2 import crops

    cm = pd.read_csv(root / "carbonmapper" / "plumes_all-sectors.csv")
    cm = pd.DataFrame(
        {
            "plume_id": cm["plume_id"],
            "acquired_utc": pd.to_datetime(cm["datetime"], utc=True, format="ISO8601"),
            "lon": cm["plume_longitude"],
            "lat": cm["plume_latitude"],
            "source": "carbonmapper",
        }
    )
    em = gpd.read_file(root / "emit" / "plume_complexes.geojson")
    centre = em.to_crs("EPSG:32610").centroid.to_crs("EPSG:4326")
    em = pd.DataFrame(
        {
            "plume_id": em["plume_id"],
            "acquired_utc": pd.to_datetime(em["acquired_utc"], utc=True, format="ISO8601"),
            "lon": centre.x,
            "lat": centre.y,
            "source": "emit",
        }
    )
    scenes = gpd.read_file(root / "sentinel2" / "scenes.geojson")
    scenes["acquired_utc"] = pd.to_datetime(scenes["acquired_utc"], utc=True, format="ISO8601")
    targets = crops.choose_targets(sites, pd.concat([cm, em]), scenes, half_m=half_m)
    targets.to_csv(interim / "s2_targets.csv", index=False)

    out = root / "sentinel2" / "crops"
    index = []
    for t in targets.drop_duplicates(["site_id", "product_uri"]).itertuples():
        site = sites[sites["site_id"] == t.site_id].iloc[0]
        tile = crops.product_prefix(t.product_uri).split("/")[1:4]
        name = f"{t.day}_T{''.join(tile)}_R{int(t.relative_orbit):03d}.tif"
        path = out / t.site_id / name
        same = (targets["site_id"] == t.site_id) & (targets["product_uri"] == t.product_uri)
        roles = targets[same]
        role = "plume_day" if (roles["role"] == "plume_day").any() else "reference"
        ids = [i for ids in roles["plume_ids"] for i in str(ids).split(";") if ids]
        seen_by = "emit" if any(i.startswith("emit-") for i in ids) else ""
        seen_by = seen_by or ("carbonmapper" if ids else "")
        if not path.exists():
            crops.crop(
                t.product_uri,
                site["longitude"],
                site["latitude"],
                half_m,
                path,
                {"site_id": t.site_id, "role": role, "cloud_cover_pct_tile": t.cloud_cover_pct},
            )
        index.append(
            {
                "site_id": t.site_id,
                "day": t.day,
                "role": role,
                "plume_seen_by": seen_by,
                "reference_for": ";".join(str(d) for d in roles["for_day"].dropna().unique()),
                "relative_orbit": int(t.relative_orbit),
                "cloud_cover_pct_tile": round(float(t.cloud_cover_pct), 2),
                "product_uri": t.product_uri,
                "file": str(path.relative_to(root / "sentinel2")),
            }
        )
    pd.DataFrame(index).sort_values(["site_id", "day"]).to_csv(out / "index.csv", index=False)
    return {"sentinel2_crops": len(index)}


def build_emit_files(raw: Path, root: Path, sites: gpd.GeoDataFrame, half_m: float = 3000) -> dict:
    """Plume-complex metadata and per-site image windows (needs the Earthdata login).

    Windows cover every EMIT scene whose outline touches a site's square window, so
    partial looks are kept; coverage is scored per site boundary downstream.
    """
    from methanewatch.provenance import PullManifest

    out = root / "emit"
    session = emit.earthdata_session()
    manifest = PullManifest.start(
        "emit-files",
        "LP DAAC protected HTTPS (CH4PLMMETA JSON, CH4ENH/UNCERT/SENS windows)",
        {"half_m": half_m, "sites": sites["site_id"].tolist()},
    )
    written: list[Path] = []

    plm = {
        r["umm"]["GranuleUR"]: r
        for p in sorted((raw / "emit").glob("emit-emitl2bch4plm-*"))
        for r in emit.load_pull(p)
    }
    meta_dir = out / "plume_metadata"
    meta_dir.mkdir(parents=True, exist_ok=True)
    for ur, rec in sorted(plm.items()):
        path = meta_dir / f"{ur}.json"
        path.write_text(json.dumps(emit.plume_metadata(rec, session), indent=1))
        written.append(path)

    enh = {
        r["umm"]["GranuleUR"]: r
        for p in sorted((raw / "emit").glob("emit-emitl2bch4enh-*"))
        for r in emit.load_pull(p)
    }
    scenes = emit.footprints(list(enh.values()))
    cookie = raw / "emit" / ".gdal_cookies"
    index = []
    for site in sites.to_crs("EPSG:32610").itertuples():
        ref = sites[sites["site_id"] == site.site_id].iloc[0]
        window = gpd.GeoSeries([site.geometry.buffer(half_m, cap_style="square")], crs="EPSG:32610")
        window = window.to_crs("EPSG:4326").iloc[0]
        touching = scenes[scenes.intersects(window)]
        for sc in touching.itertuples():
            path = out / "windows" / site.site_id / f"{sc.scene_id}.tif"
            if not path.exists():
                emit.site_window(
                    enh[sc.scene_id], ref["longitude"], ref["latitude"], half_m, path, cookie
                )
            written.append(path)
            index.append(
                {
                    "site_id": site.site_id,
                    "scene_id": sc.scene_id,
                    "acquired_utc": sc.acquired_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "window_inside_scene": bool(sc.geometry.contains(window)),
                    "file": str(path.relative_to(out)),
                }
            )
    idx = out / "windows" / "index.csv"
    pd.DataFrame(index).sort_values(["site_id", "acquired_utc"]).to_csv(idx, index=False)
    written.append(idx)
    pull_dir = out / "pulls"
    manifest.finish(out, written, n_records=len(written))
    (out / "manifest.json").rename(pull_dir / f"{manifest.pull_id}.json")
    return {"emit_plume_metadata": len(plm), "emit_windows": len(index)}
