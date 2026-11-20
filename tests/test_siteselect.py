"""A fit says which sites it covers, so sites added to the registry never join one unnoticed."""

import json

import pandas as pd
import pytest
from typer.testing import CliRunner

from methanewatch.cli import app
from methanewatch.config import load_instruments, load_model
from methanewatch.model import run, siteselect
from methanewatch.repair import run as repair_run
from tests.test_repair_outcomes import _check_table
from tests.test_searched import _detections, _inputs, _manifest, _project, _stub_sampling

PILOTS = ["acme-fill", "newby-island", "potrero-hills"]
SCREEN = "kirby-canyon"


def _with_screen_site() -> pd.DataFrame:
    """The pilots' detections plus aircraft passes over one screen-tier site."""
    extra = pd.DataFrame(
        {
            "site_id": SCREEN,
            "instrument": "aircraft",
            "detected": [True, False, False],
            "q_obs_kg_hr": [400.0, None, None],
            "overpass_id": [f"{SCREEN}:aircraft:{i}" for i in range(3)],
            "q_sigma_log": [0.4, None, None],
        }
    )
    return pd.concat([_detections(), extra], ignore_index=True)


def _tiers(sites: dict[str, str]) -> pd.Series:
    return pd.Series(sites, name="tier").rename_axis("site_id")


REGISTRY = _tiers(dict.fromkeys(PILOTS, "pilot") | {SCREEN: "screen"})


def _registry_inputs(tmp_path, tiers=REGISTRY):
    """Fit inputs with a registry of three pilots and one screen-tier site."""
    _inputs(tmp_path)
    interim = tmp_path / "interim"
    _with_screen_site().to_parquet(interim / "detections.parquet")
    tiers.reset_index().to_parquet(interim / "sites.parquet")


def test_a_tier_choice_keeps_only_that_tiers_sites():
    chosen = siteselect.select(_with_screen_site(), REGISTRY, tiers=["pilot"])
    assert chosen.site_ids == PILOTS and SCREEN not in set(chosen.detections["site_id"])
    assert chosen.not_selected == [SCREEN] and chosen.explicit
    assert chosen.manifest() == {
        "site_selection": {"tiers": ["pilot"], "sites": []},
        "sites_not_selected": [SCREEN],
    }
    pd.testing.assert_frame_equal(chosen.detections, _detections())


def test_sites_can_be_named_and_added_to_a_tier():
    det = _with_screen_site()
    named = siteselect.select(det, REGISTRY, sites=["newby-island", SCREEN])
    assert named.site_ids == [SCREEN, "newby-island"]
    assert named.not_selected == ["acme-fill", "potrero-hills"]
    both = siteselect.select(det, REGISTRY, tiers=["screen"], sites=["acme-fill"])
    assert both.site_ids == ["acme-fill", SCREEN]
    # Ids need no registry table; tiers do
    assert siteselect.select(det, None, sites=[SCREEN]).site_ids == [SCREEN]
    with pytest.raises(ValueError, match="cannot choose sites by tier"):
        siteselect.select(det, None, tiers=["pilot"])


def test_with_no_choice_a_registry_of_one_tier_is_fit_whole():
    # Today's registry: five pilots. Nothing is asked and nothing is left out.
    det = _detections()
    chosen = siteselect.select(det, _tiers(dict.fromkeys(PILOTS, "pilot")))
    assert chosen.detections is det and chosen.site_ids == PILOTS
    assert not chosen.explicit and chosen.not_selected == []
    assert siteselect.select(det, None).detections is det  # no registry table to read


def test_with_no_choice_a_registry_of_several_tiers_stops_the_fit():
    with pytest.raises(ValueError, match=r"several tiers \(pilot: 3, screen: 1\).*--tier"):
        siteselect.select(_with_screen_site(), REGISTRY)
    # A screen-tier site with no detections yet is not in the fit, so it asks nothing
    assert siteselect.select(_detections(), REGISTRY).site_ids == PILOTS


def test_unknown_tiers_and_sites_are_refused():
    det = _with_screen_site()
    with pytest.raises(ValueError, match=r"no site of tier \['pilots'\]"):
        siteselect.select(det, REGISTRY, tiers=["pilots"])
    with pytest.raises(ValueError, match=r"not in the registry or the detections: \['newby'\]"):
        siteselect.select(det, REGISTRY, sites=["newby"])
    empty = _tiers({"shoreline": "pilot"})
    with pytest.raises(ValueError, match="no detections to fit"):
        siteselect.select(det, empty, tiers=["pilot"])


def test_a_fit_of_the_pilot_tier_leaves_the_screen_site_out_and_records_it(
    tmp_path, monkeypatch, capsys
):
    _registry_inputs(tmp_path)
    _stub_sampling(monkeypatch, {})
    run_id = run.fit_real(
        _project(tmp_path),
        load_model(),
        load_instruments(),
        allow_unconfirmed=True,
        tiers=("pilot",),
    )
    manifest, used = _manifest(tmp_path, run_id)
    assert manifest["sites"] == ["newby-island", "potrero-hills"]  # as without the new site
    assert SCREEN not in set(used["site_id"]) and len(used) == 16
    assert manifest["site_selection"] == {"tiers": ["pilot"], "sites": []}
    assert manifest["sites_not_selected"] == [SCREEN]
    assert manifest["sites_left_out"] == ["acme-fill"]  # seen only by Sentinel-2, as before
    assert "sites: 3 chosen (tier pilot); 1 with detections left out" in capsys.readouterr().out


