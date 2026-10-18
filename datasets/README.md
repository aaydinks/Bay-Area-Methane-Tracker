# Datasets

The source data this project uses, one folder per source. Each folder has a README
saying where the data came from, what query produced it, what is in each file, and the
terms and credit line. Each folder's `pulls/` holds the manifest of every download it was
built from: the endpoint, the query, the time, and a sha256 hash of each raw file.

| Folder | Source | What is here | Committed? |
|---|---|---|---|
| [`emit/`](emit/) | NASA EMIT, LP DAAC, version 002 | Scene outlines (every EMIT look, plume or not) and plume-complex outlines | Yes |
| [`carbonmapper/`](carbonmapper/) | Carbon Mapper data API | Plume list (solid waste and all sectors) and scene outlines with detection limits | **No.** Only the README and manifests. The data are non-commercial and not for redistribution |
| [`sentinel2/`](sentinel2/) | ESA Copernicus Sentinel-2 Level-1C | Scene list, and small band crops around the pilot sites on plume days and reference days | Yes |
| [`census/`](census/) | US Census 2020 blocks (TIGER/Line) | Block population for the nine Bay Area counties, block outlines near the pilot sites | Yes |
| [`ghgrp/`](ghgrp/) | US EPA Greenhouse Gas Reporting Program | Operator-reported emissions for the crosswalked sites, Bay Area landfill list | Yes |
| [`calrecycle/`](calrecycle/) | CalRecycle Solid Waste Information System | Reference points for the pilot sites; screening list of 36 Bay Area landfills | Yes |

## How it is built

Downloads land in `data/raw/` (git-ignored, the local cache). `mw datasets build` then
writes the tidy tables here from those downloads. To refresh:

```bash
uv run mw ingest emit --start 2022-08-10 --bbox=-123.64,36.89,-121.20,38.87
uv run mw ingest carbonmapper --bbox=-123.64,36.89,-121.20,38.87
uv run mw s2 search --start 2022-08-10 --end 2026-10-17 --bbox=-122.8,37.3,-121.8,38.4
uv run mw ingest ghgrp --year 2023
uv run mw datasets build
uv run mw datasets build --only sentinel2-crops
```

The census block file is downloaded by hand once (see [`census/README.md`](census/README.md)).

## Areas and dates

- **Nine-county box** (`-123.64, 36.89, -121.20, 38.87`, the extent of Alameda, Contra
  Costa, Marin, Napa, San Francisco, San Mateo, Santa Clara, Solano and Sonoma counties
  from Census TIGERweb). Used for catalogs: EMIT, Carbon Mapper and census.
- **Pilot box** (`-122.8, 37.3, -121.8, 38.4`), around the five pilot sites. Used for
  Sentinel-2 scenes.
- **Dates:** 2022-08-10 (EMIT's first methane scenes) to 2026-10-17.

## Limits

- Site boundaries do not exist yet. Anything here that is "near a site" uses the
  CalRecycle reference point and a search radius, not an outline. That is a search
  step, not attribution.
- Nothing here is a finding. These are inputs to a retrospective screening analysis.
