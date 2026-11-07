"""One scheduled run: refresh the sources, rebuild their datasets, load a review copy.

The steps, in order. Nothing after a failed step runs:

0. ``checkout``: with ``branch`` set (the launchd job sets ``main``), stop unless the checkout is on
   that branch, so a schedule never runs code that is still under development.
1. ``refresh``: pull EMIT, Sentinel-2 and Carbon Mapper again and rebuild the interim tables
   (``methanewatch.refresh``). A refresh in which any source failed stops the run: the
   publication's "data through" date is the refresh's end date, so publishing would label
   older data as current.
2. ``datasets``: rewrite ``datasets/emit``, ``datasets/sentinel2`` and ``datasets/carbonmapper``
   from the pulls. The annual sources (census, boundaries, GHGRP, CalRecycle) and the pixel steps
   stay manual (ADR 0011). The changes are left for the owner to review and commit.
3. ``model_run``: decide whether the copy carries the official fit, the checked run named in
   ``publish.official_model_run`` (``config/project.yaml``). It does only while the detections that
   fit used still equal the refreshed ones for the instruments it used (``official_fit``).
   Instruments it left out, such as Sentinel-2 while its plume search has not run, are counted,
   not compared. The model is never refit here: a refit is checked by a person before it is named.
4. ``publish_build``: assemble and check a snapshot of that refresh, with the official fit's
   estimates when it is carried and none otherwise. Check results stay empty.
5. ``push``: load it into the database as a draft (``SUPABASE_DB_URL`` in ``.env``). This runs
   with or without estimates, so the free database plan never sees seven quiet days (ADR 0009).
6. ``review``: make it visible to the protected review build, only if it carries the official fit.
   The review site shows the newest review copy, so a copy without those estimates would replace
   the one with them. Otherwise the run stops here, the copy stays a draft, and the reason says
   what to refit. A scheduled run never makes anything public; that stays a confirmed, manual step
   (``mw publish set-visibility``).
7. ``deploy_hook``: if ``CF_DEPLOY_HOOK_REVIEW`` is set, ask the host to rebuild the review site.

Each run writes a manifest to ``processed/scheduled/`` (and ``latest.json``) with every step's
result, its duration and, if the run stopped, the step and the reason. The connection string and
the hook URL never appear in it: error text is scrubbed of both first. A lock file keeps two runs
from overlapping.

``launchd_plist`` writes the macOS job that runs this twice a week from the owner's checkout; the
owner installs it (README, "Scheduled run").
"""

from __future__ import annotations

import fcntl
import json
import os
import plistlib
import shutil
import subprocess
import time
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import Any

import pandas as pd

from methanewatch import datasets
from methanewatch import refresh as refresh_mod
from methanewatch.config import REPO_ROOT, ProjectConfig, load_data_terms, load_impact
from methanewatch.provenance import new_id, run_manifest, utcnow

STEPS = (
    "checkout",
    "refresh",
    "datasets",
    "model_run",
    "publish_build",
    "push",
    "review",
    "deploy_hook",
)
HOOK_ENV = "CF_DEPLOY_HOOK_REVIEW"

LAUNCHD_LABEL = "local.methanewatch.scheduled-run"
# Mondays and Thursdays at 08:00 local time: never more than four days apart, inside the seven quiet
# days after which the free database plan pauses (ADR 0009). A Mac that is asleep at that time
# runs the job when it wakes; missed times are merged into one run (launchd.plist(5)).
LAUNCHD_TIMES = ({"Weekday": 1, "Hour": 8, "Minute": 0}, {"Weekday": 4, "Hour": 8, "Minute": 0})
LAUNCHD_LOG = Path.home() / "Library" / "Logs" / "methanewatch-scheduled-run.log"


# The detection columns the persistence model reads (``persistence.prepare``)
MODEL_INPUTS = ("site_id", "instrument", "detected", "q_obs_kg_hr", "q_sigma_log")
DRIFT_KINDS = ("added", "changed", "removed")


