# PR #71: Keep fits and scheduled runs to the sites a fit covers

**Status:** merged 2026-11-19 · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/71)

## In one sentence

Adding landfills to the site list no longer changes the five pilot sites' figures, stops the
twice-weekly review copy, or adds Sentinel-2 work, unless someone chooses that on purpose.

## Why it was needed

The site list is about to grow from 5 landfills to about 60, in two regions (PR #68). Before this
change, three things would have happened the moment the new rows were added:

- The scheduled run checks that the official model fit still matches the latest satellite passes.
  It would have read every pass over a new site as an unexpected change and stopped making review
  copies.
- The model estimates all sites together, so each site's figure leans a little on the others. The
  next routine refit would have included the new sites and moved the pilots' public figures.
- Sentinel-2 passes, and a satellite cloud window for each one, would have been built for every
  site, although Sentinel-2 only sees very large plumes and is used for the pilots.

## What it adds

- **The scheduled run** compares the official fit only with passes over the sites that fit covers.
  Passes over other sites are counted in the run's record. A change at a covered site still holds
  the copy back from review, as before.
- **A fit says which sites it takes.** The fit command and the repair-check command accept a tier
  (`--tier pilot`) or named sites (`--site`). While every site is of one tier, as today, nothing
  needs to be said. Once the list holds two tiers, they stop and ask, and each run's record names
  the choice.
- **Repair checks** draw their comparison sites from the chosen sites, or from the sites of a named
  fit (`--fit`), not from every site on the list.
- **Sentinel-2 passes** are built only for the tiers named in the project settings: the pilot
  tier.
- **Two fits side by side.** The settings can name a second, "screening" fit. A site's estimate
  comes from the official fit when that fit has the site, otherwise from the screening fit, always
  marked provisional, and otherwise the site has no estimate. A screening fit that is out of date
  is left out with the reason and never holds back the official one. No screening fit is named yet.

## What we learned

With today's five pilot sites nothing changes. Rebuilt from the Nov 19, 2026 data and the official
fit, all twelve published tables are identical to the copy made that day (5 estimates, 2,200
passes, 623 plumes). The official fit already records its five sites, so the narrower check has
what it needs.

## Still to do

- The public scope gate, the command that removes old copies, and the documentation are separate
  changes (decision record 0021).
- The hold-out check still uses every site; it needs the same choice before it runs on the larger
  list.
- A pooled fit of all sites must pass the simulated-data coverage test at the real site count
  before the owner names it as a screening or official fit.
- The methods page must say that screening sites and pilots can come from different fits.
