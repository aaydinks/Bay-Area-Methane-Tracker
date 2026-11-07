"""Building a snapshot from the pipeline's outputs: flags, labels, wording, refusals."""

import json

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point
from typer.testing import CliRunner

from methanewatch.cli import app
from methanewatch.config import load_data_terms, load_impact, load_project
from methanewatch.coverage.overpasses import build_detections
from methanewatch.publish import snapshot as snap

SITES = {"newby-island": (-121.94108, 37.45897), "sonoma-central": (-122.74951, 38.29964)}


def _project(tmp_path):
    base = load_project()
    paths = base.paths.model_copy(
        update={
            "registry": tmp_path / "registry",
            "interim": tmp_path / "interim",
            "processed": tmp_path / "processed",
            "reports": tmp_path / "reports",
        }
    )
    return base.model_copy(update={"paths": paths})


def _write_inputs(tmp_path, *, bad_description=False, demo=False, cloud_detail=True):
    """``cloud_detail=False`` writes an overpass table from before ADR 0014, without
    ``valid_frac_tile`` and ``valid_frac_source``."""
    registry, interim, processed = (
        tmp_path / "registry",
        tmp_path / "interim",
        tmp_path / "processed",
    )
    for d in (
        registry,
        interim / "refresh",
        processed / "runs",
        processed / "site_estimates",
        processed / "repair_outcomes",
        tmp_path / "reports" / "validation",
    ):
        d.mkdir(parents=True, exist_ok=True)
    gpd.GeoDataFrame(
        {
            "site_id": list(SITES),
            "name": ["Newby Island Landfill", "Sonoma Central Landfill"],
            "city": ["Milpitas", "Petaluma"],
            "county": ["Santa Clara", "Sonoma"],
            "tier": "pilot",
            "status": ["active", "active"],
            "operator": [None, "Republic Services of Sonoma County"],
            "polygon_source": "provisional 500 m buffer",
            "notes": ["14 violations June 2023", "internal note"],  # never published
        },
        geometry=[Point(*xy).buffer(0.005) for xy in SITES.values()],
        crs="EPSG:4326",
    ).to_parquet(interim / "sites.parquet")
    pd.DataFrame(
        {
            "site_id": list(SITES),
            "status": "active",
            "closed": False,
            "area_km2": 0.785,
            "ghgrp_reporter": [True, True],
            "dist_neighbor_m": [1800.0, None],
        }
    ).to_parquet(interim / "site_features.parquet")
    t = pd.Timestamp("2025-06-01T18:00:00Z")
    ov = pd.DataFrame(
        {
            "overpass_id": [
                "newby-island:emit:2025-06-01",
                "newby-island:tanager1:2025-06-02",
                "sonoma-central:sentinel2:2025-06-03",
            ],
            "site_id": ["newby-island", "newby-island", "sonoma-central"],
            "instrument": ["emit", "tanager1", "sentinel2"],
            "acquired_utc": [t, t + pd.Timedelta(days=1), t + pd.Timedelta(days=2)],
            "scene_ids": [["a"], ["b"], ["c"]],
            "coverage_frac": 1.0,
            "valid_frac": 0.9,
            "usable": True,
            "coverage_source": ["cmr-granule", "stac-footprint", "s2-scene"],
        }
    )
    if cloud_detail:
        # Sen2Cor sees the Sentinel-2 site clear (0.9) on a day the whole tile is mostly cloud
        ov["valid_frac_tile"] = [None, None, 0.4]
        ov["valid_frac_source"] = ["scene", "scene", "site-sen2cor"]
    ov.to_parquet(interim / "overpasses.parquet")
    pd.DataFrame(
        {
            "overpass_id": ov["overpass_id"],
            "site_id": ov["site_id"],
            "instrument": ov["instrument"],
            "acquired_utc": ov["acquired_utc"],
            "detected": [True, True, False],
            "q_obs_kg_hr": [600.0, 1500.0, None],
            "q_sigma_log": [0.3, 0.3, None],
            "n_plumes": [1, 1, 0],
            "n_scenes": 1,
            "multi_plume": False,
        }
    ).to_parquet(interim / "detections.parquet")
    pd.DataFrame(
        {
            "plume_id": ["e1", "cm1"],
            "source": ["emit-v2", "carbonmapper"],
            "instrument": ["emit", "tanager1"],
            "acquired_utc": [t, t + pd.Timedelta(days=1)],
            "origin_lon": [-121.94, -121.94],
            "origin_lat": [37.46, 37.46],
            "q_kg_hr": [None, 1500.0],
            "q_sigma_kg_hr": [None, 400.0],
            "data_version": "v1",
            "pull_id": "pull-1",
            "site_id": "newby-island",
            "attribution": "inside",
            "distance_m": 0.0,
        }
    ).to_parquet(interim / "plumes_attributed.parquet")
    pd.DataFrame(
        {
            "site_id": ["newby-island"],
            "year": [2023],
            "source": ["GHGRP"],
            "reported_ch4_t": [2222.0],
            "reported_co2e_t": [55550.0],
            "gwp_used": [25.0],
            "facility_id": ["1006179"],
            "url": ["https://enviro.epa.gov/"],
            "pull_id": ["pull-2"],
        }
    ).to_parquet(interim / "operator_reports.parquet")
    (interim / "refresh" / "latest.json").write_text(
        json.dumps(
            {
                "run_id": "refresh-1",
                "kind": "refresh",
                "created_at": "2026-10-27T00:00:00+00:00",
                "window": {"start": "2022-08-01", "end": "2026-10-27"},
            }
        )
    )
    (processed / "runs" / "model-1.json").write_text(
        json.dumps(
            {
                "run_id": "model-1",
                "kind": "synthetic-demo" if demo else "real",
                "provisional": True,
                "created_at": "2026-10-28T00:00:00+00:00",
                "instruments": ["emit", "tanager1", "sentinel2"],
            }
        )
    )
    pd.DataFrame(
        {
            "site_id": list(SITES),
            "period": "all",
            "run_id": "model-1",
            "n_usable_overpasses": [2, 1],
            "n_detections": [2, 0],
            "f_med": [0.3, None],
            "f_lo": [0.2, None],
            "f_hi": [0.4, None],
            "qbar_kg_hr_med": [900.0, None],
            "qbar_kg_hr_lo": [500.0, None],
            "qbar_kg_hr_hi": [1800.0, None],
            "E_t_yr_med": [2300.0, None],
            "E_t_yr_lo": [900.0, None],
            "E_t_yr_hi": [5000.0, None],
            "status": ["provisional", "insufficient_data"],
            "rhat_max": 1.0,
            "ess_bulk_min": 900.0,
            "divergences": 0,
        }
    ).to_parquet(processed / "site_estimates" / "model-1.parquet")
    pd.DataFrame(
        {
            "check_id": ["c1"],
            "site_id": ["newby-island"],
            "check_type": ["air-district-notice"],
            "repair_kind": [None],
            "date_start": ["2025-05-12"],
            "date_end": [None],
            "date_confidence": ["week"],
            "description": [
                "Leaks above the limit found on the north slope."
                if bad_description
                else "A surface monitoring round found elevated readings on the north slope."
            ],
            "source_doc": ["notice-2025-05.pdf"],
            "source_doc_title": ["Notice of Violation A12345"],
            "source_url": [None],
            "source_page": ["2"],
            "entered_on": ["2026-10-31"],
        }
    ).to_csv(registry / "checks.csv", index=False)
    pd.DataFrame(
        {
            "repair_id": ["c1"],
            "site_id": ["newby-island"],
            "check_type": ["air-district-notice"],
            "date_start": [pd.Timestamp("2025-05-12")],
            "date_confidence": ["week"],
            "call": ["inconclusive"],
            "effect_med": [0.12],
            "effect_lo": [-0.41],
            "effect_hi": [0.63],
            "p_decrease": [0.36],
            "dE_t_yr_med": [-520.0],
            "dE_t_yr_lo": [-3600.0],
            "dE_t_yr_hi": [1700.0],
            "mde_pct": [75.0],
            "n_before": [14],
            "n_after": [16],
            "controls": ["sonoma-central"],
            "diag_ok": [True],
            "reason": [""],
            "run_id": ["repairs-1"],
        }
    ).to_parquet(processed / "repair_outcomes" / "repairs-1.parquet")
    (processed / "repair_outcomes" / "repairs-1.json").write_text(
        json.dumps({"run_id": "repairs-1", "kind": "repair_outcomes", "provisional": True})
    )
    if bad_description:
        return
    (tmp_path / "reports" / "validation" / "holdout").mkdir()
    (tmp_path / "reports" / "validation" / "holdout" / "holdout-synthetic-x.md").write_text(
        "# Hold-out prediction, SYNTHETIC dry run (holdout-synthetic-x)\n\n"
        "**Result: PASS**. Observed held-out detections fall inside the 90% predictive "
        "interval for **98.0%** of 50 site-folds (target at least 80%).\n"
    )


