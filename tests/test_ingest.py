"""Ingest parsers checked against small fixtures recorded from the live public APIs."""

import json
from pathlib import Path

import pandas as pd
import pytest
from shapely.geometry import box

from methanewatch.config import load_impact
from methanewatch.ingest import emit, ghgrp
from methanewatch.sentinel2 import search as s2

FX = Path(__file__).parent / "fixtures"


def test_emit_footprints_from_cmr_records():
    records = json.loads((FX / "emit_ch4enh.json").read_text())
    fp = emit.footprints(records)
    assert len(fp) == len(records)
    assert (fp["instrument"] == "emit").all()
    assert fp["valid_frac"].between(0, 1).all()
    assert fp.geometry.is_valid.all()
    assert str(fp["acquired_utc"].dt.tz) == "UTC"
    # CMR returns every scene touching the search box; not all of them cover the site.
    # That is why coverage is scored per site polygon downstream.
    search_box = box(-122.0, 37.42, -121.90, 37.50)
    site_box = box(-121.96, 37.45, -121.93, 37.48)
    assert fp.geometry.intersects(search_box).all()
    assert not fp.geometry.intersects(site_box).all()


def test_emit_rejects_v1_granules():
    records = json.loads((FX / "emit_ch4enh.json").read_text())
    records[0]["umm"]["CollectionReference"]["Version"] = "001"
    with pytest.raises(ValueError, match="version 001"):
        emit.footprints(records)


def test_emit_plume_outline():
    out = emit.plume_outlines(json.loads((FX / "emit_ch4plm.json").read_text()))
    assert len(out) == 1
    row = out.iloc[0]
    assert row["plume_id"].startswith("emit-")
    assert row["source_scenes"].startswith("['EMIT_L2B_CH4ENH")


def test_sentinel2_footprints():
    fp = s2.footprints(json.loads((FX / "s2_items.json").read_text()))
    assert (fp["instrument"] == "sentinel2").all()
    assert fp["valid_frac"].between(0, 1).all()
    assert fp["mgrs_tile"].str.startswith("MGRS-10").all()


def test_ghgrp_normalize_converts_with_configured_gwp(tmp_path):
    pull = tmp_path / "ghgrp-x"
    pull.mkdir()
    (pull / "1006179.json").write_text((FX / "ghgrp_1006179.json").read_text())
    (pull / "manifest.json").write_text(json.dumps({"pull_id": "ghgrp-x"}))
    xw = pd.DataFrame({"site_id": ["newby-island"], "ghgrp_facility_id": ["1006179"]})
    gwp = load_impact().ghgrp_gwp_ch4.by_year()
    out = ghgrp.normalize(pull, xw, gwp).set_index("year")
    assert (out["site_id"] == "newby-island").all()
    assert out.loc[2023, "reported_co2e_t"] == pytest.approx(198862.5)
    assert out.loc[2023, "reported_ch4_t"] == pytest.approx(198862.5 / 25)
    # Years without a configured GWP are dropped, not guessed
    assert set(out.index) <= set(gwp)


def _ghgrp_pull(tmp_path, *facility_ids):
    pull = tmp_path / "ghgrp-x"
    pull.mkdir()
    for fid in facility_ids:
        (pull / f"{fid}.json").write_text((FX / f"ghgrp_{fid}.json").read_text())
    (pull / "manifest.json").write_text(json.dumps({"pull_id": "ghgrp-x"}))
    return pull


