"""The remediation outcome: repair runner, MDE and the site-page table (simulated data)."""

from dataclasses import replace
from datetime import UTC, datetime

import numpy as np
import pandas as pd
import pytest
from typer.testing import CliRunner

from methanewatch import features, schemas
from methanewatch.cli import app
from methanewatch.config import Sampler, load_model, load_project, load_synthetic
from methanewatch.model import persistence, simulate
from methanewatch.model.grid import LogRateGrid
from methanewatch.repair import run
from methanewatch.repair.model import Repair, assign_periods
from methanewatch.report.build import repair_rows

WINDOWS = load_project().repair


def _passes(days: list[int]) -> pd.DataFrame:
    t0 = pd.Timestamp("2025-01-01", tz="UTC")
    return pd.DataFrame(
        {
            "overpass_id": [f"p{d}" for d in days],
            "site_id": "s1",
            "instrument": "emit",
            "acquired_utc": [t0 + pd.Timedelta(days=d) for d in days],
        }
    )


def test_rough_dates_widen_the_excluded_span():
    det = _passes([-40, -20, -1, 10, 20, 50, 80])
    date = datetime(2025, 1, 1, tzinfo=UTC)
    exact = assign_periods(det, Repair("s1", date), WINDOWS).set_index("overpass_id")["period"]
    assert exact.to_dict() == {"p-40": "before", "p-20": "before", "p-1": "before",
                               "p20": "after", "p50": "after", "p80": "after"}  # fmt: skip
    month = assign_periods(det, Repair("s1", date, date_confidence="month"), WINDOWS)
    # 31 days dropped on each side, on top of the 14-day gap after the repair
    assert month.set_index("overpass_id")["period"].to_dict() == {
        "p-40": "before", "p50": "after", "p80": "after"
    }  # fmt: skip
    with pytest.raises(ValueError, match="date_confidence"):
        assign_periods(det, Repair("s1", date, date_confidence="year"), WINDOWS)


def _repair_table() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "repair_id": ["r1"],
            "site_id": ["sonoma-central"],
            "date_start": ["2023-06-15"],
            "date_end": [None],
            "kind": ["leak-repair"],
            "description": ["surface leak repaired"],
            "source_doc": ["example order, p. 3"],
            "source_page": ["3"],
            "date_confidence": ["week"],
        }
    )


def test_load_repairs_validates_the_registry():
    table = _repair_table()
    (rep,) = run.load_repairs(table)
    assert rep.date_confidence == "week" and rep.date_end is None
    with pytest.raises(Exception):  # noqa: B017 - pandera raises its own error type
        run.load_repairs(table.assign(source_doc=""))


def _settings() -> run.Settings:
    syn, cfg = load_synthetic(), load_model()
    # A short sampler for speed, with diagnostics loosened to match it (tests only)
    loose = cfg.diagnostics.model_copy(
        update={"ess_bulk_min": 100, "rhat_max": 1.05, "max_divergences": 10}
    )
    cfg = cfg.model_copy(update={"diagnostics": loose})
    return run.Settings(
        grid=LogRateGrid.build(syn.q_min_kg_hr, syn.q_max_kg_hr, 32),
        curves={k: v.pod for k, v in syn.instruments.items()},
        release={k: v.release_prob for k, v in syn.instruments.items()},
        meas_sigma_log={k: v.meas_sigma_log for k, v in syn.instruments.items()},
        cfg=cfg,
        windows=WINDOWS,
        sampler=Sampler(chains=2, draws=200, tune=200, target_accept=0.9, seed=1),
    )


def test_simulate_on_schedule_keeps_passes_and_applies_the_drop():
    settings = _settings()
    inst = next(iter(settings.curves))
    t0 = pd.Timestamp("2025-01-01", tz="UTC")
    passes = pd.DataFrame(
        {
            "overpass_id": [f"p{i}" for i in range(400)],
            "site_id": ["s1", "s2"] * 200,
            "instrument": inst,
            "acquired_utc": [t0 + pd.Timedelta(days=i) for i in range(400)],
        }
    )
    params = pd.DataFrame(
        {"site_id": ["s1", "s2"], "f": [1.0, 1.0], "mu": [8.0, 8.0], "sigma": 0.5}
    )
    rng = np.random.default_rng(0)
    after = t0 + pd.Timedelta(days=200)
    sim = run.simulate_on_schedule(
        passes, params, settings, rng, treated="s1", after=after, factor=0.0
    )
    assert sim["overpass_id"].tolist() == passes["overpass_id"].tolist()
    late_s1 = (sim["site_id"] == "s1") & (sim["acquired_utc"] >= after)
    assert not sim.loc[late_s1, "detected"].any()
    assert sim.loc[~late_s1, "detected"].mean() > 0.3
    assert sim.loc[sim["detected"], "q_obs_kg_hr"].gt(0).all()


