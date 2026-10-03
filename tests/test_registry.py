import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point, box

from methanewatch.sites import registry

UTM = "EPSG:32610"


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
    sites = registry.build_registry(tmp_path, tmp_path / "out")
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
        registry.build_registry(tmp_path, tmp_path / "out")

    write_registry(tmp_path, [("a", "boundary", box(-100, 40, -99.9, 40.1))])
    with pytest.raises(ValueError, match="outside the Bay Area"):
        registry.build_registry(tmp_path, tmp_path / "out")


def test_missing_polygons_without_geojson(tmp_path):
    pd.DataFrame({"site_id": ["a", "b"]}).to_csv(tmp_path / "sites.csv", index=False)
    assert registry.missing_polygons(tmp_path) == ["a", "b"]


def test_screening_buffer():
    pts = gpd.GeoDataFrame({"site_id": ["x"]}, geometry=[Point(-122.0, 37.5)], crs="EPSG:4326")
    out = registry.screening_polygons(pts, buffer_m=750).to_crs(UTM)
    assert out.geometry.area.iloc[0] == pytest.approx(3.1416 * 750**2, rel=0.01)