def test_build_marks_restricted_rows_and_labels_results(tmp_path):
    _write_inputs(tmp_path)
    project = _project(tmp_path)
    s = snap.build(
        project,
        load_data_terms(),
        load_impact(),
        model_run_id="model-1",
        check_run_id="repairs-1",
        publish_id="pub-test",
    )
    t = s.tables
    assert (
        s.publication["data_through"] == "2026-10-27" and s.publication["refresh_id"] == "refresh-1"
    )
    assert s.publication["provisional"] and not s.publication["simulated"]
    assert t["sites"]["provisional"].all() and "notes" not in t["sites"].columns
    assert t["passes"].set_index("instrument")["restricted"].to_dict() == {
        "emit": False,
        "tanager1": True,
        "sentinel2": False,
    }
    assert t["plumes"].set_index("source")["restricted"].to_dict() == {
        "emit-v2": False,
        "carbonmapper": True,
    }
    assert t["plumes"].set_index("plume_id")["overpass_id"]["e1"] == "newby-island:emit:2025-06-01"
    assert t["site_estimates"]["restricted"].all()  # a restricted instrument fed the fit
    reasons = t["site_estimates"].set_index("site_id")["insufficient_reason"]
    assert pd.isna(reasons["newby-island"]) and "too few" in reasons["sonoma-central"]
    r = t["check_results"].iloc[0]
    assert (r["evidence"], r["size"], r["colour"]) == ("weak", "slight", "yellow")
    assert r["plain_reading"].startswith("Methane rose about 13%")
    assert r["restricted"] and r["check_id"] == "c1"
    assert t["checks"].iloc[0]["source_doc_title"] == "Notice of Violation A12345"
    assert t["operator_reports"].iloc[0]["gwp_confirmed"] == load_impact().ghgrp_gwp_ch4.confirmed
    assert t["validation_results"].iloc[0]["metrics"]["share_inside"] == 0.98
    assert {d["source"] for d in s.data_terms} >= {"carbonmapper", "emit-v2", "ghgrp"}
    out = s.write(tmp_path / "publications")
    again = snap.Snapshot.read(out)
    assert again.publish_id == "pub-test" and len(again.tables["passes"]) == 3
    cloud = again.tables["passes"].set_index("instrument")
    assert cloud.loc[
        "sentinel2", ["valid_frac", "valid_frac_tile", "valid_frac_source"]
    ].tolist() == [
        0.9,
        0.4,
        "site-sen2cor",
    ]
    assert cloud.loc[["emit", "tanager1"], "valid_frac_tile"].isna().all()
    assert (cloud.loc[["emit", "tanager1"], "valid_frac_source"] == "scene").all()


