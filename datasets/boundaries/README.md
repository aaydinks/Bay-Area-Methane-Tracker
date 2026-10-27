# Boundaries: counties and the Bay Area air district

Outlines for maps and for describing where a site sits. Nothing here is a model input.

| File | Source | Contents |
|---|---|---|
| `counties_2025.geojson` | US Census 2025 cartographic boundaries, 1:500,000 | The nine Bay Area counties: `GEOID`, `COUNTYFP`, `NAME`, outline. Simplified (108 KB) |
| `air_district_bay_area.geojson` | CARB air districts, `DIS='BA'` | The Bay Area air district outline **as of March 2004; check against current BAAQMD**: `NAME`, `DIS`, `boundary_as_of`, `caveat`, outline. Not simplified (629 KB) |
| `pulls/` | | Manifest of the download these were built from: every URL, the time, and a sha256 hash of each file |

Both files are EPSG:4326, coordinates rounded to 6 decimals (about 0.1 m).

## Vintage and processing

- **Counties.** Census 2025 cartographic boundary file `cb_2025_us_county_500k.zip`.
  These outlines are clipped to the shoreline, so the bay itself is not inside any county.
  Simplified with a 100 m tolerance in UTM zone 10N, keeping shared county edges shared
  (no gaps or overlaps). The simplified outline is within 115 m of the full one.
- **Air district.** CARB's layer `CaAirDistrict_PublicWeb`, queried with `DIS='BA'`. CARB's
  metadata says the layer shows "the air district boundaries and their names as of March
  2004". The outline is kept at full detail because a later step tests which landfills
  fall inside it, and some are close to its edge. Every copy of it carries
  `caveat = "check against current BAAQMD"`.

## What the outline shows

Share of each county's land inside the 2004 district outline, from these two files at
full detail:

| County | Share inside |
|---|---|
| Alameda | 99.3% |
| Contra Costa | 97.1% |
| Marin | 96.6% |
| Napa | 99.7% |
| San Francisco | 98.1% |
| San Mateo | 99.4% |
| Santa Clara | 99.7% |
| Solano | 39.8% |
| Sonoma | 38.6% |

Solano and Sonoma are split between districts. For the other seven, the 0.3 to 3.4% outside
is where the 2004 outline and the 2025 county outlines disagree: along shorelines, inlets
(Tomales Bay alone is 29 km² of Marin's 48 km²) and county lines (most of Contra Costa's
58 km² is on its Delta edge). So a site within a few hundred metres of the edge needs a
manual check.

Of the 36 landfills in the CalRecycle screening list, 32 are inside the 2004 outline. The
four outside are in Solano and Sonoma; one of them, Recology Hay Road, is 0.4 km from the
edge. All five pilot sites are inside, at least 2 km from the edge. These are reference
points, not site outlines, and the outline is from 2004: check against current BAAQMD.

## Raw only

`mw ingest boundaries` also downloads these, which stay in `data/raw/boundaries/<pull_id>/`
because they are too big to commit:

- Census 2025 California places, `cb_2025_06_place_500k.zip` (1.4 MB)
- TIGER/Line 2025 California tracts, `tl_2025_06_tract.zip` (33 MB)
- TIGER/Line 2025 California primary and secondary roads, `tl_2025_06_prisecroads.zip` (13 MB)
- TIGER/Line 2025 area water for each of the nine counties, `tl_2025_06<FIPS>_areawater.zip`
  (0.1 to 1.1 MB each)

To rebuild:

```bash
cd ~/code/Bay-Area-Methane-Tracker && uv run mw ingest boundaries
```

```bash
cd ~/code/Bay-Area-Methane-Tracker && uv run mw datasets build --only boundaries
```

## Sources, terms and credit

- Census files: `https://www2.census.gov/geo/tiger/GENZ2025/shp/` and
  `https://www2.census.gov/geo/tiger/TIGER2025/`. US government public data.
  Credit: "US Census Bureau, 2025 Cartographic Boundary Files and 2025 TIGER/Line Shapefiles."
- CARB layer: `https://gis.carb.arb.ca.gov/hosting/rest/services/California_Air_Resources_Board_Air_Districts_MIL1/MapServer/0`,
  metadata at `.../MapServer/info/metadata`. The service publishes no terms of use
  (check). Credit, following CARB's metadata: "California Air Resources Board, air
  district boundaries as of March 2004 (originally developed by Teale Data Center GIS
  Lab)."

All URLs were checked live on 2026-10-27.
