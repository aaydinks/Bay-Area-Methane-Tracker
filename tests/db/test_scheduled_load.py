"""The scheduled run with the real load: the snapshot lands as a review publication with the
official fit's estimates, its Carbon Mapper rows stay restricted, the publishable role sees none
of it, and a copy without those estimates never becomes the review copy."""

from __future__ import annotations

from itertools import count

import pandas as pd
import pytest

from methanewatch import scheduled
from methanewatch.publish import load
from methanewatch.publish import snapshot as snap
from tests.db.conftest import as_role, rows
from tests.db.test_publish_load import clean  # noqa: F401  (fixture)
from tests.test_scheduled import FIT, world  # noqa: F401  (fixture)

psycopg = pytest.importorskip("psycopg")

PUSH, SET_VISIBILITY = load.push, load.set_visibility


@pytest.fixture
def real_load(clean, monkeypatch):  # noqa: F811
    monkeypatch.setattr(load, "push", PUSH)
    monkeypatch.setattr(load, "set_visibility", SET_VISIBILITY)
    monkeypatch.setenv("SUPABASE_DB_URL", clean)
    # Two runs inside one second would share a publication id
    n = count(1)
    monkeypatch.setattr(snap, "new_id", lambda prefix, when=None: f"{prefix}-{next(n):04d}")
    return clean


def test_scheduled_run_loads_a_review_publication(real_load, world):  # noqa: F811
    project, _, calls = world

    m = scheduled.run(project)
    assert m["ok"], m["reason"]
    assert m["steps"]["push"]["rows"]["plumes"] == 1
    with psycopg.connect(real_load) as conn:
        assert rows(
            conn, "select publish_id, visibility, model_run_id from public.publications"
        ) == [(m["publish_id"], "review", FIT)]
        assert rows(conn, "select count(*) from public.site_estimates") == [(2,)]
        assert rows(conn, "select source, restricted from public.plumes") == [
            ("carbonmapper", True)
        ]
        assert rows(conn, "select count(*) from public.passes where restricted") == [(0,)]
        with as_role(conn, "anon"):
            assert rows(conn, "select count(*) from public.publications") == [(0,)]
            assert rows(conn, "select count(*) from public.passes") == [(0,)]
    assert calls["hook"]  # asked the host to rebuild the review site once


def test_a_copy_without_the_official_fit_never_replaces_the_review_copy(real_load, world):  # noqa: F811
    project, root, _ = world
    first = scheduled.run(project)
    assert first["ok"], first["reason"]

    # The next refresh has a pass the official fit never saw (7 November 2026 had no fit at all)
    path = root / "processed" / "runs" / f"{FIT}-detections.parquet"
    pd.read_parquet(path).iloc[1:].to_parquet(path)
    second = scheduled.run(project)
    assert second["stopped_at"] == "review" and "no longer matches" in second["reason"]

    with psycopg.connect(real_load) as conn:
        assert rows(
            conn, "select publish_id, visibility from public.publications order by created_at"
        ) == [(first["publish_id"], "review"), (second["publish_id"], "draft")]
        assert rows(conn, "select publish_id from public.v_current_review_publication") == [
            (first["publish_id"],)
        ]
        assert rows(
            conn, "select publish_id, count(*) from public.site_estimates group by publish_id"
        ) == [(first["publish_id"], 2)]
