"""The public scope in the database (ADR 0021, migration 0008): what the publishable key reads
when a public publication also holds a site that is still under review."""

from __future__ import annotations

import pytest

from methanewatch.config import PublicScope, load_data_terms, load_impact
from methanewatch.publish import load
from methanewatch.publish import snapshot as snap
from tests.db.conftest import as_role, rows, run_script
from tests.test_public_scope import _sonoma_under_review
from tests.test_publish_snapshot import _project, _write_inputs

psycopg = pytest.importorskip("psycopg")

SQUARE = (
    "MULTIPOLYGON(((-121.95 37.45, -121.93 37.45, -121.93 37.47, -121.95 37.47, -121.95 37.45)))"
)
CLEAR = "delete from public.publications; delete from public.runs; delete from public.data_terms;"

# One public publication with a pilot ("open-site") and a screening site ("held-site").
FIXTURE_SQL = f"""
insert into public.publications (publish_id, created_at, visibility) values
  ('pub-scope', '2026-11-19T00:00:00Z', 'public');

insert into public.sites
  (publish_id, site_id, name, tier, county, region, outline, provisional, public_scope) values
  ('pub-scope', 'open-site', 'Open Landfill', 'pilot', 'Santa Clara', 'bay-area',
   extensions.st_geomfromtext('{SQUARE}', 4326), true, true),
  ('pub-scope', 'held-site', 'Held Landfill', 'screen', 'Santa Clara', 'bay-area',
   extensions.st_geomfromtext('{SQUARE}', 4326), true, false);

insert into public.neighbours (publish_id, neighbour_id, name, kind, geom, nearest_site_id,
  public_scope) values
  ('pub-scope', 'n-open', 'Compost yard', 'compost',
   extensions.st_geomfromtext('POINT(-121.94 37.46)', 4326), 'open-site', true),
  ('pub-scope', 'n-held', 'Dairy', 'other',
   extensions.st_geomfromtext('POINT(-121.94 37.46)', 4326), 'held-site', false);

insert into public.plumes
  (publish_id, plume_id, source, instrument, acquired_utc, lon, lat, q_kg_hr, site_id,
   attribution, distance_m, overpass_id, restricted, display_only, region, public_scope,
   site_public) values
  ('pub-scope', 'open-1', 'emit-v2', 'emit', '2025-06-01T18:00:00Z', -121.94, 37.46, 700,
   'open-site', 'inside', 0, 'open-site:emit:2025-06-01', false, false, 'bay-area', true, true),
  ('pub-scope', 'held-1', 'emit-v2', 'emit', '2025-06-02T18:00:00Z', -121.94, 37.46, 800,
   'held-site', 'buffer', 120, 'held-site:emit:2025-06-02', false, false, 'bay-area', true, false),
  ('pub-scope', 'held-cm', 'carbonmapper', 'tanager1', '2025-06-03T18:00:00Z', -121.94, 37.46,
   1500, 'held-site', 'inside', 0, 'held-site:tanager1:2025-06-03', true, true, 'bay-area',
   true, false),
  ('pub-scope', 'east-1', 'emit-v2', 'emit', '2025-06-04T18:00:00Z', -121.196, 37.872, 900,
   null, 'none', null, null, false, false, null, false, true);

insert into public.passes
  (publish_id, overpass_id, site_id, instrument, acquired_utc, usable, detected, n_plumes,
   restricted, public_scope) values
  ('pub-scope', 'open-site:emit:2025-06-01', 'open-site', 'emit', '2025-06-01T18:00:00Z',
   true, true, 1, false, true),
  ('pub-scope', 'held-site:emit:2025-06-02', 'held-site', 'emit', '2025-06-02T18:00:00Z',
   true, true, 1, false, false);

insert into public.site_estimates
  (publish_id, model_run_id, site_id, n_usable_overpasses, n_detections, status, restricted,
   public_scope) values
  ('pub-scope', 'model-1', 'open-site', 3, 2, 'estimate', false, true),
  ('pub-scope', 'model-1', 'held-site', 3, 2, 'estimate', false, false);

insert into public.checks
  (publish_id, check_id, site_id, check_type, date_start, date_confidence, description,
   source_doc, public_scope) values
  ('pub-scope', 'chk-open', 'open-site', 'operator-repair', '2025-03-01', 'month',
   'A well was repaired.', 'log.pdf', true),
  ('pub-scope', 'chk-held', 'held-site', 'operator-repair', '2025-03-01', 'month',
   'A well was repaired.', 'log.pdf', false);

insert into public.check_results
  (publish_id, check_run_id, check_id, site_id, call, n_before, n_after, evidence, colour,
   plain_reading, restricted, public_scope) values
  ('pub-scope', 'repairs-1', 'chk-open', 'open-site', 'insufficient_data', 0, 0, 'none', 'grey',
   'Not enough passes to test for a change.', false, true),
  ('pub-scope', 'repairs-1', 'chk-held', 'held-site', 'insufficient_data', 0, 0, 'none', 'grey',
   'Not enough passes to test for a change.', false, false);

insert into public.operator_reports
  (publish_id, site_id, year, source, reported_ch4_t, facility_id, url, public_scope) values
  ('pub-scope', 'open-site', 2023, 'GHGRP', 100, '1', 'https://example.org/1', true),
  ('pub-scope', 'held-site', 2023, 'GHGRP', 200, '2', 'https://example.org/2', false);

insert into public.population_context
  (publish_id, site_id, radius_km, residents, label, public_scope) values
  ('pub-scope', 'open-site', 1, 10, 'residents nearby (context, not a health effect)', true),
  ('pub-scope', 'held-site', 1, 20, 'residents nearby (context, not a health effect)', false);

insert into public.site_features
  (publish_id, site_id, closed, ghgrp_reporter, public_scope) values
  ('pub-scope', 'open-site', false, true, true),
  ('pub-scope', 'held-site', false, true, false);

insert into public.update_log (publish_id, item_order, kind, site_id, text, public_scope) values
  ('pub-scope', 0, 'new-plumes', 'open-site', '1 new plume near Open Landfill.', true),
  ('pub-scope', 1, 'new-plumes', 'held-site', '1 new plume near Held Landfill.', false),
  ('pub-scope', 2, 'new-model-run', null, 'A new model run.', true);
"""

