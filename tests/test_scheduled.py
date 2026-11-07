"""The scheduled run on a small fixture project: the network pulls, the dataset writers and the
database are replaced, so nothing here touches the network (tests/db covers the real load). The
fixture's official fit is made from the fixture's own refresh, so its detections match."""

import json
import plistlib

import geopandas as gpd
import httpx
import pandas as pd
import pytest
from typer.testing import CliRunner

from methanewatch import datasets, scheduled
from methanewatch import refresh as refresh_mod
from methanewatch.cli import app
from methanewatch.config import load_project
from methanewatch.ingest import pipeline
from methanewatch.publish import load
from tests.test_refresh import UTM, utm_box

DSN = "postgresql://writer:s3cret-pw@db.example.invalid:5432/postgres"
HOOK = "https://hooks.example.invalid/deploy/abc123"
DAYS = pd.date_range("2025-01-05T18:00Z", periods=10, freq="14D")
FIT = "fit-20251101T000000Z"


def make_project(tmp_path):
    reg, interim = tmp_path / "registry", tmp_path / "interim"
    reg.mkdir()
    (interim / "footprints").mkdir(parents=True)
    pd.DataFrame(
        {"site_id": ["a", "b"], "name": ["Site A", "Site B"], "tier": "pilot",
         "status": ["", "closed"], "polygon_source": ["provisional 500 m buffer", "permit map"]}
    ).to_csv(reg / "sites.csv", index=False)  # fmt: skip
    pd.DataFrame({"site_id": ["a", "b"], "ghgrp_facility_id": ["1", ""]}).to_csv(
        reg / "operator_crosswalk.csv", index=False
    )
    gpd.GeoDataFrame(
        {"site_id": ["a", "b"], "part": "boundary"},
        geometry=[
            utm_box(590000, 4146000, 591000, 4147000),
            utm_box(600000, 4146000, 601000, 4147000),
        ],
        crs="EPSG:4326",
    ).to_file(reg / "sites.geojson", driver="GeoJSON")
    base = load_project()
    paths = base.paths.model_copy(
        update={"registry": reg, "raw": tmp_path / "raw", "interim": interim,
                "processed": tmp_path / "processed", "datasets": tmp_path / "datasets",
                "reports": tmp_path / "reports"}
    )  # fmt: skip
    publish = base.publish.model_copy(update={"official_model_run": None})
    return base.model_copy(update={"paths": paths, "publish": publish})


def name_fit(
    project, run_id, detections, *, kind="real", ok=True, dirty=False, instruments=None, missing=()
):
    """Write a model run's files (all but ``missing``) and name it the official fit."""
    processed = project.resolve(project.paths.processed)
    (processed / "runs").mkdir(parents=True, exist_ok=True)
    (processed / "site_estimates").mkdir(parents=True, exist_ok=True)
    if "manifest" not in missing:
        (processed / "runs" / f"{run_id}.json").write_text(
            json.dumps(
                {"run_id": run_id, "created_at": "2025-11-01T00:00:00Z", "kind": kind,
                 "git_dirty": dirty, "provisional": True, "diagnostics": {"ok": ok},
                 "instruments": instruments or sorted(detections["instrument"].unique())}
            )
        )  # fmt: skip
    if "detections" not in missing:
        detections.to_parquet(processed / "runs" / f"{run_id}-detections.parquet")
    if "estimates" not in missing:
        pd.DataFrame(
            {"site_id": ["a", "b"], "period": "all", "run_id": run_id,
             "n_usable_overpasses": [10, 10], "n_detections": [1, 0],
             "f_med": 0.2, "f_lo": 0.1, "f_hi": 0.4,
             "qbar_kg_hr_med": 500.0, "qbar_kg_hr_lo": 300.0, "qbar_kg_hr_hi": 800.0,
             "E_t_yr_med": 876.0, "E_t_yr_lo": 300.0, "E_t_yr_hi": 2000.0,
             "status": ["provisional", "insufficient_data"], "rhat_max": 1.004,
             "ess_bulk_min": 700.0, "divergences": 0}
        ).to_parquet(processed / "site_estimates" / f"{run_id}.parquet")  # fmt: skip
    publish = project.publish.model_copy(update={"official_model_run": run_id})
    return project.model_copy(update={"publish": publish})


def fit_detections(root):
    return pd.read_parquet(root / "processed" / "runs" / f"{FIT}-detections.parquet")


