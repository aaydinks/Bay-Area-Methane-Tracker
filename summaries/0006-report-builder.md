# PR #6: Running the model and building the dashboard

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/6)

## In one sentence

Connected the model to real inputs and built the small public dashboard the
plan promises, previewed with clearly labelled simulated landfills.

## Why it was needed

The plan's public outputs include a dashboard of per-site results. Building
it early shows how results will be presented, so the wording and caveats
are settled before any real numbers exist. It also needed a safe way to run
the model on real data: one that refuses to run while key inputs are still
unconfirmed.

## What it adds

- **A real-data run.** It saves every result with a record of the code and
  settings used. It stops with a clear message if the detection floor or
  any satellite's detection limit hasn't been set, and labels results
  "provisional" while those values are unconfirmed.
- **A demo run on invented landfills,** banner-labelled "synthetic demo" on
  every page, so the dashboard can be reviewed now.
- **The dashboard:**
  - **Main page:** landfills ranked by estimated annual methane, each with
    its 90% range, and the operator-reported figure alongside. Sites with too
    little data are listed separately rather than ranked.
  - **One page per landfill:** every satellite pass on a timeline, plumes
    with their rates and the quiet passes, plus how the site compares with
    EPA reports.
  - **Methods page:** how it works, and the result of every validation test.
- **The plan's wording rules, enforced.** Every page states it is a
  retrospective tracker giving screening indications. A page using words like
  "violation", "saved" or "real-time" stops the build entirely.

## What we learned

The dashboard reads well on a laptop and on a phone. On the demo, the true
emissions of 8 of the 10 simulated landfills fell inside their 90% ranges.
The two misses were just outside, about what a 90% range should produce. Earlier
validation runs that used an outdated rule are labelled "superseded" on the
methods page, so they can't be mistaken for current results.

## Still to do

The real dashboard needs a real model run. It goes public only after
operators and the Air District have had their two-week review window.
