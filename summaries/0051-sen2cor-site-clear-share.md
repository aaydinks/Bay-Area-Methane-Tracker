# PR #51: Sentinel-2 passes counted by Sen2Cor's view of each site

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/51)

## In one sentence

A Sentinel-2 pass now counts for a landfill when Sen2Cor's scene classification says at least
70% of the 5 km around that landfill is clear, instead of when the whole 110 km tile is clear
enough.

## Why it was needed

- **The old rule.** Whether a pass counted was judged from one cloud figure for the whole
  Sentinel-2 tile, about 110 km across. A cloudy coast could set aside a clear day over the bay,
  and a clear tile could hide a cloud over the landfill.
- **The plan.** The cloud model was meant to replace that figure, but it failed its check on
  the 2025 landfill passes (PR 49, decision record 0014). The rule written down before that
  check said Sen2Cor's classification over each site would replace the tile figure instead.
- **Sen2Cor beat the tile figure** on both errors in the held-out test. It is still far from
  clean: it called 35.7% of too-cloudy views usable (90% range 32.8 to 38.7%), against 36.9%
  for the tile figure, and threw away 9.2% of clear views, against 26.2%.

## What it adds

- **A new step, `mw s2 site-clear`.** For every Sentinel-2 pass over a pilot landfill, it reads
  Sen2Cor's classification for the same 6 km window as the cloud check and scores the central
  5 km. It needs only that one layer, about 0.1 MB per pass, instead of the 35 MB of all 13
  bands.
- **The overpass table.** For Sentinel-2:
  - `valid_frac` is now the per-site share;
  - the old tile figure is kept in `valid_frac_tile`, so the two can be compared;
  - `valid_frac_source` says which one was used.

  EMIT and Carbon Mapper passes are left as they were.
- **Every refresh** runs the step before the overpass table is built, and the twice-weekly
  scheduled run does too. If Sen2Cor's data can't be read for a pass, that pass keeps the tile
  figure, and the run stops before anything is published.

## What we learned

- **More passes count.** From August 2022 to October 2026, 1,293 of the 1,985 Sentinel-2 passes
  over the five landfills count, against 1,191 under the tile figure. 210 passes switch from
  unusable to usable and 108 the other way.

  | Site | Passes | Usable, tile figure | Usable, Sen2Cor per site | Usable → unusable | Unusable → usable |
  |---|---|---|---|---|---|
  | Acme Fill | 336 | 219 | 218 | 19 | 18 |
  | Newby Island | 336 | 171 | 235 | 8 | 72 |
  | Potrero Hills | 336 | 219 | 217 | 23 | 21 |
  | Shoreline | 336 | 171 | 230 | 10 | 69 |
  | Sonoma Central | 641 | 411 | 393 | 48 | 30 |

  These are counts of passes, not estimates, so they carry no range.
- **The bay sites gain most.** Newby Island and Shoreline lie on a tile that reaches out over the
  ocean, whose fog and cloud often push the tile figure above 30% while the bay is clear.
- **No plume is lost.** The Sentinel-2 plume search has never run on these passes, so none of
  them holds a Sentinel-2 detection. Nothing is masked before detection.
- **No estimate moves.** The first real fit left Sentinel-2 out. A Sentinel-2 pass will count as
  "looked and saw nothing" only once its plume search runs.
- **Reading only Sen2Cor's layer is more complete.** Every one of the 1,985 passes has a Sen2Cor
  share; none falls back to the tile figure. In the 13-band check, 25 views lacked a full one,
  because of:
  - a missing copy of the image (2 views);
  - an image copy cut at the edge of its strip (6 views);
  - the matching error fixed in PR 49 (17 views: 16 with no share, 1 with only part of one).
- **The download was small.** The 1,429 new windows took 75 seconds and about 0.14 GB, inside
  the approved ceiling of 0.2 GB. The rest came from the 13-band windows of the cloud check.

## Still to do

- **Rebuild the draft snapshot.** `pub-20261107T011826Z` was built before this change, so its
  Sentinel-2 passes still use the tile figure. Rebuild it before it is loaded for reviewers.
- **Publish the tile figure too, if wanted.** The website database holds one `valid_frac` per
  pass, now the per-site share. Showing the tile figure beside it needs a new database
  migration, which only the owner can apply.
- **Thin cirrus.** Sen2Cor's thin-cirrus class counts as cloud. Whether such thin cloud matters
  for plumes of 2 tonnes per hour or more has not been tested.
