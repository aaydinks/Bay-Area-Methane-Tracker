"""Carbon Mapper CO2 plumes as counts per landfill and year (ADR 0024), on made-up rows."""

import hashlib
import json

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import box, mapping

from methanewatch import config, schemas
from methanewatch.config import load_data_terms, load_project
from methanewatch.ingest import carbonmapper, carbonmapper_co2, pipeline
from tests.test_publish_snapshot import _write_inputs
from tests.test_site_metrics import _build, _write

UTM = "EPSG:32610"


def _lonlat(x, y):
    p = gpd.GeoSeries(gpd.points_from_xy([x], [y]), crs=UTM).to_crs("EPSG:4326").iloc[0]
    return p.x, p.y


def _sites():
    """Two landfills 1 km square, 400 m apart, so one plume can lie beside both."""
    return gpd.GeoDataFrame(
        {"site_id": ["a", "b"]},
        geometry=[box(590000, 4146000, 591000, 4147000), box(591400, 4146000, 592400, 4147000)],
        crs=UTM,
    ).to_crs("EPSG:4326")


def _plumes(points, **over):
    """CO2 plume rows in the layout of Carbon Mapper's list, at metric ``points`` (x, y, when)."""
    lonlat = [_lonlat(x, y) for x, y, _ in points]
    rows = pd.DataFrame(
        {
            "plume_id": [f"co2-{i}" for i in range(len(points))],
            "plume_longitude": [p[0] for p in lonlat],
            "plume_latitude": [p[1] for p in lonlat],
            "datetime": [when for _, _, when in points],
            "gas": "CO2",
            "ipcc_sector": "Energy Industries (1A1)",
            "instrument": "tan",
            "platform": "Tanager",
            "modified": "2026-01-01T00:00:00Z",
        }
    )
    return rows.assign(**over)


def _scene(scene_id, when, bounds, platform="tan"):
    geom = gpd.GeoSeries([box(*bounds)], crs=UTM).to_crs("EPSG:4326").iloc[0]
    return {
        "id": scene_id,
        "geometry": mapping(geom),
        "properties": {"datetime": when, "platform": platform, "version": "v3e"},
    }


def _scenes(items):
    return carbonmapper.scenes_table(items)


WIDE = (580000, 4140000, 600000, 4150000)  # covers both landfills


def test_a_plume_counts_for_every_landfill_it_is_on_or_beside():
    plumes = _plumes(
        [
            (590500, 4146500, "2025-03-01T19:00:00Z"),  # inside a
            (591200, 4146500, "2025-06-01T19:00:00Z"),  # 200 m from a and from b
            (589400, 4146500, "2026-02-01T19:00:00Z"),  # 600 m from a: too far
        ]
    )
    near = carbonmapper_co2.plumes_near(plumes, _sites(), buffer_m=500, metric_crs=UTM)
    assert sorted(zip(near["plume_id"], near["site_id"], near["year"], strict=True)) == [
        ("co2-0", "a", 2025),
        ("co2-1", "a", 2025),
        ("co2-1", "b", 2025),
    ]
    assert (near["ipcc_sector"] == "Energy Industries (1A1)").all()


def test_no_plumes_gives_no_rows():
    near = carbonmapper_co2.plumes_near(_plumes([]), _sites(), buffer_m=500, metric_crs=UTM)
    assert near.empty and list(near.columns) == ["plume_id", "site_id", "year", "ipcc_sector"]


def test_a_pass_needs_most_of_the_outline_and_a_day_counts_once():
    scenes = _scenes(
        [
            _scene("s1", "2025-03-01T19:00:00Z", WIDE),
            _scene("s2", "2025-03-01T20:30:00Z", WIDE),  # same day: counted once
            _scene("s3", "2025-08-09T19:00:00Z", (580000, 4140000, 590500, 4150000)),  # half of a
            _scene("s4", "2026-01-15T19:00:00Z", (580000, 4140000, 591100, 4150000)),  # a only
        ]
    )
    passes = carbonmapper_co2.passes_over(scenes, _sites(), min_coverage_frac=0.8, metric_crs=UTM)
    got = passes.groupby(["site_id", "year"]).size().to_dict()
    assert got == {("a", 2025): 1, ("a", 2026): 1, ("b", 2025): 1}