def test_ghgrp_gases_are_kept_as_epa_publishes_them(tmp_path):
    # Kiefer Landfill's rows, recorded from Envirofacts on 2026-11-23. ADR 0019 records its
    # 2023 biogenic CO2 as 40,518 t CO2e (PLAN 16.6, the check for step 12).
    pull = _ghgrp_pull(tmp_path, "1004037")
    xw = pd.DataFrame({"site_id": ["kiefer"], "ghgrp_facility_id": ["1004037"]})
    out, left_out = ghgrp.normalize_gases(pull, xw)
    assert len(left_out) == 0
    assert (out["site_id"] == "kiefer").all() and (out["source_id"] == "1004037").all()
    assert set(out["unit"]) == {"t CO2e"} and set(out["kind"]) == {"reported"}
    assert set(out["source"]) == {"ghgrp"} and out["confirmed"].all()
    assert out["value_text"].isna().all() and (out["pull_id"] == "ghgrp-x").all()
    y2023 = out[out["period"] == "2023"].set_index("metric_id")["value"].to_dict()
    assert y2023 == {
        "epa_landfill_ch4": 194423.0,
        "epa_combustion_biogenic_co2": 40518.0,
        "epa_combustion_ch4": 62.25,
        "epa_combustion_n2o": 146.02,
    }
    # One row per measure and year, and the landfill figure equals the methane comparison's
    assert not out.duplicated(["site_id", "metric_id", "period", "source"]).any()
    reports = ghgrp.normalize(pull, xw, load_impact().ghgrp_gwp_ch4.by_year()).set_index("year")
    landfill = out[out["metric_id"] == "epa_landfill_ch4"].set_index("period")["value"]
    assert landfill["2023"] == reports.loc[2023, "reported_co2e_t"]


def test_ghgrp_site_without_a_combustion_report_gets_no_combustion_rows(tmp_path):
    # Newby Island files the landfill report only: no combustion rows, and no zeros in their place
    pull = _ghgrp_pull(tmp_path, "1006179")
    xw = pd.DataFrame({"site_id": ["newby-island"], "ghgrp_facility_id": ["1006179"]})
    out, _ = ghgrp.normalize_gases(pull, xw)
    assert set(out["metric_id"]) == {"epa_landfill_ch4"}
    assert out.set_index("period").loc["2023", "value"] == pytest.approx(198862.5)


def test_ghgrp_rows_with_no_measure_are_counted_not_dropped_silently(tmp_path):
    pull = _ghgrp_pull(tmp_path, "1006179")
    rows = json.loads((pull / "1006179.json").read_text())
    # Subpart D (electricity generation, id 2) has no measure in the catalogue
    rows.append({**rows[0], "sub_part_id": 2, "gas_id": 1, "co2e_emission": 5.0})
    (pull / "1006179.json").write_text(json.dumps(rows))
    xw = pd.DataFrame({"site_id": ["newby-island"], "ghgrp_facility_id": ["1006179"]})
    out, left_out = ghgrp.normalize_gases(pull, xw)
    assert left_out.to_dict("records") == [{"sub_part_id": 2, "gas_id": 1, "rows": 1}]
    assert set(out["metric_id"]) == {"epa_landfill_ch4"}


def test_ghgrp_gases_skip_a_facility_that_is_not_in_the_crosswalk(tmp_path):
    pull = _ghgrp_pull(tmp_path, "1004037", "1006179")
    xw = pd.DataFrame(
        {"site_id": ["newby-island", "acme-fill"], "ghgrp_facility_id": ["1006179", None]}
    )
    out, _ = ghgrp.normalize_gases(pull, xw)
    assert set(out["site_id"]) == {"newby-island"}


def test_ghgrp_facility_fixture_has_pilots():
    fac = pd.read_csv(FX / "ghgrp_facilities_2023.csv")
    assert {1006179, 1007345, 1004123} <= set(fac["facility_id"])


def test_sentinel2_footprints_accept_mixed_timestamp_precision():
    # Earth Search returns most times with fractional seconds and a few without.
    items = json.loads((FX / "s2_items.json").read_text())[:2]
    items[0]["properties"]["datetime"] = "2025-06-27T19:04:08.140000Z"
    items[1]["properties"]["datetime"] = "2025-06-27T19:04:08Z"
    fp = s2.footprints(items)
    assert fp["acquired_utc"].dt.second.tolist() == [8, 8]
