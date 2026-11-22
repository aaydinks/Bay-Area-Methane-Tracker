# PR #80: Saved satellite windows follow a landfill when its outline changes

**Status:** merged 2026-11-22 · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/80)

## In one sentence

A saved Sentinel-2 cloud window is now reused only if it was cut around the landfill's current
centre, so replacing a landfill's outline cannot leave old cloud figures behind.

## Why it was needed

For each Sentinel-2 pass the project reads a small 6 km window of the cloud map around the
landfill's centre, and keeps it so it is never downloaded twice. The saved windows were filed by
landfill and pass only. If a landfill's outline changed, its centre moved, but the old windows were
still picked up, so older passes would describe a slightly different patch of ground from newer
ones.

The next step gives four of the five studied landfills their real outlines, which moves their
centres by 42 m to 449 m. This had to be right first.

## What it adds

- A check on every saved window: is it centred where this pass needs it? If not, the window is read
  again and saved, and later runs use the new one.
- Two tests for the rule.

## What we learned

- **Nothing changes today.** All 2,019 Sentinel-2 passes still use their saved windows and give the
  same clear-sky shares.
- **The cost of the next step is small.** About 1,700 windows will be read again when the four
  outlines change, roughly 0.14 GB and a couple of minutes.

## Still to do

- Give the four landfills their real outlines (the next change).