# What the public build reads, and the column that names the site in each
SITE_READS = {
    "v_sites": "site_id",
    "sites": "site_id",
    "v_neighbours": "nearest_site_id",
    "passes": "site_id",
    "v_pass_months": "site_id",
    "v_plume_days": "site_id",
    "v_public_pass_months": "site_id",
    "v_public_plume_days": "site_id",
    "site_estimates": "site_id",
    "v_public_site_estimates": "site_id",
    "checks": "site_id",
    "check_results": "site_id",
    "v_checks_with_results": "site_id",
    "v_public_checks_with_results": "site_id",
    "operator_reports": "site_id",
    "population_context": "site_id",
    "site_features": "site_id",
}


@pytest.fixture(scope="module")
def db(test_dsn):
    with psycopg.connect(test_dsn, autocommit=True) as conn:
        run_script(conn, CLEAR)
        run_script(conn, FIXTURE_SQL)
        yield conn
        run_script(conn, CLEAR)


@pytest.mark.parametrize(("relation", "column"), sorted(SITE_READS.items()))
def test_anon_reads_nothing_about_the_site_under_review(db, relation, column):
    with as_role(db, "anon"):
        seen = {r[0] for r in rows(db, f"select {column} from public.{relation}")}
    assert seen == {"open-site"}, relation


def test_the_owner_still_reads_both_sites(db):
    for relation, column in SITE_READS.items():
        if relation.startswith("v_public_"):
            continue  # these serve the public build only
        seen = {r[0] for r in rows(db, f"select {column} from public.{relation}")}
        assert seen == {"open-site", "held-site"}, relation


def test_anon_reads_the_region_of_a_site(db):
    with as_role(db, "anon"):
        assert rows(db, "select site_id, region, public_scope from public.v_sites") == [
            ("open-site", "bay-area", True)
        ]


