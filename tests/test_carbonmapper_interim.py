"""Carbon Mapper scenes and plumes -> interim tables, on synthetic rows (no real data)."""

import json

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import box, mapping

from methanewatch import datasets, schemas
from methanewatch.attribution import attribute_plumes
from methanewatch.ingest import carbonmapper


def _item(scene_id, platform, when, version="v3e"):
    return {
        "id": scene_id,
        "geometry": mapping(box(-122.1, 37.4, -121.9, 37.5)),
        "properties": {"datetime": when, "platform": platform, "version": version},
    }


def test_load_scenes_merges_collections_and_footprints_drop_emit(tmp_path):
    (tmp_path / "scenes_l2b-ch4-mf-v1.json").write_text(
        json.dumps([_item("g1", "gao", "2023-03-27T20:01:00Z", "v1")])
    )
    (tmp_path / "scenes_l2b-ch4-mfa-v3e.json").write_text(
        json.dumps(
            [
                _item("t1", "tan", "2025-05-01T19:00:00+00:00"),
                _item("t1", "tan", "2025-05-01T19:00:00+00:00"),  # same scene twice
                _item("e1", "iss", "2024-08-07T17:28:38Z"),
                _item("a1", "av3", "2024-04-08T21:26:19Z"),
            ]
        )
    )
    scenes = carbonmapper.load_scenes(tmp_path)
    assert sorted(scenes["scene_id"]) == ["a1", "e1", "g1", "t1"]

    fp = carbonmapper.footprints(scenes).set_index("scene_id")
    assert "e1" not in fp.index  # EMIT passes come from NASA's scene list
    assert fp.loc["g1", "instrument"] == "aircraft"
    assert fp.loc["a1", "instrument"] == "aircraft"
    assert fp.loc["t1", "instrument"] == "tanager1"
    assert (fp["valid_frac"] == 1.0).all()
    assert str(fp["acquired_utc"].dt.tz) == "UTC"
    assert fp.loc["g1", "data_version"] == "v1"


def _plume_rows():
    return pd.DataFrame(
        {
            "plume_id": ["GAO-1", "tan-1", "emi-1"],
            "datetime": ["2023-03-27T20:01:00Z", "2025-05-01T19:00:00Z", "2024-08-07T17:28:38Z"],
            "instrument": ["GAO", "tan", "emi"],
            "platform": ["Global Airborne Observatory", "Tanager", "ISS"],
            "plume_longitude": [-121.941, -121.941, -122.5],
            "plume_latitude": [37.459, 37.459, 38.2],
            "emission_auto": [450.0, None, 900.0],
            "emission_uncertainty_auto": [120.0, None, 300.0],
            "emission_version": ["v1", "v3e", "v3d"],
            "ipcc_sector": ["Solid Waste (6A)"] * 3,
        }
    )


def test_plumes_map_instruments_and_keep_versions():
    out = carbonmapper.plumes(_plume_rows(), "carbonmapper-test").set_index("plume_id")
    assert out.loc["GAO-1", "instrument"] == "aircraft"
    assert out.loc["tan-1", "instrument"] == "tanager1"
    assert out.loc["emi-1", "instrument"] == "emit"
    assert out.loc["GAO-1", "data_version"] == "v1"
    assert pd.isna(out.loc["tan-1", "q_kg_hr"])  # no published rate: reported, not modelled
    assert str(out["acquired_utc"].dt.tz) == "UTC"
    assert (out["source"] == "carbonmapper").all()


def test_plumes_pass_schema_after_attribution():
    plumes = carbonmapper.plumes(_plume_rows(), "carbonmapper-test")
    site = gpd.GeoDataFrame(
        {"site_id": ["newby"]}, geometry=[box(-121.945, 37.455, -121.937, 37.463)], crs="EPSG:4326"
    )
    nb = gpd.GeoDataFrame({"name": []}, geometry=[], crs="EPSG:4326")
    out = attribute_plumes(
        plumes, site, nb, buffer_m=500, search_radius_m=5000, metric_crs="EPSG:32610"
    )
    schemas.plumes.validate(out)
    assert out.set_index("plume_id").loc["GAO-1", "attribution"] == "inside"


def test_plumes_refuse_unknown_codes_and_repeats():
    rows = _plume_rows()
    with pytest.raises(ValueError, match="unknown"):
        carbonmapper.plumes(rows.assign(instrument=["GAO", "xyz", "emi"]), "p")
    with pytest.raises(ValueError, match="more than once"):
        carbonmapper.plumes(pd.concat([rows, rows.iloc[:1]]), "p")


def test_no_emit_scene_inside_the_outage():
    # EMIT was off from 2022-09-13 to 2023-01-06. No scene there means the outage
    # already counts as "no look", not as a look with no plume.
    scenes = gpd.read_file("datasets/emit/scenes.geojson")
    assert not datasets.in_emit_outage(pd.to_datetime(scenes["acquired_utc"], utc=True)).any()
