# PR #13: Real source data in a datasets folder

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/13)

## In one sentence

Pulls the project's real public data for the first time and keeps a copy in the repository, in a new
`datasets/` folder with one subfolder per source, each with a README saying where it came from.

## Why it was needed

Until now everything ran on simulated data. The downloads that did exist sat in a local folder that is never
committed, so nobody else could see them. The model, the repair test and the Sentinel-2 check all need the real
satellite looks, plume lists and population counts before any real fit can start.

## What it adds

- **NASA EMIT (version 2):** every EMIT look over the nine Bay Area counties since August 2022 (309 scenes,
  156 over the pilot sites) and the 7 reviewed plume complexes. No scene falls in EMIT's Sept 2022 to Jan 2023
  outage, and each scene is flagged so that gap reads as "no data", not "no leak".
- **Carbon Mapper:** the plume list (613 methane plumes, 597 labelled solid waste) and Carbon Mapper's own scene
  list. These files stay on the local machine only, because Carbon Mapper's terms forbid sharing the data; the
  folder holds just a README and download records.
- **Sentinel-2:** the list of all 2,101 scenes over the pilot area, and small crops (6 km square, five bands)
  around the sites on the 7 days when a plume was seen and Sentinel-2 passed under clear skies, plus clear
  earlier days to compare against.
- **Census 2020:** population for all 82,210 blocks in the nine counties (total 7,765,640), and block outlines
  within 6 km of the pilot sites.
- **EPA reports:** the operator-reported figures for the four sites EPA covers, and the list of 17 Bay Area
  landfills that report.
- **Site reference points:** the state's (CalRecycle) location and address for each pilot site, including
  Acme Fill, which EPA does not list.
- One command rebuilds the folder from fresh downloads.

## What we learned

- **Carbon Mapper's scene list includes looks with no plume** (81 of 98 EMIT scenes and 27 of 62 Tanager scenes
  had none). That answers an open question: it can count Carbon Mapper's passes, not only its finds. Some scenes
  also state Carbon Mapper's own detection limit, about 120 to 350 kg/hr for a 50% chance of seeing a plume.
- **No accounts were needed** for Carbon Mapper's plume list, Sentinel-2 pixels (a free Google copy) or the
  census counts (the 2020 block file carries them). Only NASA's EMIT files need a login.
- **Carbon Mapper's processing versions are mixed**, and its version filter had no effect, so keeping a single
  version would leave only 18 of 613 plumes. That choice needs a decision.
- Most plumes near pilot sites are at Newby Island (269 within 3 km). None were found within 3 km of Sonoma
  Central or Shoreline.
- Potrero Hills' state facility number is 48-AA-0075; earlier notes called that a permit number.

## Still to do

- EMIT plume rates and image windows around each site, once the NASA login is set up.
- Site boundaries, which turn "near a site" into proper plume attribution.
- Confirm with Carbon Mapper whether summary counts and plume days may be published before the repository goes
  public.
- Decide whether population moves to 2020 blocks (a method change), and which Carbon Mapper versions to keep.
