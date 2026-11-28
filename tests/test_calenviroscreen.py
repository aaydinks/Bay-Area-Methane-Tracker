"""CalEnviroScreen as context for the area around each landfill (ADR 0026).

``tests/fixtures/calenviroscreen/ces5_tracts_sample.geojson`` holds the eight census tracts
within 1 km of three landfills, under the column names of the state's CalEnviroScreen 5.0
geodatabase of July 2026. The outlines are the Census Bureau's 2020 tract outlines as that file
carries them, simplified to 20 m. Every figure is made up: the source's terms of reuse are not
confirmed, so none of its figures are kept in this repository.
"""

import json
import zipfile
from pathlib import Path

import geopandas as gpd
import httpx
import pandas as pd
import pytest
from shapely.geometry import box

from methanewatch import config
from methanewatch.config import load_data_terms
from methanewatch.ingest import calenviroscreen as ces
from methanewatch.ingest import pipeline
from tests.test_publish_snapshot import _write_inputs
from tests.test_site_metrics import _build, _write

SAMPLE = Path(__file__).parent / "fixtures" / "calenviroscreen" / "ces5_tracts_sample.geojson"
REGISTRY = Path(__file__).parents[1] / "data" / "registry" / "sites.geojson"
METRIC = "EPSG:32610"
FILE_URL = "https://publish.data.ca.gov/dataset/x/resource/y/download/results.gdb.zip"
PACKAGE = {
    "result": {
        "resources": [
            {"format": "CSV", "url": "https://publish.data.ca.gov/x.csv"},
            {"format": "GDB", "url": FILE_URL, "id": "y", "last_modified": "2026-10-01T14:56:05"},
        ]
    }
}


def _sample() -> gpd.GeoDataFrame:
    return gpd.read_file(SAMPLE)


def _gdb_zip(folder: Path, table: gpd.GeoDataFrame) -> Path:
    """A zipped geodatabase like the state's: one layer, tract numbers stored as numbers."""
    folder.mkdir(parents=True, exist_ok=True)
    gdb = folder / "sample.gdb"
    table.to_crs("EPSG:3310").to_file(
        gdb,
        driver="OpenFileGDB",
        layer="CES5_final_results",
        TARGET_ARCGIS_VERSION="ARCGIS_PRO_3_2_OR_LATER",
    )
    path = folder / ces.FILE
    with zipfile.ZipFile(path, "w") as z:
        for part in sorted(gdb.iterdir()):
            z.write(part, f"{gdb.name}/{part.name}")
    return path


def _outlines(*site_ids: str) -> gpd.GeoDataFrame:
    sites = gpd.read_file(REGISTRY).rename(columns={"source": "polygon_source"})
    return sites[sites["site_id"].isin(site_ids)].dissolve("site_id", as_index=False)


def _tracts(*rows) -> gpd.GeoDataFrame:
    """Made-up square tracts on a kilometre grid: (number, score, x0, x1) in km, 2 km tall."""
    return gpd.GeoDataFrame(
        {
            ces.C_TRACT: [f"0600100{n:04d}" for n, *_ in rows],
            ces.C_POPULATION: [1000 * n for n, *_ in rows],
            ces.C_SCORE: [score for _, score, *_ in rows],
            ces.C_POLLUTION: [score for _, score, *_ in rows],
            ces.C_POPCHAR: [score for _, score, *_ in rows],
        },
        geometry=[box(x0 * 1000, 0, x1 * 1000, 2000) for *_, x0, x1 in rows],
        crs=METRIC,
    )


def _site(x0: float, x1: float, source: str = "traced") -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {"site_id": ["a-landfill"], "polygon_source": [source]},
        geometry=[box(x0 * 1000, 500, x1 * 1000, 1500)],
        crs=METRIC,
    )


def _measures(tracts, sites):
    return ces.measures(tracts, sites, metric_crs=METRIC, pull_id="calenviroscreen-test")


def _values(rows, site_id="a-landfill"):
    mine = rows[rows["site_id"] == site_id].set_index("metric_id")
    return mine["value"].dropna().round(1).to_dict(), mine["value_text"].dropna().to_dict()


def test_the_portal_lists_one_geodatabase():
    assert ces.geodatabase(PACKAGE)["url"] == FILE_URL
    two = {"result": {"resources": PACKAGE["result"]["resources"] * 2}}
    with pytest.raises(ValueError, match="found 2"):
        ces.geodatabase(two)
    with pytest.raises(ValueError, match="found 0"):
        ces.geodatabase({"result": {"resources": []}})