def test_base_plume_rows_tied_to_the_site_under_review_are_hidden_from_anon(db):
    with as_role(db, "anon"):
        for relation in ("plumes", "v_plumes"):
            assert rows(db, f"select plume_id from public.{relation}") == [("open-1",)], relation


def test_public_plumes_keep_the_dot_and_drop_the_tie_to_a_site_under_review(db):
    with as_role(db, "anon"):
        got = rows(
            db,
            "select plume_id, site_id, attribution, distance_m, overpass_id, q_kg_hr, region "
            "from public.v_public_plumes order by acquired_utc",
        )
    assert got == [
        ("open-1", "open-site", "inside", 0.0, "open-site:emit:2025-06-01", 700.0, "bay-area"),
        # An open plume near the held site: its own id and rate stay, the tie is blanked
        ("held-1", None, "none", None, None, 800.0, "bay-area"),
        # A display-only plume near the held site: a dot with nothing else
        ("point-00001", None, "none", None, None, None, "bay-area"),
    ]  # east-1 lies in no region and is not returned


def test_update_feed_leaves_out_the_item_about_the_site_under_review(db):
    with as_role(db, "anon"):
        got = rows(db, "select item_order, site_id from public.update_log order by item_order")
    assert got == [(0, "open-site"), (2, None)]


def test_scope_columns_default_to_in_scope(db):
    got = rows(
        db,
        "select table_name, column_name, column_default, is_nullable "
        "from information_schema.columns where table_schema = 'public' "
        "and column_name in ('public_scope', 'site_public') and table_name not like 'v\\_%'",
    )
    assert len(got) == 12  # eleven tables carry public_scope; plumes also carries site_public
    assert all(default == "true" and nullable == "NO" for _, _, default, nullable in got)


def test_remade_plume_function_runs_as_owner_with_a_fixed_search_path(db):
    got = rows(
        db,
        "select prosecdef, proconfig from pg_proc "
        "where pronamespace = 'public'::regnamespace and proname = 'public_plumes'",
    )
    assert got == [(True, ['search_path=""'])]
    with as_role(db, "anon"):
        assert rows(db, "select count(*) from public.public_plumes()") == [(3,)]
    with as_role(db, "authenticated"), pytest.raises(psycopg.errors.InsufficientPrivilege):
        rows(db, "select count(*) from public.public_plumes()")


def test_push_carries_the_stamp_into_the_database(test_dsn, tmp_path):
    _write_inputs(tmp_path)
    _sonoma_under_review(tmp_path)
    snapshot = snap.build(
        _project(tmp_path),
        load_data_terms(),
        load_impact(),
        model_run_id="model-1",
        check_run_id="repairs-1",
        publish_id="pub-pushed",
        scope=PublicScope(regions=("bay-area",), tiers=("pilot",)),
    )
    with psycopg.connect(test_dsn, autocommit=True) as conn:
        run_script(conn, CLEAR)
    try:
        load.push(snapshot, test_dsn)
        with psycopg.connect(test_dsn) as conn:
            assert rows(
                conn, "select site_id, region, public_scope from public.sites order by site_id"
            ) == [("newby-island", "bay-area", True), ("sonoma-central", "bay-area", False)]
            plumes = rows(
                conn,
                "select plume_id, region, public_scope, site_public from public.plumes "
                "where plume_id in ('e1', 'e-sonoma', 'e-valley', 'e-east')",
            )
            assert {p[0]: p[1:] for p in plumes} == {
                "e-east": (None, False, True),
                "e-valley": ("north-valley", False, True),
                "e-sonoma": ("bay-area", True, False),
                "e1": ("bay-area", True, True),
            }
            assert rows(
                conn,
                "select distinct site_id, public_scope from public.passes order by site_id",
            ) == [("newby-island", True), ("sonoma-central", False)]
            feed = rows(conn, "select site_id, public_scope from public.update_log")
            assert feed and all(scope == (site != "sonoma-central") for site, scope in feed)
    finally:
        with psycopg.connect(test_dsn, autocommit=True) as conn:
            run_script(conn, CLEAR)
