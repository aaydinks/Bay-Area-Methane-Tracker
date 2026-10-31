"""The scheduled run on a small fixture project: the network pulls, the dataset writers and the
database are replaced, so nothing here touches the network (tests/db covers the real load)."""

import json
import plistlib

import geopandas as gpd
import httpx
import pandas as pd
import pytest
from typer.testing import CliRunner

from methanewatch import datasets, scheduled
from methanewatch.cli import app
from methanewatch.config import load_project
from methanewatch.ingest import pipeline
from methanewatch.publish import load
from tests.test_refresh import UTM, utm_box

DSN = "postgresql://writer:s3cret-pw@db.example.invalid:5432/postgres"
HOOK = "https://hooks.example.invalid/deploy/abc123"
DAYS = pd.date_range("2025-01-05T18:00Z", periods=10, freq="14D")


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
    return base.model_copy(update={"paths": paths})


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
    # Carbon Mapper rows go into the snapshot restricted
    build = m["steps"]["publish_build"]
    assert build["rows"]["plumes"] == 1 and build["restricted_rows"]["plumes"] == 1
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
