"""Air district outlines for the project's regions, with no network.

``fixtures/carb_air_districts_box.geojson`` was recorded on 2026-11-20 from the same CARB
layer and box query that ``mw ingest air-districts`` uses for the Bay Area region, plus
``maxAllowableOffset=0.01`` and ``geometryPrecision=3`` so the server returns coarse (about
1 km) outlines in 17 KB.
"""

import json
from pathlib import Path

import geopandas as gpd
import pytest

from methanewatch import datasets
from methanewatch.ingest import air_districts
from methanewatch.provenance import sha256_file
from methanewatch.sites import registry

FX = Path(__file__).parent / "fixtures" / "carb_air_districts_box.geojson"
BAY = (-123.64, 36.89, -121.20, 38.87)


def test_query_asks_for_every_district_meeting_the_box():
    q = air_districts.query(BAY)
    assert q["geometry"] == "-123.64,36.89,-121.2,38.87"
    assert q["geometryType"] == "esriGeometryEnvelope"
    assert q["spatialRel"] == "esriSpatialRelIntersects"
    assert (q["where"], q["outFields"]) == ("1=1", "NAME,DIS")
    assert (q["inSR"], q["outSR"]) == ("4326", "4326")


def test_outlines_from_the_recorded_answer():
    d = air_districts.outlines(FX)
    assert d["DIS"].tolist() == ["BA", "FRU", "LAK", "MBU", "MEN", "NS", "PLA", "SAC", "SJU", "YS"]
    names = d.set_index("DIS")["NAME"]
    assert names["BA"] == "Bay Area" and names["SJU"] == "San Joaquin Valley Unified"
    assert (d["boundary_as_of"] == "2004-03").all()
    assert d.crs == "EPSG:4326" and d.is_valid.all()


def test_outlines_refuse_an_error_or_a_cut_answer(tmp_path):
    bad = tmp_path / "bad.geojson"
    bad.write_text(json.dumps({"error": {"code": 400, "message": "Invalid query"}}))
    with pytest.raises(ValueError, match="Invalid query"):
        air_districts.outlines(bad)
    cut = json.loads(FX.read_text())
    cut["exceededTransferLimit"] = True
    bad.write_text(json.dumps(cut))
    with pytest.raises(ValueError, match="cut short"):
        air_districts.outlines(bad)


def test_pull_writes_a_manifest_and_latest_finds_it(tmp_path, monkeypatch):
    asked = []

    def fake_get(client, url):
        asked.append(url)
        return FX.read_bytes()

    monkeypatch.setattr(air_districts, "_get", fake_get)
    assert air_districts.latest(tmp_path) is None
    pull_dir = air_districts.pull(tmp_path, BAY)
    assert pull_dir.parent == tmp_path / "air-districts"
    assert len(asked) == 1 and "geometry=-123.64,36.89,-121.2,38.87" in asked[0]
    manifest = json.loads((pull_dir / "manifest.json").read_text())
    assert manifest["source"] == "air-districts" and manifest["n_records"] == 10
    assert manifest["params"]["district_as_of"] == "2004-03"
    assert manifest["files"] == {air_districts.FILE: sha256_file(pull_dir / air_districts.FILE)}
    assert air_districts.latest(tmp_path) == pull_dir / air_districts.FILE


def test_a_failed_pull_leaves_no_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(air_districts, "_get", lambda client, url: b'{"features": []}')
    with pytest.raises(ValueError, match="no district"):
        air_districts.pull(tmp_path, BAY)
    assert air_districts.latest(tmp_path) is None


def test_dataset_file_is_what_the_registry_reads(tmp_path):
    raw = tmp_path / "raw"
    pull = raw / "air-districts" / "air-districts-20990101T000000Z"
    pull.mkdir(parents=True)
    (pull / air_districts.FILE).write_bytes(FX.read_bytes())
    (pull / "manifest.json").write_text(json.dumps({"pull_id": pull.name}))
    out = tmp_path / "datasets" / "boundaries"

    assert datasets.build_air_districts(raw, out) == {"air_districts": 10}

    assert out / registry.DISTRICTS_FILE.name == out / "air_districts.geojson"
    d = registry.read_districts(out / "air_districts.geojson")
    assert list(d.columns) == ["NAME", "DIS", "geometry"] and len(d) == 10
    assert (out / "pulls" / f"{pull.name}.json").exists()
    # A point in San Jose falls in the Bay Area district, even on the coarse outline
    here = gpd.GeoSeries.from_xy([-121.89], [37.34], crs="EPSG:4326")
    assert d[d.contains(here.iloc[0])]["NAME"].tolist() == ["Bay Area"]


def test_dataset_build_without_a_pull(tmp_path):
    with pytest.raises(FileNotFoundError, match="mw ingest air-districts"):
        datasets.build_air_districts(tmp_path, tmp_path / "out")
