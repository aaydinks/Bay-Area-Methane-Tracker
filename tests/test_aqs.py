"""EPA's air monitors as context for the air near each landfill (ADR 0027), on a recorded sample.

``tests/fixtures/aqs/annual_conc_by_monitor_2025_sample.csv`` holds the fine-particle, NO2 and
ozone rows of five California monitoring stations from EPA's 2025 annual file as it stood on
2026-11-28, every column as published. Between them the stations show a year with event days,
an incomplete year, an uncertified year, two instruments at one station, an instrument under a
method name EPA says to leave out, and both map datums.
"""

import io
import json
import zipfile
from datetime import date
from pathlib import Path

import geopandas as gpd
import httpx
import pandas as pd
import pytest
from shapely.geometry import Point, box

from methanewatch import config
from methanewatch.config import load_data_terms
from methanewatch.ingest import aqs, pipeline
from methanewatch.ingest import calenviroscreen as ces
from tests.test_publish_snapshot import _write_inputs
from tests.test_site_metrics import _build, _write

SAMPLE = Path(__file__).parent / "fixtures" / "aqs" / "annual_conc_by_monitor_2025_sample.csv"
METRIC = "EPSG:32610"
YEARS = [2021, 2022, 2023, 2024, 2025]
LIMIT_KM = config.load_project().context.monitor_limit_km
SLOUGHHOUSE = ("06", "067", "5003")  # one fine-particle instrument, a full certified year
T_STREET = ("06", "067", "0010")  # two fine-particle instruments, and NO2
BISHOP = ("06", "027", "0002")  # a year with event days
LONE_PINE = ("06", "027", "1018")  # the instrument EPA's advisory says to leave out


def _published() -> pd.DataFrame:
    """The sample with every column, as the file holds it."""
    return pd.read_csv(SAMPLE, dtype=str)


def _zip(table: pd.DataFrame, year: int = 2025) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        z.writestr(f"annual_conc_by_monitor_{year}.csv", table.to_csv(index=False))
    return out.getvalue()


def _table() -> pd.DataFrame:
    return aqs.read_year(_zip(_published()), 2025)


def _at(table: pd.DataFrame, station, parameter: str = aqs.PM25.parameter) -> pd.Series:
    """Rows of one station and pollutant."""
    here = (table[aqs.STATION] == list(station)).all(axis=1)
    return here & (table[aqs.C_PARAMETER] == parameter)


def _in_year(table: pd.DataFrame, year: int, **changes) -> pd.DataFrame:
    """The same rows as another year's file would hold them."""
    return table.assign(**{aqs.C_YEAR: str(year)}, **changes)


def _site(
    station,
    km_east: float,
    *,
    site_id: str = "a-landfill",
    source: str = "CalRecycle LandfillBoundaries",
) -> gpd.GeoDataFrame:
    """A 500 m square landfill whose near edge is ``km_east`` east of a sample station."""
    row = _published()[_at(_published(), station)].iloc[0]
    datum = aqs.DATUMS[row[aqs.C_DATUM]]
    point = gpd.GeoSeries([Point(float(row[aqs.C_LON]), float(row[aqs.C_LAT]))], crs=datum)
    x, y = point.to_crs(METRIC).iloc[0].coords[0]
    west = x + km_east * 1000
    return gpd.GeoDataFrame(
        {"site_id": [site_id], "polygon_source": [source]},
        geometry=[box(west, y - 250, west + 500, y + 250)],
        crs=METRIC,
    )


def _measures(table=None, sites=None, **kwargs):
    return aqs.measures(
        table if table is not None else _table(),
        sites if sites is not None else _site(SLOUGHHOUSE, 3.0),
        metric_crs=METRIC,
        pull_id="epa-aqs-test",
        years=YEARS,
        near_km=LIMIT_KM,
        **kwargs,
    )


def _cell(rows, metric_id):
    hit = rows[rows["metric_id"] == metric_id]
    assert len(hit) <= 1
    return None if hit.empty else hit.iloc[0]


