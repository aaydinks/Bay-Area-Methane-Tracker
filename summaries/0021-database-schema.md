# PR #21: Publishing database schema and row-level rules

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/21)

## In one sentence

The database the public website will read from now has its tables, its access rules and its
read views, written as migrations that are tested in CI but not yet applied to the live project.

## Why it was needed

The website has to show real figures tied to a named run, keep Carbon Mapper data private until
Carbon Mapper confirms what may be published, and keep anything unfinished or simulated away from
the public. Those rules are easiest to enforce in one place, at the data store, where a mistake
in the website build cannot undo them.

## What it adds

- Sixteen tables in a Supabase Postgres database with PostGIS for outlines and plume points. Each
  published run is a complete snapshot: the sites, every pass and plume, the persistence estimates,
  the dated checks and their before/after results with the evidence, size and colour labels, the
  operator-reported EPA figures, residents nearby, the method checks, and a log of what changed.
- A visibility on every snapshot: draft (nobody sees it), review (the protected review build), or
  public (the website). A simulated run can never be made public; the database refuses it.
- A restricted flag on plumes, passes, estimates and check results from sources whose terms are
  unconfirmed. The website's publishable key can read only public, unrestricted rows and cannot
  write anything. Signed-in users do not exist, so that role gets nothing.
- Read views that hand geometry over as plain longitude, latitude and GeoJSON, count passes per
  site, instrument and month, and give plume days per usable pass so the map is not read as
  emissions. Every view runs with the caller's own rights.
- A CI job that applies the migrations to an empty PostGIS container and checks, as the public
  role, that draft, review and restricted rows are invisible, that aggregates only count visible
  passes, and that writes fail. Twelve tests.
- A fix the Supabase security advisor asked for: a helper function Supabase installs is no longer
  callable through the API.

## What we learned

Supabase grants broad rights to new tables by default, so the migrations take them away
explicitly rather than relying on the defaults, and the same files run unchanged on a plain
PostGIS container. The live Supabase project is on the free plan, which has no database
branches, so a container in CI is the test bed. The free plan also pauses a project after about a
week without queries; the website build will read the database only at publish time, so the site
keeps serving even if that happens.

## Still to do

Apply the migrations to the live project after review and run the Supabase advisors. Then the
publishing command (`mw publish`) that fills these tables from a run, and the website build that
reads them.
