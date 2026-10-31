# Publishing database

The website reads its figures from a Supabase Postgres database (project "Bay Area Methane Watch",
`us-east-1`, Postgres 17 with PostGIS). The database is a publishing store: `mw publish` loads one
snapshot of a run into it, and the website build reads that snapshot and writes static pages. The
browser never talks to the database.

## Layout

- `migrations/` holds numbered SQL files, applied in order. Each file is plain SQL that runs both on
  Supabase and on the PostGIS container used in CI.
  - `0001` PostGIS, the API roles where missing, and a fix the security advisor asked for.
  - `0002` the tables. Every content table carries `publish_id`; a publication is a full snapshot.
  - `0003` row-level security: the publishable key reads public, unrestricted rows only, and writes
    nothing.
  - `0004` read views for the build, all running with the caller's own rights.
  - `0005` indexes.

## Rules

- Nothing is applied to the live project without the owner's OK. Migrations are applied through the
  Supabase connector (which records them in the project's migration table) or, if the Supabase CLI is
  installed, with `supabase db push`.
- After every applied migration, run the Supabase security and performance advisors and fix what they
  report.
- Rows from a source whose terms are not confirmed (Carbon Mapper today) carry `restricted = true`.
  Row-level security hides them from the publishable key, so they cannot reach the public website even
  if a build is misconfigured.
- Simulated runs can never be made public: the database refuses that visibility.
- The secret key and the database password live only in the git-ignored `.env` and in the host's own
  settings. The browser only ever receives the publishable key, and the static build means it rarely
  needs even that.

## Testing

`tests/db/test_migrations.py` applies the migrations to an empty database, loads a few rows, and then
checks as the `anon` role that draft, review and restricted rows are invisible and that writes fail.
The tests run when `TEST_DATABASE_URL` is set; CI provides a `postgis/postgis` service container for
them. Locally they are skipped unless you point that variable at a scratch PostGIS database.
