import json

import numpy as np
import pandas as pd
import pytest

from methanewatch.config import load_instruments, load_model, load_project
from methanewatch.model import run
from methanewatch.report import build


def project_in(tmp_path):
    base = load_project()
    return base.model_copy(
        update={
            "paths": base.paths.model_copy(
                update={
                    "processed": tmp_path / "processed",
                    "interim": tmp_path / "interim",
                    "reports": tmp_path / "reports",
                }
            )
        }
    )


def fake_run(project, run_id, sites, kind="real"):
    processed = project.resolve(project.paths.processed)
    (processed / "site_estimates").mkdir(parents=True)
    (processed / "runs").mkdir(parents=True)
    n = len(sites)
    est = pd.DataFrame(
        {
            "site_id": sites,
            "period": "all",
            "run_id": run_id,
            "n_usable_overpasses": [40] * (n - 1) + [3],
            "n_detections": [10] * (n - 1) + [0],
            "f_med": 0.3,
            "f_lo": 0.2,
            "f_hi": 0.4,
            "qbar_kg_hr_med": 500.0,
            "qbar_kg_hr_lo": 400.0,
            "qbar_kg_hr_hi": 650.0,
            "E_t_yr_med": np.linspace(2000, 500, n),
            "E_t_yr_lo": 300.0,
            "E_t_yr_hi": 3000.0,
            "status": ["estimate"] * (n - 1) + ["insufficient_data"],
            "rhat_max": 1.0,
            "ess_bulk_min": 900.0,
            "divergences": 0,
        }
    )
    est.to_parquet(processed / "site_estimates" / f"{run_id}.parquet")
    det = pd.DataFrame(
        {
            "overpass_id": [f"{s}:emit:{i}" for s in sites for i in range(4)],
            "site_id": [s for s in sites for _ in range(4)],
            "instrument": "emit",
            "acquired_utc": pd.date_range("2025-01-01", periods=4 * n, freq="7D", tz="UTC"),
            "detected": [True, False, False, False] * n,
            "q_obs_kg_hr": [600.0, np.nan, np.nan, np.nan] * n,
            "q_sigma_log": [0.3, np.nan, np.nan, np.nan] * n,
        }
    )
    det.to_parquet(processed / "runs" / f"{run_id}-detections.parquet")
    manifest = {"run_id": run_id, "kind": kind, "git_sha": "abc1234def", "provisional": False}
    (processed / "runs" / f"{run_id}.json").write_text(json.dumps(manifest))


def test_build_site_writes_pages_that_pass_lint(tmp_path):
    project = project_in(tmp_path)
    fake_run(project, "fit-x", ["alpha", "beta", "gamma"])
    index = build.build_site(project, "fit-x", tmp_path / "site")
    html = index.read_text()
    assert "screening indication" in html.lower()
    assert "Insufficient data" in html and "gamma" in html
    assert (tmp_path / "site" / "sites" / "beta.html").exists()
    assert "SYNTHETIC DEMO" not in html


def test_demo_runs_are_labelled(tmp_path):
    project = project_in(tmp_path)
    fake_run(project, "demo-x", ["a", "b"], kind="synthetic-demo")
    html = build.build_site(project, "demo-x", tmp_path / "site").read_text()
    assert "SYNTHETIC DEMO" in html


def test_banned_wording_fails_the_build(tmp_path):
    project = project_in(tmp_path)
    fake_run(project, "fit-y", ["violation-landfill", "b"])
    with pytest.raises(build.LintError, match="violation"):
        build.build_site(project, "fit-y", tmp_path / "site")
    assert not (tmp_path / "site" / "index.html").exists()


def test_number_formatting():
    assert build.num(7954.4) == "7,950"
    assert build.num(98.96) == "99.0"
    assert build.num(None) == build.MISSING


def test_fit_real_needs_floor_and_detections(tmp_path):
    project = project_in(tmp_path)
    with pytest.raises(FileNotFoundError):
        run.fit_real(project, load_model(), load_instruments())
    (tmp_path / "interim").mkdir()
    pd.DataFrame({"instrument": ["emit"]}).to_parquet(tmp_path / "interim" / "detections.parquet")
    with pytest.raises(run.ConfigNotReadyError, match="q_min"):
        run.fit_real(project, load_model(), load_instruments())