def test_the_newest_full_year_follows_epas_june_refresh():
    assert aqs.newest_full_year(date(2026, 11, 28)) == 2025
    assert aqs.newest_full_year(date(2026, 6, 30)) == 2024
    assert aqs.years_read(2025) == YEARS and aqs.period(YEARS) == "2021-2025"


def test_a_years_file_keeps_only_the_two_pollutants():
    table = _table()
    assert set(table[aqs.C_PARAMETER]) == {aqs.PM25.parameter, aqs.NO2.parameter}
    assert len(table) == 91 and list(table.columns) == list(aqs.COLUMNS)


def test_a_file_with_another_layout_is_refused():
    published = _published()
    with pytest.raises(ValueError, match="layout has changed"):
        aqs.read_year(_zip(published.drop(columns=[aqs.C_CERTIFIED])), 2025)
    with pytest.raises(ValueError, match="other years"):
        aqs.read_year(_zip(published), 2024)
    renamed = published.replace({aqs.C_STANDARD: {aqs.PM25.standard: "PM25 Annual 2030"}})
    with pytest.raises(ValueError, match="PM25 Annual 2024"):
        aqs.read_year(_zip(renamed), 2025)


def test_a_year_is_listed_only_when_complete_certified_and_counting_every_day():
    listed = aqs.full_years(_table(), aqs.PM25)
    stations = {tuple(r) for r in listed[aqs.MONITOR].itertuples(index=False)}
    # T Street's second instrument is listed, its third had an incomplete year; Lone Pine's
    # year was incomplete, uncertified and under a method name EPA says to leave out
    assert stations == {(*SLOUGHHOUSE, "3"), (*T_STREET, "2"), (*BISHOP, "1"), (*BISHOP, "2")}
    # event days are included: the row that leaves them out is not the one read
    bishop = listed[_at(listed, BISHOP) & (listed[aqs.C_POC] == "1")].iloc[0]
    assert (bishop[aqs.C_EVENTS], bishop[aqs.C_MEAN]) == ("Events Included", "5.248588")
    assert len(aqs.full_years(_table(), aqs.NO2)) == 2


def test_the_superseded_instrument_is_left_out_even_with_a_full_certified_year():
    table = _table()
    lone_pine = _at(table, LONE_PINE)
    table.loc[lone_pine, [aqs.C_COMPLETE, aqs.C_CERTIFIED]] = ["Y", aqs.CERTIFIED]
    assert not _at(aqs.full_years(table, aqs.PM25), LONE_PINE).any()
    # the same instrument under its corrected method name is kept
    table.loc[lone_pine & table[aqs.C_METHOD].notna(), aqs.C_METHOD] = (
        "Teledyne T640 at 5.0 LPM (Corrected) - Broadband spectroscopy"
    )
    assert _at(aqs.full_years(table, aqs.PM25), LONE_PINE).sum() == 1


def test_two_rows_for_one_monitor_and_year_stop_the_step():
    table = _table()
    twice = pd.concat([table, table[_at(table, SLOUGHHOUSE)]], ignore_index=True)
    with pytest.raises(ValueError, match="two 'PM25 Annual 2024' rows"):
        aqs.full_years(twice, aqs.PM25)


def test_a_station_is_read_at_the_instrument_with_the_most_days():
    table = _table()
    assert _cell(_measures(table, _site(T_STREET, 1.0))[0], aqs.PM25.days)["value"] == 30.0
    table.loc[_at(table, T_STREET) & (table[aqs.C_POC] == "3"), aqs.C_COMPLETE] = "Y"
    rows, _ = _measures(table, _site(T_STREET, 1.0))
    assert _cell(rows, aqs.PM25.days)["value"] == 331.0
    assert _cell(rows, aqs.PM25.monitor)["source_id"] == "06-067-0010-88101-3"


