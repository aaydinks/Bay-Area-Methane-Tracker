# PR #64: Keep the database awake when a scheduled run stops early

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/64)

## In one sentence

The twice-weekly scheduled run now checks in with the database even when it stops partway, so a
problem with a satellite source no longer lets the free database plan pause.

## Why it was needed

The website's database is on a free plan that pauses after about seven days without activity. Until
now, the only thing that kept it active was the scheduled run loading a new copy of the data. On
Nov 12, 2026 the run stopped early because ten Sentinel-2 passes could not be read, so it never
reached the database. Nothing touched the database from Nov 9 to Nov 16, the plan paused it, and
the Nov 16 run failed with a hard-to-read connection error.

## What it adds

- Whenever a run stops before it loads its copy, or the load fails, it finishes with a single
  read-only query (`select 1`). The query reads nothing and changes nothing. It never loads data and
  never changes what the review or public sites show.
- The result goes into the run's record and the job's log as a line starting `database:`.
- When the database cannot be reached, the log says "database paused or unreachable" and how to
  resume it, instead of the raw error, which named the server address and the project.
- A wrong password is reported separately, so it is not mistaken for a pause.
- When there is a database problem, the notification on the owner's Mac now starts with it.

## What we learned

A run can stop at several points before loading anything: the wrong branch, another run still
going, or a source outage. Any of them, twice in a row, was enough to let the database pause. The
plan's own decision record (ADR 0009) already named a regular read as the way to prevent this. We
have not yet confirmed that a `select 1` alone resets the free plan's seven-day timer.

## Still to do

- The owner restores the paused project from the Supabase dashboard. This change does not do that.
- After the next run that stops early, check the log line and that the project stayed active.