def test_mde_is_the_mildest_drop_reaching_the_target():
    power = pd.DataFrame({"factor": [0.25, 0.5, 0.75], "p_drop": [0.95, 0.8, 0.3]})
    assert run.mde_pct(power) == 50.0
    assert run.mde_pct(power.assign(p_drop=[0.5, 0.2, 0.1])) is None


PLAIN_RVS = {"alpha_f", "tau_f", "alpha_mu", "tau_mu", "sigma", "z_f", "z_mu"}
REPAIR_RVS = PLAIN_RVS | {"gamma_f", "gamma_mu", "delta_f", "delta_mu"}


class _Stop(Exception):
    """Raised instead of sampling; the tests only need the model and the sampler."""


def _repair_data(covariates: tuple[str, ...] = ()):
    syn = load_synthetic().model_copy(update={"years": 3.0})
    rng = np.random.default_rng(5)
    sites, _ = simulate.sites_from_prior(4, load_model().priors, syn, rng, covariates=covariates)
    det = simulate.simulate_detections(
        sites, simulate.poisson_schedule(sites["site_id"].tolist(), syn, rng), syn, rng
    )
    date = simulate.START + pd.Timedelta(days=548)
    rep = Repair(sites["site_id"].iloc[0], pd.Timestamp(date).to_pydatetime(), repair_id="r1")
    return sites, det, rep


def _fits(settings: run.Settings, det: pd.DataFrame, rep: Repair, monkeypatch) -> list:
    """(model, sampler) of the repair fit and of the baseline fit, without sampling."""
    fits = []

    def fake_fit(model, sampler, *, seed=None, quiet=True):
        fits.append((model, sampler))
        raise _Stop

    monkeypatch.setattr(persistence, "fit", fake_fit)
    controls = sorted(set(det["site_id"]) - {rep.site_id})
    with pytest.raises(_Stop):
        settings.verify(det, rep, controls, 0)
    with pytest.raises(_Stop):
        run.baseline_params(assign_periods(det, rep, settings.windows), settings, 0)
    return fits


@pytest.mark.parametrize("empty", [None, "no names"])
def test_without_covariates_the_repair_fits_are_unchanged(empty, monkeypatch):
    sites, det, rep = _repair_data()
    settings = _settings()
    assert settings.covariates is None and load_model().covariates.names == ()
    if empty:
        settings = replace(settings, covariates=features.design_synthetic(sites, ()))
    (repair_model, repair_sampler), (base_model, base_sampler) = _fits(
        settings, det, rep, monkeypatch
    )
    assert {v.name for v in repair_model.free_RVs} == REPAIR_RVS
    assert {v.name for v in base_model.free_RVs} == PLAIN_RVS
    assert repair_sampler == base_sampler == settings.sampler


def test_covariates_reach_the_repair_and_baseline_fits(monkeypatch):
    sites, det, rep = _repair_data(("closed",))
    settings = replace(_settings(), covariates=features.design_synthetic(sites, ("closed",)))
    (repair_model, repair_sampler), (base_model, base_sampler) = _fits(
        settings, det, rep, monkeypatch
    )
    assert {v.name for v in repair_model.free_RVs} == REPAIR_RVS | {"beta_f", "beta_mu"}
    assert {v.name for v in base_model.free_RVs} == PLAIN_RVS | {"beta_f", "beta_mu"}
    assert list(base_model.coords["covariate"]) == ["closed"]
    # Power-curve fits go through settings.verify, so they use the same model and sampler
    assert repair_sampler.target_accept == base_sampler.target_accept == 0.95