def test_figures_are_written_as_epa_lists_them():
    rows, none_near = _measures()
    assert none_near == {"pm25": [], "no2": ["a-landfill"]}  # T Street's NO2 is 29 km away
    assert set(rows["period"]) == {"2021-2025"} and set(rows["source"]) == {aqs.SOURCE}
    assert set(rows["kind"]) == {"context"} and set(rows["url"]) == {aqs.PAGE}
    assert set(rows["source_id"]) == {"06-067-5003-88101-3"} and rows["confirmed"].all()
    assert (rows["unit"] == rows["metric_id"].map(aqs.UNITS)).all()
    assert _cell(rows, aqs.PM25.monitor)["value_text"] == "Sloughhouse (06-067-5003)"
    assert _cell(rows, aqs.PM25.distance)["value"] == pytest.approx(3.0, abs=0.001)
    values = rows.set_index("metric_id")["value"].dropna().drop(aqs.PM25.distance).to_dict()
    assert values == {aqs.PM25.year: 2025.0, aqs.PM25.days: 346.0, aqs.PM25.mean: 6.071387}


def test_a_monitor_is_read_at_its_newest_year_that_can_be_listed():
    older = _in_year(_table(), 2022, **{aqs.C_MEAN: "9.5"})
    table = pd.concat([older, _table()], ignore_index=True)
    assert _cell(_measures(table)[0], aqs.PM25.year)["value"] == 2025.0
    # the agency has not certified the newer year: the older one is the figure
    table.loc[_at(table, SLOUGHHOUSE) & (table[aqs.C_YEAR] == "2025"), aqs.C_CERTIFIED] = (
        "Certification not required"
    )
    rows, _ = _measures(table)
    assert _cell(rows, aqs.PM25.year)["value"] == 2022.0
    assert _cell(rows, aqs.PM25.mean)["value"] == 9.5


def test_the_nearest_station_is_the_one_listed_whatever_its_year():
    # T Street's NO2 is 1 km away with an older year; Tracy's is far away with the newest
    older = _in_year(_table()[_at(_table(), T_STREET, aqs.NO2.parameter)], 2021)
    tracy = _table()[~_at(_table(), T_STREET, aqs.NO2.parameter)]
    rows, _ = _measures(pd.concat([older, tracy], ignore_index=True), _site(T_STREET, 1.0))
    assert _cell(rows, aqs.NO2.monitor)["value_text"] == "Sacramento-1309 T Street (06-067-0010)"
    assert _cell(rows, aqs.NO2.year)["value"] == 2021.0
    assert _cell(rows, aqs.NO2.distance)["value"] == pytest.approx(1.0, abs=0.001)


def test_a_monitor_beyond_the_limit_is_not_listed():
    rows, none_near = _measures(sites=_site(SLOUGHHOUSE, 25.5))
    assert none_near["pm25"] == ["a-landfill"]
    assert not rows["metric_id"].str.startswith("aqs_pm25").any()
    rows, none_near = _measures(sites=_site(SLOUGHHOUSE, 24.5))
    assert none_near["pm25"] == []
    assert _cell(rows, aqs.PM25.distance)["value"] == pytest.approx(24.5, abs=0.001)


def test_a_provisional_outline_marks_the_rows_unchecked():
    site = _site(SLOUGHHOUSE, 3.0, source="provisional 750 m buffer around CalRecycle SWIS point")
    rows, _ = _measures(sites=site)
    assert len(rows) and not rows["confirmed"].any()


def test_a_datum_the_step_does_not_know_stops_it():
    table = _table()
    table.loc[_at(table, SLOUGHHOUSE), aqs.C_DATUM] = "UNKNOWN"
    with pytest.raises(ValueError, match="datum"):
        _measures(table)


def _fake_get(table: pd.DataFrame, seen: list):
    def get(client, url):
        seen.append(url)
        year = int(url.removesuffix(".zip")[-4:])
        return httpx.Response(
            200,
            content=_zip(_in_year(table, year), year),
            headers={"last-modified": "Mon, 13 Jul 2026 15:47:40 GMT"},
        )

    return get