def test_a_fit_with_no_choice_stops_once_the_registry_has_a_second_tier(tmp_path, monkeypatch):
    _registry_inputs(tmp_path)
    _stub_sampling(monkeypatch, {})
    with pytest.raises(run.ConfigNotReadyError, match="several tiers"):
        run.fit_real(_project(tmp_path), load_model(), load_instruments(), allow_unconfirmed=True)
    assert not (tmp_path / "processed").exists()  # nothing was fit or written


def test_a_default_fit_of_a_pilot_only_registry_is_unchanged(tmp_path, monkeypatch):
    _inputs(tmp_path)
    _tiers(dict.fromkeys(PILOTS, "pilot")).reset_index().to_parquet(
        tmp_path / "interim" / "sites.parquet"
    )
    seen = {}
    _stub_sampling(monkeypatch, seen)
    run_id = run.fit_real(
        _project(tmp_path), load_model(), load_instruments(), allow_unconfirmed=True
    )
    manifest, used = _manifest(tmp_path, run_id)
    assert manifest["sites"] == ["newby-island", "potrero-hills"] and len(used) == 16
    assert manifest["site_selection"] == {"tiers": [], "sites": []}
    assert manifest["sites_not_selected"] == []


def test_cli_fit_passes_the_choice_through_and_reports_a_refusal(tmp_path, monkeypatch):
    seen = {}

    def fake_fit_real(project, cfg, instruments, **kwargs):
        seen.update(kwargs)
        return "fit-test"

    monkeypatch.setattr(run, "fit_real", fake_fit_real)
    flags = ["--allow-unconfirmed", "--tier", "pilot", "--site", SCREEN, "--site", "acme-fill"]
    result = CliRunner().invoke(app, ["model", "fit", *flags])
    assert result.exit_code == 0, result.output
    assert seen["tiers"] == ("pilot",) and seen["sites"] == (SCREEN, "acme-fill")

    monkeypatch.undo()
    _registry_inputs(tmp_path)
    monkeypatch.setattr("methanewatch.config.load_project", lambda: _project(tmp_path))
    refused = CliRunner().invoke(app, ["model", "fit", "--allow-unconfirmed"])
    assert refused.exit_code == 1 and "several tiers" in refused.output


# --- the repair checks draw their controls from the same choice ----------------------------


def _fake_run_all(seen):
    def run_all(repairs, det, settings, **kwargs):
        seen["sites"] = sorted(det["site_id"].unique())
        seen["controls"] = kwargs["control_sites"]
        return pd.DataFrame({"repair_id": [r.repair_id for r in repairs]}), pd.DataFrame()

    return run_all


def test_repair_controls_are_the_chosen_sites_not_every_registry_site(tmp_path, monkeypatch):
    _registry_inputs(tmp_path)
    (tmp_path / "registry").mkdir()
    checks = _check_table().assign(site_id=["newby-island", SCREEN])
    checks.to_csv(tmp_path / "registry" / "checks.csv", index=False)
    seen = {}
    monkeypatch.setattr(repair_run, "run_all", _fake_run_all(seen))
    run_id = repair_run.run_real(
        _project(tmp_path),
        load_model(),
        load_instruments(),
        allow_unconfirmed=True,
        tiers=("pilot",),
    )
    # Controls: the pilots with searched passes. The checked screen-tier site keeps its own
    # passes, so its check can still be run against those controls.
    assert seen["controls"] == ["newby-island", "potrero-hills"]
    assert seen["sites"] == [SCREEN, "newby-island", "potrero-hills"]
    out = tmp_path / "processed" / "repair_outcomes"
    manifest = json.loads((out / f"{run_id}.json").read_text())
    assert manifest["site_selection"] == {"tiers": ["pilot"], "sites": []}
    assert manifest["sites_not_selected"] == [SCREEN]

    with pytest.raises(run.ConfigNotReadyError, match="several tiers"):
        repair_run.run_real(
            _project(tmp_path), load_model(), load_instruments(), allow_unconfirmed=True
        )


def test_run_all_draws_each_checks_controls_from_the_control_sites(monkeypatch):
    from datetime import UTC, datetime

    from methanewatch.repair.model import Repair

    calls = []

    class Settings:
        def verify(self, det, rep, controls, seed):
            calls.append((rep.site_id, controls))
            return type("R", (), {"call": "insufficient_data"})()

    monkeypatch.setattr(repair_run, "outcome_row", lambda rep, res, mde, run_id: {})
    monkeypatch.setattr(repair_run.schemas.repair_outcomes, "validate", lambda df: df)
    repairs = [Repair(s, datetime(2025, 1, 1, tzinfo=UTC)) for s in ("newby-island", SCREEN)]
    det = _with_screen_site()
    common = {"run_id": "r", "progress": False}

    controls = ["newby-island", "potrero-hills"]
    repair_run.run_all(repairs, det, Settings(), control_sites=controls, **common)
    assert calls == [
        ("newby-island", ["potrero-hills"]),
        (SCREEN, ["newby-island", "potrero-hills"]),
    ]
    calls.clear()
    repair_run.run_all(repairs[:1], det, Settings(), **common)  # every site, as before
    assert calls == [("newby-island", ["acme-fill", SCREEN, "potrero-hills"])]
