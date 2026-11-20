# 0018: Two regions: the Bay Area and the North Valley

- **Status:** accepted
- **Date:** 2026-11-19

## Context

The tracker was planned for the nine Bay Area counties. On 2026-11-19 the project owner decided to
widen it towards the Central Valley around Stockton.

Two facts about the present state matter:

- **The screening tier was never loaded.** The plan describes about 38 screened landfills, but the
  registry holds only the five pilot sites, each with a provisional 500 m circle. A CalRecycle list
  of 36 Bay Area sites sits in `datasets/calrecycle/` and has not been reviewed into the registry.
- **"The region" is defined in eight places.** `config/project.yaml` holds two boxes, and the code
  holds a third box and several county lists (`sites/registry.py`, `ingest/ghgrp.py`,
  `ingest/calrecycle.py`, `ingest/boundaries.py`, `datasets.py`, `sentinel2/cloudrun.py`). The
  registry check rejects any outline outside its own Bay Area box.

## Options considered

1. **Bay Area plus the North Valley** (chosen): San Joaquin, Stanislaus, Merced, Sacramento and Yolo
   counties. It reaches Stockton and stays west of 120°W.
2. **Add the whole San Joaquin Valley**, down to Kern County. Many more landfills, but oil fields
   sit beside some of them, which makes plume attribution much harder, and the eastern part lies in
   a different map zone (UTM 11), which the Sentinel-2 pixel code rejects.
3. **A full band from the coast to the Sierra.** The largest site count and the most regulators,
   with the same map-zone problem.

## Decision

- **Regions live in config.** `config/project.yaml` gains a `regions` list. Each region has an id,
  a label, its counties with FIPS codes, and an explicit bounding box. One loader serves every
  consumer; the eight separate definitions go away.
  - `bay-area`: Alameda, Contra Costa, Marin, Napa, San Francisco, San Mateo, Santa Clara, Solano,
    Sonoma.
  - `north-valley`: San Joaquin, Stanislaus, Merced, Sacramento, Yolo.
- **The map projection does not change.** Every county above lies west of 120°W, so EPSG:32610
  (UTM zone 10N) stays valid for distances and for Sentinel-2 tiles. The registry check gains a
  guard that rejects a site east of 120°W, so a later widening cannot slip past this assumption.
- **Each site records its region, air district and SWIS number.** The air district comes from
  overlaying CARB's district outlines on the site, not from the county, because some counties are
  split between districts. It stays `confirmed: false` until checked against the district itself.
  `baaqmd_facility_id` becomes `district_facility_id`.
- **The screening tier is built from CalRecycle's list** under a written rule: permitted landfills,
  open or closed; no transfer stations, exempt sites or waste-to-energy plants. The list is reviewed
  by hand before it enters the registry.
- **Outlines, in order of preference:** a hand-drawn outline; CalRecycle's public LandfillBoundaries
  layer, matched by SWIS number; a 750 m buffer around the SWIS point, marked provisional. Buffers
  of sites closer together than the buffers are wide are cut at the midline between them.
- **Sentinel-2 stays on pilot and deep-dive sites.** It sees only very large plumes and is costly
  per site.
- **Deep-dive sites in the North Valley are chosen after the first screening results**, not now.

## Consequences

- What was checked live on 2026-11-19, over the box `-123.64, 36.7, -120.0, 39.0`:
  - NASA EMIT: 477 scenes and 14 plume complexes.
  - Carbon Mapper: 1,196 methane plumes tagged as waste.
  - EPA greenhouse-gas reports for 2023: 17 Bay Area landfills and 6 in the North Valley (Forward,
    Fink Road, Kiefer, Highway 59, Billy Wright, Yolo County Central).
  - CalRecycle LandfillBoundaries: outlines for four of the five pilots (not Shoreline) and for 12
    North Valley SWIS numbers, one of which is a waste-to-energy plant.
- EPA's county field is inconsistent ("SAN JOAQUIN" and "SAN JOAQUIN COUNTY" both occur). The county
  filter must compare names without the suffix.
- Real outlines for the pilots change which plumes count towards each site, so the Bay Area fit is
  redone when they go in (see 0021 for how two fits sit side by side).
- More than one regulator is now involved. The North Valley counties are expected to fall under the
  San Joaquin Valley, Sacramento Metropolitan and Yolo-Solano districts (check each site against the
  overlay). Each has its own landfill rule and records process, still to be read.
- Dairies and other methane sources sit near Valley landfills. A plume that Carbon Mapper tags with
  a sector other than waste is marked ambiguous and never assigned to a landfill. That rule also
  touches the pilots, so it lands together with their new outlines and refit.
- **Still to check:** terms of use for the CalRecycle layer; the date of CARB's district outlines;
  the final box of each region against county outlines.
- The project name still says "Bay Area". The owner will decide on the name later; until then, new
  copy avoids naming a region in titles.
