"""Measures beside the methane estimate (ADR 0019): the catalogue and the published rows."""

import pandas as pd
import pytest

from methanewatch import config
from methanewatch.config import Measure, MetricsConfig, PublicScope, load_data_terms, load_impact
from methanewatch.ingest import ghgrp
from methanewatch.publish import schemas as pub
from methanewatch.publish import snapshot as snap
from methanewatch.report.lint import check_text
from tests.test_public_scope import _sonoma_under_review
from tests.test_publish_snapshot import _project, _write_inputs


def _rows(**over):
    """Two EPA rows at Newby Island and one at Sonoma Central."""
    rows = pd.DataFrame(
        {
            "site_id": ["newby-island", "newby-island", "sonoma-central"],
            "metric_id": ["epa_landfill_ch4", "epa_combustion_biogenic_co2", "epa_landfill_ch4"],
            "period": ["2023", "2023", "2023"],
            "source": "ghgrp",
            "value": [198862.5, 10379.0, 107440.25],
            "value_text": None,
            "unit": "t CO2e",
            "kind": "reported",
            "confirmed": True,
            "source_id": ["1006179", "1006179", "1004123"],
            "url": "https://data.epa.gov/efservice/",
            "pull_id": "ghgrp-x",
        }
    )
    return rows.assign(**over)


def _write(tmp_path, rows, name="ghgrp"):
    folder = tmp_path / "interim" / "site_metrics"
    folder.mkdir(parents=True, exist_ok=True)
    rows.to_parquet(folder / f"{name}.parquet")


def _build(tmp_path, **kw):
    return snap.build(
        _project(tmp_path),
        load_data_terms(),
        load_impact(),
        model_run_id="model-1",
        check_run_id="repairs-1",
        publish_id="pub-measures",
        **kw,
    )


def test_catalogue_covers_every_epa_gas_and_names_known_sources():
    metrics = config.load_metrics()
    assert metrics.unknown_sources(load_data_terms()) == []
    for metric_id in ghgrp.GAS_MEASURES.values():
        entry = metrics.measures[metric_id]
        assert (entry.unit, entry.kind, entry.source) == (ghgrp.UNIT, "reported", ghgrp.SOURCE)


def test_catalogue_text_passes_the_wording_check():
    for metric_id, entry in config.load_metrics().measures.items():
        for text in (entry.label, entry.unit, entry.caveat or ""):
            assert check_text(text) == [], metric_id


def test_a_source_the_terms_do_not_list_is_reported():
    metrics = MetricsConfig(
        measures={"x": Measure(label="X", unit="t", kind="reported", source="nowhere")}
    )
    assert metrics.unknown_sources(load_data_terms()) == ["nowhere"]


def test_a_measure_kind_outside_the_three_is_refused():
    with pytest.raises(ValueError):
        Measure(label="X", unit="t", kind="estimated", source="ghgrp")


def test_snapshot_carries_the_measures_and_the_catalogue(tmp_path):
    _write_inputs(tmp_path)
    _write(tmp_path, _rows())
    s = _build(tmp_path)
    rows = s.tables["site_metrics"]
    assert list(rows.columns) == [*pub.site_metrics.columns, "public_scope"]
    assert len(rows) == 3 and "pull_id" not in rows
    # EPA's figures are open data: shown as published, never as a reduced display-only form
    assert not rows["restricted"].any() and not rows["display_only"].any()
    assert rows["public_scope"].all() and rows["confirmed"].all()
    assert rows["value_text"].isna().all()  # no text value is not the word "None"
    newby = rows[rows["site_id"] == "newby-island"].set_index("metric_id")["value"]
    assert newby.to_dict() == {
        "epa_landfill_ch4": 198862.5,
        "epa_combustion_biogenic_co2": 10379.0,
    }

    catalogue = s.tables["metric_catalogue"]
    measures = config.load_metrics().measures
    assert catalogue["metric_id"].tolist() == list(measures)  # in the order of the file
    assert catalogue["sort_order"].tolist() == list(range(1, len(measures) + 1))
    assert catalogue.set_index("metric_id").loc["epa_landfill_ch4", "label"] == (
        measures["epa_landfill_ch4"].label
    )
    assert "public_scope" not in catalogue

    again = snap.Snapshot.read(s.write(tmp_path / "publications"))
    assert len(again.tables["site_metrics"]) == 3
    assert len(again.tables["metric_catalogue"]) == len(measures)


