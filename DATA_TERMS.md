# Data terms and credits

This project is non-commercial. Raw downloads live under `data/raw/` and are never committed.
The committed copies of each dataset are in `datasets/` (see `datasets/README.md`); Carbon Mapper's
folder there is git-ignored except for its README and pull manifests.
Before publishing any derived table, confirm below that the source's terms allow it.

| Source | Use | Terms (to confirm) | Derived tables publishable? | Credit line |
|---|---|---|---|---|
| Carbon Mapper (Tanager-1, EMIT, aircraft plumes) | Plume locations and rates | Free for non-commercial use; API key required. Confirmed verbally to the project owner (reported 2026-11-08): figures may be shown on the website, but the data, downloads, data tables and individual values may not be republished. Written terms: check | no; display only (ADR 0017): shown on the website, never in downloads, and plume rates never shown | _to fill from the product guide_ |
| Carbon Mapper CO2 plume and scene lists | Counts per landfill and year: days searched for CO2, and CO2 plumes on or beside the landfill (ADR 0024) | Same service and non-commercial terms as above. Whether the display terms reported on 2026-11-08 also cover CO2 counts has not been asked: check | no; review copies only until confirmed | "Carbon Mapper (non-commercial use)" |
| NASA EMIT L2B CH4 enhancement and plume complexes (v002) | Scene footprints (overpasses), plume outlines | NASA open data; metadata public, files need Earthdata login | _to confirm_ | _to fill from LP DAAC citation (DOIs 10.5067/EMIT/EMITL2BCH4ENH.002, 10.5067/EMIT/EMITL2BCH4PLM.002)_ |
| ESA Copernicus Sentinel-2 (L1C; metadata via Earth Search STAC; pixels from Google Cloud's public mirror `gcp-public-data-sentinel-2`) | Scene footprints, large-plume check | Copernicus open data licence; AWS L1C bands are requester-pays | _to confirm_ | "Contains modified Copernicus Sentinel data [year]" |
| Wind reanalysis (HRRR or ERA5) | Plume quantification | NOAA open data / Copernicus licence | _to confirm_ | _to fill_ |
| CloudSEN12+ v1.1 (Hugging Face `tacofoundation/cloudsen12`, revision `f9490f7`) | Expert cloud labels to train and test the Sentinel-2 cloud model (ADR 0012, 0013) | CC0 1.0 on the v1.1 cards, checked 2026-10-31; older copies state other terms (check) | yes (test metrics only; no pixels are redistributed) | "CloudSEN12+ (Aybar et al. 2024, Data in Brief 56:110852)" |
| US EPA GHGRP (Envirofacts REST) | Operator-reported subpart HH methane | US government public data | yes | "US EPA Greenhouse Gas Reporting Program, accessed via Envirofacts" |
| Bay Area Air Quality Management District | Permits, orders, monitoring reports | Public records | yes, with citation | _to fill_ |
| Northern Sonoma County APCD | Records for the two sites in its area, none requested yet | Public records; terms not checked | _to confirm_ | _to fill_ |
| Sacramento Metro AQMD | Records for the six sites in its area, none requested yet | Public records; terms not checked | _to confirm_ | _to fill_ |
| San Joaquin Valley APCD | Records for the eleven sites in its area, none requested yet | Public records; terms not checked | _to confirm_ | _to fill_ |
| Yolo-Solano AQMD | Records for the four sites in its area, none requested yet | Public records; terms not checked | _to confirm_ | _to fill_ |
| US Census ACS 5-year (B01003) and TIGERweb block groups | Population context, areal-weighted | Public data; ACS API needs a free key | yes | "US Census Bureau, American Community Survey 5-year estimates" |
| US Census 2020 TIGER/Line blocks (`tl_2020_06_tabblock20`, carries `POP20`) | Block population near sites | Public data, no key | yes | "US Census Bureau, 2020 Census, TIGER/Line Shapefiles" |
| CalRecycle Solid Waste Information System (SWIS) | Site reference points, addresses, status | Public records | yes, with citation | "CalRecycle Solid Waste Information System (SWIS)" |
| CalRecycle LandfillBoundaries layer (layer 9 of OEHHA's `CalEnviroScreen_4_Indicator_Facility_Data` map service; data as of September 2021) | Outlines of screening-tier sites | Checked 2026-11-21: the layer, its service and its catalogue entry state no terms; the layer credits CalRecycle. CalRecycle's [conditions of use](https://calrecycle.ca.gov/help/conditionsofuse/) treat information on its website as public domain unless marked otherwise, and recommend written permission before part of a publication is reused. OEHHA's [conditions of use](https://oehha.ca.gov/public-information/conditions-use) add disclaimers only. Written confirmation from CalRecycle: check | yes, with credit, on that reading; _to confirm in writing_ | "CalRecycle, landfill boundaries (drawn from permit maps; data as of September 2021)" |
| US Census 2025 cartographic boundaries and TIGER/Line 2025 (counties, places, tracts, roads, area water) | Map outlines, descriptive context | Public data, no key | yes | "US Census Bureau, 2025 Cartographic Boundary Files and 2025 TIGER/Line Shapefiles" |
| CARB air district boundaries (`CaAirDistrict_PublicWeb`, as of March 2004; check against current BAAQMD) | Descriptive district outline, never a covariate | Public map service; no terms published (check) | _to confirm_ | "California Air Resources Board, air district boundaries as of March 2004 (originally developed by Teale Data Center GIS Lab)" |

Record the date each row was checked and a link to the terms page.

**Air districts.** The four districts added in November 2026 are named as CARB's list of
districts writes them (https://ww2.arb.ca.gov/california-air-districts, read 2026-11-23). Which
sites fall in which district is read from CARB's 2004 outlines and is not yet checked with any
district. A district enters `config/data_terms.yaml`, and so the website's list of sources, only
once records from it are in hand and its terms have been checked.
