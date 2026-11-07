"""Sen2Cor's clear share per pilot site-day (ADR 0014 fallback), on synthetic data.

No network: the SCL tile is a small local GeoTIFF and the catalogue is a stand-in.
"""

import json

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import rasterio
from shapely.geometry import box
from typer.testing import CliRunner

from methanewatch.sentinel2 import siteclear as scl
from methanewatch.sentinel2 import sitecloud as sc

ULX, ULY = 499980.0, 4200000.0
N = sc.WINDOW_PX
L1C = "S2C_MSIL1C_20250601T185921_N0511_R013_T10SEG_20250601T204525.SAFE"


def full(value=4):
    return np.full((N, N), value, np.uint8)


def scored(scl):
    rs, cs = sc.scored_slice()
    return scl[rs, cs]


def test_share_counts_cloud_shadow_and_cirrus_over_the_scored_area_only():
    s = full()
    s[:10, :] = 9  # outer ring: ignored
    block = scored(s)
    block[:64] = 10  # thin cirrus counts as unusable (ADR 0014)
    block[64:96] = 3
    block[96:127] = 0  # no data
    out = scl.share(s)
    assert out["scl_nodata_share"] == pytest.approx(31 / 254)
    assert out["clear_scl"] == pytest.approx(1 - 96 / (254 - 31))
    assert np.isnan(scl.share(np.zeros((N, N), np.uint8))["clear_scl"])


def test_window_is_snapped_on_the_scl_files_own_grid(tmp_path, monkeypatch):
    n = 12000 // sc.RES_M
    p = tmp_path / "SCL.tif"
    profile = {"driver": "GTiff", "height": n, "width": n, "count": 1, "dtype": "uint8"}
    profile |= {"crs": "EPSG:32610", "transform": rasterio.transform.from_origin(ULX, ULY, 20, 20)}
    with rasterio.open(p, "w", **profile) as dst:
        dst.write(np.full((1, n, n), 4, np.uint8))
    monkeypatch.setattr(scl, "_vsi", lambda href: href)
    b = scl.scl_bounds(str(p), 505017.3, 4193981.9)
    assert tuple(b) == sc.snapped_bounds(ULX, ULY, 505017.3, 4193981.9)

    profile["transform"] = rasterio.transform.from_origin(ULX, ULY, 10, 10)
    with rasterio.open(tmp_path / "ten.tif", "w", **profile) as dst:
        dst.write(np.full((1, n, n), 4, np.uint8))
    with pytest.raises(ValueError, match="20 m grid"):
        scl.scl_bounds(str(tmp_path / "ten.tif"), 505017.3, 4193981.9)


def test_fetch_takes_the_fullest_granule_and_none_without_a_match(monkeypatch):
    cands = [{"collection": "c", "item": "empty", "href": "e"}]
    cands += [{"collection": "c", "item": "full", "href": "f"}]
    monkeypatch.setattr(sc, "scl_candidates", lambda uri, client: cands)
    monkeypatch.setattr(scl, "scl_bounds", lambda href, x, y: np.array([1.0, 2.0, 3.0, 4.0]))
    data = {"e": np.zeros((N, N), np.uint8), "f": full()}
    monkeypatch.setattr(sc, "read_scl", lambda href, bounds: data[href])
    w = scl.fetch(L1C, 0.0, 0.0)
    assert w.source["item"] == "full" and (w.scl == 4).all() and w.bounds[0] == 1.0

    monkeypatch.setattr(sc, "scl_candidates", lambda uri, client: [])
    assert scl.fetch(L1C, 0.0, 0.0) is None


def passes(*uris):
    n = len(uris)
    return pd.DataFrame(
        {
            "overpass_id": [f"o{i}" for i in range(n)],
            "site_id": ["s"] * n,
            "day": ["2025-06-01"] * n,
            "acquired_utc": pd.to_datetime(["2025-06-01T19:00Z"] * n),
            "scene_id": ["sc"] * n,
            "product_uri": list(uris),
            "platform": ["sentinel-2c"] * n,
            "baseline": ["N0511"] * n,
            "valid_frac": [0.4] * n,
            "x": [0.0] * n,
            "y": [0.0] * n,
        }
    )