def test_without_measure_files_the_table_is_empty_and_the_catalogue_is_still_there(tmp_path):
    _write_inputs(tmp_path)
    s = _build(tmp_path)
    assert len(s.tables["site_metrics"]) == 0
    assert list(s.tables["site_metrics"].columns) == [*pub.site_metrics.columns, "public_scope"]
    assert len(s.tables["metric_catalogue"]) == len(config.load_metrics().measures)


def test_every_source_file_is_read(tmp_path):
    _write_inputs(tmp_path)
    _write(tmp_path, _rows().iloc[:2])
    _write(tmp_path, _rows().iloc[2:], name="other")
    assert len(_build(tmp_path).tables["site_metrics"]) == 3


def test_a_row_for_a_site_that_is_not_in_the_registry_is_left_out(tmp_path):
    _write_inputs(tmp_path)
    _write(tmp_path, _rows(site_id=["newby-island", "newby-island", "somewhere-else"]))
    assert set(_build(tmp_path).tables["site_metrics"]["site_id"]) == {"newby-island"}


def test_a_measure_missing_from_the_catalogue_stops_the_build(tmp_path):
    _write_inputs(tmp_path)
    _write(tmp_path, _rows(metric_id=["epa_landfill_ch4", "made_up", "epa_landfill_ch4"]))
    with pytest.raises(snap.MeasureError, match="made_up"):
        _build(tmp_path)


@pytest.mark.parametrize(
    ("column", "value"), [("unit", "t CH4"), ("kind", "observed"), ("source", "census")]
)
def test_a_row_that_disagrees_with_the_catalogue_stops_the_build(tmp_path, column, value):
    _write_inputs(tmp_path)
    _write(tmp_path, _rows(**{column: value}))
    with pytest.raises(snap.MeasureError, match=f"{column} differs"):
        _build(tmp_path)


def test_a_measure_with_neither_a_number_nor_text_is_refused(tmp_path):
    _write_inputs(tmp_path)
    _write(tmp_path, _rows(value=[None, 1.0, 2.0]))
    with pytest.raises(Exception, match="number or a text value"):
        _build(tmp_path)


def test_rows_follow_their_source_terms(tmp_path):
    # Carbon Mapper is display-only, and a source the terms do not list is held back
    metrics = MetricsConfig(
        measures={
            "cm_count": Measure(label="A", unit="plumes", kind="observed", source="carbonmapper"),
            "epa_landfill_ch4": config.load_metrics().measures["epa_landfill_ch4"],
            "mystery": Measure(label="B", unit="t", kind="reported", source="unlisted"),
        }
    )
    rows = _rows(
        metric_id=["cm_count", "epa_landfill_ch4", "mystery"],
        source=["carbonmapper", "ghgrp", "unlisted"],
        unit=["plumes", "t CO2e", "t"],
        kind=["observed", "reported", "reported"],
        site_id="newby-island",
    )
    _write_inputs(tmp_path)
    _write(tmp_path, rows)
    got = _build(tmp_path, metrics=metrics).tables["site_metrics"].set_index("metric_id")
    assert got["restricted"].to_dict() == {
        "cm_count": True,
        "epa_landfill_ch4": False,
        "mystery": True,
    }
    assert got["display_only"].to_dict() == {
        "cm_count": True,
        "epa_landfill_ch4": False,
        "mystery": False,
    }


def test_rows_of_a_site_under_review_are_out_of_the_public_scope(tmp_path):
    _write_inputs(tmp_path)
    _sonoma_under_review(tmp_path)
    _write(tmp_path, _rows())
    scope = PublicScope(regions=("bay-area",), tiers=("pilot",))
    rows = _build(tmp_path, scope=scope).tables["site_metrics"]
    assert rows.groupby("site_id")["public_scope"].all().to_dict() == {
        "newby-island": True,
        "sonoma-central": False,
    }


def test_a_banned_phrase_in_the_catalogue_stops_the_build(tmp_path):
    _write_inputs(tmp_path)
    entry = config.load_metrics().measures["epa_landfill_ch4"]
    metrics = MetricsConfig(
        measures={
            "epa_landfill_ch4": entry.model_copy(update={"caveat": "A violation was recorded."})
        }
    )
    with pytest.raises(snap.WordingError, match=r"metric_catalogue\.caveat"):
        _build(tmp_path, metrics=metrics)
