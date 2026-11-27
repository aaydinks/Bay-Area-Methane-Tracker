"""EPA's landfill gas program file as measures per landfill (ADR 0025), on a recorded sample.

``tests/fixtures/lmop/lmop_ca_2024-09_sample.csv`` holds the rows of seven landfills from EPA's
California workbook of September 2024, every column as published.
"""

import io
import json
from pathlib import Path

import httpx
import pandas as pd
import pytest

from methanewatch import config
from methanewatch.config import load_data_terms
from methanewatch.ingest import lmop, pipeline
from tests.test_publish_snapshot import _write_inputs
from tests.test_site_metrics import _build, _write

SAMPLE = Path(__file__).parent / "fixtures" / "lmop" / "lmop_ca_2024-09_sample.csv"
URL = "https://www.epa.gov/system/files/documents/2024-09/lmopdataca.xlsx"
# The two links EPA's page carried on 2026-11-27: one from its map, one from its list
PAGE = (
    '<area alt="CA" href="/system/files/documents/2024-09/lmopdataca.xlsx" shape="poly">'
    f'<a href="{URL}" class="file">California</a>'
    '<a href="/system/files/documents/2024-09/lmopdataco.xlsx" class="file">Colorado</a>'
)


def _table():
    return pd.read_csv(SAMPLE)


def _workbook(table=None) -> bytes:
    out = io.BytesIO()
    (table if table is not None else _table()).to_excel(out, sheet_name=lmop.SHEET, index=False)
    return out.getvalue()


def _crosswalk(**over):
    rows = pd.DataFrame(
        {
            "site_id": ["newby-island", "acme-fill", "sonoma-central", "aerojet", "burlingame"],
            "lmop_landfill_id": pd.array([225, 36, 1929, 37, None], dtype="Int64"),
            "confirmed": [True, True, True, False, False],
            "notes": "",
        }
    )
    return rows.assign(**over)


def _measures(table=None, crosswalk=None):
    return lmop.measures(
        table if table is not None else _table(),
        crosswalk if crosswalk is not None else _crosswalk(),
        edition="2024-09",
        url=URL,
        pull_id="epa-lmop-test",
    )


def _cell(rows, site_id, metric_id):
    hit = rows[(rows["site_id"] == site_id) & (rows["metric_id"] == metric_id)]
    assert len(hit) <= 1
    return None if hit.empty else hit.iloc[0]


def test_the_page_links_one_edition_of_the_state_file():
    assert lmop.state_file(PAGE) == (URL, "2024-09")


def test_two_editions_or_none_stop_the_pull():
    newer = '<a href="/system/files/documents/2025-03/lmopdataca.xlsx">California</a>'
    with pytest.raises(ValueError, match="found 2"):
        lmop.state_file(PAGE + newer)
    with pytest.raises(ValueError, match="found 0"):
        lmop.state_file("<p>moved</p>")


def test_figures_are_written_as_epa_lists_them():
    rows, gone = _measures()
    assert gone == []
    assert set(rows["period"]) == {"2024-09"} and set(rows["source"]) == {lmop.SOURCE}
    assert set(rows["kind"]) == {"reported"} and set(rows["url"]) == {URL}
    newby = rows[rows["site_id"] == "newby-island"].set_index("metric_id")
    assert newby["value"].dropna().to_dict() == {
        lmop.WASTE: 35860073.0,
        lmop.WASTE_YEAR: 2022.0,
        lmop.COLLECTED: 5.145,
        lmop.FLARED: 5.145,
        lmop.PROJECTS: 0.0,  # four shut down and one candidate: none operational
    }
    assert newby.loc[lmop.SYSTEM, "value_text"] == "Yes"
    assert set(newby["source_id"]) == {"225"}
    assert (rows["unit"] == rows["metric_id"].map(lmop.UNITS)).all()


def test_running_projects_are_counted_and_their_types_named():
    rows, _ = _measures()
    assert _cell(rows, "acme-fill", lmop.PROJECTS)["value"] == 3.0
    assert _cell(rows, "acme-fill", lmop.PROJECT_TYPES)["value_text"] == (
        "Boiler, Cogeneration, Microturbine"
    )
    # one operational project among six rows, five of them shut down
    assert _cell(rows, "sonoma-central", lmop.PROJECTS)["value"] == 1.0
    assert _cell(rows, "sonoma-central", lmop.PROJECT_TYPES)["value_text"] == "Reciprocating Engine"
    # no running project: a true zero, and no list of types
    assert _cell(rows, "newby-island", lmop.PROJECT_TYPES) is None


def test_a_blank_figure_gives_no_row():
    rows, _ = _measures()
    # EPA gives Acme no flared figure, and gives this landfill no waste or gas figures at all
    assert _cell(rows, "acme-fill", lmop.FLARED) is None
    assert set(rows.loc[rows["site_id"] == "aerojet", "metric_id"]) == {
        lmop.SYSTEM,
        lmop.PROJECTS,
    }
    assert "burlingame" not in set(rows["site_id"])  # no match, so nothing is written


def test_a_gas_system_that_is_neither_yes_nor_no_is_left_out():
    table = _table()
    table.loc[table[lmop.C_ID] == 225, lmop.C_SYSTEM] = "Unknown"
    rows, _ = _measures(table)
    assert _cell(rows, "newby-island", lmop.SYSTEM) is None


def test_a_row_is_confirmed_only_when_its_match_is():
    rows, _ = _measures()
    by_site = rows.groupby("site_id")["confirmed"].agg(["all", "any"])
    assert by_site.loc["newby-island", "all"] and not by_site.loc["aerojet", "any"]


