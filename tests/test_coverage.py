import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import box

from methanewatch.attribution import attribute_plumes
from methanewatch.config import Coverage
from methanewatch.coverage.overpasses import build_detections, from_footprints, q_sigma_log
from methanewatch.validate.gate1 import counts_by_year, evaluate

UTM = "EPSG:32610"
COV = Coverage(min_coverage_frac=0.8, min_valid_frac=0.7)


def utm_box(x0, y0, x1, y1):
    return gpd.GeoSeries([box(x0, y0, x1, y1)], crs=UTM).to_crs("EPSG:4326").iloc[0]


# Two 1 km sites near Milpitas in UTM 10N
SITES = gpd.GeoDataFrame(
    {"site_id": ["a", "b"]},
    geometry=[utm_box(590000, 4146000, 591000, 4147000), utm_box(600000, 4146000, 601000, 4147000)],
    crs="EPSG:4326",
)


def scenes(rows):
    return gpd.GeoDataFrame(
        pd.DataFrame(
            rows, columns=["scene_id", "instrument", "acquired_utc", "valid_frac", "geometry"]
        ),
        geometry="geometry",
        crs="EPSG:4326",
    ).assign(acquired_utc=lambda d: pd.to_datetime(d["acquired_utc"], utc=True))


def test_footprints_collapse_same_day_and_score_coverage():
    fp = scenes(
        [
            ("s1", "emit", "2025-03-01T18:00Z", 0.9, utm_box(589000, 4145000, 592000, 4148000)),
            ("s2", "emit", "2025-03-01T18:01Z", 0.5, utm_box(590500, 4145000, 592000, 4148000)),
            ("s3", "emit", "2025-03-09T18:00Z", 0.9, utm_box(590500, 4145000, 592000, 4148000)),
            ("s4", "emit", "2025-03-09T18:00Z", 0.9, utm_box(700000, 4145000, 701000, 4146000)),
        ]
    )
    ov = from_footprints(fp, SITES, COV, source="cmr-granule", metric_crs=UTM).set_index(
        "overpass_id"
    )
    assert list(ov.index) == ["a:emit:2025-03-01", "a:emit:2025-03-09"]
    assert ov.loc["a:emit:2025-03-01", "scene_ids"] == ["s1", "s2"]
    assert ov.loc["a:emit:2025-03-01", "coverage_frac"] == pytest.approx(1.0, abs=1e-3)
    assert ov.loc["a:emit:2025-03-01", "usable"]
    assert ov.loc["a:emit:2025-03-09", "coverage_frac"] == pytest.approx(0.5, abs=1e-3)
    assert not ov.loc["a:emit:2025-03-09", "usable"]


def overpass_table():
    return pd.DataFrame(
        {
            "overpass_id": ["a:emit:2025-03-01", "a:emit:2025-04-01", "b:emit:2025-03-01"],
            "site_id": ["a", "a", "b"],
            "instrument": "emit",
            "acquired_utc": pd.to_datetime(
                ["2025-03-01T18:00Z", "2025-04-01T18:00Z", "2025-03-01T18:00Z"], utc=True
            ),
            "coverage_frac": 1.0,
            "valid_frac": 1.0,
            "usable": [True, True, False],
            "coverage_source": "cmr-granule",
        }
    )


def plume_table():
    return pd.DataFrame(
        {
            "plume_id": ["p1", "p2", "p3", "p4"],
            "source": "emit-v2",
            "instrument": "emit",
            "acquired_utc": pd.to_datetime(
                [
                    "2025-03-01T18:00Z",
                    "2025-03-01T18:00Z",
                    "2025-03-01T18:00Z",
                    "2025-05-01T18:00Z",
                ],
                utc=True,
            ),
            "q_kg_hr": [300.0, 400.0, 900.0, 500.0],
            "q_sigma_kg_hr": [30.0, 40.0, 90.0, 50.0],
            "site_id": ["a", "a", "b", "a"],
            "attribution": ["inside", "buffer", "inside", "inside"],
        }
    )


def test_build_detections_sums_plumes_and_reports_gaps():
    det, unmatched = build_detections(overpass_table(), plume_table())
    det = det.set_index("overpass_id")
    assert det.loc["a:emit:2025-03-01", "q_obs_kg_hr"] == 700
    assert det.loc["a:emit:2025-03-01", "multi_plume"]
    assert not det.loc["a:emit:2025-04-01", "detected"]
    assert "b:emit:2025-03-01" not in det.index  # unusable overpass
    # p3 sits on an unusable overpass; p4 has no overpass at all
    assert sorted(unmatched["plume_id"]) == ["p3", "p4"]


def test_build_detections_averages_repeat_scenes_in_a_day():
    # Two aircraft lines over site a on one day; each sees two sources. The day's
    # rate is the mean of the per-line totals, not the sum of all four plumes.
    ov = overpass_table().assign(instrument="aircraft")
    ov["overpass_id"] = ov["overpass_id"].str.replace("emit", "aircraft")
    plumes = pd.DataFrame(
        {
            "plume_id": ["l1a", "l1b", "l2a", "l2b"],
            "source": "carbonmapper",
            "instrument": "aircraft",
            "acquired_utc": pd.to_datetime(
                [
                    "2025-03-01T18:00Z",
                    "2025-03-01T18:00Z",
                    "2025-03-01T19:00Z",
                    "2025-03-01T19:00Z",
                ],
                utc=True,
            ),
            "q_kg_hr": [300.0, 100.0, 500.0, 300.0],
            "q_sigma_kg_hr": [30.0, 40.0, 50.0, 20.0],
            "site_id": "a",
            "attribution": "inside",
        }
    )
    det, _ = build_detections(ov, plumes)
    row = det.set_index("overpass_id").loc["a:aircraft:2025-03-01"]
    assert row["q_obs_kg_hr"] == pytest.approx(600)  # mean of 400 and 800
    assert row["n_plumes"] == 4
    assert row["n_scenes"] == 2
    var = (30**2 + 40**2 + 50**2 + 20**2) / 4
    assert row["q_sigma_log"] == pytest.approx(np.sqrt(np.log1p(var / 600**2)))


def test_q_sigma_log_moment_match():
    got = q_sigma_log(pd.Series([100.0]), pd.Series([50.0])).iloc[0]
    assert got == pytest.approx(np.sqrt(np.log(1.25)))


def test_attribute_plumes_uses_origin_points():
    origin = gpd.GeoSeries(
        gpd.points_from_xy([590500, 591300, 595000], [4146500, 4146500, 4146500]), crs=UTM
    ).to_crs("EPSG:4326")
    plumes = pd.DataFrame(
        {"plume_id": ["in", "near", "mid"], "origin_lon": origin.x, "origin_lat": origin.y}
    )
    out = attribute_plumes(
        plumes, SITES, SITES.iloc[0:0], buffer_m=500, search_radius_m=5000, metric_crs=UTM
    ).set_index("plume_id")
    assert out.loc["in", "attribution"] == "inside"
    assert out.loc["near", "attribution"] == "buffer"
    assert out.loc["mid", "attribution"] == "nearby"


def test_gate1_flags_missing_denominator():
    table = counts_by_year(plume_table(), overpass_table(), ["a", "b"])
    res = evaluate(table, ["a", "b"], missing_polygons=[])
    assert not res.passed
    assert any("b: 1 emit plumes but no usable emit overpasses" in p for p in res.problems)
    res = evaluate(table[table.site_id == "a"], ["a"], missing_polygons=["a"])
    assert "no boundary polygon: a" in res.problems
