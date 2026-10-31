"""Repeatable refreshes: merged pulls, skipped partial pulls, and a full refresh run
on a small fixture project with the network steps replaced (no network)."""

import json
import warnings

import geopandas as gpd
import httpx
import pandas as pd
import pytest
from shapely.geometry import box, mapping

from methanewatch import refresh
from methanewatch.config import load_project
from methanewatch.ingest import carbonmapper, pipeline

UTM = "EPSG:32610"


def utm_box(x0, y0, x1, y1):
    return gpd.GeoSeries([box(x0, y0, x1, y1)], crs=UTM).to_crs("EPSG:4326").iloc[0]


def _plume_csv(path, rows):
    base = {
        "instrument": "tan",
        "platform": "Tanager",
        "plume_longitude": -121.94,
        "plume_latitude": 37.46,
        "emission_uncertainty_auto": 50.0,
        "ipcc_sector": "Solid Waste (6A)",
    }
    pd.DataFrame([{**base, **r} for r in rows]).to_csv(path, index=False)


def _pull(root, name, rows, scenes=(), finished=True):
    d = root / "carbonmapper" / name
    d.mkdir(parents=True)
    _plume_csv(d / "plumes_all-sectors.csv", rows)
    items = [
        {
            "id": sid,
            "geometry": mapping(box(-122.0, 37.4, -121.9, 37.5)),
            "properties": {"datetime": when, "platform": "tan", "version": "v3e"},
        }
        for sid, when in scenes
    ]
    (d / "scenes_l2b-ch4-mfa-v3e.json").write_text(json.dumps(items))
    if finished:
        (d / "manifest.json").write_text("{}")
    return d


def test_merged_pulls_keep_newest_version_and_older_plumes(tmp_path):
    _pull(
        tmp_path,
        "carbonmapper-20261001T000000Z",
        [
            {"plume_id": "p1", "datetime": "2025-05-01T19:00:00Z",
             "modified": "2025-06-01T00:00:00Z", "emission_auto": 300.0, "emission_version": "v3d"},
            {"plume_id": "p2", "datetime": "2023-03-01T19:00:00Z",
             "modified": "2023-04-01T00:00:00Z", "emission_auto": 500.0, "emission_version": "v3"},
        ],
        scenes=[("s1", "2025-05-01T19:00:00Z")],
    )  # fmt: skip
    # A later pull with a shorter window: p1 reprocessed, p2 not in the window
    _pull(
        tmp_path,
        "carbonmapper-20261101T000000Z",
        [{"plume_id": "p1", "datetime": "2025-05-01T19:00:00Z", "modified": "2026-10-20T00:00:00Z",
          "emission_auto": 350.0, "emission_version": "v3e"}],
        scenes=[("s1", "2025-05-01T19:00:00Z"), ("s2", "2026-10-01T19:00:00Z")],
    )  # fmt: skip
    # An unfinished pull (no manifest) is ignored
    _pull(tmp_path, "carbonmapper-20261201T000000Z", [], finished=False)

    pulls = carbonmapper.finished_pulls(tmp_path)
    assert [p.name for p in pulls] == [
        "carbonmapper-20261001T000000Z",
        "carbonmapper-20261101T000000Z",
    ]
    assert carbonmapper.latest_pull(tmp_path).name == "carbonmapper-20261101T000000Z"

    plumes = carbonmapper.plumes(carbonmapper.merged_plumes(pulls)).set_index("plume_id")
    assert sorted(plumes.index) == ["p1", "p2"]  # p2 survives the shorter window
    assert plumes.loc["p1", "data_version"] == "v3e"
    assert plumes.loc["p1", "q_kg_hr"] == 350.0
    assert plumes.loc["p1", "pull_id"] == "carbonmapper-20261101T000000Z"
    scenes = carbonmapper.merged_scenes(pulls)
    assert sorted(scenes["scene_id"]) == ["s1", "s2"]


def test_expired_token_falls_back_to_no_token():
    seen = []

    def handler(request):
        seen.append("Authorization" in request.headers)
        if "Authorization" in request.headers:
            return httpx.Response(401, json={"detail": "Given token not valid"})
        return httpx.Response(200, text="plume_id\n")

    client = httpx.Client(transport=httpx.MockTransport(handler), headers={"Authorization": "x"})
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        r = carbonmapper._get(client, "/catalog/plume-csv", [])
    assert r.status_code == 200
    assert seen == [True, False]
    assert "Authorization" not in client.headers  # later requests skip the token too
    assert any("token" in str(w.message) for w in caught)