def test_overpass_tables_from_before_the_cloud_columns_publish_them_as_null(tmp_path):
    _write_inputs(tmp_path, cloud_detail=False)
    s = snap.build(
        _project(tmp_path),
        load_data_terms(),
        load_impact(),
        model_run_id="model-1",
        check_run_id="repairs-1",
        publish_id="pub-old",
    )
    passes = snap.Snapshot.read(s.write(tmp_path / "publications")).tables["passes"]
    assert len(passes) == 3 and (passes["valid_frac"] == 0.9).all()
    assert passes["valid_frac_tile"].isna().all() and passes["valid_frac_source"].isna().all()


@pytest.mark.parametrize("with_open_plume", [False, True])
def test_restricted_plumes_never_mark_an_open_pass(tmp_path, with_open_plume):
    # Carbon Mapper republishes EMIT plumes under its own terms: a copy seen on an open EMIT pass
    # must not make that pass detected, nor add to its rate or plume count.
    _write_inputs(tmp_path)
    interim = tmp_path / "interim"
    t = pd.Timestamp("2025-06-01T18:00:00Z")
    plumes = pd.DataFrame(
        {
            "plume_id": ["emi20250601t180000-A", "cm1", "emit-7-2025-06-01"],
            "source": ["carbonmapper", "carbonmapper", "emit-v2"],
            "instrument": ["emit", "tanager1", "emit"],
            "acquired_utc": [t, t + pd.Timedelta(days=1), t],
            "origin_lon": -121.94,
            "origin_lat": 37.46,
            "q_kg_hr": [1631.0, 1500.0, 900.0],
            "q_sigma_kg_hr": [300.0, 400.0, 200.0],
            "data_version": "v1",
            "site_id": "newby-island",
            "attribution": "inside",
            "distance_m": 0.0,
        }
    )
    if not with_open_plume:
        plumes = plumes[plumes["source"] == "carbonmapper"]
    plumes.to_parquet(interim / "plumes_attributed.parquet")
    # The coverage step pools every source, so its table counts the copy on the EMIT pass.
    ov = pd.read_parquet(interim / "overpasses.parquet")
    pooled = build_detections(ov, plumes)[0]
    pooled.to_parquet(interim / "detections.parquet")
    assert pooled.set_index("instrument")["detected"]["emit"]

    s = snap.build(_project(tmp_path), load_data_terms(), load_impact(), publish_id="pub-test")
    passes = s.tables["passes"].set_index("instrument")
    emit, tanager = passes.loc["emit"], passes.loc["tanager1"]
    assert not emit["restricted"] and tanager["restricted"]
    if with_open_plume:  # only NASA's own plume counts
        assert (emit["detected"], emit["q_obs_kg_hr"], emit["n_plumes"]) == (True, 900.0, 1)
    else:
        assert not emit["detected"] and pd.isna(emit["q_obs_kg_hr"]) and emit["n_plumes"] == 0
    # A restricted pass keeps what the coverage step found.
    assert (tanager["detected"], tanager["q_obs_kg_hr"], tanager["n_plumes"]) == (True, 1500.0, 1)


