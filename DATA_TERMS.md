# Data terms and credits

This project is non-commercial. Raw downloads live under `data/raw/` and are never committed.
The committed copies of each dataset are in `datasets/` (see `datasets/README.md`); Carbon Mapper's
folder there is git-ignored except for its README and pull manifests.
Before publishing any derived table, confirm below that the source's terms allow it.

| Source | Use | Terms (to confirm) | Derived tables publishable? | Credit line |
|---|---|---|---|---|
| Carbon Mapper (Tanager-1, EMIT, aircraft plumes) | Plume locations and rates | Free for non-commercial use; API key required | _to confirm_ | _to fill from the product guide_ |
| NASA EMIT L2B CH4 enhancement and plume complexes (v002) | Scene footprints (overpasses), plume outlines | NASA open data; metadata public, files need Earthdata login | _to confirm_ | _to fill from LP DAAC citation (DOIs 10.5067/EMIT/EMITL2BCH4ENH.002, 10.5067/EMIT/EMITL2BCH4PLM.002)_ |
| ESA Copernicus Sentinel-2 (L1C; metadata via Earth Search STAC; pixels from Google Cloud's public mirror `gcp-public-data-sentinel-2`) | Scene footprints, large-plume check | Copernicus open data licence; AWS L1C bands are requester-pays | _to confirm_ | "Contains modified Copernicus Sentinel data [year]" |
| Wind reanalysis (HRRR or ERA5) | Plume quantification | NOAA open data / Copernicus licence | _to confirm_ | _to fill_ |
| CloudSEN12+ v1.1 (Hugging Face `tacofoundation/cloudsen12`, revision `f9490f7`) | Expert cloud labels to train and test the Sentinel-2 cloud model (ADR 0012, 0013) | CC0 1.0 on the v1.1 cards, checked 2026-10-31; older copies state other terms (check) | yes (test metrics only; no pixels are redistributed) | "CloudSEN12+ (Aybar et al. 2024, Data in Brief 56:110852)" |
| US EPA GHGRP (Envirofacts REST) | Operator-reported subpart HH methane | US government public data | yes | "US EPA Greenhouse Gas Reporting Program, accessed via Envirofacts" |
| Bay Area Air Quality Management District | Permits, orders, monitoring reports | Public records | yes, with citation | _to fill_ |
| US Census ACS 5-year (B01003) and TIGERweb block groups | Population context, areal-weighted | Public data; ACS API needs a free key | yes | "US Census Bureau, American Community Survey 5-year estimates" |
| US Census 2020 TIGER/Line blocks (`tl_2020_06_tabblock20`, carries `POP20`) | Block population near sites | Public data, no key | yes | "US Census Bureau, 2020 Census, TIGER/Line Shapefiles" |
| CalRecycle Solid Waste Information System (SWIS) | Site reference points, addresses, status | Public records | yes, with citation | "CalRecycle Solid Waste Information System (SWIS)" |
| US Census 2025 cartographic boundaries and TIGER/Line 2025 (counties, places, tracts, roads, area water) | Map outlines, descriptive context | Public data, no key | yes | "US Census Bureau, 2025 Cartographic Boundary Files and 2025 TIGER/Line Shapefiles" |
| CARB air district boundaries (`CaAirDistrict_PublicWeb`, as of March 2004; check against current BAAQMD) | Descriptive district outline, never a covariate | Public map service; no terms published (check) | _to confirm_ | "California Air Resources Board, air district boundaries as of March 2004 (originally developed by Teale Data Center GIS Lab)" |

Record the date each row was checked and a link to the terms page.
