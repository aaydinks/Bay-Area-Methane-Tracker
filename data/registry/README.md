# Site registry

Hand-curated inputs. These are the only data files tracked in git.

| File | Contents |
|---|---|
| `sites.csv` | One row per landfill: attributes, tier (`pilot` / `screen`), known neighbor sources |
| `sites.geojson` | Boundary polygons, keyed by `site_id`; pilot sites also get `working_face` and `closed` parts. **For now every outline is a provisional 500 m circle** around the CalRecycle SWIS point, and `polygon_source` in `sites.csv` says so. Real outlines replace them under ADR 0018 |
| `checks.csv` | Dated checks: Air District inspections and notices, operator repairs (with a `repair_kind`), CARB plume notices. **Every row cites a source document** (order, notice, monitoring report, operator log). An official title goes in `source_doc_title`; `description` is in the project's own words |
| `operator_crosswalk.csv` | Maps `site_id` to EPA GHGRP and CARB reporting IDs |

Blank fields in `sites.csv` are filled from permits and Air District records; do not fill them from memory.
The screening tier is proposed by `mw sites screen` and enters this folder only after a hand review.

## Identifying columns in `sites.csv`

| Column | Rule |
|---|---|
| `region` | The project region of the site's county (`config/project.yaml`). `mw sites build` works it out from `county` and stops if this column says otherwise, or if the county is in no region |
| `swis_number` | CalRecycle's site number, in the form `43-AN-0003`. No two sites may share one. The five pilots' numbers come from `datasets/calrecycle/swis_pilot_sites.csv`, checked against CalRecycle on 2026-10-17 |
| `air_district` | **Leave blank until a person has checked it with the district.** While blank, the build reads the district from CARB's outlines (`datasets/boundaries/air_districts.geojson`, as of March 2004): the district that holds most of the site's outline. That value is marked unconfirmed. Once checked, write CARB's name for the district here (for example `Bay Area`); the build then marks it confirmed and uses it even where the old outline disagrees |
| `district_facility_id` | The site's facility number at its air district, from permits (this column was `baaqmd_facility_id`) |

`mw sites build` lists any site within 500 m of a district edge, or in no district outline, so those are checked first.
