"""One scheduled run: refresh the sources, rebuild their datasets, load a review copy.

The steps, in order. Nothing after a failed step runs:

1. ``refresh``: pull EMIT, Sentinel-2 and Carbon Mapper again and rebuild the interim tables
   (``methanewatch.refresh``). A refresh in which any source failed stops the run: the
   publication's "data through" date is the refresh's end date, so publishing would label
   older data as current.
2. ``datasets``: rewrite ``datasets/emit``, ``datasets/sentinel2`` and ``datasets/carbonmapper``
   from the pulls. The annual sources (census, boundaries, GHGRP, CalRecycle) and the pixel steps
   stay manual (ADR 0011). The changes are left for the owner to review and commit.
3. ``publish_build``: assemble and check a snapshot of that refresh. There is no model run until
   detection curves are sourced, so estimates and check results stay empty (ADR 0009).
4. ``push``: load it into the database as a draft (``SUPABASE_DB_URL`` in ``.env``).
5. ``review``: make it visible to the protected review build. A scheduled run never makes anything
   public; that stays a confirmed, manual step (``mw publish set-visibility``).
6. ``deploy_hook``: if ``CF_DEPLOY_HOOK_REVIEW`` is set, ask the host to rebuild the review site.

Each run writes a manifest to ``processed/scheduled/`` (and ``latest.json``) with every step's
result, its duration and, if the run stopped, the step and the reason. The connection string and
the hook URL never appear in it: error text is scrubbed of both first. A lock file keeps two runs
from overlapping.
"""

from __future__ import annotations

import fcntl
import json
import os
import shutil
import time
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import Any

from methanewatch import datasets
from methanewatch import refresh as refresh_mod
from methanewatch.config import ProjectConfig, load_data_terms, load_impact
from methanewatch.provenance import new_id, run_manifest, utcnow

STEPS = ("refresh", "datasets", "publish_build", "push", "review", "deploy_hook")
HOOK_ENV = "CF_DEPLOY_HOOK_REVIEW"


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
        }

    def publish_build() -> dict[str, Any]:
        s = snap.build(
            project,
            load_data_terms(),
            load_impact(),
            refresh_id=state["refresh_id"],
            notes=f"scheduled run {run_id}",
        )
        s.write(project.resolve(project.paths.processed) / "publications")
        state["snapshot"] = s
        tables = s.tables
        return {
            "publish_id": s.publish_id,
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
        ("refresh", do_refresh, ""),
        ("datasets", (lambda: _datasets(project)) if build_datasets else None, "--no-datasets"),
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
            "options": {"push": push, "datasets": build_datasets, "skip": sorted(skip)},
            "refresh_id": state.get("refresh_id"),
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
