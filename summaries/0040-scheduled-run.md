# PR #40: One command from fresh data to the review website

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/40)

## In one sentence

A single command now pulls the satellite data again, rebuilds the tables, packages a snapshot and
loads it into the website's database for the private review build, so a schedule can run it.

## Why it was needed

The website's database was empty: every step from the satellite data to the dashboard existed, but
each had to be run by hand, in order, and nothing ran on a schedule. The sources publish late (Carbon
Mapper plumes appear about a month after a flight), so the data needs refreshing regularly.

## What it adds

- `mw scheduled-run` does six steps in order: refresh EMIT, Sentinel-2 and Carbon Mapper; update the
  copies of those three sources in the repository; build a snapshot of that refresh; load it into the
  database; make it visible to the private review build; and, if one is set up, ask the host to
  rebuild the review site.
- It never makes anything public. Making a snapshot public stays a separate, confirmed step.
- If a source fails during the refresh, nothing is published, so old data is never labelled as new.
- Every run leaves a record of each step, how long it took, and why it stopped if it did. Passwords
  and private links are blanked out of that record.
- Model estimates and repair checks stay empty until the detection curves are sourced; the review
  site shows passes, plumes and method checks, with empty states for the rest.

## What we learned

On the real data the whole run takes about 19 seconds and half a gigabyte of memory before the
database step. Without the database connection string it stops at the load step and says so. Carbon
Mapper's plumes go into the snapshot marked restricted, as the data terms require; a test against a
throwaway copy of the database checks that the public key cannot see them.

## Still to do

- The owner adds the database connection string to `.env`, then the first real review snapshot is
  loaded.
- The schedule itself (on the owner's Mac or on GitHub), in its own pull request.