def test_the_file_is_read_with_tract_numbers_as_the_census_writes_them(tmp_path):
    tracts = ces.read_tracts(_gdb_zip(tmp_path, _sample()))
    assert len(tracts) == 8 and tracts[ces.C_TRACT].str.len().eq(11).all()
    assert "06085504602" in set(tracts[ces.C_TRACT])


def test_a_file_missing_a_column_is_refused(tmp_path):
    with pytest.raises(ValueError, match="layout has changed"):
        ces.read_tracts(_gdb_zip(tmp_path, _sample().drop(columns=[ces.C_POLLUTION])))


def test_figures_are_written_as_the_file_gives_them(tmp_path):
    tracts = ces.read_tracts(_gdb_zip(tmp_path, _sample()))
    rows, outside = _measures(tracts, _outlines("newby-island", "acme-fill", "sonoma-central"))
    assert outside == []
    assert set(rows["period"]) == {"5.0"} and set(rows["source"]) == {ces.SOURCE}
    assert set(rows["kind"]) == {"context"} and set(rows["url"]) == {ces.PAGE}
    assert (rows["unit"] == rows["metric_id"].map(ces.UNITS)).all()
    assert rows["confirmed"].all()  # all three outlines are drawn ones
    values, text = _values(rows, "newby-island")
    assert text == {ces.TRACT: "06085504602"}
    assert values == {
        ces.TRACT_POPULATION: 1200.0,
        ces.SCORE: 61.5,
        ces.POLLUTION: 72.5,
        ces.POPCHAR: 44.5,
        ces.TRACTS_NEAR: 3.0,
        ces.NEAR_LOWEST: 35.0,
        ces.NEAR_HIGHEST: 61.5,
    }
    assert set(rows.loc[rows["site_id"] == "newby-island", "source_id"]) == {"06085504602"}
    # the sample gives this landfill's own tract no score, and its one neighbour 18.5
    values, text = _values(rows, "sonoma-central")
    assert text == {ces.TRACT: "06097151100"} and ces.SCORE not in values
    assert values == {
        ces.TRACT_POPULATION: 800.0,
        ces.POLLUTION: 22.5,
        ces.TRACTS_NEAR: 2.0,
        ces.NEAR_LOWEST: 18.5,
        ces.NEAR_HIGHEST: 18.5,
    }


def test_the_tract_is_the_one_holding_most_of_the_outline():
    # the outline runs from 1.4 km to 2.4 km: 60% in the first tract, 40% in the second
    rows, _ = _measures(_tracts((1, 20.0, 0, 2), (2, 80.0, 2, 4)), _site(1.4, 2.4))
    values, text = _values(rows)
    assert text[ces.TRACT] == "06001000001"
    assert (values[ces.SCORE], values[ces.TRACT_POPULATION]) == (20.0, 1000.0)


def test_tracts_within_a_kilometre_are_counted_and_nothing_is_averaged():
    # tracts 2 km wide; the outline sits in the second, 0.5 km from the third and 2.5 km
    # from the first and from the fourth
    tracts = _tracts((1, 5.0, 0, 2), (2, 40.0, 3.5, 5.5), (3, 90.0, 6, 8), (4, 99.0, 8, 10))
    rows, _ = _measures(tracts, _site(4.5, 5.5))
    values, _ = _values(rows)
    assert (values[ces.TRACTS_NEAR], values[ces.NEAR_LOWEST], values[ces.NEAR_HIGHEST]) == (
        2.0,
        40.0,
        90.0,
    )


def test_a_tract_without_a_score_gives_no_percentile_row():
    tracts = _tracts((1, None, 0, 2), (2, 60.0, 2, 4))
    rows, _ = _measures(tracts, _site(0.5, 1.5))
    values, text = _values(rows)
    assert text[ces.TRACT] == "06001000001" and values[ces.TRACT_POPULATION] == 1000.0
    assert ces.SCORE not in values and ces.POPCHAR not in values
    # the neighbouring tract has a score, so the range is its score alone
    assert (values[ces.NEAR_LOWEST], values[ces.NEAR_HIGHEST]) == (60.0, 60.0)
    alone, _ = _measures(_tracts((1, None, 0, 2)), _site(0.5, 1.5))
    assert set(alone["metric_id"]) == {ces.TRACT, ces.TRACT_POPULATION, ces.TRACTS_NEAR}


def test_a_provisional_outline_marks_its_rows_unchecked():
    site = _site(0.5, 1.5, source="provisional 750 m buffer around CalRecycle SWIS point")
    rows, _ = _measures(_tracts((1, 50.0, 0, 2)), site)
    assert len(rows) and not rows["confirmed"].any()