def test_nasa_emit_complexes_are_listed_as_open_plumes(tmp_path):
    _write_inputs(tmp_path)
    t = pd.Timestamp("2025-06-01T18:00:00Z")
    lon, lat = SITES["newby-island"]
    gpd.GeoDataFrame(
        {
            "plume_id": ["emit-1-2025-06-01", "emit-2-2025-06-01"],
            "granule_ur": [
                "EMIT_L2B_CH4PLM_002_20250601T180000_000001",
                "EMIT_L2B_CH4PLM_002_20250601T180000_000002",
            ],
            "acquired_utc": [t, t],
            "source_scenes": ["['a']", "['a']"],
        },
        geometry=[Point(lon, lat).buffer(0.001), Point(-121.2, 37.9).buffer(0.001)],
        crs="EPSG:4326",
    ).to_parquet(tmp_path / "interim" / "emit_plume_outlines.parquet")

    s = snap.build(_project(tmp_path), load_data_terms(), load_impact(), publish_id="pub-test")
    plumes = s.tables["plumes"].set_index("plume_id")
    near, far = plumes.loc["emit-1-2025-06-01"], plumes.loc["emit-2-2025-06-01"]
    assert (near["source"], near["instrument"], near["restricted"]) == ("emit-v2", "emit", False)
    assert (near["site_id"], near["attribution"]) == ("newby-island", "inside")
    assert near["overpass_id"] == "newby-island:emit:2025-06-01"
    assert (near["lon"], near["lat"]) == pytest.approx((lon, lat), abs=1e-5)  # outline centroid
    assert pd.isna(near["q_kg_hr"]) and near["data_version"] == "002"
    assert far["attribution"] == "none" and pd.isna(far["overpass_id"]) and not far["restricted"]
    # Listed, not counted: a complex has no rate, so it does not mark its pass.
    emit = s.tables["passes"].set_index("instrument").loc["emit"]
    assert not emit["detected"] and emit["n_plumes"] == 0
    assert len(plumes) == 4  # the two attributed plumes are still there


def test_banned_wording_in_a_description_stops_the_build(tmp_path):
    _write_inputs(tmp_path, bad_description=True)
    # The official title may say "Violation"; the project's own description may not say "limit"-type
    # claims either, but only the banned list is enforced: put a banned word in the description.
    checks = pd.read_csv(tmp_path / "registry" / "checks.csv")
    checks.loc[0, "description"] = "Repairs after the violation were completed in real-time."
    checks.to_csv(tmp_path / "registry" / "checks.csv", index=False)
    with pytest.raises(snap.WordingError, match=r"checks\.description"):
        snap.build(
            _project(tmp_path),
            load_data_terms(),
            load_impact(),
            model_run_id="model-1",
            check_run_id="repairs-1",
        )


def test_simulated_runs_are_refused_unless_allowed(tmp_path):
    _write_inputs(tmp_path, demo=True)
    project = _project(tmp_path)
    with pytest.raises(snap.SimulatedRunError):
        snap.build(project, load_data_terms(), load_impact(), model_run_id="model-1")
    s = snap.build(
        project, load_data_terms(), load_impact(), model_run_id="model-1", allow_simulated=True
    )
    assert s.publication["simulated"] and s.publication["visibility"] == "draft"


