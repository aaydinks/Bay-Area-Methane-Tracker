"""Apply the migrations to an empty PostGIS database and check what the publishable key sees.

The database comes from ``conftest.py``; a few rows are loaded here and read back as ``anon``.
"""

from __future__ import annotations

import pytest

from tests.db.conftest import MIGRATIONS, as_role, rows, run_script

psycopg = pytest.importorskip("psycopg")
from psycopg import errors  # noqa: E402

SQUARE = (
    "MULTIPOLYGON(((-121.95 37.45, -121.93 37.45, -121.93 37.47, -121.95 37.47, -121.95 37.45)))"
)

FIXTURE_SQL = f"""
insert into public.runs (run_id, kind, created_at) values
  ('model-public', 'model', '2026-09-30T00:00:00Z'),
  ('model-draft', 'model', '2026-10-19T00:00:00Z');

insert into public.publications
  (publish_id, created_at, visibility, simulated, model_run_id, data_through) values
  ('pub-public', '2026-10-01T00:00:00Z', 'public', false, 'model-public', '2026-09-01'),
  ('pub-review', '2026-10-15T00:00:00Z', 'review', false, null, '2026-09-15'),
  ('pub-draft',  '2026-10-20T00:00:00Z', 'draft',  false, 'model-draft', '2026-09-20');

insert into public.data_terms (source, display_name, confirmed) values
  ('carbonmapper', 'Carbon Mapper', false);

insert into public.sites (publish_id, site_id, name, tier, outline, polygon_source, provisional)
values
  ('pub-public', 'newby-island', 'Newby Island Landfill', 'pilot',
   extensions.st_geomfromtext('{SQUARE}', 4326), 'provisional 500 m buffer', true),
  ('pub-draft', 'newby-island', 'Newby Island Landfill', 'pilot',
   extensions.st_geomfromtext('{SQUARE}', 4326), 'traced', false);

insert into public.plumes
  (publish_id, plume_id, source, instrument, acquired_utc, lon, lat, q_kg_hr, site_id,
   attribution, restricted) values
  ('pub-public', 'cm-1', 'carbonmapper', 'tanager1', '2025-06-01T18:00:00Z', -121.94, 37.46,
   1500, 'newby-island', 'inside', true),
  ('pub-public', 'emit-1', 'emit-v2', 'emit', '2024-08-07T18:00:00Z', -121.94, 37.46,
   null, 'newby-island', 'buffer', false),
  ('pub-draft', 'emit-2', 'emit-v2', 'emit', '2025-01-01T18:00:00Z', -121.94, 37.46,
   null, 'newby-island', 'inside', false);

insert into public.passes
  (publish_id, overpass_id, site_id, instrument, acquired_utc, usable, detected, n_plumes,
   restricted) values
  ('pub-public', 'newby-island:emit:2024-08-07', 'newby-island', 'emit',
   '2024-08-07T18:00:00Z', true, true, 1, false),
  ('pub-public', 'newby-island:emit:2024-09-01', 'newby-island', 'emit',
   '2024-09-01T18:00:00Z', true, false, 0, false),
  ('pub-public', 'newby-island:tanager1:2025-06-01', 'newby-island', 'tanager1',
   '2025-06-01T18:00:00Z', true, true, 1, true);

insert into public.site_estimates
  (publish_id, model_run_id, site_id, n_usable_overpasses, n_detections, status, restricted)
values
  ('pub-public', 'model-public', 'newby-island', 3, 2, 'estimate', true),
  ('pub-public', 'model-public', 'shoreline', 2, 0, 'insufficient_data', false);

insert into public.checks
  (publish_id, check_id, site_id, check_type, date_start, date_confidence, description,
   source_doc, source_doc_title) values
  ('pub-public', 'chk-1', 'newby-island', 'air-district-notice', '2025-03-01', 'month',
   'Notice issued after surface monitoring.', 'baaqmd-2025-03.pdf', 'Notice of Violation A12345');

insert into public.check_results
  (publish_id, check_run_id, check_id, site_id, call, effect_med, effect_lo, effect_hi,
   change_pct_med, p_decrease, n_before, n_after, evidence, size, colour, plain_reading,
   restricted) values
  ('pub-public', 'repairs-1', 'chk-1', 'newby-island', 'inconclusive', 0.1, -0.4, 0.6,
   10.5, 0.4, 6, 7, 'weak', 'slight', 'yellow',
   'Methane rose about 11% (90% range -33% to 82%) after this check; weak evidence.', false);

insert into public.boundaries (boundary_id, kind, name, geom) values
  ('county-santa-clara', 'county', 'Santa Clara', extensions.st_geomfromtext('{SQUARE}', 4326));
"""


@pytest.fixture(scope="module")
def db(test_dsn):
    """The migrated database with this module's sample rows loaded."""
    with psycopg.connect(test_dsn, autocommit=True) as conn:
        run_script(conn, FIXTURE_SQL)
        yield conn
        run_script(
            conn,
            "delete from public.publications; delete from public.runs; "
            "delete from public.data_terms; delete from public.boundaries;",
        )


