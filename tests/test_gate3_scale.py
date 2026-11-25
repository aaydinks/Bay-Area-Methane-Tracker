"""The region term, and the coverage test in the shape of a real fit (ADR 0023)."""

import numpy as np
import pandas as pd
import pytest
from typer.testing import CliRunner

from methanewatch import features
from methanewatch.cli import app
from methanewatch.config import load_instruments, load_model, load_project, load_synthetic
from methanewatch.model import run, simulate
from methanewatch.validate import gates, synthetic
from tests.test_searched import _manifest, _project, _stub_sampling
from tests.test_siteselect import PILOTS, SCREEN, _registry_inputs

REAL = ["newby-island", "kiefer", "altamont", "forward"]
REGION_OF = pd.Series(
    {
        "newby-island": "bay-area",
        "altamont": "bay-area",
        "kiefer": "north-valley",
        "forward": "north-valley",
    }
)


def _feature_table(site_ids) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "site_id": list(site_ids),
            "status": "active",
            "closed": False,
            "area_km2": 1.0,
            "ghgrp_reporter": True,
            "dist_neighbor_m": 500.0,
        }
    )


# --- the region term ---------------------------------------------------------------------


def test_every_region_term_names_a_region_of_the_project():
    regions = {r.id for r in load_project().regions}
    assert set(features.REGION_TERMS.values()) <= regions
    assert set(features.REGION_TERMS) <= features.BINARY


def test_a_region_term_is_needed_only_when_sites_span_regions():
    assert features.region_terms(["bay-area", "bay-area"]) == ()
    assert features.region_terms(["north-valley"]) == ()
    assert features.region_terms(["bay-area", "north-valley", "bay-area"]) == ("north_valley",)


def test_the_region_term_is_built_from_the_registry_region():
    table = features.with_regions(_feature_table(REAL), REGION_OF)
    cov = features.design(table, ["north_valley"])
    # Centred yes/no: two of four sites are in the North Valley
    assert cov.X[:, 0].tolist() == [-0.5, 0.5, -0.5, 0.5]
    assert cov.manifest()["center"] == {"north_valley": 0.5}

    with pytest.raises(ValueError, match="needs each site's region"):
        features.design(_feature_table(REAL), ["north_valley"])
    no_forward = features.with_regions(_feature_table(REAL), REGION_OF.drop("forward"))
    with pytest.raises(ValueError, match=r"no region for \['forward'\]"):
        features.design(no_forward, ["north_valley"])
    one_region = features.with_regions(_feature_table(REAL[:1] + REAL[2:3]), REGION_OF)
    with pytest.raises(ValueError, match="does not vary"):
        features.design(one_region, ["north_valley"])


def test_simulated_sites_take_the_region_values_they_are_given():
    cfg, syn = load_model(), load_synthetic()
    columns = pd.DataFrame({"north_valley": [False, False, True, True, True]})
    sites, hyper = simulate.sites_from_prior(
        5, cfg.priors, syn, np.random.default_rng(3), covariates=("north_valley",), columns=columns
    )
    assert sites["north_valley"].tolist() == columns["north_valley"].tolist()
    assert {"beta_f_north_valley", "beta_mu_north_valley"} <= set(hyper)
    with pytest.raises(ValueError, match="5 rows of covariate values for 4 sites"):
        simulate.sites_from_prior(
            4,
            cfg.priors,
            syn,
            np.random.default_rng(3),
            covariates=("north_valley",),
            columns=columns,
        )


# --- the layout of a real fit ------------------------------------------------------------


def _real_detections() -> pd.DataFrame:
    passes = {
        ("newby-island", "tanager1"): 5,
        ("newby-island", "aircraft"): 2,
        ("altamont", "emit"): 3,
        ("kiefer", "emit"): 7,
        ("forward", "aircraft"): 1,
    }
    rows = [
        {"site_id": s, "instrument": j, "detected": i == 0}
        for (s, j), n in passes.items()
        for i in range(n)
    ]
    return pd.DataFrame(rows)


def test_the_layout_keeps_counts_and_regions_and_names_no_site():
    layout = synthetic.layout_from_detections(_real_detections(), REGION_OF, "made-up passes")
    # Bay Area first, then the North Valley, each in the order of the real ids
    assert layout.sites["site_id"].tolist() == ["synth-00", "synth-01", "synth-02", "synth-03"]
    assert layout.sites["region"].tolist() == ["bay-area"] * 2 + ["north-valley"] * 2
    assert layout.sites["north_valley"].tolist() == [False, False, True, True]
    assert layout.covariates == ("north_valley",)
    counts = layout.schedule.set_index(["site_id", "instrument"])["n_overpasses"].to_dict()
    assert counts == {
        ("synth-00", "emit"): 3,  # altamont
        ("synth-01", "aircraft"): 2,  # newby-island
        ("synth-01", "tanager1"): 5,
        ("synth-02", "aircraft"): 1,  # forward
        ("synth-03", "emit"): 7,  # kiefer
    }
    text = layout.sites.to_csv() + layout.schedule.to_csv()
    assert not any(name in text for name in REAL)