def test_cli_build_writes_a_snapshot(tmp_path, monkeypatch):
    _write_inputs(tmp_path)
    monkeypatch.setattr("methanewatch.config.load_project", lambda: _project(tmp_path))
    result = CliRunner().invoke(
        app, ["publish", "build", "--model-run", "model-1", "--check-run", "repairs-1"]
    )
    assert result.exit_code == 0, result.output
    assert "passes: 3 rows" in result.output and "provisional" in result.output
    pub_id = result.output.strip().splitlines()[-1].split()[-1]
    assert (tmp_path / "processed" / "publications" / pub_id / "manifest.json").exists()
    check = CliRunner().invoke(app, ["publish", "check", pub_id])
    assert check.exit_code == 0 and "passed" in check.output


def test_insufficient_reasons_name_the_part_of_the_rule_that_applies():
    # The rule (PLAN 6.6): fewer than 8 usable passes, a 90% range over 2 orders of magnitude,
    # or failed diagnostics. Each insufficient row says which; estimated rows say nothing.
    from methanewatch.config import load_model

    cfg = load_model()
    est = pd.DataFrame(
        {
            "site_id": ["ok", "few", "wide", "diverged", "few-and-wide", "old-rule"],
            "n_usable_overpasses": [28, 5, 18, 30, 6, 30],
            "e_t_yr_lo": [11000.0, 900.0, 8.0, 300.0, 1.0, 300.0],
            "e_t_yr_hi": [17000.0, 1800.0, 998.0, 1500.0, 900.0, 1500.0],
            "status": ["provisional"] + ["insufficient_data"] * 5,
            "rhat_max": [1.005, 1.005, 1.005, 1.005, 1.005, 1.005],
            "ess_bulk_min": [700.0] * 6,
            "divergences": [0, 0, 0, 2, 0, 0],
        }
    )
    r = snap.insufficient_reasons(est, cfg).set_axis(est["site_id"])
    assert r["ok"] is None
    assert r["few"] == "too few usable passes (5; at least 8 needed)"
    assert r["wide"] == "the 90% range is too wide (its top is more than 100 times its bottom)"
    assert r["diverged"] == "the model fit failed its convergence checks"
    assert r["few-and-wide"].startswith("too few usable passes (6;")
    assert "; the 90% range is too wide" in r["few-and-wide"]
    assert r["old-rule"] == "marked insufficient by the model run"


def _set_model_manifest(tmp_path, **fields):
    path = tmp_path / "processed" / "runs" / "model-1.json"
    manifest = json.loads(path.read_text())
    path.write_text(json.dumps({**manifest, **fields}))


def test_snapshot_names_the_instruments_a_fit_left_out(tmp_path):
    # ADR 0016: the published model manifest says which instruments were left out and why
    _write_inputs(tmp_path)
    _set_model_manifest(
        tmp_path,
        instruments=["emit", "tanager1"],
        instruments_left_out={"sentinel2": {"reason": "plume search not run", "n_passes": 1}},
    )
    s = snap.build(_project(tmp_path), load_data_terms(), load_impact(), model_run_id="model-1")
    model = next(r for r in s.runs if r["kind"] == "model")["manifest"]
    assert model["instruments_left_out"]["sentinel2"]["reason"] == "plume search not run"
    assert s.model_instruments() == (["emit", "tanager1"], {"sentinel2": "plume search not run"})


def test_snapshot_of_an_older_fit_shows_the_gap_without_a_reason(tmp_path):
    _write_inputs(tmp_path)
    _set_model_manifest(tmp_path, instruments=["emit", "tanager1"])
    s = snap.build(_project(tmp_path), load_data_terms(), load_impact(), model_run_id="model-1")
    assert s.model_instruments() == (["emit", "tanager1"], {"sentinel2": "not in this model run"})


def test_cli_build_says_which_instruments_the_model_run_used(tmp_path, monkeypatch):
    _write_inputs(tmp_path)
    _set_model_manifest(
        tmp_path,
        instruments=["emit", "tanager1"],
        instruments_left_out={"sentinel2": {"reason": "plume search not run"}},
    )
    monkeypatch.setattr("methanewatch.config.load_project", lambda: _project(tmp_path))
    result = CliRunner().invoke(app, ["publish", "build", "--model-run", "model-1"])
    assert result.exit_code == 0, result.output
    assert (
        "model run instruments: emit, tanager1; left out: sentinel2 (plume search not run)"
        in result.output
    )
