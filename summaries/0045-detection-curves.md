# PR #45: Source a detection curve for each instrument and the emission floor

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/45)

## In one sentence

Each instrument now has a published figure for how small a methane plume it can see, so the
main model can finally run on real data, with every result marked provisional.

## Why it was needed

The model works out how often a landfill emits from both the passes where a plume was seen and
the passes where none was. A pass with no plume only means something once you know how small a
plume that instrument could have missed. Without those figures the model refused to run on real
data, and nothing could be estimated for the five pilot sites.

## What it adds

- For each instrument, the emission rate it catches half the time, and how quickly detection
  rises around that rate, all at a wind of about 3 m/s:
  - Carbon Mapper aircraft: about 29 kg/hr (90% of the time at 45 kg/hr).
  - Tanager-1: about 114 kg/hr (90% at 200 kg/hr).
  - EMIT: about 600 kg/hr (90% at 1,060 kg/hr).
  - Sentinel-2: about 7,000 kg/hr on vegetated ground.
- An emission floor of 18 kg/hr. The estimates count only methane released above this rate.
- A decision record (ADR 0015) listing each source, the table or section each figure comes
  from, the arithmetic, and what is still in doubt.

## What we learned

- Every published test of these instruments was flown over bright desert or Wyoming range. None
  was flown over ground like the Bay Area's, so the figures are probably optimistic.
- The Tanager-1 figure comes from conference slides, not a peer-reviewed paper.
- AVIRIS-3, which flew six of the 14 aircraft passes over Newby Island, has no published
  detection curve.
- Sentinel-2's limit on vegetated ground looks several times higher than the "about 2 t/hr"
  in the plan. The lower figures come from desert sites.
- Only the aircraft can see emissions below about 100 kg/hr. Acme Fill and Shoreline were
  never flown, so their estimates at low rates rest mostly on the model's starting assumptions.

## Still to do

- Confirm each curve against controlled releases or the project's own data. Until then, every
  result is provisional.
- Find out whether the Tanager-1 pilot passes used its standard or its more sensitive mode.
- Run the planned sensitivity checks, with each curve halved and doubled.
