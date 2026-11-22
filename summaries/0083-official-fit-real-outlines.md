# PR #83: The fit on the real outlines becomes the official one

**Status:** merged 2026-11-22 · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/83)

## In one sentence

The twice-weekly run now carries the estimates from the fit made on the four real landfill
outlines, so review copies can be made again.

## Why it was needed

The project names one checked fit as official. The twice-weekly run copies that fit's estimates
into each review copy, but only while the fit still matches the refreshed data. PR 82 gave four
studied landfills their real outlines, and four more plumes now count at Potrero Hills. The old
official fit was made before that, so it no longer matched, and every run would have stopped
before review and loaded a draft instead.

## What it adds

- **A new official fit.** `publish.official_model_run` in `config/project.yaml` now names
  `fit-20261122T211406Z`, the fit of the five studied landfills on the outlines from PR 82. The
  README line that quotes the name is updated to match.

Nothing on the public website changes with this step. The public copy was made earlier and keeps
its figures until the owner promotes a new one.

## What we learned

- **The new fit matches the refreshed data.** A trial of the twice-weekly run that loads nothing
  carried the fit without stopping: 95 passes at the five landfills, the same in the fit and in
  the refreshed tables.
- **The fit passes its diagnostics** and was made from committed code with no local changes.
- **Two figures move.** Newby Island is about 14,500 tonnes a year (11,400 to 18,200), against
  14,100 (11,300 to 17,700) before. Potrero Hills is about 1,440 (760 to 2,390), against 750 (310
  to 1,470), because four more plumes fall within 500 m of its real outline. Acme Fill, Shoreline
  and Sonoma Central still have too little data for an estimate. All figures stay provisional.

## Still to do

- Rebuild the locked review website so reviewers see the new outlines and figures (owner's
  go-ahead).
- Decide when the public copy moves to the new figures (owner's decision).
- The hold-out and placebo checks have not yet run on real data.
- The methods page does not yet describe the sector rule from PR 81.
