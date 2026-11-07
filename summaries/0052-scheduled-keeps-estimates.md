# PR #52: Keep the latest estimates in scheduled review copies

**Status:** merged 2026-11-06 · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/52)

## In one sentence

The twice-weekly refresh now carries the latest model estimates into every review copy it
makes, instead of publishing a copy with none.

## Why it was needed

The twice-weekly refresh was written before the model had run on real data, so the copies it
built had sites, passes and plumes but no estimates. Reviewers see the newest review copy. Once
the refresh ran, its copy would have pushed aside the one with the first real estimates
(Newby Island and Potrero Hills), and the reviewer site would have shown no estimates at all.

## What it adds

- Each scheduled copy uses the newest model run that was fit to real data, passed its quality
  checks and was made from code with no unsaved changes. Simulated runs and runs that failed
  their checks are never used.
- If no such run exists, the copy is still built, and the run's record says why it has no
  estimates.
- The refresh never reruns the model itself. New estimates still come only from a deliberate
  fit.

## What we learned

The first scheduled run (Nov 6, 2026) showed the gap: it was started before this fix.

## Still to do

Between fits, a copy's passes and plumes are newer than its estimates. The site should show the
date of the data behind the estimates, separately from the copy's own "data through" date.
