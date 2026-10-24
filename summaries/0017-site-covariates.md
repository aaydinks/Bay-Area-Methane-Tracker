# PR #17: Site traits as model covariates

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/17)

## In one sentence

Lets a few known traits of each landfill, such as whether it is closed and how large it is, inform the
estimates, without changing the model at all when they are switched off.

## Why it was needed

The model treats every landfill alike until the satellite data says otherwise. For sites with only a few passes
that wastes what we already know: a closed landfill has no active tipping area, and a bigger footprint has more
surface that can leak. Feeding those traits in lets thin sites borrow from similar sites instead of from the
Bay Area average. With about 5 pilot sites and 36 in the screening list, a separate machine-learning model would
overfit, so the traits go into the existing model instead.

## What it adds

- **A site traits table** (`mw features build`): closed or not, footprint area, whether the site reports to the
  EPA, and distance to the nearest other methane source. Built from the site boundaries, so it waits on them.
- **Optional covariates in the model and the repair test**, chosen in `config/model.yaml`, at most two or three,
  and none by default. Nearby population is never used as an input; county and operator stay descriptive.
- **A Gate 3 option** to simulate and test with covariates, and a decision record (ADR 0008).

## What we learned

The first full check with two covariates got the ranges right (88.5 to 90.2% coverage against a 90% target) but
failed the sampler checks: 11.5% of fits against a 10% limit, mostly from one or two "divergences" each. A
slightly more careful sampler setting for covariate fits fixed it: 4.5% failing, coverage 88.8 to 89.8%. Both
reports are kept.

## Still to do

- Draw the site boundaries, build the traits table, and decide which two covariates to switch on.
- Rerun the prior check and the hold-out test once real data is in.
- A seasonal effect would need a per-season parameter; it is left for later.