@pytest.fixture
def world(tmp_path, monkeypatch):
    """Fixture project with fake pulls, dataset writers, database and deploy hook."""
    project = make_project(tmp_path)
    interim = tmp_path / "interim"
    calls = {"push": [], "visibility": [], "hook": [], "datasets": []}

    def fake_emit(project, bbox, start, end):
        gpd.GeoDataFrame(
            {"scene_id": [f"s{i}" for i in range(10)], "instrument": "emit",
             "acquired_utc": DAYS, "valid_frac": 0.95},
            geometry=[utm_box(585000, 4140000, 605000, 4150000)] * 10,
            crs="EPSG:4326",
        ).to_parquet(interim / "footprints" / "emit.parquet")  # fmt: skip
        return {"emit_scenes": 10}

    def fake_carbonmapper(project, bbox, start, end):
        origin = gpd.GeoSeries(gpd.points_from_xy([590500], [4146500]), crs=UTM).to_crs(4326)
        (interim / "plumes").mkdir(exist_ok=True)
        pd.DataFrame(
            {"plume_id": ["p1"], "source": "carbonmapper", "instrument": "emit",
             "acquired_utc": [DAYS[2]], "origin_lon": origin.x, "origin_lat": origin.y,
             "q_kg_hr": [600.0], "q_sigma_kg_hr": [150.0], "data_version": "v3e", "pull_id": "x"}
        ).to_parquet(interim / "plumes" / "carbonmapper.parquet")  # fmt: skip
        return {"plumes": 1}

    monkeypatch.setattr(pipeline, "ingest_emit", fake_emit)
    monkeypatch.setattr(pipeline, "ingest_sentinel2", lambda *a: {"sentinel2_scenes": 0})
    monkeypatch.setattr(pipeline, "ingest_carbonmapper", fake_carbonmapper)
    for name in ("emit", "sentinel2", "carbonmapper"):
        monkeypatch.setattr(
            datasets,
            f"build_{name}",
            lambda raw, out, name=name: calls["datasets"].append(name) or {f"{name}_rows": 1},
        )
    monkeypatch.setattr(
        load, "push", lambda snapshot, dsn: calls["push"].append(dsn) or {"passes": 20}
    )

    def fake_visibility(dsn, publish_id, visibility):
        calls["visibility"].append((publish_id, visibility))
        return {"publish_id": publish_id, "from": "draft", "to": visibility}

    monkeypatch.setattr(load, "set_visibility", fake_visibility)

    def fake_post(url, timeout):
        calls["hook"].append(url)
        return httpx.Response(204)

    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setenv("SUPABASE_DB_URL", DSN)
    monkeypatch.setenv("CF_DEPLOY_HOOK_REVIEW", HOOK)
    # The official fit used the detections of a refresh with the same pulls
    assert refresh_mod.run(project)["ok"]
    project = name_fit(project, FIT, pd.read_parquet(interim / "detections.parquet"))
    return project, tmp_path, calls


def test_a_run_refreshes_builds_pushes_and_marks_review(world):
    project, root, calls = world
    m = scheduled.run(project)

    assert m["ok"] and m["stopped_at"] is None
    assert [s for s, r in m["steps"].items() if not r["ok"]] == []
    assert m["visibility"] == "review"
    assert calls["datasets"] == ["emit", "sentinel2", "carbonmapper"]
    assert calls["push"] == [DSN]
    assert calls["visibility"] == [(m["publish_id"], "review")]  # never public
    assert calls["hook"] == [HOOK]
    assert m["steps"]["refresh"]["refresh_id"] == m["refresh_id"]
    # The official fit still matches the refresh, so its estimates are carried
    fit = m["steps"]["model_run"]
    assert m["model_run_id"] == fit["model_run_id"] == FIT and "no_estimates" not in fit
    assert fit["instruments"] == ["emit"] and fit["detections"] > 0 and fit["left_out"] == {}
    # Carbon Mapper rows go into the snapshot restricted
    build = m["steps"]["publish_build"]
    assert build["rows"]["plumes"] == 1 and build["restricted_rows"]["plumes"] == 1
    assert build["model_run_id"] == FIT and build["rows"]["site_estimates"] == 2
    assert (root / "processed" / "publications" / m["publish_id"] / "manifest.json").exists()
    # The manifest is on disk and holds neither the connection string nor the hook
    text = (root / "processed" / "scheduled" / "latest.json").read_text()
    assert json.loads(text)["run_id"] == m["run_id"]
    assert "s3cret-pw" not in text and "abc123" not in text


