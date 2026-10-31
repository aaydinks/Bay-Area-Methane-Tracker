"""Load a snapshot into the database and manage its visibility.

One transaction per push: either every table lands or nothing does. The connection string
comes from ``SUPABASE_DB_URL`` in the git-ignored ``.env`` (the session pooler); nothing here
reads a key from anywhere else.
"""

from __future__ import annotations

import json
import math
import os
from datetime import UTC, datetime
from typing import Any

import pandas as pd
import psycopg
from psycopg.types.json import Jsonb

from methanewatch.publish import schemas as pub
from methanewatch.publish.feed import update_items
from methanewatch.publish.snapshot import Snapshot

ENV_DSN = "SUPABASE_DB_URL"
VISIBILITY_RANK = {"draft": 0, "review": 1, "public": 2}


class NoDatabaseError(RuntimeError):
    pass


def dsn_from_env() -> str:
    dsn = os.environ.get(ENV_DSN)
    if not dsn:
        raise NoDatabaseError(
            f"{ENV_DSN} is not set; put the session pooler connection string in .env"
        )
    return dsn


def _clean(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, pd.Timestamp):
        return None if pd.isna(value) else value.to_pydatetime()
    if isinstance(value, dict | list):
        return Jsonb(value)
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        return value.item()
    return value


def _rows(df: pd.DataFrame, columns: list[str], extra: dict[str, Any]) -> list[tuple]:
    return [
        tuple(_clean(r.get(c, extra.get(c))) for c in columns)
        for r in ({**extra, **row} for row in df.to_dict("records"))
    ]


def _insert(
    cur,
    table: str,
    df: pd.DataFrame,
    columns: list[str],
    publish_id: str,
    *,
    geometry: dict[str, str] | None = None,
) -> int:
    if not len(df):
        return 0
    geometry = geometry or {}
    cols = ["publish_id", *columns]
    placeholders = []
    for c in cols:
        expr = geometry.get(c, "%s")
        placeholders.append(expr)
    sql = f"insert into public.{table} ({', '.join(cols)}) values ({', '.join(placeholders)})"
    cur.executemany(sql, _rows(df, cols, {"publish_id": publish_id}))
    return len(df)


def previous_publication(cur, visibility_floor: str) -> dict | None:
    """The newest publication at ``visibility_floor`` or above, with its diffable tables."""
    allowed = [
        v for v, rank in VISIBILITY_RANK.items() if rank >= VISIBILITY_RANK[visibility_floor]
    ]
    cur.execute(
        "select publish_id, model_run_id, check_run_id from public.publications "
        "where visibility = any(%s) order by created_at desc limit 1",
        (allowed,),
    )
    row = cur.fetchone()
    if not row:
        return None
    publish_id, model_run_id, check_run_id = row
    tables = {}
    for name, cols in {
        "plumes": ["source", "plume_id"],
        "checks": ["check_id"],
        "validation_results": ["report_id"],
        "sites": ["site_id", "polygon_source"],
    }.items():
        cur.execute(
            f"select {', '.join(cols)} from public.{name} where publish_id = %s", (publish_id,)
        )
        tables[name] = pd.DataFrame(cur.fetchall(), columns=cols)
    return {
        "publish_id": publish_id,
        "model_run_id": model_run_id,
        "check_run_id": check_run_id,
        "tables": tables,
    }


