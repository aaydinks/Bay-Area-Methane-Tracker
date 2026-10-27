"""Boundary pull and tidy outputs, with no network.

``fixtures/carb_air_district_ba.geojson`` was recorded on 2026-10-27 from the same CARB
layer and filter that ``mw ingest boundaries`` uses, plus ``maxAllowableOffset=0.01`` and
``geometryPrecision=3`` so the server returns a coarse (about 1 km) outline of 5 KB.
The county shapefile here is made up.
"""

import json
import zipfile
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import box

from methanewatch import datasets
from methanewatch.ingest import boundaries
from methanewatch.provenance import sha256_file

FX = Path(__file__).parent / "fixtures"


def _fake_download(client, url, path):
    if url == boundaries.sources()[boundaries.DISTRICT_FILE]:
        path.write_bytes((FX / "carb_air_district_ba.geojson").read_bytes())
    else:
        path.write_bytes(url.encode())


def test_pull_writes_manifest_with_sha256(tmp_path, monkeypatch):
    monkeypatch.setattr(boundaries, "_download", _fake_download)
    pull_dir = boundaries.pull(tmp_path)
    assert pull_dir.parent == tmp_path / "boundaries"
    manifest = json.loads((pull_dir / "manifest.json").read_text())
    assert manifest["source"] == "boundaries"
    assert manifest["pull_id"] == pull_dir.name
    assert manifest["params"]["files"] == boundaries.sources()
    assert manifest["params"]["district_as_of"] == "2004-03"
    assert set(manifest["files"]) == set(boundaries.sources())
    assert len(manifest["files"]) == 14  # counties, places, tracts, roads, 9 x water, district
    for name, digest in manifest["files"].items():
        assert digest == sha256_file(pull_dir / name)
    assert manifest["n_records"] == 14


def test_pull_stops_when_carb_sends_an_error(tmp_path, monkeypatch):
    fetched = []

    def error_download(client, url, path):
        fetched.append(url)
        path.write_text(json.dumps({"error": {"code": 400, "message": "Invalid query"}}))

    monkeypatch.setattr(boundaries, "_download", error_download)
    with pytest.raises(ValueError, match="Invalid query"):
        boundaries.pull(tmp_path)
    assert len(fetched) == 1  # the Census files were never requested
    assert not list((tmp_path / "boundaries").glob("*/manifest.json"))


def test_district_from_recorded_carb_response():
    d = boundaries.district(FX / "carb_air_district_ba.geojson")
    assert len(d) == 1
    row = d.iloc[0]
    assert (row["NAME"], row["DIS"]) == ("Bay Area", "BA")
    assert row["boundary_as_of"] == "2004-03"
    assert row["caveat"] == "check against current BAAQMD"
    assert d.crs == "EPSG:4326"
    assert d.is_valid.all()
    minx, miny, maxx, maxy = d.total_bounds
    assert minx >= -123.64 and maxx <= -121.20 and miny >= 36.89 and maxy <= 38.87


def _county_zip(raw_pull: Path) -> None:
    rows = [("06", fips, f"County {fips}") for fips in boundaries.COUNTY_FIPS]
    rows += [("06", "067", "Sacramento"), ("32", "001", "Churchill")]
    gdf = gpd.GeoDataFrame(
        {
            "STATEFP": [r[0] for r in rows],
            "COUNTYFP": [r[1] for r in rows],
            "GEOID": [r[0] + r[1] for r in rows],
            "NAME": [r[2] for r in rows],
            "ALAND": 1,
        },
        geometry=[box(-123 + 0.1 * i, 37.5, -122.9 + 0.1 * i, 37.6) for i in range(len(rows))],
        crs="EPSG:4269",
    )
    shp = raw_pull / "shp"
    shp.mkdir()
    gdf.to_file(shp / "cb_2025_us_county_500k.shp")
    with zipfile.ZipFile(raw_pull / boundaries.COUNTY_FILE, "w") as z:
        for f in shp.iterdir():
            z.write(f, f.name)


def test_build_boundaries_writes_tidy_geojson(tmp_path):
    raw = tmp_path / "raw"
    pull = raw / "boundaries" / "boundaries-20990101T000000Z"
    pull.mkdir(parents=True)
    _county_zip(pull)
    fixture = (FX / "carb_air_district_ba.geojson").read_bytes()
    (pull / boundaries.DISTRICT_FILE).write_bytes(fixture)
    (pull / "manifest.json").write_text(json.dumps({"pull_id": pull.name}))
    out = tmp_path / "datasets" / "boundaries"

    counts = datasets.build_boundaries(raw, out)

    assert counts == {"boundaries_counties": 9, "boundaries_air_district": 1}
    counties = gpd.read_file(out / "counties_2025.geojson")
    assert list(counties.columns) == ["GEOID", "COUNTYFP", "NAME", "geometry"]
    assert counties["COUNTYFP"].tolist() == list(boundaries.COUNTY_FIPS)
    assert counties.crs == "EPSG:4326"
    assert counties.is_valid.all()
    district = json.loads((out / "air_district_bay_area.geojson").read_text())
    assert len(district["features"]) == 1
    assert district["features"][0]["properties"] == {
        "NAME": "Bay Area",
        "DIS": "BA",
        "boundary_as_of": "2004-03",
        "caveat": "check against current BAAQMD",
    }
    assert (out / "pulls" / f"{pull.name}.json").exists()


def test_build_boundaries_without_a_pull(tmp_path):
    with pytest.raises(FileNotFoundError, match="mw ingest boundaries"):
        datasets.build_boundaries(tmp_path, tmp_path / "out")