def test_a_failed_source_stops_the_run_before_publishing(world, monkeypatch):
    project, root, calls = world

    def down(*args):
        raise httpx.ConnectError("source is down")

    monkeypatch.setattr(pipeline, "ingest_sentinel2", down)
    m = scheduled.run(project)

    assert not m["ok"] and m["stopped_at"] == "refresh"
    assert "sentinel2" in m["reason"] and "source is down" in m["reason"]
    assert m["refresh_id"]  # the failed refresh is still named
    assert m["steps"]["publish_build"] == {"ok": False, "not_run": True}
    assert calls["push"] == [] and calls["hook"] == []
    assert not (root / "processed" / "publications").exists()


def test_without_a_connection_string_the_run_stops_at_the_push(world, monkeypatch):
    project, _, calls = world
    monkeypatch.delenv("SUPABASE_DB_URL")
    m = scheduled.run(project)

    assert m["stopped_at"] == "push" and "SUPABASE_DB_URL is not set" in m["reason"]
    assert m["steps"]["publish_build"]["ok"]  # the snapshot is built and kept
    assert m["steps"]["review"]["not_run"] and calls["hook"] == []


def test_errors_are_scrubbed_of_secrets(world, monkeypatch):
    project, _, _ = world

    def refused(snapshot, dsn):
        raise RuntimeError(f"could not connect with {dsn} (password s3cret-pw)")

    monkeypatch.setattr(load, "push", refused)
    m = scheduled.run(project)

    assert m["stopped_at"] == "push"
    assert "s3cret-pw" not in json.dumps(m) and "<hidden>" in m["reason"]


def test_a_failing_deploy_hook_is_reported(world, monkeypatch):
    project, _, _ = world
    monkeypatch.setattr(httpx, "post", lambda url, timeout: httpx.Response(500))
    m = scheduled.run(project)

    assert m["stopped_at"] == "deploy_hook" and "HTTP 500" in m["reason"]
    assert m["steps"]["review"]["ok"]  # the data is loaded; only the rebuild request failed
    assert "abc123" not in json.dumps(m)


def test_without_a_hook_the_last_step_is_skipped(world, monkeypatch):
    project, _, calls = world
    monkeypatch.delenv("CF_DEPLOY_HOOK_REVIEW")
    m = scheduled.run(project)

    assert m["ok"] and m["steps"]["deploy_hook"]["skipped"] and calls["hook"] == []


def test_no_push_builds_the_snapshot_only(world):
    project, root, calls = world
    m = scheduled.run(project, push=False, build_datasets=False)

    assert m["ok"] and calls["push"] == [] and calls["datasets"] == []
    assert all(m["steps"][s]["skipped"] for s in ("datasets", "push", "review", "deploy_hook"))
    assert (root / "processed" / "publications" / m["publish_id"]).exists()


def test_two_runs_never_overlap(world):
    project, root, calls = world
    out = root / "processed" / "scheduled"
    out.mkdir(parents=True)
    with scheduled._lock(out / ".lock"):
        m = scheduled.run(project)
    assert m["stopped_at"] == "lock" and "in progress" in m["reason"]
    assert m["steps"]["refresh"]["not_run"] and calls["push"] == []


def test_cli_exit_codes(world, monkeypatch):
    project, _, _ = world
    monkeypatch.setattr("methanewatch.config.load_project", lambda: project)
    ok = CliRunner().invoke(app, ["scheduled-run"])
    assert ok.exit_code == 0, ok.output
    assert "visible to the review build" in ok.output

    monkeypatch.delenv("SUPABASE_DB_URL")
    stopped = CliRunner().invoke(app, ["scheduled-run"])
    assert stopped.exit_code == 2
    assert "stopped at push" in stopped.output and "SUPABASE_DB_URL" in stopped.output

    built = CliRunner().invoke(app, ["scheduled-run", "--no-push"])
    assert built.exit_code == 0 and "not loaded" in built.output