def test_covariates_need_the_site_features_table(tmp_path, monkeypatch):
    registry, interim = tmp_path / "registry", tmp_path / "interim"
    registry.mkdir()
    interim.mkdir()
    base = load_project()
    project = base.model_copy(
        update={"paths": base.paths.model_copy(update={"registry": registry, "interim": interim})}
    )
    cfg = load_model()
    cov_cfg = cfg.model_copy(
        update={"covariates": cfg.covariates.model_copy(update={"names": ("closed",)})}
    )
    # An empty list never looks for the table
    assert run.site_covariates(project, cfg, ["a", "b"]) is None
    with pytest.raises(FileNotFoundError, match="run `mw features build` first"):
        run.site_covariates(project, cov_cfg, ["a", "b"])

    # At the command line the same message exits with code 2
    _repair_table().to_csv(registry / "repairs.csv", index=False)
    pd.DataFrame(
        {
            "overpass_id": ["p1", "p2"],
            "site_id": ["sonoma-central", "newby-island"],
            "instrument": "emit",
            "acquired_utc": pd.Timestamp("2023-01-01", tz="UTC"),
        }
    ).to_parquet(interim / "detections.parquet")
    monkeypatch.setattr("methanewatch.config.load_project", lambda: project)
    monkeypatch.setattr("methanewatch.config.load_model", lambda: cov_cfg)
    result = CliRunner().invoke(app, ["repair", "run", "--allow-unconfirmed"])
    assert result.exit_code == 2
    assert "mw features build" in result.output

    # With the table, the design covers only the sites in the detections
    pd.DataFrame({"site_id": ["a", "b", "c"], "closed": [True, False, True]}).to_parquet(
        interim / "site_features.parquet"
    )
    cov = run.site_covariates(project, cov_cfg, ["a", "b"])
    assert cov.names == ("closed",) and cov.site_ids == ("a", "b")


def _outcome(**kw) -> dict:
    base = {
        "repair_id": "r1",
        "site_id": "s1",
        "date_start": pd.Timestamp("2025-03-01"),
        "date_confidence": "exact",
        "call": "inconclusive",
        "effect_med": -0.4,
        "effect_lo": -1.2,
        "effect_hi": 0.3,
        "p_decrease": 0.8,
        "dE_t_yr_med": 10.0,
        "dE_t_yr_lo": -5.0,
        "dE_t_yr_hi": 30.0,
        "mde_pct": 75.0,
        "n_before": 12,
        "n_after": 9,
        "controls": "s2;s3",
        "diag_ok": True,
        "reason": "",
        "run_id": "repairs-x",
    }
    return base | kw


def test_outcome_schema_needs_an_effect_unless_insufficient():
    empty = dict.fromkeys(["effect_med", "effect_lo", "effect_hi", "p_decrease"], None)
    ok = pd.DataFrame([_outcome(), _outcome(repair_id="r2", call="insufficient_data", **empty)])
    schemas.repair_outcomes.validate(ok)
    with pytest.raises(Exception):  # noqa: B017
        schemas.repair_outcomes.validate(pd.DataFrame([_outcome(call="drop", effect_med=None)]))


def test_site_page_rows_read_as_percent_change():
    out = pd.DataFrame([_outcome(), _outcome(repair_id="r2", site_id="s2", mde_pct=None)])
    (row,) = repair_rows(out, "s1")
    assert row["call"] == "inconclusive"
    assert row["change"] == "-33% (-70% to +35%)"
    assert row["mde"] == "75%" and row["passes"] == "12 / 9"
    assert repair_rows(out, "s2")[0]["mde"] == "none tested"
    assert repair_rows(None, "s1") == []


@pytest.mark.slow
def test_run_all_end_to_end_on_simulated_sites():
    syn = load_synthetic().model_copy(update={"years": 3.0})
    rng = np.random.default_rng(5)
    sites, _ = simulate.sites_from_prior(4, load_model().priors, syn, rng)
    det = simulate.simulate_detections(
        sites, simulate.poisson_schedule(sites["site_id"].tolist(), syn, rng), syn, rng
    )
    date = simulate.START + pd.Timedelta(days=548)
    reps = [Repair(sites["site_id"].iloc[0], pd.Timestamp(date).to_pydatetime(), repair_id="r1")]
    outcomes, power = run.run_all(
        reps, det, _settings(), run_id="repairs-test", n_power_fits=2, progress=False
    )
    assert outcomes["repair_id"].tolist() == ["r1"]
    assert outcomes["call"].iloc[0] != "insufficient_data", outcomes["reason"].iloc[0]
    assert set(power["factor"]) == set(run.POWER_FACTORS)
    assert power["n_fits"].eq(2).all()
