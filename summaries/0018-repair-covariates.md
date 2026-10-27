# PR #18: Site traits in the repair check

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/18)

## In one sentence

When site traits are switched on, the repair check now uses them too, both for its verdict and for the smallest
drop it could have detected.

## Why it was needed

PR #17 let a few known traits of each landfill, such as whether it is closed and how large it is, inform the
emission estimates. The repair check's own model could already accept them, but the command that runs it over
every documented repair never passed them on. Switching the traits on would have changed the emission estimates
and left the repair verdicts on the old model.

Each verdict also comes with the smallest drop the check could have seen at that site, worked out from simulated
repeats of the same test. If those repeats used a different model from the verdict, the two numbers would not
describe the same test.

## What it adds

- **The same traits in every fit** behind a repair outcome: the verdict, the fit that sets each site's typical
  emissions before the repair, and the simulated repeats behind the smallest detectable drop.
- **The more careful sampler setting** that fits with traits need (ADR 0008).
- **An early stop.** If traits are switched on but the traits table has not been built, the command stops before
  any fitting and says to build the table first.
- **A record of the traits.** The run record lists which traits were used and how they were scaled.
- **No change by default.** With no traits chosen, which is the default, nothing changes.

## What we learned

Nothing new about the data. The simulated repeats needed no change of their own. Each site's typical values
already include the effect of its traits, and a site's traits are the same before and after a repair.

## Still to do

- Build the traits table once the site boundaries exist, then choose which traits to switch on.
- The simulated placebo check for the repair test (Gate 5) still runs without traits. Extend it before relying on
  repair verdicts made with traits.
