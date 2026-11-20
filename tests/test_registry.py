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
