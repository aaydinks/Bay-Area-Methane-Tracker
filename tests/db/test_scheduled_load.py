"""The scheduled run with the real load: the snapshot lands as a review publication, its Carbon
Mapper rows stay restricted, and the publishable role sees none of it."""

from __future__ import annotations

import pytest

from methanewatch import scheduled
from methanewatch.publish import load
from tests.db.conftest import as_role, rows
from tests.db.test_publish_load import clean  # noqa: F401  (fixture)
from tests.test_scheduled import world  # noqa: F401  (fixture)

psycopg = pytest.importorskip("psycopg")

PUSH, SET_VISIBILITY = load.push, load.set_visibility


def test_scheduled_run_loads_a_review_publication(clean, world, monkeypatch):  # noqa: F811
    project, _, calls = world
    monkeypatch.setattr(load, "push", PUSH)
    monkeypatch.setattr(load, "set_visibility", SET_VISIBILITY)
    monkeypatch.setenv("SUPABASE_DB_URL", clean)

    m = scheduled.run(project)
    assert m["ok"], m["reason"]
    assert m["steps"]["push"]["rows"]["plumes"] == 1
    with psycopg.connect(clean) as conn:
        assert rows(conn, "select publish_id, visibility from public.publications") == [
            (m["publish_id"], "review")
        ]
        assert rows(conn, "select source, restricted from public.plumes") == [
            ("carbonmapper", True)
        ]
        assert rows(conn, "select count(*) from public.passes where restricted") == [(0,)]
        with as_role(conn, "anon"):
            assert rows(conn, "select count(*) from public.publications") == [(0,)]
            assert rows(conn, "select count(*) from public.passes") == [(0,)]
    assert calls["hook"]  # asked the host to rebuild the review site once
