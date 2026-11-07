"""Registry -> coverage build -> Gate 1 on a small fixture project (no network)."""

import geopandas as gpd
import pandas as pd
import pandas.api.types as ptypes
import pytest
from shapely.geometry import box

from methanewatch.config import load_project
from methanewatch.coverage import build
from methanewatch.sites import registry
from methanewatch.validate import gate1

UTM = "EPSG:32610"


def utm_box(x0, y0, x1, y1):
    return gpd.GeoSeries([box(x0, y0, x1, y1)], crs=UTM).to_crs("EPSG:4326").iloc[0]


def fixture_project(tmp_path):
    """Two pilot sites, a compost neighbour and ten EMIT scenes over both; no plumes yet."""
    reg, interim = tmp_path / "registry", tmp_path / "interim"
    (interim / "footprints").mkdir(parents=True)
    (interim / "plumes").mkdir()
    reg.mkdir()
    pd.DataFrame({"site_id": ["a", "b"], "tier": ["pilot", "pilot"]}).to_csv(
        reg / "sites.csv", index=False
    )
    gpd.GeoDataFrame(
        {
            "site_id": ["a", "b", "compost"],
            "part": ["boundary", "boundary", "neighbor"],
            "name": ["", "", "compost"],
        },
        geometry=[
            utm_box(590000, 4146000, 591000, 4147000),
            utm_box(600000, 4146000, 601000, 4147000),
            utm_box(601600, 4146000, 601900, 4146300),
        ],
        crs="EPSG:4326",
    ).to_file(reg / "sites.geojson", driver="GeoJSON")

    project = load_project().model_copy(
        update={
            "paths": load_project().paths.model_copy(
                update={"registry": reg, "interim": interim, "reports": tmp_path / "reports"}
            )
        }
    )
    registry.build_registry(reg, interim, metric_crs=UTM)

    days = pd.date_range("2025-01-05T18:00Z", periods=10, freq="14D")
    gpd.GeoDataFrame(
        {
            "scene_id": [f"s{i}" for i in range(10)],
            "instrument": "emit",
            "acquired_utc": days,
            "valid_frac": 0.95,
        },
        geometry=[utm_box(585000, 4140000, 605000, 4150000)] * 10,
        crs="EPSG:4326",
    ).to_parquet(interim / "footprints" / "emit.parquet")
    return project, reg, interim, days


def test_pipeline_on_fixture(tmp_path):
    project, reg, interim, days = fixture_project(tmp_path)
    origin = gpd.GeoSeries(
        gpd.points_from_xy([590500, 601200, 590500], [4146500, 4146100, 4146500]), crs=UTM
    ).to_crs("EPSG:4326")
    pd.DataFrame(
        {
            "plume_id": ["p1", "p2", "p3"],
            "source": "emit-v2",
            "instrument": "emit",
            "acquired_utc": [days[2], days[2], pd.Timestamp("2025-12-01T18:00Z")],
            "origin_lon": origin.x,
            "origin_lat": origin.y,
            "q_kg_hr": [600.0, 800.0, 700.0],
            "q_sigma_kg_hr": [150.0, 200.0, 175.0],
            "data_version": "002",
            "pull_id": "fixture",
        }
    ).to_parquet(interim / "plumes" / "emit.parquet")

    counts = build.build(project)
    assert counts == {
        "overpasses": 20,
        "usable": 20,
        "s2_site_share": 0,
        "s2_tile_fallback": 0,
        "detections": 1,
        "unmatched_plumes": 1,
    }
    att = pd.read_parquet(interim / "plumes_attributed.parquet").set_index("plume_id")
    assert att.loc["p2", "attribution"] == "ambiguous"  # compost facility within the buffer

    table = gate1.counts_by_year(
        att.reset_index(), pd.read_parquet(interim / "overpasses.parquet"), ["a", "b"]
    )
    result = gate1.evaluate(table, ["a", "b"], registry.missing_polygons(reg))
    assert result.passed, result.problems
    report = gate1.write_report(
        table, result, tmp_path / "reports", unmatched=counts["unmatched_plumes"]
    )
    assert "PASS" in report.read_text()


@pytest.mark.parametrize(
    "plume_files",
    [
        {},
        {"carbonmapper.parquet": pd.DataFrame()},
        {"emit.parquet": pd.DataFrame(columns=["plume_id", "q_kg_hr", "acquired_utc"])},
    ],
    ids=["no-files", "empty-file", "empty-file-with-columns"],
)
def test_build_without_plumes(tmp_path, plume_files):
    """A refresh whose plume sources all came back empty: every usable pass is a non-detection."""
    project, _, interim, _ = fixture_project(tmp_path)
    for name, frame in plume_files.items():
        frame.to_parquet(interim / "plumes" / name)

    counts = build.build(project)
    assert counts["overpasses"] == counts["usable"] == 20
    assert counts["detections"] == 0
    assert counts["unmatched_plumes"] == 0

    det = pd.read_parquet(interim / "detections.parquet")
    assert len(det) == 20 and not det["detected"].any()
    assert ptypes.is_float_dtype(det["q_obs_kg_hr"]) and det["q_obs_kg_hr"].isna().all()
    assert ptypes.is_float_dtype(det["q_sigma_log"])

    att = pd.read_parquet(interim / "plumes_attributed.parquet")
    assert att.empty and {"source", "distance_m"} <= set(att.columns)  # read by the snapshot
    assert ptypes.is_float_dtype(att["q_kg_hr"]) and ptypes.is_float_dtype(att["q_sigma_kg_hr"])
    assert isinstance(att["acquired_utc"].dtype, pd.DatetimeTZDtype)
    assert str(att["acquired_utc"].dt.tz) == "UTC"
