# PR #57: The same rule for the repair checks and the hold-out check

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/57)

## In one sentence

The before-and-after test of dated checks and the hold-out check now leave out unsearched
instruments, as the main model fit has since PR 55, so none of the three reads Sentinel-2's
unsearched passes as passes that saw nothing.

## Why it was needed

- **PR 55 covered only the main fit.** It made `mw model fit` take an instrument only once a
  plume search has run on its passes. Sentinel-2's own search has not run yet, so its 1,293
  usable passes stay out.
- **Two other steps read the same table of passes:**
  - the test of whether emissions changed after a dated inspection, notice or repair
    (`mw repair run`);
  - the hold-out check, which fits on 80% of the passes and predicts detections in the rest
    (`mw validate holdout`).

  Both still took every instrument. Their next real run would have counted the unsearched
  Sentinel-2 passes as "looked and saw nothing", around each check date and in the held-out
  folds.

## What it adds

- **One selection for all three.** The model fit, the repair checks and the hold-out check now
  go through one shared step. They leave out the same instruments, for the same reason.
- **The same deliberate way back in.** `--include-unsearched sentinel2` works on all three
  commands.
- **The same record.** The repair run's record now lists the instruments it used, what it left
  out and why. The hold-out report says so in plain words and in its run record.
- **An honest label for a real hold-out run.** The website's method-check table labelled every
  hold-out row "Dry run on simulated data", even a run on real passes. A real run's note now
  says it used real detections and names any instrument left out. No real hold-out run has been
  published yet. The table's caption no longer says every row is simulated.

## What we learned

- Nothing new about the data. No repair-check run or hold-out run on real passes was made or
  published here.

## Still to do

- **A record of which passes were searched.** As in PR 55, the rule works per instrument, not
  per pass. A Sentinel-2 search over only some passes would let every pass in.