def test_a_run_on_the_wrong_branch_stops_before_the_refresh(world, monkeypatch):
    project, _, calls = world
    monkeypatch.setattr(scheduled, "current_branch", lambda repo=None: "feat/experiment")
    m = scheduled.run(project, branch="main")

    assert m["stopped_at"] == "checkout" and "feat/experiment, not main" in m["reason"]
    assert m["steps"]["refresh"]["not_run"] and calls["push"] == []

    monkeypatch.setattr(scheduled, "current_branch", lambda repo=None: "main")
    m = scheduled.run(project, branch="main")
    assert m["ok"] and m["steps"]["checkout"]["branch"] == "main"


def test_the_notification_quotes_the_reason_safely(monkeypatch, tmp_path):
    osascript = tmp_path / "osascript"
    osascript.touch()
    seen = []
    monkeypatch.setattr(scheduled.shutil, "which", lambda name: str(osascript))
    monkeypatch.setattr(scheduled.subprocess, "run", lambda args, **kw: seen.append(args))

    assert scheduled.notify('Stopped at push: "SUPABASE_DB_URL" is not set \\ check .env')
    ((cmd, flag, script),) = seen
    assert cmd == str(osascript) and flag == "-e"
    assert script == (
        'display notification "Stopped at push: \\"SUPABASE_DB_URL\\" is not set \\\\ check .env"'
        ' with title "Methane Watch scheduled run"'
    )


def test_the_launchd_job_runs_on_main_twice_a_week(tmp_path):
    repo, mw, log = tmp_path / "repo", tmp_path / "repo/.venv/bin/mw", tmp_path / "job.log"
    job = plistlib.loads(scheduled.launchd_plist(repo, mw, log))

    assert job["Label"] == scheduled.LAUNCHD_LABEL
    assert job["ProgramArguments"] == [str(mw), "scheduled-run", "--branch", "main", "--notify"]
    assert job["WorkingDirectory"] == str(repo)
    assert job["StandardOutPath"] == job["StandardErrorPath"] == str(log)
    assert "/usr/bin" in job["EnvironmentVariables"]["PATH"].split(":")
    assert job["RunAtLoad"] is False
    days = sorted(t["Weekday"] for t in job["StartCalendarInterval"])
    assert days == [1, 4]  # Monday and Thursday: never 7 quiet days for the database
    no_datasets = plistlib.loads(scheduled.launchd_plist(repo, mw, log, datasets=False))
    assert no_datasets["ProgramArguments"][-1] == "--no-datasets"


def test_cli_writes_the_launchd_job_and_prints_the_commands(tmp_path):
    out = tmp_path / "agents" / "job.plist"
    result = CliRunner().invoke(app, ["scheduled-plist", "--out", str(out)])
    assert result.exit_code == 0, result.output
    job = plistlib.loads(out.read_bytes())
    assert job["ProgramArguments"][1:3] == ["scheduled-run", "--branch"]
    assert f"launchctl bootstrap gui/$(id -u) {out}" in result.output
    assert f"launchctl bootout gui/$(id -u)/{scheduled.LAUNCHD_LABEL}" in result.output


def test_a_refresh_that_changes_the_fit_detections_leaves_the_copy_a_draft(world):
    project, root, calls = world
    # The fit saw one pass fewer and a different rate on another than this refresh gives
    det = fit_detections(root)
    seen = det.index[det["detected"]][0]
    det.loc[seen, "q_obs_kg_hr"] *= 2
    det.drop(index=det.index[~det["detected"]][0]).to_parquet(
        root / "processed" / "runs" / f"{FIT}-detections.parquet"
    )
    m = scheduled.run(project)

    fit = m["steps"]["model_run"]
    assert fit["ok"] and fit["model_run_id"] is None and m["model_run_id"] is None
    assert {k: fit["drift"]["emit"][k] for k in ("added", "changed", "removed")} == {
        "added": 1, "changed": 1, "removed": 0
    }  # fmt: skip
    assert m["steps"]["publish_build"]["rows"]["site_estimates"] == 0
    # Loaded as a draft, so the database stays active, but never marked review
    assert calls["push"] == [DSN] and calls["visibility"] == [] and calls["hook"] == []
    assert not m["ok"] and m["stopped_at"] == "review" and m["visibility"] is None
    assert f"{m['publish_id']} stays a draft" in m["reason"]
    assert f"official fit {FIT} no longer matches" in m["reason"]
    assert "emit: 1 pass added, 1 pass changed" in m["reason"]
    assert det.loc[seen, "overpass_id"] in m["reason"]
    assert "publish.official_model_run" in m["reason"]
    assert m["steps"]["deploy_hook"] == {"ok": False, "not_run": True}


