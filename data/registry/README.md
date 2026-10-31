# Site registry

Hand-curated inputs. These are the only data files tracked in git.

| File | Contents |
|---|---|
| `sites.csv` | One row per landfill: attributes, tier (`pilot` / `screen`), known neighbor sources |
| `sites.geojson` | Boundary polygons (to be drawn in weeks 1–2 over imagery and permit maps), keyed by `site_id`; pilot sites also get `working_face` and `closed` parts |
| `checks.csv` | Dated checks: Air District inspections and notices, operator repairs (with a `repair_kind`), CARB plume notices. **Every row cites a source document** (order, notice, monitoring report, operator log). An official title goes in `source_doc_title`; `description` is in the project's own words |
| `operator_crosswalk.csv` | Maps `site_id` to EPA GHGRP and CARB reporting IDs |

Blank fields in `sites.csv` are filled from permits and Air District records; do not fill them from memory.
The screening tier (~38 sites under Rule 8-34) is added in week 2.
