import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point, box

from methanewatch.sites import registry

UTM = "EPSG:32610"
BAY = (-123.64, 36.89, -121.20, 38.87)


def utm_box(x0, y0, x1, y1):
    return gpd.GeoSeries([box(x0, y0, x1, y1)], crs=UTM).to_crs("EPSG:4326").iloc[0]


def write_registry(tmp_path, polys):
    pd.DataFrame({"site_id": ["a", "b"], "name": ["A", "B"], "tier": ["pilot", "screen"]}).to_csv(
        tmp_path / "sites.csv", index=False
    )
    gpd.GeoDataFrame(
        pd.DataFrame(polys, columns=["site_id", "part", "geometry"]),
        geometry="geometry",
        crs="EPSG:4326",
    ).to_file(tmp_path / "sites.geojson", driver="GeoJSON")


def test_build_registry(tmp_path):
    write_registry(
        tmp_path,
        [
            ("a", "boundary", utm_box(590000, 4146000, 591000, 4147000)),
            ("a", "working_face", utm_box(590200, 4146200, 590400, 4146400)),
            ("b", "boundary", utm_box(600000, 4146000, 601000, 4147000)),
        ],
    )
    sites = registry.build_registry(tmp_path, tmp_path / "out", region_bbox=BAY)
    assert sorted(sites["site_id"]) == ["a", "b"]
    assert sites.set_index("site_id").loc["a", "working_face_geom"].startswith("POLYGON")
    assert (tmp_path / "out" / "sites.parquet").exists()
    assert registry.missing_polygons(tmp_path) == []


def test_registry_rejects_overlaps_and_far_away_polygons(tmp_path):
    write_registry(
        tmp_path,
        [
            ("a", "boundary", utm_box(590000, 4146000, 591000, 4147000)),
            ("b", "boundary", utm_box(590500, 4146000, 591500, 4147000)),
        ],
    )
    with pytest.raises(ValueError, match="overlap"):
        registry.build_registry(tmp_path, tmp_path / "out", region_bbox=BAY)

    write_registry(tmp_path, [("a", "boundary", box(-100, 40, -99.9, 40.1))])
    with pytest.raises(ValueError, match="outside the project's regions"):
        registry.build_registry(tmp_path, tmp_path / "out", region_bbox=BAY)


def test_registry_rejects_a_site_east_of_utm_zone_10(tmp_path):
    # Inside a box that reaches too far east, so only the zone guard can catch it
    wide = (-123.64, 36.89, -119.0, 38.87)
    write_registry(tmp_path, [("a", "boundary", box(-119.6, 37.0, -119.5, 37.1))])
    with pytest.raises(ValueError, match="east of 120°W"):
        registry.build_registry(tmp_path, tmp_path / "out", region_bbox=wide)
    # A metric CRS other than UTM 10N has no such limit
    sites = registry.build_registry(
        tmp_path, tmp_path / "out", region_bbox=wide, metric_crs="EPSG:3310"
    )
    assert list(sites["site_id"]) == ["a"]


def test_registry_box_has_a_small_margin(tmp_path):
    # Just outside the regions' box but inside the margin: accepted
    write_registry(tmp_path, [("a", "boundary", box(-121.21, 38.88, -121.19, 38.90))])
    assert len(registry.build_registry(tmp_path, tmp_path / "out", region_bbox=BAY)) == 1


def test_missing_polygons_without_geojson(tmp_path):
    pd.DataFrame({"site_id": ["a", "b"]}).to_csv(tmp_path / "sites.csv", index=False)
    assert registry.missing_polygons(tmp_path) == ["a", "b"]


def test_screening_buffer():
    pts = gpd.GeoDataFrame({"site_id": ["x"]}, geometry=[Point(-122.0, 37.5)], crs="EPSG:4326")
    out = registry.screening_polygons(pts, buffer_m=750).to_crs(UTM)
    assert out.geometry.area.iloc[0] == pytest.approx(3.1416 * 750**2, rel=0.01)


# --- region, SWIS number and air district (ADR 0018) ---------------------------------------

REGIONS = {"Santa Clara": "bay-area", "Solano": "bay-area", "San Joaquin": "north-valley"}
A = ("a", "boundary", utm_box(590000, 4146000, 591000, 4147000))
B = ("b", "boundary", utm_box(600000, 4146000, 601000, 4147000))


def write_sites(tmp_path, rows, polys=(A, B)):
    """``rows`` are dicts of ``sites.csv`` columns; ``site_id`` a and b get the two boxes."""
    pd.DataFrame(rows).to_csv(tmp_path / "sites.csv", index=False)
    gpd.GeoDataFrame(
        pd.DataFrame(list(polys), columns=["site_id", "part", "geometry"]),
        geometry="geometry",
        crs="EPSG:4326",
    ).to_file(tmp_path / "sites.geojson", driver="GeoJSON")


def districts():
    """Two made-up districts that meet at x = 595 km, so site a is in West and b in East."""
    return gpd.GeoDataFrame(
        {"NAME": ["West", "East"], "DIS": ["W", "E"]},
        geometry=[box(500000, 4100000, 595000, 4200000), box(595000, 4100000, 700000, 4200000)],
        crs=UTM,
    ).to_crs("EPSG:4326")


def test_a_built_registry_always_has_the_id_columns(tmp_path):
    write_registry(tmp_path, [A, B])
    sites = registry.build_registry(tmp_path, tmp_path / "out", region_bbox=BAY)
    for col in registry.ID_COLUMNS:
        assert (sites[col] == "").all()
    assert not sites["air_district_confirmed"].any()


