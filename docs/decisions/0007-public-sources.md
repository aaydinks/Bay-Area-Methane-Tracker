# 0007: Public data sources that need no login

- **Status:** accepted
- **Date:** 2026-10-03

## Context

Week 1 called for checking each source before code depends on it (PLAN
section 11). These were checked live on 2026-10-03. Small recorded responses
live in `tests/fixtures/`, so CI never touches the network.

## Findings and decisions

### NASA EMIT (LP DAAC, CMR via `earthaccess`)

| Collection | Version | What it gives | Login needed |
|---|---|---|---|
| `EMITL2BCH4ENH` | 002 | Per-scene methane enhancement; granule footprint polygon, time, scene `CloudCover` (%) | No for metadata; yes for the GeoTIFFs |
| `EMITL2BCH4PLM` | 002 | Reviewed plume complexes; outline, time, `PLUME_ID`, `SOURCE_SCENES` | No for metadata; yes for `CH4PLMMETA` JSON |

- **EMIT is the denominator source that works today.** Footprints come from
  `EMITL2BCH4ENH` metadata. A search box around Newby Island returned 36 scenes
  (Aug 2022 – Aug 2026); the pilot area returned 156.
- **Not every catalog hit covers a site.** CMR returns every scene that touches
  the search box, and one fixture scene misses the site box entirely. Coverage
  is scored per site polygon in `coverage build`.
- `valid_frac` uses the scene-level cloud percentage for now. That is a scene
  average, not the cloud share over a site. Replace it with the per-pixel mask
  once Earthdata access exists.
- Plume-complex outlines are stored in `interim/emit_plume_outlines.parquet`
  but kept out of `interim/plumes/`. Their rates are in the login-only metadata
  file, and a detection without a rate cannot enter the likelihood.
- The pilot area has 4 plume complexes: 2023-08-18, 2023-08-22, 2024-08-03 and
  2024-08-07. The last one is centred near Newby Island. Attribution waits for
  the site polygons.
- The code refuses any granule whose collection version is not 002.

### Sentinel-2 (Earth Search STAC, `sentinel-2-l1c`)

- Scene search and footprints need no login. 2025 over the pilot area gave 550
  scenes.
- **The L1C band files on AWS are in a requester-pays bucket.** Pixels must
  come from Copernicus Data Space (free account) or from the public L2A COGs.
  This is decided in ADR 0004, after reading the open pipeline.
- `valid_frac` uses tile-level `eo:cloud_cover` until the cloud mask is applied
  during retrieval.

### EPA GHGRP (Envirofacts REST, no key)

- Tables: `pub_dim_facility` (facilities, `reported_subparts`, county) and
  `pub_facts_subp_ghg_emission` (facility, year, `sub_part_id`, `gas_id`,
  `co2e_emission`).
- IDs: subpart HH (municipal landfills) = 31, CH4 = 2.
- 17 Bay Area facilities reported subpart HH in 2023.
- Crosswalk (`data/registry/operator_crosswalk.csv`):

  | Site | GHGRP facility | Subpart HH CH4 years |
  |---|---|---|
  | Newby Island | 1006179 | 2010–2023 |
  | Sonoma Central | 1004123 | 2010–2023 |
  | Potrero Hills | 1007345 | 2010–2023 |
  | Shoreline | 1005910 | 2010–2018 |
  | Acme Fill | none found | — |

- Emissions are published in t CO2e. Tonnes of CH4 use the GWP configured per
  reporting year in `config/impact.yaml: ghgrp_gwp_ch4`: 25 for 2010–2023,
  **unconfirmed**. Years without a configured GWP are left out rather than
  converted with a guess.

## Consequences

- Gate 1 can run for the EMIT and Sentinel-2 denominators as soon as the pilot
  polygons exist.
- EMIT rates and per-site cloud fractions need Earthdata credentials in
  `~/.netrc`.
- Carbon Mapper (Tanager-1, aircraft) is still blocked on API access (ADR 0001).