def window13(path, scl):
    w = sc.Window13(
        dn=np.zeros((13, N, N), np.uint16),
        valid=np.ones((N, N), bool),
        scl=scl,
        bounds=np.array([ULX, ULY - 6000, ULX + 6000, ULY]),
        consts={"quantification": 10000.0},
        scl_source={"collection": "sentinel-2-c1-l2a", "item": "w13", "href": "h"},
    )
    return w.save(path)


def test_run_reuses_caches_and_lists_what_has_no_share(tmp_path, monkeypatch):
    old = tmp_path / "s2scl-20261101T000000Z"
    scl.SclWindow(full(9), np.zeros(4), {"item": "cached"}).save(scl.cache_file(old, "s", "a.SAFE"))
    windows = tmp_path / "s2windows-20261107T000000Z"
    window13(sc.cache_file(windows, "s", "b.SAFE"), full(8))  # full SCL: reused
    partial = full()
    scored(partial)[:10] = 0
    window13(sc.cache_file(windows, "s", "c.SAFE"), partial)  # partial: read again

    def fetch(uri, x, y, client):
        if uri == "e.SAFE":
            raise RuntimeError("Remote end closed connection without response")
        if uri == "d.SAFE":
            return None
        return scl.SclWindow(full(), np.zeros(4), {"collection": "c", "item": uri})

    monkeypatch.setattr(scl, "fetch", fetch)
    pull = tmp_path / "s2scl-20261108T000000Z"
    out, new = scl.run(
        passes("a.SAFE", "b.SAFE", "c.SAFE", "d.SAFE", "e.SAFE"),
        [old],
        [windows],
        pull,
        workers=2,
        client=object(),
    )
    out = out.set_index("product_uri")
    assert out.loc["a.SAFE", "fetch"] == "cached" and out.loc["a.SAFE", "valid_frac_site"] == 0.0
    assert out.loc["b.SAFE", "fetch"] == "window" and out.loc["b.SAFE", "scl_item"] == "w13"
    assert out.loc["c.SAFE", "fetch"] == "new" and out.loc["c.SAFE", "valid_frac_site"] == 1.0
    assert out.loc["d.SAFE", "site_source"] == scl.NO_L2A
    assert np.isnan(out.loc["d.SAFE", "valid_frac_site"])
    assert out.loc["e.SAFE", "site_source"] == scl.ERROR
    assert "Remote end closed" in out.loc["e.SAFE", "error"]
    assert (out["valid_frac"] == 0.4).all()  # the tile figure is kept
    assert new == [scl.cache_file(pull, "s", "c.SAFE")]  # no-match passes are not cached


def test_more_than_one_percent_no_data_gives_no_share():
    df = pd.DataFrame(
        {
            "fetch": ["new", "new", "cached"],
            "clear_scl": [0.9, 0.9, 0.2],
            "scl_nodata_share": [0.0, 0.02, 0.01],
        }
    )
    out = scl.site_shares(df)
    assert list(out["site_source"]) == [scl.SITE, scl.PARTIAL, scl.SITE]
    assert out["valid_frac_site"].tolist()[0] == 0.9 and np.isnan(out["valid_frac_site"][1])


def test_nothing_is_asked_of_earth_search_when_every_pass_is_cached(tmp_path, monkeypatch):
    import pystac_client

    def refuse(url):
        raise AssertionError("Earth Search opened")

    monkeypatch.setattr(pystac_client.Client, "open", staticmethod(refuse))
    old = tmp_path / "s2scl-20261101T000000Z"
    scl.SclWindow(full(), np.zeros(4), {"item": "c"}).save(scl.cache_file(old, "s", "a.SAFE"))
    out, new = scl.run(passes("a.SAFE"), [old], [], tmp_path / "s2scl-new")
    assert out.loc[0, "valid_frac_site"] == 1.0 and new == []


def project_on(tmp_path):
    from methanewatch.config import load_project

    base = load_project()
    paths = base.paths.model_copy(update={"raw": tmp_path / "raw", "interim": tmp_path / "interim"})
    return base.model_copy(update={"paths": paths})


