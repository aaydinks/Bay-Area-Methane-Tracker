"""Prune old draft and review publications in the migrated database (ADR 0021)."""

from __future__ import annotations

import pytest

from methanewatch.publish import load
from tests.db.conftest import rows, run_script

psycopg = pytest.importorskip("psycopg")


@pytest.fixture
def seeded(test_dsn):
    """Six publications a day apart, oldest first: review, public, review, draft, review,
    draft. Each has one update-feed row, so the cascade can be seen."""
    spec = ["review", "public", "review", "draft", "review", "draft"]
    with psycopg.connect(test_dsn, autocommit=True) as conn:
        run_script(conn, "delete from public.publications")
        for i, visibility in enumerate(spec):
            conn.execute(
                "insert into public.publications (publish_id, visibility, created_at) "
                "values (%s, %s, timestamptz '2026-11-01' + %s * interval '1 day')",
                (f"pub-{i}", visibility, i),
            )
            conn.execute(
                "insert into public.update_log (publish_id, item_order, kind, text) "
                "values (%s, 0, 'note', 'x')",
                (f"pub-{i}",),
            )
    yield test_dsn
    with psycopg.connect(test_dsn, autocommit=True) as conn:
        run_script(conn, "delete from public.publications")


def _left(dsn) -> list[str]:
    with psycopg.connect(dsn) as conn:
        return [r[0] for r in rows(conn, "select publish_id from public.publications order by 1")]


def test_dry_run_lists_and_counts_but_removes_nothing(seeded):
    plan = load.prune(seeded, keep_review=1, keep_draft=1)
    assert [p["publish_id"] for p in plan["publications"]] == ["pub-0", "pub-2", "pub-3"]
    assert plan["rows"]["update_log"] == 3 and plan["rows"]["passes"] == 0
    assert plan["deleted"] == 0 and not plan["applied"]
    assert plan["kept"] == {"draft": 1, "public": 1, "review": 1}
    assert len(_left(seeded)) == 6


def test_apply_removes_the_old_copies_and_their_rows(seeded):
    done = load.prune(seeded, keep_review=1, keep_draft=1, apply=True)
    assert done["deleted"] == 3
    assert _left(seeded) == ["pub-1", "pub-4", "pub-5"]  # the public copy and the newest two
    with psycopg.connect(seeded) as conn:
        left = rows(conn, "select publish_id from public.update_log order by 1")
    assert [r[0] for r in left] == ["pub-1", "pub-4", "pub-5"]
    # A second run finds nothing more
    assert load.prune(seeded, keep_review=1, keep_draft=1, apply=True)["deleted"] == 0


def test_defaults_keep_everything_at_this_size(seeded):
    assert load.prune(seeded, apply=True)["deleted"] == 0
    assert len(_left(seeded)) == 6
