# CalRecycle site records

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
