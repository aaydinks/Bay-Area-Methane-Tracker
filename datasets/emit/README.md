# NASA EMIT methane products (version 002)

EMIT is an imaging spectrometer on the International Space Station. Its methane products
are archived at NASA's LP DAAC.

| File | Collection | Contents |
|---|---|---|
| `scenes.geojson` | `EMITL2BCH4ENH` v002 | One row per EMIT scene touching the nine-county box: `scene_id`, `acquired_utc`, `cloud_cover_pct` (scene average), `in_outage`, outline |
| `plume_complexes.geojson` | `EMITL2BCH4PLM` v002 | One row per reviewed plume complex: `plume_id`, `granule_ur`, `acquired_utc`, `source_scenes`, outline |
| `pulls/` | | Manifests of the catalog searches these were built from |

**Why version 002.** Version 1 kept enhancement data only for scenes with a plume.
Version 2 keeps every scene, plume or not, and those no-plume scenes are the denominator
of the pass table. The code refuses any granule that is not version 002.

**Counts (pulled 2026-10-17):** 309 scenes in the nine-county box (156 in the pilot box),
from 2022-08-10 to 2026-08-21, and 7 plume complexes. Only the 2024-08-07 complex
(`emit-3416`) lies at a pilot site (Newby Island); the others are 8 to 77 km from the
nearest pilot site.

**Outage.** EMIT was paused from 2022-09-13 to 2023-01-06 by a power issue outside the
instrument. No scene falls in that gap (`in_outage` is false for every row). The model
must read the gap as "no data", not "no leak".

**Not here yet (needs a NASA Earthdata login in `~/.netrc`):**
- Plume-complex details from each complex's metadata file: emission rate and uncertainty
  (N/A when the plume fails the product's criteria), point of maximum enhancement.
- Enhancement, uncertainty and sensitivity image windows (60 m, ppm m) around each pilot
  site, for every scene that covers it.

**Skipped on purpose:** radiance (L1B) files. They are very large and nothing in the
pipeline uses them.

**Query:** CMR through `earthaccess.search_data`, short names above, version `002`,
dates 2022-08-10 to 2026-10-17, boxes in [`../README.md`](../README.md). Metadata needs no
login.

**Terms and credit:** NASA open data. Cite the products by DOI:
10.5067/EMIT/EMITL2BCH4ENH.002 and 10.5067/EMIT/EMITL2BCH4PLM.002 (wording to confirm in
`DATA_TERMS.md`).