def test_only_temporary_errors_are_retried():
    def err(code):
        req = httpx.Request("GET", "https://x")
        return httpx.HTTPStatusError("e", request=req, response=httpx.Response(code, request=req))

    assert carbonmapper._transient(err(503))
    assert carbonmapper._transient(err(429))
    assert carbonmapper._transient(httpx.ConnectError("down"))
    assert not carbonmapper._transient(err(404))
    assert not carbonmapper._transient(err(401))


def _fixture_project(tmp_path):
    reg, interim = tmp_path / "registry", tmp_path / "interim"
    reg.mkdir()
    (interim / "footprints").mkdir(parents=True)
    pd.DataFrame(
        {"site_id": ["a", "b"], "tier": "pilot", "status": ["", "closed"],
         "polygon_source": ["provisional 500 m buffer", "permit map"]}
    ).to_csv(reg / "sites.csv", index=False)  # fmt: skip
    pd.DataFrame({"site_id": ["a", "b"], "ghgrp_facility_id": ["1", ""]}).to_csv(
        reg / "operator_crosswalk.csv", index=False
    )
    gpd.GeoDataFrame(
        {"site_id": ["a", "b"], "part": "boundary"},
        geometry=[
            utm_box(590000, 4146000, 591000, 4147000),
            utm_box(600000, 4146000, 601000, 4147000),
        ],
        crs="EPSG:4326",
    ).to_file(reg / "sites.geojson", driver="GeoJSON")
    base = load_project()
    paths = base.paths.model_copy(
        update={"registry": reg, "raw": tmp_path / "raw", "interim": interim,
                "datasets": tmp_path / "datasets", "reports": tmp_path / "reports"}
    )  # fmt: skip
    return base.model_copy(update={"paths": paths}), interim


def test_refresh_survives_a_failed_source_and_repeats_identically(tmp_path, monkeypatch):
    project, interim = _fixture_project(tmp_path)
    days = pd.date_range("2025-01-05T18:00Z", periods=10, freq="14D")
    calls = []

    def fake_emit(project, bbox, start, end):
        calls.append(("emit", bbox, start, end))
        gpd.GeoDataFrame(
            {"scene_id": [f"s{i}" for i in range(10)], "instrument": "emit",
             "acquired_utc": days, "valid_frac": 0.95},
            geometry=[utm_box(585000, 4140000, 605000, 4150000)] * 10,
            crs="EPSG:4326",
        ).to_parquet(interim / "footprints" / "emit.parquet")  # fmt: skip
        return {"emit_scenes": 10}

    def down(*args):
        raise httpx.ConnectError("source is down")

    def rebuild(project):
        origin = gpd.GeoSeries(gpd.points_from_xy([590500], [4146500]), crs=UTM).to_crs(4326)
        (interim / "plumes").mkdir(exist_ok=True)
        pd.DataFrame(
            {"plume_id": ["p1"], "source": "carbonmapper", "instrument": "emit",
             "acquired_utc": [days[2]], "origin_lon": origin.x, "origin_lat": origin.y,
             "q_kg_hr": [600.0], "q_sigma_kg_hr": [150.0], "data_version": "v3e", "pull_id": "old"}
        ).to_parquet(interim / "plumes" / "carbonmapper.parquet")  # fmt: skip
        return {"plumes": 1}

    monkeypatch.setattr(pipeline, "ingest_emit", fake_emit)
    monkeypatch.setattr(pipeline, "ingest_sentinel2", down)
    monkeypatch.setattr(pipeline, "ingest_carbonmapper", down)
    monkeypatch.setattr(pipeline, "write_carbonmapper", rebuild)

    first = refresh.run(project)
    det1 = pd.read_parquet(interim / "detections.parquet")
    second = refresh.run(project)
    det2 = pd.read_parquet(interim / "detections.parquet")

    # The configured window and area are used every time
    ing = project.ingest
    assert calls[0][1:3] == (ing.bbox, ing.start)
    assert not first["ok"]
    steps = first["steps"]
    assert not steps["sentinel2"]["ok"] and "source is down" in steps["sentinel2"]["error"]
    assert steps["carbonmapper_rebuild"]["ok"]  # tables rebuilt from earlier pulls
    assert steps["sites"]["provisional_outlines"] == ["a"]
    assert steps["coverage"]["detections"] == 1
    assert steps["features"]["sites"] == 2
    pd.testing.assert_frame_equal(det1, det2)
    assert (interim / "csv" / "detections.csv").exists()
    latest = json.loads((interim / "refresh" / "latest.json").read_text())
    assert latest["run_id"] == second["run_id"]
    assert len(list((interim / "refresh").glob("refresh-*.json"))) == 2


def test_refresh_rejects_unknown_sources(tmp_path):
    project, _ = _fixture_project(tmp_path)
    with pytest.raises(ValueError, match="unknown sources"):
        refresh.run(project, skip=["landsat"])
