# PR #19: County outlines and the Bay Area air district

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/19)

## In one sentence

Adds the public county and air district outlines the maps and site descriptions need. CARB's district
outline dates from March 2004, so it is labelled "check against current BAAQMD" everywhere.

## Why it was needed

Maps of the project data were drawn from boundary files downloaded by hand, outside the pipeline and
without a pull record. A later step will also say which air district each landfill sits in, purely as a
description, never as a model input. Both need the same outlines, pulled the same way as every other source:
from a recorded address, at a recorded time, with a fingerprint of each file.

## What it adds

- **One download command** for 14 public files: Census 2025 county and place outlines; 2025 census tracts,
  main roads, and lakes and bays for the nine counties; and CARB's Bay Area air district outline. Every
  download is logged with its address, time and a fingerprint.
- **Two small committed map files.** The nine counties, simplified to about 100 m of detail (108 KB). The
  air district at full detail (629 KB). Tracts, roads and water are too large to commit and stay local.
- **A README** with sources, credit lines and the 2004 caveat.

## What we learned

- **Split counties.** CARB's 2004 outline takes in about 40% of Solano's and Sonoma's area. The other seven
  counties are 96.6 to 99.7% inside. The gaps are where the 2004 outline and the 2025 county lines disagree:
  along shorelines, inlets such as Tomales Bay, and county lines.
- **Landfills.** 32 of the 36 landfills in the screening list fall inside the 2004 outline. One of the four
  outside, Recology Hay Road in Solano, is only 0.4 km from the edge.
- **Pilot sites.** All five are inside, at least 2 km from the edge.

These counts use the CalRecycle reference points, not site outlines, and a 2004 boundary: check against
current BAAQMD before relying on them.

## Still to do

- Check the district outline against the current BAAQMD boundary, starting with sites near its edge.
- Confirm CARB's terms of use for the outline; the map service publishes none.
- Add a descriptive `air_district` column to the site traits (a later pull request).
- Move the four public maps (overview, EMIT coverage, pilot sites, site traits) into the package. They were
  left out to keep this change small.
