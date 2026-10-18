# PR #2: The emissions model and its first test

**Status:** merged October 7, 2026 · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/2)

## In one sentence

Built the statistical model at the heart of the project, which turns a
handful of satellite passes into an annual methane estimate per landfill, and
showed on simulated data that its uncertainty ranges are honest.

## Why it was needed

A satellite passes over a landfill only every few days or weeks. When it sees
a plume, that proves a leak on that day, not how often the site leaks. When
it sees nothing, the site may be clean, or the leak may be too small for that
instrument to detect.

To say how much a site emits in a year, the project needs a method that:
- uses every pass, including the ones where nothing was seen;
- knows what each instrument can and cannot detect;
- reports a range, not a single number.

The plan says to prove such a method works on simulated data before trusting
it on real data. That proof is "Gate 3".

## What it adds

- **The model.** For each site it estimates:
  - the share of time the site is emitting above a detection floor;
  - the typical leak rate while it is emitting;
  - the resulting tonnes of methane per year, each with a 90% range.

  Sites share information, so a site with few passes gets a wide range
  instead of a made-up precise number.
- **A simulator** that invents landfills with known emissions and generates
  the satellite passes those landfills would produce.
- **The Gate 3 test.** It simulates many landfills, runs the model on them,
  and checks how often the 90% range contains the true value.

## What we learned

- **Gate 3 passed.** Across 2,000 simulated sites, the 90% ranges contained
  the truth:

  | Estimate | How often the 90% range contained the truth |
  |---|---|
  | Emitting share | 91.0% |
  | Typical leak rate | 90.0% |
  | Annual total | 89.5% |

  The target was 85–95%. 7% of model runs failed the internal quality checks,
  under the 10% limit.
- **It holds for thin data too.** The ranges stayed honest even for sites
  where the satellites never saw a plume.
- **What the model assumes before seeing data.** Its built-in starting
  assumptions put a typical site at about 1,000 tonnes of methane a year,
  within a plausible range of roughly 34 to 15,600 tonnes. One of them was
  adjusted to avoid a numerical problem. These assumptions are recorded as a
  proposal for the faculty sponsor to review.

## Still to do

The model has only seen simulated data. It needs real satellite passes, site
boundaries and each instrument's published detection limits before it can
produce a real estimate.
