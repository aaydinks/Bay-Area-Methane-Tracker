# PR #55: Leave out of the fit any instrument nobody has searched

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/55)

## In one sentence

The model now takes an instrument's passes only once a plume search has run on them, so
Sentinel-2's 1,293 unsearched passes no longer enter a default fit as passes that saw nothing.

## Why it was needed

- **What a pass without a plume means.** The model reads every usable pass with no plume as
  "looked and saw nothing". That is true only if someone searched the image for plumes.
- **Sentinel-2 has never been searched.** The project's own Sentinel-2 plume search has not
  run on the landfill passes. The first real fit (November 6) left Sentinel-2's passes out by
  hand. Since PR 51 there are 1,293 of them, against 95 from all other instruments.
- **The risk.** A default fit would have taken all 1,293 as passes that saw nothing. Sentinel-2
  sees only large plumes, so each would have counted as evidence that no large leak was there,
  although nobody had looked.

## What it adds

- **The rule.** Each instrument now lists the plume sources whose search covers its images:
  - Carbon Mapper for Tanager-1 and the aircraft;
  - Carbon Mapper and NASA for EMIT;
  - the project's own search for Sentinel-2.

  A fit takes an instrument only if one of those sources has written its plume table. An empty
  table counts: the search ran and found nothing.
- **A deliberate way back in.** `mw model fit --include-unsearched sentinel2` keeps an
  unsearched instrument on purpose, and the run says so.
- **A record of what was left out.** Each run's record names any instrument left out, with the
  reason, its usable passes and its detections. It also names any site that had no other
  passes. The saved table of passes holds only the rows the fit used.
- **What readers see.**
  - Each site page names the instruments in the estimate and says why any were left out.
  - The pass table marks Sentinel-2 "not in the estimate".
  - The methods page states the rule.
  - The download notes list the model's instruments.
  - `mw publish build` prints them too.
- **Decision record 0016** sets out the options and why this one was chosen.

## What we learned

- **EMIT's rated plumes arrive through Carbon Mapper** (20 of them), not through NASA's own
  table, whose plume complexes carry no rate. A rule keyed to NASA's source alone would have
  dropped EMIT as well.
- **"At least one plume found" would have been the wrong test.** Sentinel-2 detects half of
  plumes only at about 7 t/hr. A search of these landfills may well find nothing, and that
  result has to count as a search.
- **No published estimate changes.** The official fit already left Sentinel-2 out, and it was
  not re-run. Its record predates this change, so its site pages say only that Sentinel-2's
  passes are not part of the run, without the reason.

## Still to do

- **A record of which passes were searched.** The rule works per instrument, not per pass. A
  Sentinel-2 search over only one year would let every pass in. Before the first fit with
  Sentinel-2, either search every pass or have the search record which passes it covered.
- **The same rule for the repair checks and the hold-out check.** Both read the same table
  and still take every instrument.
- **Did Carbon Mapper process every EMIT image?** EMIT's passes come from NASA's image list. If
  Carbon Mapper skipped some images, those passes count as searched when they were not.
