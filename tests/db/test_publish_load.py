"""Push a built snapshot into the migrated database and check visibility and the feed."""

from __future__ import annotations

import pytest

from methanewatch.config import load_data_terms, load_impact
from methanewatch.publish import load
from methanewatch.publish import snapshot as snap
from tests.db.conftest import as_role, rows, run_script
from tests.test_publish_snapshot import _project, _write_inputs

psycopg = pytest.importorskip("psycopg")


@pytest.fixture
def clean(test_dsn):
    with psycopg.connect(test_dsn, autocommit=True) as conn:
        run_script(
            conn,
            "delete from public.publications; delete from public.runs; "
            "delete from public.data_terms;",
        )
    yield test_dsn
    with psycopg.connect(test_dsn, autocommit=True) as conn:
        run_script(
            conn,
            "delete from public.publications; delete from public.runs; "
            "delete from public.data_terms;",
        )


def _snapshot(tmp_path, publish_id, **kw):
    _write_inputs(tmp_path, **kw)
    return snap.build(
        _project(tmp_path),
        load_data_terms(),
        load_impact(),
        model_run_id="model-1",
        check_run_id="repairs-1",
        publish_id=publish_id,
        **({"allow_simulated": True} if kw.get("demo") else {}),
    )


def test_push_loads_every_table_as_a_draft_and_the_feed(clean, tmp_path):
    first = _snapshot(tmp_path / "a", "pub-a")
    counts = load.push(first, clean)
    assert counts["sites"] == 2 and counts["passes"] == 3 and counts["plumes"] == 2
    assert counts["check_results"] == 1 and counts["validation_results"] == 1
    with psycopg.connect(clean) as conn:
        assert rows(conn, "select visibility from public.publications") == [("draft",)]
        kinds = [k for (k,) in rows(conn, "select kind from public.update_log order by item_order")]
        assert kinds == [
            "new-plumes",
            "new-record",
            "new-model-run",
            "new-check-run",
            "gate-result",
        ]
        assert rows(conn, "select count(*) from public.plumes where new_in_update") == [(2,)]
        (lon, lat) = rows(
            conn,
            "select round(extensions.st_x(centroid)::numeric, 2), "
            "round(extensions.st_y(centroid)::numeric, 2) "
            "from public.sites where site_id = 'newby-island'",
        )[0]
        assert (float(lon), float(lat)) == (-121.94, 37.46)
        with as_role(conn, "anon"):
            assert rows(conn, "select count(*) from public.publications") == [(0,)]

    load.set_visibility(clean, "pub-a", "review")
    second = _snapshot(tmp_path / "b", "pub-b")
    load.push(second, clean)
    with psycopg.connect(clean) as conn:
        # Same plumes and records as the review publication: nothing new to report
        assert rows(conn, "select count(*) from public.update_log where publish_id = 'pub-b'") == [
            (0,)
        ]
        assert rows(
            conn, "select count(*) from public.plumes where publish_id = 'pub-b' and new_in_update"
        ) == [(0,)]


def test_public_visibility_hides_restricted_rows_from_anon(clean, tmp_path):
    load.push(_snapshot(tmp_path, "pub-c"), clean)
    load.set_visibility(clean, "pub-c", "public")
    with psycopg.connect(clean) as conn:
        assert rows(conn, "select published_at is not null from public.publications") == [(True,)]
        with as_role(conn, "anon"):
            assert rows(conn, "select source from public.v_plumes order by 1") == [("emit-v2",)]
            assert rows(conn, "select instrument from public.v_pass_months order by 1") == [
                ("emit",),
                ("sentinel2",),
            ]
            assert rows(conn, "select count(*) from public.site_estimates") == [
                (0,)
            ]  # all restricted
            assert rows(conn, "select check_id, colour from public.v_checks_with_results") == [
                ("c1", None)
            ]
            assert rows(conn, "select credit_line from public.data_terms where source = 'ghgrp'")[
                0
            ][0].startswith("US EPA")


def test_simulated_runs_can_never_be_public(clean, tmp_path):
    load.push(_snapshot(tmp_path, "pub-sim", demo=True), clean)
    load.set_visibility(clean, "pub-sim", "review")
    with pytest.raises(ValueError, match="simulated"):
        load.set_visibility(clean, "pub-sim", "public")
    with pytest.raises(LookupError):
        load.set_visibility(clean, "pub-missing", "review")