def test_a_collection_with_no_scene_gives_an_empty_table_and_no_passes():
    empty = carbonmapper.scenes_table([])
    assert empty.empty and "geometry" in empty and "scene_id" in empty
    passes = carbonmapper_co2.passes_over(empty, _sites(), min_coverage_frac=0.8, metric_crs=UTM)
    assert passes.empty


def test_a_zero_is_written_only_for_a_year_that_was_searched():
    near = pd.DataFrame(
        {
            "plume_id": ["p1", "p2", "p3"],
            "site_id": ["a", "a", "b"],
            "year": [2025, 2025, 2023],
            "ipcc_sector": "Energy Industries (1A1)",
        }
    )
    days = pd.to_datetime(["2024-05-01", "2025-03-01", "2025-07-01", "2025-03-01"], utc=True)
    passes = pd.DataFrame({"site_id": ["a", "a", "a", "b"], "day": days, "year": days.year})
    rows = carbonmapper_co2.yearly_counts(near, passes, "carbonmapper-co2-test")
    schemas.site_metrics.validate(rows)
    got = {(r.site_id, r.period, r.metric_id): r.value for r in rows.itertuples()}
    assert got == {
        ("a", "2024", "cm_co2_passes"): 1.0,
        ("a", "2024", "cm_co2_plumes"): 0.0,  # searched, none found
        ("a", "2025", "cm_co2_passes"): 2.0,
        ("a", "2025", "cm_co2_plumes"): 2.0,
        ("b", "2025", "cm_co2_passes"): 1.0,
        ("b", "2025", "cm_co2_plumes"): 0.0,
        # a plume in a year with no listed pass keeps its count, with no pass count beside it
        ("b", "2023", "cm_co2_plumes"): 1.0,
    }
    assert (rows["source"] == "carbonmapper-co2").all() and (rows["kind"] == "observed").all()
    assert (rows["unit"] == "count").all() and (rows["pull_id"] == "carbonmapper-co2-test").all()


def test_nothing_searched_and_nothing_found_gives_no_rows():
    near = pd.DataFrame(columns=["plume_id", "site_id", "year", "ipcc_sector"])
    passes = pd.DataFrame(columns=["site_id", "day", "year"])
    assert carbonmapper_co2.yearly_counts(near, passes, "x").empty


class _Response:
    def __init__(self, *, text="", payload=None):
        self.text, self._payload = text, payload

    def json(self):
        return self._payload


def _fake_api(monkeypatch, plumes, scenes_by_collection, calls):
    """Stand in for the API: the plume list, the collection list and one page per collection."""

    def get(client, path, params):
        calls.append((path, dict(params)))
        if path == "/catalog/plume-csv":
            return _Response(text=plumes.to_csv(index=False))
        if path == "/stac/collections":
            ids = [*scenes_by_collection, "l2b-ch4-mfa-v3e", "l3a-vis-co2-mfa-v1", "l2b-co2"]
            return _Response(payload={"collections": [{"id": i} for i in ids]})
        items = scenes_by_collection[dict(params)["collections"]]
        return _Response(payload={"features": items, "numberMatched": len(items)})

    monkeypatch.setattr(carbonmapper, "_get", get)


def _pull(tmp_path, monkeypatch, plumes, scenes=None, calls=None):
    scenes = scenes or {
        "l2b-co2-mfa-v3e": [_scene("s1", "2025-03-01T19:00:00Z", WIDE)],
        "l2b-co2-mfal-v3e": [],
    }
    _fake_api(monkeypatch, plumes, scenes, calls if calls is not None else [])
    return carbonmapper_co2.pull(
        (-122.0, 37.0, -121.0, 38.0),
        pd.Timestamp("2022-08-01").date(),
        pd.Timestamp("2026-11-25").date(),
        tmp_path / "raw",
    )