def detections_drift(
    fit: pd.DataFrame, now: pd.DataFrame, instruments: Sequence[str]
) -> dict[str, dict[str, Any]]:
    """How ``now`` differs from the detections a fit used, for each of ``instruments``.

    Passes are matched on ``overpass_id`` and compared on ``MODEL_INPUTS`` only, so other columns
    and row order do not count. Empty when they are equal. Each entry has the number of passes
    ``added``, ``changed`` and ``removed`` since the fit and up to three example pass ids.
    """
    cols = ["overpass_id", *MODEL_INPUTS]
    m = fit.loc[fit["instrument"].isin(instruments), cols].merge(
        now.loc[now["instrument"].isin(instruments), cols],
        on="overpass_id",
        how="outer",
        suffixes=("_fit", "_now"),
        indicator=True,
    )
    same = pd.Series(True, index=m.index)
    for c in MODEL_INPUTS:
        a, b = m[f"{c}_fit"], m[f"{c}_now"]
        same &= (a == b).fillna(False).astype(bool) | (a.isna() & b.isna())
    kind = (
        pd.Series("", index=m.index)
        .mask(~same, "changed")
        .mask(m["_merge"].eq("left_only"), "removed")
        .mask(m["_merge"].eq("right_only"), "added")
    )
    m = m.assign(kind=kind, instrument=m["instrument_fit"].fillna(m["instrument_now"]))
    drift = {}
    for inst, g in m[m["kind"] != ""].groupby("instrument"):
        counts = g["kind"].value_counts()
        drift[str(inst)] = {k: int(counts.get(k, 0)) for k in DRIFT_KINDS} | {
            "examples": sorted(g["overpass_id"].astype(str))[:3]
        }
    return drift


def describe_drift(drift: dict[str, dict[str, Any]]) -> str:
    """``emit: 2 passes added, 1 pass changed (e.g. a:emit:2026-11-05, ...)``, per instrument."""
    parts = []
    for inst, d in sorted(drift.items()):
        counts = ", ".join(
            f"{d[k]} {'pass' if d[k] == 1 else 'passes'} {k}" for k in DRIFT_KINDS if d[k]
        )
        parts.append(f"{inst}: {counts} (e.g. {', '.join(d['examples'])})")
    return "; ".join(parts)


def official_fit(project: ProjectConfig) -> dict[str, Any]:
    """Whether a copy of the current interim tables may carry the official fit's estimates.

    ``model_run_id`` is the run to carry, or None with ``no_estimates`` saying why: no fit is
    named, its files are missing, it is not a real fit from a clean checkout that passed its
    checks, or the detections it used differ from ``interim/detections.parquet`` for its
    instruments (``drift``). ``left_out`` counts the current detections of other instruments.
    """
    run_id = project.publish.official_model_run
    if not run_id:
        return {
            "official": None,
            "model_run_id": None,
            "no_estimates": "no official fit is named (publish.official_model_run)",
        }
    out: dict[str, Any] = {"official": run_id, "model_run_id": None}
    processed = project.resolve(project.paths.processed)
    files = {
        "manifest": processed / "runs" / f"{run_id}.json",
        "estimates": processed / "site_estimates" / f"{run_id}.parquet",
        "detections": processed / "runs" / f"{run_id}-detections.parquet",
    }
    missing = [k for k, path in files.items() if not path.exists()]
    if missing:
        why = f"official fit {run_id} has no {' or '.join(missing)} on disk"
        return out | {"no_estimates": why}
    manifest = json.loads(files["manifest"].read_text())
    problems = []
    if manifest.get("kind") != "real":
        problems.append(f"it is a {manifest.get('kind') or 'unlabelled'} run, not a real fit")
    if (manifest.get("diagnostics") or {}).get("ok") is not True:
        problems.append("it failed its convergence checks")
    if manifest.get("git_dirty"):
        problems.append("it was fit from a checkout with unsaved changes")
    if problems:
        return out | {"no_estimates": f"official fit {run_id}: {'; '.join(problems)}"}

    used = pd.read_parquet(files["detections"])
    instruments = sorted(manifest.get("instruments") or used["instrument"].unique())
    det_path = project.resolve(project.paths.interim) / "detections.parquet"
    now = (
        pd.read_parquet(det_path)
        if det_path.exists()
        else pd.DataFrame(columns=["overpass_id", *MODEL_INPUTS])
    )
    left_out = now.loc[~now["instrument"].isin(instruments), "instrument"].value_counts()
    out |= {
        "instruments": instruments,
        "detections": int(used["instrument"].isin(instruments).sum()),
        "left_out": {str(k): int(v) for k, v in left_out.sort_index().items()},
    }
    drift = detections_drift(used, now, instruments)
    if drift:
        return out | {
            "drift": drift,
            "no_estimates": (
                f"official fit {run_id} no longer matches the refreshed detections "
                f"({describe_drift(drift)})"
            ),
        }
    return out | {"model_run_id": run_id}


class Stop(Exception):
    """A step failed or could not start; the message is the plain reason."""


class Busy(Stop):
    """Another scheduled run holds the lock."""