def test_migrations_apply_in_order():
    names = [p.name for p in sorted(MIGRATIONS.glob("*.sql"))]
    assert names[0].startswith("0001_")
    assert [n[:4] for n in names] == sorted(n[:4] for n in names)


def test_every_table_has_row_level_security(db):
    missing = rows(
        db,
        """
        select c.relname from pg_class c
        join pg_namespace n on n.oid = c.relnamespace
        where n.nspname = 'public' and c.relkind in ('r', 'p') and not c.relrowsecurity
        """,
    )
    assert missing == []


def test_every_view_runs_as_the_caller(db):
    bad = rows(
        db,
        """
        select c.relname from pg_class c
        join pg_namespace n on n.oid = c.relnamespace
        where n.nspname = 'public' and c.relkind = 'v'
          and coalesce(array_to_string(c.reloptions, ','), '') not ilike '%security_invoker=true%'
          and coalesce(array_to_string(c.reloptions, ','), '') not ilike '%security_invoker=on%'
        """,
    )
    assert bad == []


def test_anon_sees_only_public_publications(db):
    with as_role(db, "anon"):
        assert rows(db, "select publish_id from public.publications") == [("pub-public",)]
        assert rows(db, "select publish_id from public.v_current_publication") == [("pub-public",)]
        assert rows(db, "select publish_id from public.v_current_review_publication") == [
            ("pub-public",)
        ]
    assert rows(db, "select publish_id from public.v_current_review_publication") == [
        ("pub-review",)
    ]


def test_anon_never_sees_restricted_or_unpublished_rows(db):
    with as_role(db, "anon"):
        assert rows(db, "select plume_id from public.plumes order by 1") == [("emit-1",)]
        assert rows(db, "select plume_id from public.v_plumes order by 1") == [("emit-1",)]
        assert rows(db, "select instrument from public.passes order by 1") == [
            ("emit",),
            ("emit",),
        ]
        assert rows(db, "select site_id, status from public.site_estimates") == [
            ("shoreline", "insufficient_data")
        ]
        assert rows(db, "select site_id from public.sites") == [("newby-island",)]
        assert rows(db, "select polygon_source from public.sites") == [
            ("provisional 500 m buffer",)
        ]


def test_anon_aggregates_use_unrestricted_passes_only(db):
    with as_role(db, "anon"):
        (usable, plume_days, includes_restricted) = rows(
            db,
            "select usable_passes, plume_days, includes_restricted from public.v_plume_days",
        )[0]
    assert (usable, plume_days, includes_restricted) == (2, 1, False)
    (usable_all, plume_days_all, includes_all) = rows(
        db, "select usable_passes, plume_days, includes_restricted from public.v_plume_days"
    )[0]
    assert (usable_all, plume_days_all, includes_all) == (3, 2, True)


def test_anon_sees_runs_of_public_publications_only(db):
    with as_role(db, "anon"):
        assert rows(db, "select run_id from public.runs") == [("model-public",)]


def test_anon_reads_checks_with_results_and_geometry_as_geojson(db):
    with as_role(db, "anon"):
        (check_type, colour, title) = rows(
            db, "select check_type, colour, source_doc_title from public.v_checks_with_results"
        )[0]
        (lon, lat, geojson) = rows(db, "select lon, lat, outline_geojson from public.v_sites")[0]
        (kind, bgeo) = rows(db, "select kind, geojson from public.v_boundaries")[0]
    assert (check_type, colour) == ("air-district-notice", "yellow")
    assert title.startswith("Notice of")
    assert round(lon, 2) == -121.94 and round(lat, 2) == 37.46
    assert geojson["type"] == "MultiPolygon"
    assert (kind, bgeo["type"]) == ("county", "MultiPolygon")


def test_anon_cannot_write(db):
    with as_role(db, "anon"), pytest.raises(errors.InsufficientPrivilege):
        db.execute(
            "insert into public.update_log (publish_id, item_order, kind, text) "
            "values ('pub-public', 1, 'note', 'x')"
        )


def test_authenticated_has_no_access(db):
    with as_role(db, "authenticated"), pytest.raises(errors.InsufficientPrivilege):
        db.execute("select count(*) from public.sites")


def test_simulated_runs_cannot_be_public(db):
    with pytest.raises(errors.CheckViolation):
        db.execute(
            "insert into public.publications (publish_id, visibility, simulated) "
            "values ('pub-sim', 'public', true)"
        )


def test_restricted_defaults_to_true_on_source_tables(db):
    defaults = rows(
        db,
        """
        select c.table_name, c.column_default
        from information_schema.columns c
        join information_schema.tables t
          on t.table_schema = c.table_schema and t.table_name = c.table_name
        where c.table_schema = 'public' and c.column_name = 'restricted'
          and t.table_type = 'BASE TABLE'
        order by 1
        """,
    )
    assert [t for t, _ in defaults] == ["check_results", "passes", "plumes", "site_estimates"]
    assert all(d == "true" for _, d in defaults)