def test_a_site_on_no_tract_is_reported_and_writes_nothing():
    rows, outside = _measures(_tracts((1, 50.0, 0, 2)), _site(20, 21))
    assert outside == ["a-landfill"] and rows.empty


def _fake_get(content: bytes, seen: list):
    def get(client, url, params=None):
        seen.append(url)
        if url == ces.PACKAGE:
            assert params == {"id": ces.DATASET}
            return httpx.Response(200, json=PACKAGE)
        return httpx.Response(
            200, content=content, headers={"last-modified": "Thu, 01 Oct 2026 14:56:05 GMT"}
        )

    return get


def test_the_pull_keeps_to_its_own_folder_and_records_the_version(tmp_path, monkeypatch):
    seen: list = []
    content = _gdb_zip(tmp_path / "made", _sample()).read_bytes()
    monkeypatch.setattr(ces, "_get", _fake_get(content, seen))
    raw = tmp_path / "raw"
    pull_dir = ces.pull(raw)
    assert seen == [ces.PACKAGE, FILE_URL]
    assert pull_dir.parent == raw / ces.SOURCE
    assert [p.name for p in raw.iterdir()] == [ces.SOURCE]
    manifest = json.loads((pull_dir / "manifest.json").read_text())
    assert manifest["n_records"] == 8
    assert manifest["params"]["version"] == "5.0" and manifest["params"]["file_url"] == FILE_URL
    assert ces.finished_pulls(raw) == [pull_dir]
    assert len(ces.read_tracts(pull_dir / ces.FILE)) == 8


def test_a_file_with_another_layout_stops_the_pull_and_leaves_nothing(tmp_path, monkeypatch):
    bad = _gdb_zip(tmp_path / "made", _sample().rename(columns={ces.C_SCORE: "Score"}))
    monkeypatch.setattr(ces, "_get", _fake_get(bad.read_bytes(), []))
    raw = tmp_path / "raw"
    with pytest.raises(ValueError, match="layout has changed"):
        ces.pull(raw)
    assert not raw.exists()


def test_the_step_writes_the_measures_for_every_site_in_the_table(tmp_path, monkeypatch):
    base = config.load_project()
    folders = {name: tmp_path / name for name in ("raw", "interim")}
    project = base.model_copy(update={"paths": base.paths.model_copy(update=folders)})
    content = _gdb_zip(tmp_path / "made", _sample()).read_bytes()
    monkeypatch.setattr(ces, "_get", _fake_get(content, []))
    with pytest.raises(FileNotFoundError, match="mw ingest calenviroscreen"):
        pipeline.write_calenviroscreen(project)
    ces.pull(tmp_path / "raw")
    with pytest.raises(FileNotFoundError, match="mw sites build"):
        pipeline.write_calenviroscreen(project)
    (tmp_path / "interim").mkdir()
    _outlines("newby-island", "acme-fill").to_parquet(tmp_path / "interim" / "sites.parquet")
    counts = pipeline.write_calenviroscreen(project)
    assert counts["version"] == "5.0" and counts["tracts_in_file"] == 8
    assert (counts["sites_on_a_tract"], counts["sites_on_a_scored_tract"]) == (2, 2)
    assert (counts["sites_with_a_provisional_outline"], counts["sites_on_no_tract"]) == (0, 0)
    rows = pd.read_parquet(tmp_path / "interim" / "site_metrics" / f"{ces.SOURCE}.parquet")
    assert len(rows) == counts["rows"] == 16


def test_the_catalogue_describes_the_measures_as_the_step_writes_them():
    measures = config.load_metrics().measures
    for metric_id, unit in ces.UNITS.items():
        entry = measures[metric_id]
        assert (entry.unit, entry.kind, entry.source) == (unit, "context", ces.SOURCE)
    # every context measure in the catalogue is one this step writes
    context = {m for m, entry in measures.items() if entry.kind == "context"}
    assert context == set(ces.UNITS)


def test_the_source_stays_in_review_copies_until_its_terms_are_confirmed():
    term = load_data_terms().sources[ces.SOURCE]
    assert term.restricted and not term.display_only and not term.confirmed
    assert term.terms_url and term.credit_line and term.instruments == ()


def test_published_rows_are_restricted(tmp_path):
    tracts = ces.read_tracts(_gdb_zip(tmp_path / "made", _sample()))
    rows, _ = _measures(tracts, _outlines("newby-island", "acme-fill", "sonoma-central"))
    _write_inputs(tmp_path)
    _write(tmp_path, rows, name=ces.SOURCE)
    got = _build(tmp_path).tables["site_metrics"]
    assert len(got) and got["restricted"].all() and not got["display_only"].any()