@contextmanager
def _lock(path: Path) -> Iterator[None]:
    with path.open("w") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Busy("another scheduled run is in progress") from None
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def _secrets() -> list[str]:
    """Values that must never reach a manifest or the console."""
    dsn = os.environ.get("SUPABASE_DB_URL") or ""
    values = [dsn, os.environ.get(HOOK_ENV) or ""]
    if dsn:
        from psycopg.conninfo import conninfo_to_dict

        # A malformed string is reported by the push step itself
        with suppress(Exception):
            values.append(str(conninfo_to_dict(dsn).get("password") or ""))
    return sorted((v for v in values if v), key=len, reverse=True)


def scrub(text: str, secrets: Sequence[str]) -> str:
    for s in secrets:
        text = text.replace(s, "<hidden>")
    return text


def _refresh_failures(manifest: dict[str, Any]) -> str:
    steps = manifest["steps"].items()
    failed = [f"{k} ({v.get('error', 'failed')})" for k, v in steps if not v["ok"]]
    return "; ".join(failed) or "the tables were not rebuilt"


def current_branch(repo: Path = REPO_ROOT) -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return out.stdout.strip()


def _datasets(project: ProjectConfig) -> dict[str, Any]:
    raw = project.resolve(project.paths.raw)
    root = project.resolve(project.paths.datasets)
    return {
        **datasets.build_emit(raw, root / "emit"),
        **datasets.build_sentinel2(raw, root / "sentinel2"),
        **datasets.build_carbonmapper(raw, root / "carbonmapper"),
    }


def run(
    project: ProjectConfig,
    *,
    push: bool = True,
    build_datasets: bool = True,
    skip: Sequence[str] = (),
    branch: str | None = None,
) -> dict[str, Any]:
    """Run the steps and write the manifest. ``manifest["ok"]`` is False if the run stopped."""
    from methanewatch.publish import snapshot as snap

    out = project.resolve(project.paths.processed) / "scheduled"
    out.mkdir(parents=True, exist_ok=True)
    started = utcnow()
    run_id, n = new_id("scheduled", started), 1
    while (out / f"{run_id}.json").exists():
        n += 1
        run_id = f"{new_id('scheduled', started)}-{n}"
    secrets = _secrets()
    steps: dict[str, dict[str, Any]] = {}
    state: dict[str, Any] = {}

    def step(name: str, fn: Callable[[], dict[str, Any]]) -> None:
        t0 = time.perf_counter()
        try:
            result = fn()
        except Exception as exc:
            reason = str(exc) if isinstance(exc, Stop) else f"{type(exc).__name__}: {exc}"
            steps[name] = {
                "ok": False,
                "seconds": round(time.perf_counter() - t0, 2),
                "error": scrub(reason, secrets),
            }
            raise Stop(steps[name]["error"]) from exc
        steps[name] = {"ok": True, "seconds": round(time.perf_counter() - t0, 2), **result}

    def checkout() -> dict[str, Any]:
        on = current_branch()
        if on != branch:
            raise Stop(
                f"the checkout is on {on or 'an unknown branch'}, not {branch}; "
                f"switch it to {branch} for scheduled runs"
            )
        return {"branch": on}

    def do_refresh() -> dict[str, Any]:
        m = refresh_mod.run(project, skip=skip)
        state["refresh_id"] = m["run_id"]
        if not m["ok"]:
            raise Stop(f"refresh {m['run_id']} did not finish cleanly: {_refresh_failures(m)}")
        coverage = m["steps"].get("coverage", {})
        return {
            "refresh_id": m["run_id"],
            "data_through": m["window"]["end"],
            "passes": coverage.get("overpasses"),
            "usable_passes": coverage.get("usable"),
            "s2_site_share": coverage.get("s2_site_share"),
            "s2_tile_fallback": coverage.get("s2_tile_fallback"),
        }

    def model_run() -> dict[str, Any]:
        result = official_fit(project)
        state["model_run_id"] = result["model_run_id"]
        state["no_estimates"] = result.get("no_estimates")
        return result

    def publish_build() -> dict[str, Any]:
        model_run_id = state["model_run_id"]
        s = snap.build(
            project,
            load_data_terms(),
            load_impact(),
            refresh_id=state["refresh_id"],
            model_run_id=model_run_id,
            notes=f"scheduled run {run_id}; "
            + (f"estimates from {model_run_id}" if model_run_id else "no estimates"),
        )
        s.write(project.resolve(project.paths.processed) / "publications")
        state["snapshot"] = s
        tables = s.tables
        return {
            "publish_id": s.publish_id,
            "model_run_id": model_run_id,
            "rows": {k: len(v) for k, v in tables.items()},
            "restricted_rows": {
                k: int(tables[k]["restricted"].sum())
                for k in ("passes", "plumes", "site_estimates", "check_results")
                if "restricted" in tables[k]
            },
        }

    def do_push() -> dict[str, Any]:
        from methanewatch.publish import load

        state["dsn"] = load.dsn_from_env()
        return {"rows": load.push(state["snapshot"], state["dsn"])}

    def review() -> dict[str, Any]:
        from methanewatch.publish import load

        if state["no_estimates"]:
            raise Stop(
                f"{state['snapshot'].publish_id} stays a draft, so the review site keeps its copy: "
                f"{state['no_estimates']}. Fit again (mw model fit), check the fit, and name it in "
                "publish.official_model_run (config/project.yaml)"
            )
        r = load.set_visibility(state["dsn"], state["snapshot"].publish_id, "review")
        return {"from": r["from"], "to": r["to"]}

    def deploy_hook() -> dict[str, Any]:
        hook = os.environ.get(HOOK_ENV)
        if not hook:
            return {"skipped": True, "reason": f"{HOOK_ENV} is not set"}
        import httpx

        r = httpx.post(hook, timeout=30)
        if r.status_code >= 400:
            raise Stop(f"the deploy hook answered HTTP {r.status_code}")
        return {"status": r.status_code}

    plan: list[tuple[str, Callable[[], dict[str, Any]] | None, str]] = [
        ("checkout", checkout if branch else None, "no branch required"),
        ("refresh", do_refresh, ""),
        ("datasets", (lambda: _datasets(project)) if build_datasets else None, "--no-datasets"),
        ("model_run", model_run, ""),
        ("publish_build", publish_build, ""),
        ("push", do_push if push else None, "--no-push"),
        ("review", review if push else None, "--no-push"),
        ("deploy_hook", deploy_hook if push else None, "--no-push"),
    ]
    stopped_at, reason = None, None
    try:
        with _lock(out / ".lock"):
            for name, fn, why_skipped in plan:
                if fn is None:
                    steps[name] = {"ok": True, "skipped": True, "reason": why_skipped}
                    continue
                step(name, fn)
    except Busy as exc:
        stopped_at, reason = "lock", str(exc)
    except Stop as exc:
        stopped_at, reason = next(k for k, v in steps.items() if not v["ok"]), str(exc)
    for name in STEPS:
        steps.setdefault(name, {"ok": False, "not_run": True})

    manifest = run_manifest(
        run_id,
        extra={
            "kind": "scheduled",
            "started_at": started.isoformat(),
            "finished_at": utcnow().isoformat(),
            "options": {
                "push": push,
                "datasets": build_datasets,
                "skip": sorted(skip),
                "branch": branch,
            },
            "refresh_id": state.get("refresh_id"),
            "model_run_id": state.get("model_run_id"),
            "publish_id": state["snapshot"].publish_id if "snapshot" in state else None,
            "visibility": steps["review"].get("to") if steps["review"]["ok"] else None,
            "steps": {name: steps[name] for name in STEPS},
            "ok": stopped_at is None,
            "stopped_at": stopped_at,
            "reason": reason,
        },
    )
    path = out / f"{run_id}.json"
    path.write_text(json.dumps(manifest, indent=2, default=str))
    shutil.copyfile(path, out / "latest.json")
    return manifest


