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

**Files behind the Earthdata login (pulled 2026-10-18):**

| File | Contents |
|---|---|
| `plume_metadata/<granule>.json` | NASA's metadata for each of the 7 plume complexes: maximum enhancement (ppm m) and where it is, wind speed and source, emission rate and uncertainty (kg/hr), fetch length, source scenes |
| `windows/<site_id>/<scene_id>.tif` | 6 km x 6 km window around each pilot site's reference point, 60 m, three bands: enhancement (ppm m), uncertainty (ppm m), sensitivity. One per EMIT scene touching the window: 169 in all, 118 of them covering the whole window |
| `windows/index.csv` | Site, scene, time, whether the scene covers the whole window, file |

Only 1 of the 7 complexes has a rate: 2023-08-18, about 2,800 ± 290 kg/hr, 8.7 km from
Potrero Hills, so it is not at a pilot site. The other six, including the 2024-08-07
complex at Newby Island (maximum 5,899 ppm m), have no rate because they fail the
product's criteria. A bright pixel in a window is not a plume; single-pixel highs occur
in many windows with no reviewed plume.

Access: set `EARTHDATA_TOKEN` in `.env` (or put the login in `~/.netrc`), then run
`uv run mw datasets build --only emit-files`. The token resolves LP DAAC's redirect to a
short-lived signed link that GDAL reads in windows; neither is written to disk.

**Skipped on purpose:** radiance (L1B) files. They are very large and nothing in the
pipeline uses them.

**Query:** CMR through `earthaccess.search_data`, short names above, version `002`,
dates 2022-08-10 to 2026-10-17, boxes in [`../README.md`](../README.md). Metadata needs no
login.

**Terms and credit:** NASA open data. Cite the products by DOI:
10.5067/EMIT/EMITL2BCH4ENH.002 and 10.5067/EMIT/EMITL2BCH4PLM.002 (wording to confirm in
`DATA_TERMS.md`).