def write_inputs(interim, *, days=("2025-06-01T19:00Z",), cloud=70.0):
    """One site inside one Sentinel-2 tile and one EMIT scene, seen on each of ``days``."""
    (interim / "footprints").mkdir(parents=True, exist_ok=True)
    x, y = ULX + 6000, ULY - 6000
    site = gpd.GeoSeries([box(x - 300, y - 300, x + 300, y + 300)], crs=sc.METRIC_CRS)
    gpd.GeoDataFrame({"site_id": ["s"]}, geometry=site.to_crs(4326)).to_parquet(
        interim / "sites.parquet"
    )
    tile = gpd.GeoSeries([box(ULX, ULY - 50000, ULX + 50000, ULY)], crs=sc.METRIC_CRS)
    n = len(days)
    stamps = [pd.Timestamp(d).strftime("%Y%m%dT%H%M%S") for d in days]
    gpd.GeoDataFrame(
        {
            "scene_id": [f"sc{i}" for i in range(n)],
            "instrument": "sentinel2",
            "acquired_utc": pd.to_datetime(list(days)),
            "valid_frac": 1 - cloud / 100,
            "product_uri": [L1C.replace("20250601T185921", st) for st in stamps],
            "platform": "sentinel-2c",
        },
        geometry=[tile.to_crs(4326).iloc[0]] * n,
        crs="EPSG:4326",
    ).to_parquet(interim / "footprints" / "sentinel2.parquet")
    gpd.GeoDataFrame(
        {"scene_id": ["g"], "instrument": "emit", "acquired_utc": pd.to_datetime([days[0]])},
        geometry=[tile.to_crs(4326).iloc[0]],
        crs="EPSG:4326",
    ).assign(valid_frac=0.5).to_parquet(interim / "footprints" / "emit.parquet")
    origin = gpd.GeoSeries(gpd.points_from_xy([x], [y]), crs=sc.METRIC_CRS).to_crs(4326)
    (interim / "plumes").mkdir(exist_ok=True)
    pd.DataFrame(
        {"plume_id": ["p1"], "source": "carbonmapper", "instrument": "emit",
         "acquired_utc": pd.to_datetime([days[0]]), "origin_lon": origin.x, "origin_lat": origin.y,
         "q_kg_hr": [600.0], "q_sigma_kg_hr": [150.0], "data_version": "v3e", "pull_id": "p"}
    ).to_parquet(interim / "plumes" / "carbonmapper.parquet")  # fmt: skip


def test_pull_covers_every_sentinel2_site_day_from_the_footprints(tmp_path, monkeypatch):
    project = project_on(tmp_path)
    interim, raw = tmp_path / "interim", tmp_path / "raw"
    write_inputs(interim, days=("2025-06-01T19:00Z", "2025-06-11T19:00Z"))
    seen = []

    def fetch(uri, x, y, client):
        seen.append(uri)
        return scl.SclWindow(full(), np.zeros(4), {"item": uri})

    monkeypatch.setattr(scl, "fetch", fetch)
    counts = scl.pull(project, workers=1, client=object())
    assert counts["passes"] == 2 and counts["new_windows"] == 2 and counts[scl.SITE] == 2
    table = pd.read_parquet(interim / scl.TABLE)
    assert set(table["overpass_id"]) == {"s:sentinel2:2025-06-01", "s:sentinel2:2025-06-11"}
    assert table["valid_frac"].tolist() == pytest.approx([0.3, 0.3])
    assert (table["valid_frac_site"] == 1.0).all()
    man = json.loads((raw / scl.SOURCE / counts["pull_id"] / "manifest.json").read_text())
    assert len(man["files"]) == 2 and man["params"]["n_passes"] == 2

    # A second run reads nothing new and writes no pull
    again = scl.pull(project, workers=1, client=object())
    assert again["new_windows"] == 0 and again["pull_id"] is None and len(seen) == 2
    assert len(list((raw / scl.SOURCE).iterdir())) == 1


