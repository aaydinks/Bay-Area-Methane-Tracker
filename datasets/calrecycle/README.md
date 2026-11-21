# CalRecycle site records

## Screening list: `swis_landfills.csv`

Every SWIS site in the project's fourteen counties that has a "Solid Waste Landfill"
activity: 62 sites (31 active, 29 closed, 1 closing, 1 planned), including all five pilots.
36 are in the nine Bay Area counties and 26 in the five North Valley counties (Merced 2,
Sacramento 7, San Joaquin 12, Stanislaus 3, Yolo 2), pulled 2026-11-21. The 36 Bay Area
rows are the same as in the pull of 2026-10-18. Columns: SWIS
number, name, county, site and landfill status, regulatory status, address, latitude and
longitude, page URL. Rebuild with `mw ingest calrecycle` then
`mw datasets build --only calrecycle`.

This stands in for the Air District's Rule 8-34 list until that arrives. It is not the
same thing: a few entries are industrial or small rural units (for example the USS-Posco
waste unit), and old dumps recorded under other activity types are not included. Review
it before treating it as the 38-site screen.

Reviewed on 2026-11-21: the 28 permitted landfills that were not already pilots entered the
site registry as the Bay Area screening tier (`data/registry/sites.csv`). One landfill that
reports methane to EPA is not on this list: Davis Street Sanitary Landfill in San Leandro
(SWIS 01-AA-0006, EPA facility 1003800), which CalRecycle records under the activity "Solid
Waste Disposal Site". Fourteen closed, permitted Bay Area sites carry that activity.

North Valley, 2026-11-21: of the 26 landfills, 20 are permitted and are proposed for the
screening tier (`mw sites screen`); they are not in the registry until the list has been
reviewed by hand. The other six, all in San Joaquin County, are unpermitted and are left out.

## Pilot reference points: `swis_pilot_sites.csv`

`swis_pilot_sites.csv`: one row per pilot site from CalRecycle's Solid Waste Information
System (SWIS), read from each site's Details page on 2026-10-17. Columns: SWIS number,
name, SWIS page id, address, latitude and longitude, operational status, page URL, and
EPA GHGRP's own latitude and longitude for comparison.

**What the point is.** A single reference point per site, used to centre search windows
and image crops until real boundaries exist. It is not a boundary and it does not
attribute plumes. EPA's point is within about 1.6 km of CalRecycle's for each of the four
sites EPA lists.

**Notes from the lookup:**
- Acme Fill has no EPA GHGRP record, so CalRecycle is its only point (SWIS 07-AA-0002,
  "Acme Landfill", operator Acme Fill Corporation).
- Potrero Hills Landfill's SWIS number is 48-AA-0075. Earlier project notes called that
  a permit number.
- Sonoma Central is listed as "Central Disposal Site" (SWIS 49-AA-0001) at 500 Meacham
  Road.
- Shoreline is listed as "Shoreline Regional SLF/Mountain View SLF" (43-AA-0006, closed)
  at 1780 Amphitheater Parkway; EPA lists 2600 Shoreline Blvd.

**Source:** `https://www2.calrecycle.ca.gov/SolidWaste/Site/Details/<id>`. Public, no
login. Credit: "CalRecycle Solid Waste Information System (SWIS)."