def push(snapshot: Snapshot, dsn: str, *, compare_with: str = "review") -> dict[str, int]:
    """Load the snapshot as a draft in one transaction. Returns row counts per table."""
    p = snapshot.publication
    counts: dict[str, int] = {}
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        prev = previous_publication(cur, compare_with)
        names = dict(
            zip(snapshot.tables["sites"]["site_id"], snapshot.tables["sites"]["name"], strict=True)
        )
        items, new_plumes = update_items(
            snapshot.tables,
            prev["tables"] if prev else None,
            current_runs={"model_run_id": p["model_run_id"], "check_run_id": p["check_run_id"]},
            previous_runs={
                "model_run_id": prev["model_run_id"],
                "check_run_id": prev["check_run_id"],
            }
            if prev
            else None,
            site_names=names,
        )
        plumes = snapshot.tables["plumes"]
        if len(plumes):
            key = list(
                zip(plumes["source"].astype(str), plumes["plume_id"].astype(str), strict=True)
            )
            plumes = plumes.assign(new_in_update=[k in new_plumes for k in key])
        update_log = pd.DataFrame(items, columns=list(pub.update_log.columns))

        cur.execute(
            "insert into public.publications (publish_id, created_at, visibility, simulated, "
            "provisional, refresh_id, model_run_id, check_run_id, data_through, source_lag_days, "
            "git_sha, git_dirty, notes) "
            "values (%s, %s, 'draft', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                p["publish_id"],
                p["created_at"],
                p["simulated"],
                p["provisional"],
                p["refresh_id"],
                p["model_run_id"],
                p["check_run_id"],
                p["data_through"],
                p["source_lag_days"],
                p["git_sha"],
                p["git_dirty"],
                p["notes"],
            ),
        )
        for run in snapshot.runs:
            m = run["manifest"] or {}
            cur.execute(
                "insert into public.runs (run_id, kind, created_at, git_sha, git_dirty, "
                "config_sha256, versions, manifest) values (%s, %s, %s, %s, %s, %s, %s, %s) "
                "on conflict (run_id) do update set manifest = excluded.manifest",
                (
                    run["run_id"],
                    run["kind"],
                    m.get("created_at"),
                    m.get("git_sha"),
                    m.get("git_dirty"),
                    Jsonb(m.get("config_sha256") or {}),
                    Jsonb(m.get("versions") or {}),
                    Jsonb(m),
                ),
            )
        for t in snapshot.data_terms:
            cur.execute(
                "insert into public.data_terms (source, display_name, raw_publishable, "
                "derived_publishable, confirmed, checked_on, terms_url, credit_line) "
                "values (%s, %s, %s, %s, %s, %s, %s, %s) on conflict (source) do update set "
                "display_name = excluded.display_name, raw_publishable = excluded.raw_publishable, "
                "derived_publishable = excluded.derived_publishable, "
                "confirmed = excluded.confirmed, checked_on = excluded.checked_on, "
                "terms_url = excluded.terms_url, credit_line = excluded.credit_line",
                (
                    t["source"],
                    t["display_name"],
                    t["raw_publishable"],
                    t["derived_publishable"],
                    t["confirmed"],
                    t["checked_on"],
                    t["terms_url"],
                    t["credit_line"],
                ),
            )
        pid = p["publish_id"]
        sites = snapshot.tables["sites"].rename(columns={"outline_wkt": "outline"})
        counts["sites"] = _insert(
            cur,
            "sites",
            sites,
            [c for c in pub.sites.columns if c != "outline_wkt"] + ["outline"],
            pid,
            geometry={"outline": "extensions.st_multi(extensions.st_geomfromtext(%s, 4326))"},
        )
        nb = snapshot.tables["neighbours"].rename(columns={"geom_wkt": "geom"})
        counts["neighbours"] = _insert(
            cur,
            "neighbours",
            nb,
            [c for c in pub.neighbours.columns if c != "geom_wkt"] + ["geom"],
            pid,
            geometry={"geom": "extensions.st_geomfromtext(%s, 4326)"},
        )
        counts["plumes"] = _insert(cur, "plumes", plumes, list(pub.plumes.columns), pid)
        counts["passes"] = _insert(
            cur, "passes", snapshot.tables["passes"], list(pub.passes.columns), pid
        )
        counts["site_estimates"] = _insert(
            cur,
            "site_estimates",
            snapshot.tables["site_estimates"],
            list(pub.site_estimates.columns),
            pid,
        )
        counts["checks"] = _insert(
            cur, "checks", snapshot.tables["checks"], list(pub.checks.columns), pid
        )
        counts["check_results"] = _insert(
            cur,
            "check_results",
            snapshot.tables["check_results"],
            list(pub.check_results.columns),
            pid,
        )
        counts["operator_reports"] = _insert(
            cur,
            "operator_reports",
            snapshot.tables["operator_reports"],
            list(pub.operator_reports.columns),
            pid,
        )
        counts["population_context"] = _insert(
            cur,
            "population_context",
            snapshot.tables["population"],
            list(pub.population.columns),
            pid,
        )
        counts["site_features"] = _insert(
            cur,
            "site_features",
            snapshot.tables["site_features"],
            list(pub.site_features.columns),
            pid,
        )
        vr = snapshot.tables["validation_results"].copy()
        if len(vr):
            vr["metrics"] = vr["metrics"].map(
                lambda m: m if isinstance(m, dict) else json.loads(m) if isinstance(m, str) else {}
            )
        counts["validation_results"] = _insert(
            cur, "validation_results", vr, list(pub.validation_results.columns), pid
        )
        counts["update_log"] = _insert(
            cur,
            "update_log",
            update_log.assign(data_through=p["data_through"]),
            [*pub.update_log.columns, "data_through"],
            pid,
        )
        conn.commit()
    return counts


def set_visibility(dsn: str, publish_id: str, visibility: str) -> dict:
    """Promote or demote a publication. A simulated run can never become public."""
    if visibility not in VISIBILITY_RANK:
        raise ValueError(f"visibility must be one of {list(VISIBILITY_RANK)}")
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(
            "select simulated, visibility from public.publications where publish_id = %s",
            (publish_id,),
        )
        row = cur.fetchone()
        if not row:
            raise LookupError(f"no publication {publish_id}")
        simulated, current = row
        if visibility == "public" and simulated:
            raise ValueError(f"{publish_id} is a simulated run and cannot be made public")
        published_at = datetime.now(UTC) if visibility == "public" else None
        cur.execute(
            "update public.publications set visibility = %s, "
            "published_at = coalesce(%s, published_at) where publish_id = %s",
            (visibility, published_at, publish_id),
        )
        conn.commit()
    return {"publish_id": publish_id, "from": current, "to": visibility}


def list_publications(dsn: str) -> list[dict]:
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(
            "select publish_id, visibility, simulated, provisional, data_through, created_at "
            "from public.publications order by created_at desc"
        )
        return [
            dict(
                zip(
                    [
                        "publish_id",
                        "visibility",
                        "simulated",
                        "provisional",
                        "data_through",
                        "created_at",
                    ],
                    r,
                    strict=True,
                )
            )
            for r in cur.fetchall()
        ]
