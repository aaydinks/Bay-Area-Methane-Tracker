"""Registry -> coverage build -> Gate 1 on a small fixture project (no network)."""

import geopandas as gpd
import pandas as pd
from shapely.geometry import box

from methanewatch.config import load_project
from methanewatch.coverage import build
from methanewatch.sites import registry
from methanewatch.validate import gate1

UTM = "EPSG:32610"


def utm_box(x0, y0, x1, y1):
    return gpd.GeoSeries([box(x0, y0, x1, y1)], crs=UTM).to_crs("EPSG:4326").iloc[0]


def test_pipeline_on_fixture(tmp_path):
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
    assert counts == {"overpasses": 20, "usable": 20, "detections": 1, "unmatched_plumes": 1}
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
