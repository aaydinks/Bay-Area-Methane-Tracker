# 0021: What the public site may show, two fits side by side, and old copies

- **Status:** accepted
- **Date:** 2026-11-19

## Context

The site went public on 2026-11-08 with the five pilot sites. 0018 adds several dozen more sites
in two regions. The owner decided that North Valley results go to the locked review copy first and
become public only after a review window with operators and their air districts.

Three things stand in the way:

- **A publication is promoted as a whole.** Its visibility is draft, review or public. There is no
  way to make five sites public and hold the rest back.
- **The public build reads some tables directly.** The display-only views of 0017 cover plumes,
  passes, estimates and check results. Sites, neighbours, operator reports, population, site
  features, the update log and run records are read straight through row-level security. Every
  plume in the box is published, including those that belong to no site.
- **A publication carries one fit, and a fit pools every site in the registry.** Once the registry
  grows, the next routine refit would include the new sites and move the pilots' public figures.
  The scheduled run would also read the new sites as unexpected change and stop making review
  copies.

Separately, every push stores a full copy and nothing removes old ones. The scheduled run pushes
twice a week, and the free database plan has a size limit.

## Options considered

1. **A second database for review.** Clean separation, but two schemas to keep in step and a second
   free project that pauses when idle.
2. **Hold new sites out of the registry until they may be public.** No gate needed, but then nothing
   can be reviewed.
3. **A scope on every row, enforced in the database and in the build** (chosen).

## Decision

**Public scope**

- An allowlist of regions and tiers in `config/public_scope.json`. JSON, because the database tests
  and the web build read it and neither reads YAML. It starts as exactly what is public today: the
  Bay Area pilot tier.
- `mw publish build` stamps each row as in scope or not. A plume with no site is in scope only if it
  lies inside an in-scope region.
- It is enforced three times:
  - in the database, on every public policy and on the five display-only functions, including the
    tables the public build reads directly;
  - in the web build's data fetch;
  - in the public-output check, which reads the committed allowlist itself and fails the build if a
    site or plume outside it appears.
- New columns default to "in scope", so applying the migration cannot blank the live site.
- Only the owner widens the scope.

**Two fits**

- `official_model_run` stays the source of every figure for the sites it covers.
- A new, optional `screening_model_run` supplies estimates only for sites the official fit does not
  cover. Those rows are marked provisional.
- A fit names the sites it includes and records them. The scheduled run's change check looks only at
  the official fit's sites. Repair-test controls come from the fit being tested.
- The owner decides when a pooled fit becomes the official one. Before that it must pass the
  synthetic coverage test at the real site count, with a region term and each region's own pass
  rates. Trial reports are written outside `reports/validation/`, because everything in that folder
  is published.

**Old copies**

- A prune command removes old draft and review publications. It is a dry run unless told otherwise,
  it never removes a public publication, and it always keeps the newest review copy.

## Consequences

- The pilots' public figures cannot change by accident: not through a larger registry, a routine
  refit, or a publication that also holds new sites.
- Review and public are still one database and one publication; the scope decides what each build
  may read. A mistake in the scope migration could hide or expose rows, so it ships with a fixture
  that has an out-of-scope site and an out-of-scope plume, tested as the anonymous database role.
- Figures for screening sites and for pilots may come from different fits for a while. Each row says
  which fit it came from, and the methods page must say so too.
- Pruning deletes data from the live database, so each run needs the owner's go-ahead.