def test_without_an_official_fit_the_copy_stays_a_draft(world):
    project, _, calls = world
    publish = project.publish.model_copy(update={"official_model_run": None})
    m = scheduled.run(project.model_copy(update={"publish": publish}))

    assert m["stopped_at"] == "review" and "no official fit is named" in m["reason"]
    assert m["steps"]["model_run"]["official"] is None
    assert calls["push"] == [DSN] and calls["visibility"] == []


@pytest.mark.parametrize(
    ("change", "why"),
    [
        ({"kind": "synthetic-demo"}, "it is a synthetic-demo run, not a real fit"),
        ({"ok": False}, "it failed its convergence checks"),
        ({"dirty": True}, "it was fit from a checkout with unsaved changes"),
        ({"missing": ("estimates",)}, "has no estimates on disk"),
        ({"missing": ("manifest", "detections")}, "has no manifest or detections on disk"),
    ],
)
def test_an_official_fit_that_cannot_be_carried_says_why(world, change, why):
    project, root, _ = world
    project = name_fit(project, "fit-other", fit_detections(root), **change)
    result = scheduled.official_fit(project)

    assert result["official"] == "fit-other" and result["model_run_id"] is None
    assert why in result["no_estimates"]


def test_instruments_the_fit_left_out_are_counted_not_compared(world):
    project, root, _ = world
    det = pd.read_parquet(root / "interim" / "detections.parquet")
    s2 = det.head(2).assign(
        instrument="sentinel2",
        overpass_id=lambda d: d["site_id"] + ":sentinel2:" + d.index.astype(str),
        detected=False,
        q_obs_kg_hr=float("nan"),
    )
    pd.concat([det, s2]).to_parquet(root / "interim" / "detections.parquet")
    result = scheduled.official_fit(project)

    assert result["model_run_id"] == FIT and result["instruments"] == ["emit"]
    assert result["left_out"] == {"sentinel2": 2}


def test_detections_drift_compares_the_model_inputs_by_pass():
    fit = pd.DataFrame(
        {"overpass_id": ["a:emit:1", "a:emit:2", "b:emit:1", "a:tanager1:1"],
         "site_id": ["a", "a", "b", "a"], "instrument": ["emit"] * 3 + ["tanager1"],
         "detected": [True, False, False, False], "q_obs_kg_hr": [500.0, None, None, None],
         "q_sigma_log": [0.3, None, None, None], "n_scenes": [1, 1, 1, 1]}
    )  # fmt: skip
    # Order, other columns and instruments outside the fit do not count; missing equals missing
    same = fit.iloc[::-1].assign(n_scenes=2)
    other = pd.DataFrame({"overpass_id": ["a:sentinel2:1"], "site_id": "a",
                          "instrument": "sentinel2", "detected": True,
                          "q_obs_kg_hr": 90.0, "q_sigma_log": 0.5})  # fmt: skip
    assert scheduled.detections_drift(fit, pd.concat([same, other]), ["emit", "tanager1"]) == {}

    now = fit.copy()
    now.loc[0, "q_obs_kg_hr"] = 510.0  # changed
    now = pd.concat([now.drop(index=2), now.head(1).assign(overpass_id="a:emit:3")])
    drift = scheduled.detections_drift(fit, now, ["emit", "tanager1"])
    assert drift == {
        "emit": {"added": 1, "changed": 1, "removed": 1,
                 "examples": ["a:emit:1", "a:emit:3", "b:emit:1"]}
    }  # fmt: skip
    assert scheduled.describe_drift(drift) == (
        "emit: 1 pass added, 1 pass changed, 1 pass removed (e.g. a:emit:1, a:emit:3, b:emit:1)"
    )


def test_cli_reports_a_copy_without_estimates(world):
    project, root, _ = world
    fit_detections(root).head(0).to_parquet(
        root / "processed" / "runs" / f"{FIT}-detections.parquet"
    )
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("methanewatch.config.load_project", lambda: project)
        stopped = CliRunner().invoke(app, ["scheduled-run"])
        built = CliRunner().invoke(app, ["scheduled-run", "--no-push"])

    assert stopped.exit_code == 2 and "stopped at review" in stopped.output
    assert "stays a draft" in stopped.output and "no longer matches" in stopped.output
    assert built.exit_code == 0 and "model_run: ok" in built.output
    assert "no estimates: official fit" in built.output and "not loaded" in built.output