def test_the_pull_keeps_to_its_own_folder_and_records_each_years_file(tmp_path, monkeypatch):
    seen: list = []
    monkeypatch.setattr(aqs, "_get", _fake_get(_published(), seen))
    raw = tmp_path / "raw"
    pull_dir = aqs.pull(raw, 2025)
    assert seen == [f"{aqs.BASE}/annual_conc_by_monitor_{y}.zip" for y in YEARS]
    assert pull_dir.parent == raw / aqs.SOURCE
    assert [p.name for p in raw.iterdir()] == [aqs.SOURCE]
    manifest = json.loads((pull_dir / "manifest.json").read_text())
    assert manifest["params"]["years"] == YEARS and manifest["n_records"] == 5 * 91
    assert manifest["params"]["files"]["2023"]["url"] == seen[2]
    assert sorted(manifest["files"]) == [aqs.file_name(y) for y in YEARS]
    assert aqs.finished_pulls(raw) == [pull_dir] and aqs.pull_years(pull_dir) == YEARS
    assert len(aqs.read_pull(pull_dir)) == 5 * 91


def test_a_file_with_another_layout_stops_the_pull_and_leaves_nothing(tmp_path, monkeypatch):
    bad = _published().rename(columns={aqs.C_MEAN: "Mean"})
    monkeypatch.setattr(aqs, "_get", _fake_get(bad, []))
    raw = tmp_path / "raw"
    with pytest.raises(ValueError, match="layout has changed"):
        aqs.pull(raw, 2025)
    assert not raw.exists()


def test_the_step_writes_the_measures_for_every_site_in_the_table(tmp_path, monkeypatch):
    base = config.load_project()
    folders = {name: tmp_path / name for name in ("raw", "interim")}
    project = base.model_copy(update={"paths": base.paths.model_copy(update=folders)})
    monkeypatch.setattr(aqs, "_get", _fake_get(_published(), []))
    with pytest.raises(FileNotFoundError, match="mw ingest aqs"):
        pipeline.write_aqs(project)
    aqs.pull(tmp_path / "raw", 2025)
    with pytest.raises(FileNotFoundError, match="mw sites build"):
        pipeline.write_aqs(project)
    (tmp_path / "interim").mkdir()
    provisional = "provisional 500 m buffer"
    sites = pd.concat(
        [
            _site(SLOUGHHOUSE, 3.0, site_id="near-one"),
            _site(T_STREET, 1.0, site_id="near-both", source=provisional),
            _site(SLOUGHHOUSE, 80.0, site_id="near-none"),
        ],
        ignore_index=True,
    )
    sites.to_parquet(tmp_path / "interim" / "sites.parquet")
    counts = pipeline.write_aqs(project)
    assert counts["years"] == "2021-2025"
    assert counts["sites_with_a_fine_particle_monitor"] == 2
    assert counts["sites_with_an_no2_monitor"] == 1
    assert (counts["sites_with_neither"], counts["sites_with_a_provisional_outline"]) == (1, 1)
    rows = pd.read_parquet(tmp_path / "interim" / "site_metrics" / f"{aqs.SOURCE}.parquet")
    assert len(rows) == counts["rows"] == 15


def test_the_catalogue_describes_the_measures_as_the_step_writes_them():
    measures = config.load_metrics().measures
    for metric_id, unit in aqs.UNITS.items():
        entry = measures[metric_id]
        assert (entry.unit, entry.kind, entry.source) == (unit, "context", aqs.SOURCE)
    # the catalogue names the limit that config/project.yaml sets
    assert f"within {LIMIT_KM:g} km" in measures[aqs.PM25.monitor].caveat
    # every context measure in the catalogue is one a step writes
    context = {m for m, entry in measures.items() if entry.kind == "context"}
    assert context == set(aqs.UNITS) | set(ces.UNITS)


def test_the_source_is_open_and_names_its_terms():
    term = load_data_terms().sources[aqs.SOURCE]
    assert term.confirmed and not term.restricted and not term.display_only
    assert term.terms_url and term.credit_line and term.instruments == ()


def test_published_rows_are_open(tmp_path):
    rows, _ = _measures(sites=_site(SLOUGHHOUSE, 3.0, site_id="newby-island"))
    _write_inputs(tmp_path)
    _write(tmp_path, rows, name=aqs.SOURCE)
    got = _build(tmp_path).tables["site_metrics"]
    assert len(got) == 5 and not got["restricted"].any() and not got["display_only"].any()
    assert set(got["kind"]) == {"context"}