def test_the_pull_asks_for_co2_and_keeps_to_its_own_folder(tmp_path, monkeypatch):
    calls = []
    plumes = _plumes([(590500, 4146500, "2025-03-01T19:00:00Z")])
    pull_dir = _pull(tmp_path, monkeypatch, plumes, calls=calls)

    assert pull_dir.parent == tmp_path / "raw" / "carbonmapper-co2"
    assert pull_dir.name.startswith("carbonmapper-co2-")
    plume_call = next(params for path, params in calls if path == "/catalog/plume-csv")
    assert plume_call["plume_gas"] == "CO2" and "sectors" not in plume_call
    # only scene-level CO2 collections are searched, whatever else the API lists
    searched = sorted(params["collections"] for path, params in calls if path == "/stac/search")
    assert searched == ["l2b-co2-mfa-v3e", "l2b-co2-mfal-v3e"]

    manifest = json.loads((pull_dir / "manifest.json").read_text())
    assert manifest["source"] == "carbonmapper-co2"
    assert manifest["params"]["plume_gas"] == "CO2"
    assert manifest["params"]["scene_collections"] == searched
    assert sorted(manifest["files"]) == [
        "plumes_co2.csv",
        "scenes_l2b-co2-mfa-v3e.json",
        "scenes_l2b-co2-mfal-v3e.json",
    ]
    assert carbonmapper_co2.finished_pulls(tmp_path / "raw") == [pull_dir]
    # the methane steps look in raw/carbonmapper and so never see this pull
    assert carbonmapper.finished_pulls(tmp_path / "raw") == []


def test_a_list_holding_another_gas_stops_the_pull_and_leaves_nothing(tmp_path, monkeypatch):
    plumes = _plumes(
        [(590500, 4146500, "2025-03-01T19:00:00Z"), (590600, 4146500, "2025-03-02T19:00:00Z")],
        gas=["CO2", "CH4"],
    )
    with pytest.raises(ValueError, match="other gases"):
        _pull(tmp_path, monkeypatch, plumes)
    assert not (tmp_path / "raw" / "carbonmapper-co2").exists()


def test_no_co2_collection_listed_stops_the_pull(tmp_path, monkeypatch):
    def get(client, path, params):
        if path == "/catalog/plume-csv":
            return _Response(text="")
        return _Response(payload={"collections": [{"id": "l2b-ch4-mfa-v3e"}]})

    monkeypatch.setattr(carbonmapper, "_get", get)
    with pytest.raises(RuntimeError, match="l2b-co2-"):
        carbonmapper_co2.pull(
            (-122.0, 37.0, -121.0, 38.0),
            pd.Timestamp("2022-08-01").date(),
            pd.Timestamp("2026-11-25").date(),
            tmp_path / "raw",
        )


def _project(tmp_path):
    base = load_project()
    paths = base.paths.model_copy(update={"raw": tmp_path / "raw", "interim": tmp_path / "interim"})
    return base.model_copy(update={"paths": paths})


def _methane_pull(raw):
    """A finished methane pull: one plume inside landfill a and one scene over both."""
    pull_dir = raw / "carbonmapper" / "carbonmapper-20260101T000000Z"
    pull_dir.mkdir(parents=True)
    lon, lat = _lonlat(590500, 4146500)
    pd.DataFrame(
        {
            "plume_id": ["ch4-1"],
            "datetime": ["2025-03-01T19:00:00Z"],
            "instrument": ["tan"],
            "platform": ["Tanager"],
            "plume_longitude": [lon],
            "plume_latitude": [lat],
            "emission_auto": [450.0],
            "emission_uncertainty_auto": [120.0],
            "emission_version": ["v3e"],
            "ipcc_sector": ["Solid Waste (6A)"],
            "gas": ["CH4"],
            "modified": ["2026-01-01T00:00:00Z"],
        }
    ).to_csv(pull_dir / "plumes_all-sectors.csv", index=False)
    (pull_dir / "scenes_l2b-ch4-mfa-v3e.json").write_text(
        json.dumps([_scene("m1", "2025-03-01T19:00:00Z", WIDE)])
    )
    (pull_dir / "manifest.json").write_text("{}")


def _digests(interim):
    files = [
        interim / "footprints" / "carbonmapper.parquet",
        interim / "plumes" / "carbonmapper.parquet",
    ]
    return {f.name + f.parent.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}


