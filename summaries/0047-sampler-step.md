# PR #47: Take smaller sampler steps so the real-data fit passes its checks

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/47)

## In one sentence

The model's sampler now takes smaller steps (target_accept 0.95 instead of 0.9), which removes
the rare failed steps it hit on the first real-data fit without changing the estimates.

## Why it was needed

The model's ranges come from a sampler that wanders through the possible answers. A
"divergence" is a step where that wander broke down, and the project's rule is strict: any
divergence fails the whole fit and every site is reported as insufficient data. The first fit
on real data (run `fit-20261107T004543Z`, Nov 7, 2026 UTC) had 2 divergences, so all five
sites failed, although the other checks (r-hat 1.006, effective sample size 716) passed.

## What it adds

- The sampler's target acceptance rate goes from 0.9 to 0.95 in `config/model.yaml`, and the
  plan says so. Fits with site traits already used 0.95 (ADR 0008).
- The diagnostic rule is unchanged: a fit with any divergence still fails.

Same data and settings, only the step setting and the random seed changed:

| target_accept | Seed | Divergences | r-hat (max) | ESS (min) |
|---|---|---|---|---|
| 0.90 | default | 2 | 1.006 | 716 |
| 0.90 | 1 | 2 | 1.009 | 537 |
| 0.90 | 2 | 1 | 1.011 | 652 |
| 0.95 | default | 0 | 1.006 | 693 |
| 0.95 | 1 | 0 | 1.003 | 733 |
| 0.95 | 2 | 0 | 1.007 | 619 |
| 0.95 | 3 | 0 | 1.006 | 695 |

## What we learned

The divergences came from the step size, not from the model or the data. Across all these runs
the estimates moved by about 1%. Newby Island's median stayed between 14,057 and 14,141 t/yr.
The seed stays at its default; no seed was chosen to make the checks pass.

## Still to do

Record the first fit on real data from `main` with this setting, and publish it for review as a
provisional screening indication.