def test_a_match_epa_no_longer_lists_is_reported_and_writes_nothing():
    crosswalk = _crosswalk(lmop_landfill_id=pd.array([225, 36, 1929, 99999, None], dtype="Int64"))
    rows, gone = _measures(crosswalk=crosswalk)
    assert gone == [99999] and "aerojet" not in set(rows["site_id"])


def test_landfill_figures_that_differ_between_rows_stop_the_step():
    table = _table()
    table.loc[table.index[table[lmop.C_ID] == 36][0], lmop.C_WASTE] = 1.0
    with pytest.raises(ValueError, match="differing"):
        lmop.landfills(table)


def test_a_workbook_missing_a_column_is_refused():
    with pytest.raises(ValueError, match="layout has changed"):
        lmop.read_workbook(_workbook(_table().drop(columns=[lmop.C_FLARED])))


def test_one_epa_landfill_belongs_to_one_site(tmp_path):
    path = tmp_path / "lmop_crosswalk.csv"
    _crosswalk(lmop_landfill_id=pd.array([225, 225, 1929, 37, None], dtype="Int64")).to_csv(
        path, index=False
    )
    with pytest.raises(ValueError, match="more than one site"):
        lmop.read_crosswalk(path)


def _fake_get(content: bytes, seen: list):
    def get(client, url):
        seen.append(url)
        body = PAGE.encode() if url == lmop.PAGE else content
        return httpx.Response(
            200, content=body, headers={"last-modified": "Mon, 09 Sep 2024 17:36:32 GMT"}
        )

    return get


def test_the_pull_keeps_to_its_own_folder_and_records_the_edition(tmp_path, monkeypatch):
    seen: list = []
    monkeypatch.setattr(lmop, "_get", _fake_get(_workbook(), seen))
    pull_dir = lmop.pull(tmp_path)
    assert seen == [lmop.PAGE, URL]
    assert pull_dir.parent == tmp_path / lmop.SOURCE
    assert [p.name for p in tmp_path.iterdir()] == [lmop.SOURCE]
    params = json.loads((pull_dir / "manifest.json").read_text())["params"]
    assert params["edition"] == "2024-09" and params["file_url"] == URL
    assert lmop.finished_pulls(tmp_path) == [pull_dir]
    assert len(lmop.read_workbook(pull_dir / lmop.FILE)) == len(_table())


def test_a_workbook_with_another_layout_stops_the_pull_and_leaves_nothing(tmp_path, monkeypatch):
    bad = _workbook(_table().rename(columns={lmop.C_WASTE: "Waste"}))
    monkeypatch.setattr(lmop, "_get", _fake_get(bad, []))
    with pytest.raises(ValueError, match="layout has changed"):
        lmop.pull(tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_the_step_writes_the_measures_and_lists_unmatched_landfills(tmp_path, monkeypatch):
    base = config.load_project()
    folders = {name: tmp_path / name for name in ("raw", "interim", "registry")}
    project = base.model_copy(update={"paths": base.paths.model_copy(update=folders)})
    monkeypatch.setattr(lmop, "_get", _fake_get(_workbook(), []))
    with pytest.raises(FileNotFoundError, match="mw ingest lmop"):
        pipeline.write_lmop(project)
    (tmp_path / "registry").mkdir()
    _crosswalk().to_csv(tmp_path / "registry" / "lmop_crosswalk.csv", index=False)
    counts = pipeline.ingest_lmop(project)
    assert counts["edition"] == "2024-09" and counts["sites_matched"] == 4
    assert counts["matches_checked_by_hand"] == 3
    rows = pd.read_parquet(tmp_path / "interim" / "site_metrics" / f"{lmop.SOURCE}.parquet")
    assert len(rows) == counts["rows"]
    # in the project's counties and matched to no site: listed for a hand check
    unmatched = pd.read_csv(tmp_path / "interim" / "lmop_unmatched.csv")
    assert sorted(unmatched[lmop.C_ID]) == [250, 333, 344]


def test_every_registry_site_has_a_line_in_the_match_list():
    registry = config.load_project().resolve(config.load_project().paths.registry)
    sites = pd.read_csv(registry / "sites.csv", dtype=str)
    crosswalk = lmop.read_crosswalk(registry / "lmop_crosswalk.csv")
    assert sorted(crosswalk["site_id"]) == sorted(sites["site_id"])
    assert crosswalk["notes"].str.len().gt(0).all()  # each line says why
    # a match is called checked only for a landfill studied in depth
    pilots = set(sites.loc[sites["tier"] == "pilot", "site_id"])
    assert set(crosswalk.loc[crosswalk["confirmed"], "site_id"]) <= pilots
    assert crosswalk.loc[crosswalk["confirmed"], "lmop_landfill_id"].notna().all()


def test_the_catalogue_describes_the_measures_as_the_step_writes_them():
    measures = config.load_metrics().measures
    for metric_id, unit in lmop.UNITS.items():
        entry = measures[metric_id]
        assert (entry.unit, entry.kind, entry.source) == (unit, "reported", lmop.SOURCE)


def test_the_source_is_open_and_names_its_terms():
    term = load_data_terms().sources[lmop.SOURCE]
    assert term.confirmed and not term.restricted and not term.display_only
    assert term.terms_url and term.instruments == ()


def test_published_rows_are_open(tmp_path):
    rows, _ = _measures()
    _write_inputs(tmp_path)
    _write(tmp_path, rows, name=lmop.SOURCE)
    got = _build(tmp_path).tables["site_metrics"]
    assert len(got) and not got["restricted"].any() and not got["display_only"].any()
    assert set(got["site_id"]) <= {"newby-island", "acme-fill", "sonoma-central"}
