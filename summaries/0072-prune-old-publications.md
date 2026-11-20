# PR #72: A command that removes old review copies from the database

**Status:** merged 2026-11-19 · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/72)

## In one sentence

The project can now list the old draft and review copies held in its publishing database and, when
told to, remove them, without ever touching a public copy.

## Why it was needed

Each refresh stores a complete copy of every table, twice a week, and nothing ever removed an old
one. The database is on a free plan with a size limit. With five landfills that was no concern.
The plan now adds several dozen sites, so each copy grows by about ten times and the limit would
be reached within months.

## What it adds

- **`mw publish prune`.** By default it only lists what could go: review copies older than the
  newest eight, and drafts older than the newest two.
- **`--apply` removes them**, after asking for confirmation. Everything that belongs to a removed
  copy goes with it.
- **Two things always stay:** every public copy, and the newest review copy (the next refresh
  compares itself with it to say what changed).
- **It never runs by itself.** It is not part of the scheduled refresh. Removing data from the
  live database needs the project owner's go-ahead each time.
- **A removed copy can be restored.** The files it was loaded from stay on disk and can be loaded
  again.

## What we learned

Listing only, against the live database on Nov 19, 2026: it holds 2 public copies and 6 review
copies, so with the default limits nothing would be removed yet. The four oldest review copies
together hold about 11,500 rows.

## Still to do

- Decide how many review copies to keep once the site list has grown. A removed review copy also
  disappears from the review site's list of past updates.
- Run records are small and are not removed. Revisit if they grow.