def test_a_co2_pull_changes_no_methane_table(tmp_path, monkeypatch):
    project = _project(tmp_path)
    interim = tmp_path / "interim"
    interim.mkdir()
    _sites().to_parquet(interim / "sites.parquet")
    _methane_pull(tmp_path / "raw")
    before_counts = pipeline.write_carbonmapper(project)
    before = _digests(interim)

    # three CO2 plumes: on landfill a, beside both, and on a in a year with no CO2 scene
    plumes = _plumes(
        [
            (590500, 4146500, "2025-03-01T19:00:00Z"),
            (591200, 4146500, "2025-06-01T19:00:00Z"),
            (590500, 4146500, "2023-06-01T19:00:00Z"),
        ]
    )
    _pull(tmp_path, monkeypatch, plumes)
    counts = pipeline.write_carbonmapper_co2(project)

    assert pipeline.write_carbonmapper(project) == before_counts
    assert _digests(interim) == before
    methane = pd.read_parquet(interim / "plumes" / "carbonmapper.parquet")
    assert methane["plume_id"].tolist() == ["ch4-1"]
    written = sorted(p.relative_to(interim).as_posix() for p in interim.rglob("*.parquet"))
    assert written == [
        "footprints/carbonmapper.parquet",
        "plumes/carbonmapper.parquet",
        "site_metrics/carbonmapper-co2.parquet",
        "sites.parquet",
    ]

    assert counts["co2_plumes"] == 3 and counts["plumes_near_a_site"] == 3
    assert counts["co2_scenes"] == 1 and counts["sites_with_a_pass"] == 2
    assert counts["near_plumes_by_sector"] == {"Energy Industries (1A1)": 3}
    rows = pd.read_parquet(interim / "site_metrics" / "carbonmapper-co2.parquet")
    got = {(r.site_id, r.period, r.metric_id): r.value for r in rows.itertuples()}
    assert got == {
        ("a", "2025", "cm_co2_passes"): 1.0,
        ("a", "2025", "cm_co2_plumes"): 2.0,
        ("b", "2025", "cm_co2_passes"): 1.0,
        ("b", "2025", "cm_co2_plumes"): 1.0,
        ("a", "2023", "cm_co2_plumes"): 1.0,
    }


def test_counting_needs_a_pull_and_a_site_table(tmp_path, monkeypatch):
    project = _project(tmp_path)
    with pytest.raises(FileNotFoundError, match="mw ingest carbonmapper-co2"):
        pipeline.write_carbonmapper_co2(project)
    _pull(tmp_path, monkeypatch, _plumes([(590500, 4146500, "2025-03-01T19:00:00Z")]))
    with pytest.raises(FileNotFoundError, match="mw sites build"):
        pipeline.write_carbonmapper_co2(project)


def test_the_catalogue_describes_the_counts_as_the_step_writes_them():
    measures = config.load_metrics().measures
    for metric_id in (carbonmapper_co2.PASSES, carbonmapper_co2.PLUMES):
        entry = measures[metric_id]
        assert (entry.unit, entry.kind, entry.source) == (
            carbonmapper_co2.UNIT,
            "observed",
            carbonmapper_co2.SOURCE,
        )
    # the distance the page states is the distance the count uses
    buffer_m = load_project().attribution.buffer_m
    assert f"within {buffer_m:g} m" in measures[carbonmapper_co2.PLUMES].caveat


def test_the_co2_source_is_held_back_until_its_terms_are_settled():
    terms = load_data_terms()
    term = terms.sources[carbonmapper_co2.SOURCE]
    assert term.restricted and not term.display_only
    assert term.instruments == ()  # no instrument of the methane model belongs to this source
    assert carbonmapper_co2.SOURCE not in terms.display_only_sources()


def test_published_counts_are_restricted_and_never_display_only(tmp_path):
    days = pd.to_datetime(["2025-03-01"], utc=True)
    rows = carbonmapper_co2.yearly_counts(
        pd.DataFrame(columns=["plume_id", "site_id", "year", "ipcc_sector"]),
        pd.DataFrame({"site_id": ["newby-island"], "day": days, "year": days.year}),
        "carbonmapper-co2-test",
    )
    _write_inputs(tmp_path)
    _write(tmp_path, rows, name="carbonmapper-co2")
    got = _build(tmp_path).tables["site_metrics"]
    assert len(got) == 2
    assert got["restricted"].all() and not got["display_only"].any()
    assert got.set_index("metric_id")["value"].to_dict() == {
        "cm_co2_passes": 1.0,
        "cm_co2_plumes": 0.0,
    }
