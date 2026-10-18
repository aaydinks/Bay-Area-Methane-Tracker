# PR #3: Checking whether repairs worked

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/3)

## In one sentence

Added the test that judges whether a landfill's emissions dropped after a
documented repair, and measured how often that test raises false alarms.

## Why it was needed

Showing that repairs work is one of the project's three main goals. Today
there are no public numbers on whether a landfill repair cut emissions.
Carbon Mapper's own CEO has said the methods are still being developed.

A naive before/after comparison can mislead in two ways:
- **Changes that hit every site at once.** A new satellite coming online, or
  the seasons, can shift emissions everywhere at the same time.
- **Chance.** With few satellite passes, random variation alone can look like
  a drop.

The plan requires two safeguards: compare against landfills that weren't
repaired, and measure the false-alarm rate on fake repair dates before
publishing any real result. That measurement is "Gate 5", and it must come
in at or below 10%.

## What it adds

- **The repair test.** It compares a site's emissions in the year before and
  the year after a repair, against control landfills over the same period.
  Each result comes as the change with a 90% range, the probability that
  emissions fell, and a verdict:
  - **drop** or **rise**, only when the evidence is strong;
  - **inconclusive** otherwise;
  - **insufficient data** when either year has too few passes.
- **Placebo tests.** The same test run on random dates at sites where nothing
  changed, to count false alarms.
- **A power check.** Plants known drops in simulated data to see how big a
  drop the test can actually catch.
- **A quick count of passes** around any repair date, to decide early whether
  a case, such as Sonoma Central's 2023 repairs, has enough data.

## What we learned

- **The plan's original rule failed its own gate, by design.** Calling a change
  whenever the 90% range excluded zero raises false alarms about 10% of the
  time by construction, right at the limit. The first run came in at 12.9%.
  Raising the bar to 97.5% certainty brought false alarms down to **2.0%**,
  across 40 independent simulated scenarios. The 90% range is still reported
  with every result.
- **The test struggles to see modest drops.** With simulated satellite
  revisit rates, a 75% drop at a typical site was caught only 43% of the time.
  No tested drop was caught 80% of the time. Many real repairs will come back
  "inconclusive", so every result must show the smallest drop the data could
  have detected.

## Still to do

Gate 5 proper runs on real satellite records and documented repair dates.
Those dates come from the Air District records request and operator logs.