def test_a_layout_of_one_region_has_no_region_term():
    det = _real_detections()
    bay = det[det["site_id"].isin(["newby-island", "altamont"])]
    layout = synthetic.layout_from_detections(bay, REGION_OF, "made-up passes")
    assert layout.covariates == () and "north_valley" not in layout.sites
    with pytest.raises(ValueError, match=r"no region for: \['kiefer'\]"):
        synthetic.layout_from_detections(det, REGION_OF.drop("kiefer"), "made-up passes")


def _results(bay_covered: float, valley_covered: float, n: int = 200) -> pd.DataFrame:
    """Made-up site fits: ``n`` per region, with these shares of intervals holding the truth."""
    frames = []
    for first, (region, share) in enumerate(
        (("bay-area", bay_covered), ("north-valley", valley_covered))
    ):
        covered = np.arange(n) < round(share * n)
        frames.append(
            pd.DataFrame(
                {
                    "site_id": [f"synth-{2 * first + i % 2:02d}" for i in range(n)],
                    "region": region,
                    "replicate": np.arange(n) // 2,
                    "diag_ok": True,
                    "n_detections": np.arange(n) % 20,
                    **{f"{q}_covered": covered for q in synthetic.QUANTITIES},
                    "E_t_yr_true": 100.0,
                    "E_t_yr_med": 110.0,
                    "E_t_yr_lo": 50.0,
                    "E_t_yr_hi": 200.0,
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


def test_each_region_must_be_inside_the_band_as_well():
    syn = load_synthetic()
    both = synthetic.evaluate(_results(0.90, 0.91), syn)
    assert both.passed
    assert both.coverage_by_region == {
        "bay-area": dict.fromkeys(synthetic.QUANTITIES, 0.90),
        "north-valley": dict.fromkeys(synthetic.QUANTITIES, 0.91),
    }
    assert both.n_site_fits_by_region == {"bay-area": 200, "north-valley": 200}
    # Pooled 0.89 is inside the band, but the North Valley alone is not
    uneven = synthetic.evaluate(_results(0.95, 0.83), syn)
    assert 0.85 <= uneven.coverage["E_t_yr"] <= 0.95 and not uneven.passed
    # Without regions the test is the one it was
    plain = synthetic.evaluate(_results(0.95, 0.83).drop(columns="region"), syn)
    assert plain.passed and plain.coverage_by_region == {}


def test_the_report_at_scale_shows_each_region_and_names_no_site(tmp_path):
    layout = synthetic.layout_from_detections(_real_detections(), REGION_OF, "made-up passes")
    results = _results(0.90, 0.91)
    gate = synthetic.evaluate(results, load_synthetic())
    report = synthetic.write_report(
        results, None, gate, tmp_path, "synthetic-test", layout.covariates, layout
    )
    text = report.read_text()
    assert text.startswith("# Gate 3 at the real site count (synthetic-test)")
    assert "**Result: PASS**" in text and "100 replicates x 4 sites = 400 site fits" in text
    assert "Site covariates: north_valley (each site in its real region;" in text
    assert "| bay-area | 200 | 0.900 | 0.900 | 0.900 |" in text
    assert "| north-valley | 200 | 0.910 | 0.910 | 0.910 |" in text
    assert "made-up passes" in text and not any(name in text for name in REAL)
    assert not any(name in (tmp_path / "synthetic-test.csv").read_text() for name in REAL)


def test_the_test_at_scale_writes_outside_the_published_folder(tmp_path, monkeypatch):
    seen = {}

    def fake_gate(n_replicates, out_root, *, layout=None, **kwargs):
        seen.update(n=n_replicates, out_root=out_root, layout=layout)
        return synthetic.evaluate(_results(0.9, 0.9), load_synthetic())

    _registry_inputs(tmp_path)
    regions = {**dict.fromkeys(PILOTS, "bay-area"), SCREEN: "north-valley"}
    sites = pd.read_parquet(tmp_path / "interim" / "sites.parquet")
    sites.assign(region=sites["site_id"].map(regions)).to_parquet(
        tmp_path / "interim" / "sites.parquet"
    )
    monkeypatch.setattr(synthetic, "gate", fake_gate)
    monkeypatch.setattr("methanewatch.config.load_project", lambda: _project(tmp_path))
    assert gates.synthetic_recovery_at_scale(7)
    assert seen["n"] == 7 and seen["out_root"].name == "trials"
    layout = seen["layout"]
    # The two pilots with searched passes and the screen-tier site; Sentinel-2 is left out
    assert layout.sites["region"].tolist() == ["bay-area", "bay-area", "north-valley"]
    assert set(layout.schedule["instrument"]) <= {"aircraft", "emit", "tanager1"}
    assert layout.source.startswith("usable passes of ")


# --- a real fit that pools regions -------------------------------------------------------


def _two_region_inputs(tmp_path):
    _registry_inputs(tmp_path)
    interim = tmp_path / "interim"
    regions = {**dict.fromkeys(PILOTS, "bay-area"), SCREEN: "north-valley"}
    sites = pd.read_parquet(interim / "sites.parquet")
    sites.assign(region=sites["site_id"].map(regions)).to_parquet(interim / "sites.parquet")
    _feature_table([*PILOTS, SCREEN]).to_parquet(interim / "site_features.parquet")


def test_a_fit_that_pools_regions_stops_without_the_region_term(tmp_path, monkeypatch):
    _two_region_inputs(tmp_path)
    _stub_sampling(monkeypatch, {})
    args = (_project(tmp_path), load_model(), load_instruments())
    with pytest.raises(run.ConfigNotReadyError, match=r"several regions.*--covariate north_valley"):
        run.fit_real(*args, allow_unconfirmed=True, tiers=("pilot", "screen"))
    assert not (tmp_path / "processed").exists()  # nothing was fit or written

    run_id = run.fit_real(
        *args, allow_unconfirmed=True, tiers=("pilot", "screen"), covariates=("north_valley",)
    )
    manifest, _ = _manifest(tmp_path, run_id)
    assert manifest["sites"] == [SCREEN, "newby-island", "potrero-hills"]
    assert manifest["covariates"]["names"] == ["north_valley"]
    assert manifest["covariates"]["center"]["north_valley"] == pytest.approx(1 / 3)


def test_a_fit_of_one_region_needs_no_term_and_refuses_one(tmp_path, monkeypatch):
    _two_region_inputs(tmp_path)
    _stub_sampling(monkeypatch, {})
    args = (_project(tmp_path), load_model(), load_instruments())
    run_id = run.fit_real(*args, allow_unconfirmed=True, tiers=("pilot",))
    manifest, _ = _manifest(tmp_path, run_id)
    assert manifest["covariates"] is None
    with pytest.raises(run.ConfigNotReadyError, match="does not vary"):
        run.fit_real(*args, allow_unconfirmed=True, tiers=("pilot",), covariates=("north_valley",))


def test_cli_passes_the_region_term_and_refuses_mixed_options(monkeypatch):
    seen = {}

    def fake_fit_real(project, cfg, instruments, **kwargs):
        seen.update(kwargs)
        return "fit-test"

    monkeypatch.setattr(run, "fit_real", fake_fit_real)
    flags = ["--allow-unconfirmed", "--tier", "pilot", "--covariate", "north_valley"]
    assert CliRunner().invoke(app, ["model", "fit", *flags]).exit_code == 0
    assert seen["covariates"] == ("north_valley",)
    assert CliRunner().invoke(app, ["model", "fit", "--allow-unconfirmed"]).exit_code == 0
    assert seen["covariates"] is None  # the list in config/model.yaml stands

    mixed = CliRunner().invoke(
        app, ["validate", "synthetic", "--at-scale", "--covariates", "closed"]
    )
    assert mixed.exit_code == 1 and "drop --covariates" in mixed.output


@pytest.mark.slow
def test_one_replicate_in_the_shape_of_a_small_two_region_fit():
    rows = [
        {"site_id": f"site-{i}", "instrument": inst, "detected": False}
        for i in range(6)
        for inst, n in (("tanager1", 8), ("emit", 10), ("aircraft", 3))
        for _ in range(n)
    ]
    region_of = pd.Series({f"site-{i}": "bay-area" if i < 4 else "north-valley" for i in range(6)})
    layout = synthetic.layout_from_detections(pd.DataFrame(rows), region_of, "made-up passes")
    out = synthetic.run(1, seed=4, progress=False, layout=layout)
    assert len(out) == 6 and out["diag_ok"].all()
    assert out["region"].tolist() == ["bay-area"] * 4 + ["north-valley"] * 2
    assert (out["n_overpasses"] == 21).all()
    assert {"hyper_beta_f_north_valley", "hyper_beta_mu_north_valley"} <= set(out.columns)