def notify(message: str) -> bool:
    """Show a macOS notification; the launchd job has no terminal. False where there is none."""
    osascript = shutil.which("osascript") or "/usr/bin/osascript"
    if not Path(osascript).exists():
        return False
    text = message[:240].replace("\\", "\\\\").replace('"', '\\"')
    script = f'display notification "{text}" with title "Methane Watch scheduled run"'
    subprocess.run([osascript, "-e", script], check=False, timeout=30)
    return True


def launchd_plist(repo: Path, mw: Path, log: Path = LAUNCHD_LOG, *, datasets: bool = True) -> bytes:
    """The launchd job: ``mw scheduled-run`` on ``main``, from ``repo``, at ``LAUNCHD_TIMES``.

    Absolute paths throughout: launchd starts jobs with a bare environment. PATH keeps
    ``/usr/bin`` for git (the manifest's code version) and osascript (the notification).
    """
    args = [str(mw), "scheduled-run", "--branch", "main", "--notify"]
    if not datasets:
        args.append("--no-datasets")
    return plistlib.dumps(
        {
            "Label": LAUNCHD_LABEL,
            "ProgramArguments": args,
            "WorkingDirectory": str(repo),
            "EnvironmentVariables": {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin"},
            "StartCalendarInterval": [dict(t) for t in LAUNCHD_TIMES],
            "StandardOutPath": str(log),
            "StandardErrorPath": str(log),
            "ProcessType": "Background",
            "RunAtLoad": False,
        }
    )
