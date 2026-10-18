# PR #7: Three more checks on the results

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/7)

## In one sentence

Added the remaining validation tests from the plan:
- does the model predict passes it hasn't seen?
- how do its estimates compare with operators' reports?
- how well does Sentinel-2 agree with better satellites?

## Why it was needed

The plan lists five tests a result must pass before it is shared. Two were
already built; these are the other three. Together with the earlier ones,
they are what make a published number defensible.

## What it adds

- **Hold-out prediction** (part of "Gate 4"). Part of each site's satellite
  passes are hidden, the model is fitted on the rest, and it predicts how many
  plumes the hidden passes should contain. If it predicts well, its picture of
  each site can be trusted. Target: the actual count falls inside the
  prediction range for at least 80% of hidden sets.
- **Comparison with operators' reports** (part of Gate 4). Each year a site
  reported to the EPA is marked as above, below or consistent with the
  satellite estimate. Every gap needs a written explanation before the gate
  passes. A gap is a question to answer, not proof that either side is wrong:
  the satellites see only daytime, clear-sky emissions above a floor, while
  operators' figures come mostly from waste models.
- **Sentinel-2 agreement.** Sentinel-2 is checked against EMIT and Carbon
  Mapper passes on the same day: how often it catches their plumes, by plume
  size, and how often it reports plumes they didn't see. The plan sets no pass
  mark; this measures what Sentinel-2 is good for.

## What we learned

On simulated landfills, the hold-out test passed easily. The actual count
fell inside the prediction range 98% of the time, and predicted and actual
plume totals were close (for example, 30.2 predicted against 30.0 observed).

## Still to do

All three tests need real data. Running the operator comparison will also
mean writing the explanation for each gap it finds.
