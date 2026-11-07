# PR #53: Let the coverage step run when there are no plumes

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/53)

## In one sentence

The step that matches plumes to satellite passes no longer crashes when no plume
source has anything to report.

## Why it was needed

The coverage step lists every pass over each landfill, then marks the passes where a
plume was seen. When the plume folder was empty, or held only empty files, it built a
stand-in table with no rows whose columns had no number or date types. The rates in
that table could not be used in arithmetic, so the step crashed when it took the
logarithm of the error on each rate.

Real updates always include Carbon Mapper plumes, so this never failed on real data.
It did fail on small test projects, and it would have failed on an update in which
every plume source came back empty. That update should be a valid result: every pass
seen, no plume found.

## What it adds

- The stand-in table now takes its column types from the project's plume table rules:
  rates and distances are numbers, times are UTC dates. It also has every column a real
  plume table has. The old one lacked the plume source, which the step that prepares
  the public copy reads, so an empty update would have failed there next.
- A test that runs the coverage step with no plume files, with an empty file, and with
  an empty file that has some columns. In each case all 20 passes come out as passes
  with no plume, and no plume is left unmatched.

## What we learned

Nothing new about the landfills. The fault had been there since the coverage step was
first written; it was found while writing tests for PR 51.

## Still to do

Nothing for this change.