def test_coverage_uses_the_site_share_for_sentinel2_and_keeps_the_tile_figure(tmp_path):
    from methanewatch.coverage import build
    from methanewatch.coverage.overpasses import apply_site_clear

    assert build.SITE_CLEAR == scl.TABLE
    project = project_on(tmp_path)
    ov = pd.DataFrame(
        {
            "overpass_id": ["s:sentinel2:a", "s:sentinel2:b", "s:sentinel2:c", "s:emit:a"],
            "site_id": "s",
            "instrument": ["sentinel2", "sentinel2", "sentinel2", "emit"],
            "acquired_utc": pd.to_datetime(["2025-06-01T19:00Z"] * 4),
            "coverage_frac": [1.0, 1.0, 0.5, 1.0],
            "valid_frac": [0.3, 0.9, 0.3, 0.5],
            "usable": [False, True, False, False],
            "coverage_source": ["s2-scene"] * 3 + ["cmr-granule"],
        }
    )
    table = pd.DataFrame(
        {
            "overpass_id": ["s:sentinel2:a", "s:sentinel2:b", "s:sentinel2:c", "s:emit:a"],
            "valid_frac_site": [0.95, np.nan, 0.95, 0.0],
        }
    )
    out = apply_site_clear(ov, table, project.coverage).set_index("overpass_id")
    a, b, c, e = (
        out.loc[k] for k in ["s:sentinel2:a", "s:sentinel2:b", "s:sentinel2:c", "s:emit:a"]
    )
    assert a["valid_frac"] == 0.95 and a["valid_frac_tile"] == 0.3 and a["usable"]
    assert a["valid_frac_source"] == "site-sen2cor"
    assert b["valid_frac"] == 0.9 and b["valid_frac_source"] == "tile" and b["usable"]
    assert c["valid_frac"] == 0.95 and not c["usable"]  # too little of the site in view
    assert e["valid_frac"] == 0.5 and e["valid_frac_source"] == "scene"  # EMIT left as it is
    assert np.isnan(e["valid_frac_tile"]) and not e["usable"]

    no_table = apply_site_clear(ov, None, project.coverage)
    assert (
        no_table.loc[no_table["instrument"] == "sentinel2", "valid_frac_source"] == "tile"
    ).all()
    assert no_table["usable"].tolist() == ov["usable"].tolist()


def test_detections_count_the_same_passes_as_the_overpass_table(tmp_path, monkeypatch):
    from methanewatch.coverage import build

    project = project_on(tmp_path)
    interim = tmp_path / "interim"
    write_inputs(interim, cloud=70.0)  # the tile rule calls the pass unusable
    monkeypatch.setattr(
        scl, "fetch", lambda uri, x, y, client: scl.SclWindow(full(), np.zeros(4), {"item": "i"})
    )
    scl.pull(project, workers=1, client=object())
    counts = build.build(project)
    ov = pd.read_parquet(interim / "overpasses.parquet").set_index("instrument")
    det = pd.read_parquet(interim / "detections.parquet")
    assert ov.loc["sentinel2", "usable"] and ov.loc[
        "sentinel2", "valid_frac_tile"
    ] == pytest.approx(0.3)
    assert "s:sentinel2:2025-06-01" in set(det["overpass_id"])
    assert counts["s2_site_share"] == 1 and counts["s2_tile_fallback"] == 0


def test_refresh_reads_sen2cor_before_coverage_and_a_failure_keeps_the_tile_figure(
    tmp_path, monkeypatch
):
    from methanewatch import refresh
    from methanewatch.ingest import pipeline

    project = project_on(tmp_path)
    interim = tmp_path / "interim"
    write_inputs(interim)
    for name in ("ingest_emit", "ingest_sentinel2", "ingest_carbonmapper"):
        monkeypatch.setattr(pipeline, name, lambda *a: {"ok": 1})
    monkeypatch.setattr(refresh, "_sites", lambda project: {"sites": 1})
    monkeypatch.setattr(refresh, "_features", lambda project: {"sites": 1})

    def down(uri, x, y, client):
        raise ConnectionError("Earth Search is down")

    monkeypatch.setattr(scl, "fetch", down)
    import pystac_client

    monkeypatch.setattr(pystac_client.Client, "open", staticmethod(lambda url: object()))
    m = refresh.run(project, csv=False)
    steps = m["steps"]
    assert list(steps).index("s2_site_clear") < list(steps).index("coverage")
    assert (
        not steps["s2_site_clear"]["ok"] and "could not be read" in steps["s2_site_clear"]["error"]
    )
    assert steps["coverage"]["ok"] and steps["coverage"]["s2_tile_fallback"] == 1
    assert not m["ok"]
    ov = pd.read_parquet(interim / "overpasses.parquet").set_index("instrument")
    assert ov.loc["sentinel2", "valid_frac_source"] == "tile"

    skipped = refresh.run(project, skip=["sentinel2"], csv=False)
    assert "s2_site_clear" not in skipped["steps"]


def test_cli_lists_site_clear():
    from methanewatch.cli import app

    res = CliRunner().invoke(app, ["s2", "--help"])
    assert "site-clear" in res.output
