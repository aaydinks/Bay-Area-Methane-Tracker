# US Census 2020 blocks

| File | Contents |
|---|---|
| `blocks_2020_population.csv` | All 82,210 census blocks in the nine Bay Area counties: `GEOID20`, county, tract, block, `POP20` (2020 total population), `HOUSING20`, land and water area (m²), internal point, urban/rural code |
| `blocks_2020_within_6km_of_pilots.parquet` | Outlines (GeoParquet, EPSG:4326) of the 4,494 blocks within 6 km of a pilot site's reference point, with `POP20` and `HOUSING20` |

Counties: Alameda 001, Contra Costa 013, Marin 041, Napa 055, San Francisco 075,
San Mateo 081, Santa Clara 085, Solano 095, Sonoma 097. The pilot sites are in Santa
Clara (Newby Island, Shoreline), Contra Costa (Acme Fill), Sonoma (Sonoma Central) and
Solano (Potrero Hills).

**Source.** TIGER/Line 2020 blocks for California, `tl_2020_06_tabblock20.zip`
(382 MB, kept in `data/raw/census/`, not committed), from
`https://www2.census.gov/geo/tiger/TIGER2020/TABBLOCK20/`. The file already carries
`POP20`, the 2020 Census count (the same figure as `P1_001N` in the redistricting file).
So no Census API key was needed. The nine-county total is 7,765,640.

To rebuild:

```bash
cd ~/code/Bay-Area-Methane-Tracker && mkdir -p data/raw/census/tiger2020-tabblock20 && curl -L -o data/raw/census/tiger2020-tabblock20/tl_2020_06_tabblock20.zip https://www2.census.gov/geo/tiger/TIGER2020/TABBLOCK20/tl_2020_06_tabblock20.zip
```

```bash
cd ~/code/Bay-Area-Methane-Tracker && uv run mw datasets build --only census
```

**Use with care.** Block counts have noise added on purpose to protect privacy, so single
blocks can look odd. Sum over circles (1 km and 3 km around each site outline), not
single blocks. The 6 km cut leaves room for those circles once outlines replace the
reference points.

**Not decided yet.** The current code (`mw population build`) uses ACS 5-year block
groups with area weighting. Switching to 2020 blocks is a method change for a short ADR,
not something this data pull decides.

**Terms and credit:** US government public data. "US Census Bureau, 2020 Census,
TIGER/Line Shapefiles."