def test_region_comes_from_the_county_and_a_different_one_is_refused(tmp_path):
    rows = [
        {"site_id": "a", "name": "A", "county": "Santa Clara", "region": ""},
        {"site_id": "b", "name": "B", "county": "San Joaquin", "region": "north-valley"},
    ]
    write_sites(tmp_path, rows)
    sites = registry.build_registry(
        tmp_path, tmp_path / "out", region_bbox=BAY, county_region=REGIONS
    )
    assert sites.set_index("site_id")["region"].to_dict() == {
        "a": "bay-area",
        "b": "north-valley",
    }

    rows[1]["region"] = "bay-area"
    rows[0]["county"] = "Fresno"
    write_sites(tmp_path, rows)
    with pytest.raises(ValueError) as err:
        registry.build_registry(tmp_path, tmp_path / "out", region_bbox=BAY, county_region=REGIONS)
    assert "a: county Fresno is in no region" in str(err.value)
    assert "b: region bay-area but San Joaquin County is in north-valley" in str(err.value)


def test_swis_numbers_are_checked_for_form_and_reuse(tmp_path):
    rows = [
        {"site_id": "a", "name": "A", "swis_number": "43-AN-0003"},
        {"site_id": "b", "name": "B", "swis_number": ""},
    ]
    write_sites(tmp_path, rows)
    sites = registry.build_registry(tmp_path, tmp_path / "out", region_bbox=BAY)
    assert sites.set_index("site_id")["swis_number"].to_dict() == {"a": "43-AN-0003", "b": ""}

    rows[1]["swis_number"] = "3388"
    write_sites(tmp_path, rows)
    with pytest.raises(ValueError, match="b: swis_number 3388 is not of the form"):
        registry.build_registry(tmp_path, tmp_path / "out", region_bbox=BAY)

    rows[1]["swis_number"] = "43-AN-0003"
    write_sites(tmp_path, rows)
    with pytest.raises(ValueError, match="used by more than one site"):
        registry.build_registry(tmp_path, tmp_path / "out", region_bbox=BAY)


def test_the_old_facility_id_column_name_is_refused(tmp_path):
    write_sites(tmp_path, [{"site_id": "a", "name": "A", "baaqmd_facility_id": ""}], polys=(A,))
    with pytest.raises(ValueError, match="rename column baaqmd_facility_id"):
        registry.build_registry(tmp_path, tmp_path / "out", region_bbox=BAY)


def test_air_district_is_read_from_the_outlines_and_stays_unconfirmed(tmp_path):
    write_sites(tmp_path, [{"site_id": "a", "name": "A"}, {"site_id": "b", "name": "B"}])
    sites = registry.build_registry(
        tmp_path, tmp_path / "out", region_bbox=BAY, districts=districts()
    ).set_index("site_id")
    assert sites["air_district"].to_dict() == {"a": "West", "b": "East"}
    assert not sites["air_district_confirmed"].any()
    # a's east edge is at 591 km and b's west edge at 600 km; the districts meet at 595 km
    assert sites["air_district_edge_m"]["a"] == pytest.approx(4000, abs=20)
    assert sites["air_district_edge_m"]["b"] == pytest.approx(5000, abs=20)
    notes = registry.district_notes(sites.reset_index())
    assert notes == ["air district of 2 site(s) is read from CARB's 2004 outlines, unconfirmed"]


def test_a_checked_air_district_wins_over_the_outlines(tmp_path):
    rows = [
        {"site_id": "a", "name": "A", "air_district": "East"},
        {"site_id": "b", "name": "B", "air_district": ""},
    ]
    write_sites(tmp_path, rows)
    sites = registry.build_registry(
        tmp_path, tmp_path / "out", region_bbox=BAY, districts=districts()
    ).set_index("site_id")
    assert sites["air_district"].to_dict() == {"a": "East", "b": "East"}
    assert sites["air_district_confirmed"].to_dict() == {"a": True, "b": False}

    rows[0]["air_district"] = "Bay Area AQMD"
    write_sites(tmp_path, rows)
    with pytest.raises(ValueError, match="a: air_district Bay Area AQMD is not a CARB district"):
        registry.build_registry(tmp_path, tmp_path / "out", region_bbox=BAY, districts=districts())


def test_a_site_across_or_beside_a_district_edge_is_flagged(tmp_path):
    across = ("a", "boundary", utm_box(594700, 4146000, 595900, 4147000))  # 300 m West, 900 m East
    beside = ("b", "boundary", utm_box(595200, 4150000, 596200, 4151000))  # 200 m inside East
    outside = ("c", "boundary", utm_box(590000, 4250000, 591000, 4251000))  # in no outline
    write_sites(
        tmp_path,
        [{"site_id": s, "name": s.upper()} for s in "abc"],
        polys=(across, beside, outside),
    )
    sites = registry.build_registry(
        tmp_path, tmp_path / "out", region_bbox=BAY, districts=districts()
    )
    by = sites.set_index("site_id")
    assert by["air_district"].to_dict() == {"a": "East", "b": "East", "c": ""}
    assert by["air_district_edge_m"]["a"] == pytest.approx(0, abs=1)
    notes = registry.district_notes(sites)
    assert notes[0] == "no air district found for: c"
    assert "a: 0 m from an air district edge (read as East); check it first" in notes
    assert any(n.startswith("b: 200 m from an air district edge (read as East)") for n in notes)
    assert notes[-1].startswith("air district of 2 site(s)")


def test_read_districts_is_none_without_the_file(tmp_path):
    assert registry.read_districts(tmp_path / "air_districts.geojson") is None
    districts().to_file(tmp_path / "air_districts.geojson", driver="GeoJSON")
    assert list(registry.read_districts(tmp_path / "air_districts.geojson")["NAME"]) == [
        "West",
        "East",
    ]
