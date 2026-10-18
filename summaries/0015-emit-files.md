# PR #15: EMIT plume rates and image windows around the sites

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/15)

## In one sentence

Adds the NASA EMIT files that need a login: the details of each reviewed plume complex and a small methane image
around each pilot site for every EMIT pass.

## Why it was needed

The EMIT scene list (#13) says when EMIT looked at each site, but not what it saw. These files hold what it saw:
the methane signal around each site on each pass, and NASA's own rate estimate for each reviewed plume. They are
the EMIT side of the pass table and a cross-check on our own wind-based rates.

## What it adds

- NASA's details for all 7 reviewed plume complexes in the nine counties: peak signal, where it is, wind, and the
  emission rate with its uncertainty when NASA gives one.
- 169 small images (6 km square, 60 m pixels): one for each EMIT pass over each pilot site, with three layers:
  methane signal, its uncertainty, and the sensitivity. 118 of the passes cover the whole square.
- The login can now be a NASA token kept in the local `.env` file, which is never committed.

## What we learned

- Only 1 of the 7 plume complexes has a NASA rate: about 2,800 kg/hr (± 290) on 18 Aug 2023, 8.7 km from
  Potrero Hills, so not at a pilot site. The other six fail NASA's criteria for a rate, including the Newby Island
  plume of 7 Aug 2024. Our own wind-based rate will be the only estimate for that one.
- Between 31 and 38 EMIT passes touch each pilot site from Aug 2022 to Aug 2026.
- A bright pixel in one of these images is not a plume. Single-pixel highs show up at sites with no reviewed plume.

## Still to do

Score how much of each site each pass covers once site boundaries exist, and use the per-pixel data to replace the
scene-wide cloud figure in the pass table.
