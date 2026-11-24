# Bay Area Landfill Methane Watch: Coding Plan

Companion to *Bay Area Landfill Methane Watch: Project Plan* (Oct 3, 2026). That document says **what** to build and **why**. This one says **how**: repo layout, data schemas, module specs, the statistical model in implementable form, the validation suite as code, and a week-by-week build order tied to the project plan's gates.

Budget: about 100–120 hours over 12 weeks at 8–10 hours a week. Every choice below is sized to that budget. The project has one Python package, flat files, one Makefile, and a static dashboard. There are no services, databases to run, or orchestration frameworks.

**Amended November 2026 (PR 68).** The project now covers two regions and more than the methane estimate. §16 says what changed and in what order it is built; where §16 and an earlier section disagree, §16 wins. The decisions are in ADRs 0018 to 0021.

---

## 0. Ground rules that shape the code

1. **Never read a non-detection as zero.** The model needs every overpass, including those where nothing was seen. The `overpasses` table therefore matters as much as the `plumes` table (see §4.2 and the week-1 spike in §11).
2. **Every published number carries an interval.** No function in `report/` accepts a point estimate without bounds.
3. **"Insufficient data" and "inconclusive" are first-class outputs**, not errors. The rules are in config, not ad hoc.
4. **Gates are tests.** Each phase gate from the project plan is a `mw validate …` command that exits non-zero on failure and writes a report to `reports/validation/`.
5. **Provenance on every pull.** Each raw download writes a manifest row (source, endpoint, params, time, record count, sha256, code version).
6. **Disputed constants live in config, never in code.** This covers GWP factors, $/t, POD curves, buffers, and floors. Each one has a `source` and a `confirmed: bool` field.
7. **Wording guardrails are enforced in code.** Report templates say "screening indication" and "retrospective tracker", and a test fails if generated text contains "saved", "real-time", "violation" or "non-compliant" (§9.4).

---

## 1. Tech stack

| Concern | Choice | Why |
|---|---|---|
| Language / env | Python 3.12, `uv` with a lockfile | Fast, reproducible installs |
| Tables | pandas + **GeoParquet** files, queried with **DuckDB** (in-process) | No server; SQL over Parquet when convenient |
| Schema checks | `pandera` | Catches bad joins and units at write time |
| Geo | geopandas, shapely, pyproj | Polygons, buffers, distances (in EPSG:32610, UTM 10N) |
| Rasters | rasterio, rioxarray, xarray | Sentinel-2 bands, EMIT enhancement maps |
| Catalog search | `pystac-client`, `earthaccess` | Sentinel-2 STAC, NASA EMIT via CMR |
| HTTP | `httpx` + `tenacity` (retry/backoff) + an on-disk cache | Polite API pulls, resumable |
| Wind | `herbie` (HRRR) and/or `cdsapi` (ERA5) | Behind one interface; decided in week 3 |
| Model | **PyMC** + ArviZ (nutpie sampler if installed) | Hierarchical Bayes; grid-marginalized likelihood |
| CLI | `typer` | `mw <group> <command>` |
| Config | YAML + `pydantic` models | Typed, validated config with citations |
| Tests / lint | pytest, hypothesis (a few property tests), ruff, pre-commit | |
| Dashboard | Jinja2 templates + Vega-Lite (via altair) → static HTML on GitHub Pages | No backend; per-site pages |
| Write-up | Quarto or plain Markdown → PDF | Technical note + 2-page briefing |
| Pipeline | `Makefile` targets that call the CLI; one end-to-end notebook that calls the same functions | Re-runnable without a workflow engine |

---

## 2. Repository layout

```
methane-watch/
├── README.md                  # purpose, non-commercial use, data terms, how to rerun
├── LICENSE                    # code license (MIT or Apache-2.0); data terms are separate
├── DATA_TERMS.md              # Carbon Mapper non-commercial terms, EMIT/ESA/EPA terms, credit lines
├── pyproject.toml / uv.lock
├── Makefile
├── .env.example               # CARBON_MAPPER_API_KEY=, CDSE_USER=, ... (real .env is git-ignored)
├── config/
│   ├── project.yaml           # paths, CRS, buffers, windows, thresholds
│   ├── instruments.yaml       # POD curves, measurement error, provenance per instrument
│   ├── impact.yaml            # GWP20, GWP100, $/t, radius for population context
│   └── model.yaml             # priors, grid, sampler settings, "insufficient data" rules
├── data/                      # git-ignored except data/registry/
│   ├── registry/              # sites.geojson, repairs.csv, operator_crosswalk.csv (hand-curated, committed)
│   ├── raw/<source>/<pull_id>/  # immutable downloads + manifest.json
│   ├── interim/               # normalized Parquet
│   └── processed/             # model inputs/outputs
├── src/methanewatch/
│   ├── config.py              # pydantic models, loader
│   ├── provenance.py          # pull manifests, hashing, run manifests
│   ├── schemas.py             # pandera schemas for every table in §4
│   ├── sites/                 # registry build, polygon QA, OSM/LMOP screening polygons
│   ├── ingest/
│   │   ├── carbonmapper.py
│   │   ├── emit.py
│   │   ├── ghgrp.py
│   │   └── airdistrict.py     # parses hand-entered repair/enforcement records
│   ├── coverage/              # builds the overpasses table (the denominator)
│   ├── attribution.py         # plume → site assignment, ambiguity flags
│   ├── sentinel2/
│   │   ├── search.py          # scene search, cloud filter
│   │   ├── retrieval.py       # MBMP fractional absorption → ΔXCH4
│   │   ├── masks.py           # low-reflectance, shadow, water masks
│   │   └── detect.py          # plume segmentation, origin finding
│   ├── wind/                  # WindProvider protocol + HRRR/ERA5 implementations
│   ├── quantify.py            # IME, U_eff, rate + Monte Carlo uncertainty
│   ├── model/
│   │   ├── pod.py             # detection-probability curves
│   │   ├── grid.py            # log-rate quadrature grid and helpers
│   │   ├── persistence.py     # PyMC hierarchical model (§6)
│   │   ├── simulate.py        # synthetic sites/overpasses with known truth
│   │   └── summarize.py       # posteriors → site_estimates table
│   ├── repair/
│   │   ├── model.py           # before/after with control sites (§7)
│   │   └── placebo.py
│   ├── validate/              # the five tests (§8) + gate checks
│   ├── impact.py              # CH4 avoided, CO2e, $, population context (§9)
│   ├── report/                # dashboard builder, templates, wording lint
│   └── cli.py                 # typer app: `mw ...`
├── notebooks/
│   ├── 00_end_to_end.ipynb    # reruns everything via package functions
│   └── scratch/               # exploration; not part of the pipeline
├── tests/                     # unit + small integration tests (fast; run in CI)
├── reports/
│   ├── validation/            # gate reports (Markdown + figures), committed
│   └── site/                  # built dashboard (published via GitHub Pages)
└── docs/
    ├── decisions/             # short ADRs: 0001-storage, 0002-wind-product, 0003-pod-curves, ...
    ├── technical-note/
    └── briefing/
```

**Data in git:** only `data/registry/` (hand-curated, small) and derived summary tables that the data terms allow. **Do not commit raw Carbon Mapper data.** Check whether the terms allow redistributing derived tables before publishing them (record the answer in `DATA_TERMS.md`).

---

## 3. Configuration

`config/instruments.yaml` (illustrative shape; **values are placeholders until sourced**):

```yaml
instruments:
  sentinel2:
    pod:                       # probit in log-rate: POD(q) = Φ((ln q − ln q50) / w)
      q50_kg_hr: null          # fit from the ML study's curve; plan cites ~90% POD at 2,200–2,500 kg/hr
      w: null
      source: "<ML detection study, see project plan Validation section>"
      confirmed: false
    meas_sigma_log: 0.4        # log-scale rate error; controlled release: 75% within ±50%
  tanager1:   { pod: {q50_kg_hr: null, w: null, source: null, confirmed: false}, meas_sigma_log: null }
  emit:       { pod: {...}, meas_sigma_log: null }
  aircraft:   { pod: {...}, meas_sigma_log: null }   # AVIRIS-NG / GAO
```

Rules:
- The persistence model refuses to run on real data while any POD entry it uses has `confirmed: false`, unless `--allow-unconfirmed` is passed. That flag stamps every output "PROVISIONAL".
- Every config value used in a published number is echoed into the run manifest.

`config/impact.yaml`:

```yaml
gwp20: {value: 84, source: "<link in project plan>", confirmed: false}
gwp100: {value: 25, source: "derived: 427,000 t CO2e / 17,000 t CH4 (two outlets)", confirmed: false,
         note: "25 matches the IPCC AR4 value; check which AR the CARB rule uses"}
usd_per_t_co2e: {value: 80, source: "derived: $34M/yr / 427,000 t CO2e", confirmed: false}
population_radius_km: [1, 3, 5]
```

`config/project.yaml` holds the attribution buffer (start at 500 m), search radius (5 km), repair windows, and the "insufficient data" thresholds (§6.6).

---

## 4. Data model

Every table has a pandera schema in `schemas.py` and is written as Parquet (GeoParquet when it has geometry). Times are UTC `timestamp[us, tz=UTC]`. Rates are kg/hr. Annual totals are t/yr.

### 4.1 `sites` (from `data/registry/sites.geojson`)

| column | type | notes |
|---|---|---|
| site_id | str | slug, e.g. `newby-island` |
| name, city, county, operator | str | |
| tier | enum | `pilot` (5) / `screen` (every other listed landfill in the two regions; see §16.2) |
| region | enum | `bay-area` / `north-valley` (§16.1) |
| air_district | str? | from an overlay of CARB's district outlines; unconfirmed until checked |
| swis_number | str? | CalRecycle's site number |
| status | enum | `active` / `closed` / `mixed` |
| district_facility_id | str? | from permits (was `baaqmd_facility_id`) |
| ghgrp_facility_id | str? | via `operator_crosswalk.csv` |
| geometry | MultiPolygon | full permitted footprint |
| working_face_geom, closed_geom | MultiPolygon? | pilot sites only |
| polygon_source | str | `manual-imagery`, `permit-map`, `osm`, `buffer` |
| neighbors | list[str] | known co-located sources (compost, WWTP, energy plant) |
| notes | str | |

### 4.2 `overpasses`: the denominator

One row per (site, instrument, observation day), not per scene. Same-day repeat passes from one instrument collapse to one row so that repeat passes are not counted as independent evidence.

| column | type | notes |
|---|---|---|
| overpass_id | str | `{site}:{instrument}:{date}` |
| site_id, instrument | str | |
| acquired_utc | timestamp | first acquisition that day |
| scene_ids | list[str] | |
| coverage_frac | float | fraction of site polygon inside the footprint |
| valid_frac | float | fraction cloud-free / unmasked. Sentinel-2: Sen2Cor's clear share over the central 5.08 km around the site (ADR 0014), else the tile figure |
| valid_frac_tile | float | Sentinel-2 only: the tile-level figure (`1 − eo:cloud_cover/100`), kept for comparison |
| valid_frac_source | enum | `site-sen2cor`, `tile` (Sentinel-2 pass with no Sen2Cor share), `scene` (other instruments) |
| usable | bool | `coverage_frac ≥ 0.8 and valid_frac ≥ 0.7` (config) |
| coverage_source | enum | `stac-footprint`, `cmr-granule`, `s2-scene`, `inferred` |

### 4.3 `plumes`

| column | type | notes |
|---|---|---|
| plume_id | str | source ID, never re-minted |
| source | enum | `carbonmapper`, `emit-v2`, `s2-local` |
| instrument | str | |
| acquired_utc | timestamp | |
| origin_lon, origin_lat | float | |
| plume_geom | Polygon? | |
| q_kg_hr, q_sigma_kg_hr | float | as reported |
| wind_speed_ms, wind_source | float, str | as reported |
| data_version | str | e.g. EMIT v2 only; v1 is decommissioned |
| site_id | str? | after attribution |
| attribution | enum | `inside`, `buffer`, `ambiguous`, `nearby`, `none` |
| distance_m | float | origin to polygon edge (0 if inside); published only for a plume tied to a site |
| pull_id | str | → provenance |

### 4.4 `detections` (model input, built by joining 4.2 + 4.3)

`overpass_id, site_id, instrument, detected: bool, q_obs_kg_hr?, q_sigma_log?, n_plumes, n_scenes`. Several attributed plumes in one scene are summed (separate sources seen at once), and a flag is set for them. Aircraft fly several lines over a site in one day and see the same sources each time, so the per-scene totals of one day are averaged, not summed.

### 4.5 `s2_retrievals`

`scene_id, ref_scene_id, site_id, date, valid_frac, masked_frac, detected, ime_kg, plume_len_m, u10_ms, ueff_ms, q_kg_hr, q_lo, q_hi, flags[]`. Enhancement rasters go to `data/interim/s2/<site>/<date>.tif`.

### 4.6 `wind`

`site_id, time_utc, u10, v10, speed, product, product_version`.

### 4.7 `repairs` (hand-entered: `data/registry/repairs.csv`)

`repair_id, site_id, date_start, date_end, kind (well-field|cover|leak-repair|other), description, source_doc, source_page, date_confidence (exact|week|month), entered_on`. **No row without a source document.**

### 4.8 `operator_reports`

`site_id, year, source (GHGRP|CARB-MRR), reported_ch4_t, method_note, facility_id, url, pull_id`.

### 4.9 `site_estimates` (model output)

`site_id, period, run_id, n_overpasses{by instrument}, n_detections, f_med/f_lo/f_hi, qbar_med/lo/hi, E_t_yr_med/lo/hi, status (estimate|insufficient_data|provisional), rhat_max, ess_bulk_min, divergences`.

### 4.10 `provenance` (`data/raw/**/manifest.json` → `provenance.parquet`)

`pull_id, source, endpoint, params_json, started_at, finished_at, n_records, sha256, file_paths, git_sha`.

### 4.11 `site_metrics` and its catalogue (§16.3, ADR 0019)

`site_id, metric_id, period, source, value, value_text, unit, kind (reported|observed|context), confirmed, source_id, url, pull_id`. One row per site, measure, period and source. Each ingest step writes its own file under `data/interim/site_metrics/`.

- **The catalogue is `config/metrics.yaml`:** `metric_id → label, unit, kind, source, caveat`. It is published with each copy as `metric_catalogue`. A row whose measure is not in the catalogue, or whose unit, kind or source differs from it, stops `mw publish build`.
- **Figures stay in the unit the source publishes.** EPA's gases are in t CO2e and are not converted.
- **A missing row means not reported, never zero.**

---

## 5. Module specs by build phase

### Phase 1: Site registry (`sites/`)

- **Pilot (5):** Newby Island, Acme Fill, Sonoma Central, Shoreline, Potrero Hills. Draw polygons by hand (QGIS or geojson.io) over recent imagery, cross-checked against permit maps. Tag the working face and closed cells.
- **Screen (~38):** get the list from the Air District (Rule 8-34 landfills). Use EPA LMOP coordinates where they help. Pull `landuse=landfill` polygons from OpenStreetMap, and fall back to a 750 m buffer around the point (`polygon_source=buffer`).
- `mw sites build` validates the result. It checks that polygons are valid, that each falls in the 9 Bay Area counties, and that polygons don't overlap. It then writes `interim/sites.parquet` and a QA map (`reports/validation/sites_map.html`).
- Record known neighbors, which matters most at Newby Island (compost facility, energy facility, wastewater plant).
- *Amended November 2026:* the screening tier was never loaded from an Air District list. It is now built from CalRecycle's list for both regions, with outlines from CalRecycle's boundary layer where one exists, and the region check replaces the nine-county check (§16.1, §16.2).

### Phase 2: Ingest and the overpass table

**2a. Carbon Mapper (`ingest/carbonmapper.py`)**
- Read the Carbon Mapper product guide and API docs. **Do not guess endpoints.** Record in `docs/decisions/0001-carbonmapper-api.md`:
  1. how to query plumes by bbox and date,
  2. the fields for rate and uncertainty,
  3. whether scene or acquisition footprints are exposed, which decides the denominator,
  4. rate limits and terms.
- Pull every plume within 5 km of each site polygon. The raw JSON goes to `raw/carbonmapper/<pull_id>/` with a manifest. Normalize to the `plumes` schema.
- The pull is idempotent and incremental (`--since` the last pull). This lets it re-run monthly as the 30-day lag clears.

**2b. EMIT v2 (`ingest/emit.py`)**
- Use `earthaccess` (Earthdata login via `~/.netrc`). Find the v2 CH4 plume-complex and enhancement collection short names in CMR and record them. **Reject any v1 granule.**
- Granule footprints give EMIT's overpass coverage directly. That makes EMIT the most reliable denominator, even though EMIT plumes are manually reviewed before release.

**2c. Coverage (`coverage/`)**: builds `overpasses`:
- EMIT: CMR granule polygons ∩ site polygons, with the EMIT cloud mask where available.
- Carbon Mapper instruments (Tanager-1, aircraft): from footprints if the API or STAC exposes them. **If not, use the fallback ladder:**
  1. Ask Carbon Mapper for acquisition lists. This is outreach step 5 in the project plan.
  2. Use Tanager/aircraft detections for the rate distribution only (μ, σ). Estimate f from instruments with known coverage (EMIT, Sentinel-2).
  3. As a last resort, infer coverage from plumes at *other* sites on the same scene/day (`coverage_source=inferred`). Flag the result and run a sensitivity check.
- Sentinel-2: every scene from search is an overpass. `valid_frac` is Sen2Cor's clear share over the site (`mw s2 site-clear`, run by `mw refresh`; ADR 0014). The cloud model is not used: it failed its check on recent passes.

**2d. Attribution (`attribution.py`)**
- `inside`: origin within polygon. `buffer`: within polygon + 500 m and no other registry/neighbor polygon is closer. `ambiguous`: within the buffer of two candidates, or a known neighbor is closer. `nearby`: within 5 km but outside the buffer.
- Only `inside` and `buffer` feed the model. `ambiguous` plumes are listed on the dashboard, never assigned to a site.
- A plume on or beside a site that its source tags with a sector other than waste is also `ambiguous` (ADR 0022). A plume with no tag follows the distance rule alone.

**2e. Operator reports (`ingest/ghgrp.py`)**: EPA GHGRP subpart HH (landfills), via the FLIGHT export or the Envirofacts API. The project plan notes the exact steps are unverified, so confirm them in week 8. Map facilities to sites through `operator_crosswalk.csv`.

**2f. Air District records (`ingest/airdistrict.py`)**: there is no scraping here. Repair dates and enforcement events are entered by hand into `repairs.csv` from the order, lawsuit, fine notice, monitoring reports, and any operator logs. A loader validates them.

**Gate 1 (`mw validate gate1`)**: writes a plume table for all 5 pilot sites with counts per instrument per year, plus overpass counts per instrument per year. It **fails** if any pilot site has zero rows in `overpasses` for an instrument that has detections there, because that means the denominator is missing.

### Phase 3: Sentinel-2 retrieval (`sentinel2/`)

1. **Read the open MIT-licensed pipeline first.** The repo link is in the project plan. Note its inputs (L1C vs L2A), its reference-scene logic, and its unit conversions in `docs/decisions/0004-s2-pipeline.md`. Wrap or vendor only what you have read. Keep the license notice.
2. **Search:** STAC search for scenes intersecting each pilot polygon. Use L1C top-of-atmosphere reflectance if the method requires it (Copernicus Data Space Ecosystem; free account).
3. **Multi-band multi-pass (MBMP):** compute the per-scene band ratio `R = (c·B12 − B11)/B11` with `c` fit by regression over the scene. Difference against a clean reference scene from the same relative orbit, then convert fractional absorption to ΔXCH4 using the method's lookup.
4. **Masks (`masks.py`):** low-reflectance threshold on B12, shadow (cloud-shadow and terrain), water (NDWI), bright surfaces. Follow the low-reflectance artifact approach cited in the plan. Masked pixels are excluded from detection, and `masked_frac` is stored.
5. **Detection (`detect.py`):** threshold the enhancement at k·σ of the local background (start at k=2, configurable), take connected components above a minimum pixel count, and use the origin in the component nearest the upwind edge. A detection counts only if its origin is inside polygon + buffer.
6. **Policy:** an S2 detection never supports a site-specific claim by itself. It must coincide with a Carbon Mapper or EMIT plume (§0, risk table).

**Gate 2 (`mw validate gate2`):** reproduce one plume that Carbon Mapper also shows, from an S2 scene within ±1 day, with a rate whose interval overlaps Carbon Mapper's.
**Fallback:** Bay Area landfills may never produce a plume above S2's ~2 t/hr limit on a matching day. If so, reproduce the open pipeline's own published example plume (any site) to prove the retrieval works, and record that no Bay Area match exists. That is itself a finding.

### Phase 4: Wind and quantification (`wind/`, `quantify.py`)

- `WindProvider` protocol: `get(site_id, time_utc) -> (u10, v10, meta)`.
- **Week 3 decision (ADR 0002):** HRRR (3 km, hourly, archived on AWS, accessed via `herbie`) versus ERA5 (≈31 km, hourly). The Bay Area's sea breeze and terrain argue for HRRR, with ERA5 kept as a cross-check. Record the choice, the version, and the bias between the two at the pilot sites.
- **IME method:** `Q = U_eff · IME / L`, where IME is the integrated mass enhancement (kg) over plume pixels, `L = sqrt(plume area)`, and `U_eff = a·U10 + b` from the method's published calibration (cite it in the ADR).
- **Uncertainty:** Monte Carlo (n=1000) over U10 (±1.5 m/s or the product's error), the U_eff coefficients, and background noise in IME. Report the median and the 5th/95th percentiles.
- Unit test: a synthetic Gaussian plume with known Q on a grid, recovered within 10%.

### Phase 5: Persistence model (`model/`). See §6.

### Phase 6: Repair verification (`repair/`). See §7.

### Phase 7: Package (`report/`, notebook)

- `make all` rebuilds everything from raw caches. `notebooks/00_end_to_end.ipynb` calls the same functions and renders the key figures.
- The dashboard is described in §10.

---

## 6. Persistence model: implementable spec

The project plan calls its model structure a proposal to be tested on simulated data first. This section is the concrete version of that proposal. The synthetic test (§8.1) decides whether it holds.

### 6.1 Quantities

- `q_min`: the emission floor (config). Define `f_s` as the fraction of observed hours with emissions ≥ `q_min`. Put `q_min` near the most sensitive instrument's ~10% POD point. Below that, the data say nothing and the prior would be doing the work.
- While emitting, `q ~ LogNormal(μ_s, σ_s)` truncated to `[q_min, q_max]`. The truncated density is `g_s(q)`.
- `Q̄_s = E[q | q ≥ q_min]`, computed on the grid (§6.3). The closed form `exp(μ+σ²/2) · Φ((μ+σ²−ln q_min)/σ) / Φ((μ−ln q_min)/σ)` (ignoring `q_max`) is a unit-test check.
- `E_s = f_s · Q̄_s · 8760 / 1000` in t/yr.
- **Interpretation, stated in every output:** E_s is the annualized emission from events above `q_min` during observable (daytime, clear-sky) conditions. It is not the site's total emissions. Diffuse emissions below the floor are invisible to these instruments.

### 6.2 Likelihood per usable overpass i at site s with instrument j

- Detection probability curve: `POD_j(q) = Φ((ln q − ln q50_j) / w_j)`, from config.
- Probability of a detection: `p_sj = f_s · ∫ POD_j(q) g_s(q) dq`
- **Non-detection:** `log(1 − p_sj)`
- **Detection with measured rate `q_obs` and log-scale error `τ_i`:**
  `log f_s + log ∫ POD_j(q) · g_s(q) · LogNormal(q_obs | ln q, τ_i) dq`
  Here `τ_i` is taken from the reported uncertainty when it exists, or from the instrument default in config. This is the "weighted by detectability" form, not a hard truncation.
- **Optional (v2):** make POD depend on wind, POD_j(q/u). Do it only if the synthetic tests show it matters.

### 6.3 Numerical integration on a log-rate grid (`model/grid.py`)

- K = 96 points uniform in `x = ln q` over `[ln q_min, ln q_max]` with `q_max` = 20,000 kg/hr, using trapezoid weights in x.
- **Integrate in log space so no Jacobian is needed.** Define `h_s(x)` as a Normal(μ_s, σ_s) density in x, truncated to the grid range and normalized on the grid so that Σ w_k h_s(x_k) = 1. Every integral `∫ … g_s(q) dq` becomes `Σ_k w_k · … · h_s(x_k)`. For example, `Q̄_s = Σ_k w_k e^{x_k} h_s(x_k)`.
- Precompute constants: `POD[j, k]` (instruments × grid) and the measurement kernel `M[i, k] = LogNormal(q_obs_i | x_k, τ_i)` for detections.
- `h_s(x_k)` is a PyTensor expression of (μ_s, σ_s). All integrals become matrix products followed by a log-sum-exp. This keeps the model fast enough to fit hundreds of synthetic datasets.

### 6.4 Hierarchy and priors (`model/persistence.py`)

Non-centered parameterization throughout:

```
logit f_s = α_f + τ_f · z_f[s]            α_f ~ N(-1, 1.5),   τ_f ~ HalfNormal(1)
μ_s       = α_μ + τ_μ · z_μ[s]            α_μ ~ N(ln 300, 1), τ_μ ~ HalfNormal(0.75)
σ_s       = σ  (shared to start)          σ   ~ HalfNormal(1)
z_f, z_μ ~ N(0, 1)
```

The numbers are starting points. Run a **prior predictive check** first. Implied annual totals should span plausible landfill magnitudes (from a few t/yr to tens of thousands of t/yr) without piling up at the extremes. Record the final priors in ADR 0005.

Sampler: 4 chains × 1000 draws after 1000 tuning steps, `target_accept=0.95` (0.9 until the first real-data fit diverged at it; summary 0047). A fit **fails the diagnostics** if `r̂ > 1.01`, bulk ESS < 400, or there are any divergences. A failed fit is not reported.

### 6.5 Known modeling caveats (each gets a check)

| Caveat | Check |
|---|---|
| Daytime / clear-sky sampling bias | Report f as "observable-hours" fraction. Sensitivity run with a diurnal multiplier in simulation |
| Persistence → autocorrelated overpasses | Same-day collapse (§4.2). Simulation with Markov on/off emitters to measure interval under-coverage |
| Manual review: some real plumes never released | Sensitivity run with a release probability r_j ∈ {0.7, 0.85, 1.0} multiplying POD |
| POD curve uncertainty | Rerun with q50 × {0.5, 1, 2}. Report rank stability |
| Neighbor contamination | Only `inside`/`buffer` plumes. Count `ambiguous` per site on the dashboard |
| Passes nobody searched counted as "saw nothing" | An instrument enters a real fit only once a plume table from one of its sources exists (ADR 0016); the run manifest and site pages name any instrument left out |

### 6.6 "Insufficient data" rule (config)

A site is reported as `insufficient_data` instead of a number when any of these holds:
- it has fewer than 8 usable overpasses in the period,
- the 90% interval for E_s spans more than 2 orders of magnitude,
- it failed the diagnostics.

Thresholds are tunable once the synthetic tests show what is achievable.

---

## 7. Repair verification: implementable spec

The repair date is **known**, so this is a before/after comparison with controls, not a search for an unknown change point. An unknown-change-point model is an optional extra for exploratory plots only.

- **Windows:** `before = [t_r − W, t_start)` and `after = (t_end + gap, t_r + W]`, with W = 12 months and gap = 14 days by default. Overpasses during the repair itself are excluded.
- **Model:** the persistence model with a site × period structure:
  ```
  logit f_{s,after} = logit f_{s,before} + γ_f + δ_f[s]·treated_s
  μ_{s,after}       = μ_{s,before}       + γ_μ + δ_μ[s]·treated_s
  ```
  The common shifts `γ` are estimated from **control sites**: other landfills seen by the same instruments over the same windows. They absorb instrument changes, such as Tanager-1 coming online, and seasonal effects.
- **Effect reported:** the posterior of `log(E_after/E_before)` net of controls, with its median, 90% interval, and probability of a decrease. Also convert to t/yr for impact accounting.
- **Call rule:** "drop" if P(effect < 0) ≥ 0.975, "rise" if P(effect < 0) ≤ 0.025, and **"inconclusive" otherwise**. This is a two-sided 95% test with a nominal false-positive rate of 5%. The effect is still reported with its 90% interval. An earlier rule called a result whenever the 90% interval excluded 0, which has a nominal false-positive rate of exactly the 10% gate; see ADR 0006.
- **Placebo test (`repair/placebo.py`):** draw ≥200 random pseudo-repair dates at control sites, with the same windows and the same real overpass schedule.
  - In each placebo fit, **remove the pseudo-treated site from the control set** used to estimate γ. Otherwise it partly cancels its own effect.
  - False-positive rate = the share called "drop" or "rise". **Gate 5: FPR ≤ 10%**, with a Wilson interval reported. No repair result is published before this passes.
  - Pseudo-dates at the same few sites have overlapping windows, so they are not independent and the Wilson interval is optimistic. Also report the FPR per site and a block-bootstrap interval over sites.
- **Power check:** inject synthetic drops (−25%, −50%, −75%) into the real overpass schedule at each pilot site. Report the minimum detectable effect, so an "inconclusive" result can be read correctly.
- **Sonoma Central first, after counting (week 2, right after Gate 1):** `mw repair count --site sonoma-central` lists overpasses per instrument in each window. In mid-2023 only EMIT and aircraft were flying, so if either window has fewer than about 5 usable overpasses, mark the case "insufficient data" and move to another repair.

---

## 8. Validation suite (the five tests as code)

All tests live under `mw validate <name>`. Each writes `reports/validation/<name>/<run_id>.md` with figures and exits non-zero on gate failure.

### 8.1 Synthetic recovery (`validate synthetic`): Gate 3

- The simulator (`model/simulate.py`) draws S sites with known (f_s, μ_s, σ). **Draw the truths from the prior's hyperparameters, not from fixed values.** That is the setting where 85–95% coverage of 90% intervals is the right expectation. Also run a fixed-truth scenario set (for example, one rare large emitter and one frequent small emitter) and report it separately. Overpass schedules are resampled from the real `overpasses` table once it exists, or drawn from assumed rates before then. It applies `POD_j`, release probability, and measurement error, and emits `detections` in the real schema.
- Run R = 200 replicate datasets with S = 10 sites each. Fit each one. Record whether the 90% interval contains the truth for f_s, Q̄_s, and E_s.
- **Pass:** coverage within [85%, 95%] for each quantity, pooled over sites and replicates, with a binomial CI shown.
- Also run: rank-based simulation-based calibration histograms (diagnostic only) and the misspecification scenarios from §6.5. These are reported, not gated.
- Run cost: the grid model fits in seconds to tens of seconds, so 200 fits can run overnight. `--quick` (R = 20) runs in CI.

### 8.2 Matched pairs (`validate matched-pairs`)

- Pair each S2 scene with Carbon Mapper/EMIT overpasses at the same site within ±1 day, preferring the same day.
- Binned by reference rate (`<500, 500–1000, 1000–2000, 2000–5000, >5000 kg/hr`):
  - **Hit rate:** S2 detection when the reference saw a plume.
  - **False-positive rate:** S2 detection when the reference had a usable overpass and saw no plume. This needs reference coverage, so it is only possible for EMIT if the Carbon Mapper footprints are unavailable.
- Report counts and Wilson intervals. There is no minimum, per the project plan.

### 8.3 Hold-out prediction (`validate holdout`): part of Gate 4

- For each site, split usable overpasses 80/20, stratified by instrument, over 5 random folds.
- Fit on 80%. Draw the posterior-predictive number of detections in the held-out 20%.
- **Pass:** the observed held-out count falls inside the 90% predictive interval for ≥ 80% of site-folds (a proposed threshold). Also show a calibration plot of predicted versus observed detection frequency.

### 8.4 Operator comparison (`validate operator`): part of Gate 4

- For each site-year, compare the model's E_s interval with GHGRP-reported CH4. Classify each as `model above`, `model below`, or `consistent`.
- Output a table and a forest plot. Each gap gets a free-text "possible explanations" column: floor definition, daytime bias, reporting method, neighbors.
- **Gate:** all gaps documented. This is a documentation gate, not a numeric one.

### 8.5 Placebo repairs (`validate placebo`): Gate 5

See §7. **Pass: FPR ≤ 10%** under the 97.5% call rule (nominal 5%). On synthetic data, run placebos across independent simulated worlds and bootstrap over worlds.

---

## 9. Impact accounting (`impact.py`)

### 9.1 Functions

```python
ch4_avoided_t(E_before_t_yr, E_after_t_yr, years_held) -> Interval   # propagates posterior draws
to_co2e(ch4_t, horizon: Literal["gwp20","gwp100"]) -> Interval       # reads config; marks unconfirmed
to_usd(co2e_t) -> Interval                                           # reads config; marks unconfirmed
population_within(site_id, radius_km) -> int                          # ACS block-group areal interpolation
```

- All functions operate on **posterior draws** and return intervals, never single numbers.
- `ch4_avoided_t` returns `None` unless the repair call is "drop". Nothing is "saved" otherwise.
- GWP20 and GWP100 results are always shown side by side.

### 9.2 Unit test: the worked example from the project plan

100 kg/hr × 4,380 h = 438 t CH4. At GWP 25 that is ≈ 10,950 t CO2e (≈ 11,000), and at $80/t it is ≈ $876k (≈ $0.9M). The test asserts these numbers exactly.

### 9.3 Population context

Use ACS 5-year population by block group (Census API plus TIGER shapes). Interpolate by area overlap with the buffer around the site polygon. The label reads "residents nearby (context, not a health effect)".

### 9.4 Wording lint (`report/lint.py`)

- A test renders every template with fixture data and scans the output for banned phrases: `saved` (outside the verified-drop template), `real-time`, `violation`, `non-compliant`, `illegal`, `lives`, `health impact`.
- It also requires "screening indication" on every site page and "retrospective" in the dashboard header.

---

## 10. Dashboard and publications (`report/`)

- **Index page:** a ranked table of sites with E_s median and 90% interval as a dot-and-whisker plot. Insufficient-data sites are listed separately, not ranked. Columns: usable overpasses by instrument, detections, ambiguous plumes nearby, GHGRP figure, data through (date). The header states: retrospective tracker, data lag ≈30 days, screening indications only, data credits.
- **Site page:** map with the polygon, working face, plume origins (attributed and ambiguous), and neighbors. A timeline of every usable overpass (detections with rates and error bars; non-detections as ticks). Posterior densities for f, Q̄, and E. Repair markers with the effect and interval, or "inconclusive". The operator comparison. Sources and pull dates.
- **Methods page:** an auto-generated summary of the validation results with links to `reports/validation/`.
- **Build:** `mw report build` writes `reports/site/`, published to GitHub Pages **only after the review window** (outreach steps 2–3).
- The technical note and the two-page briefing pull figures and tables from the same run (`run_id` in their captions).

---

## 11. Week-1 unknowns (spikes)

These are resolved before code depends on them. Each produces an ADR.

| Unknown | How to resolve | Blocks |
|---|---|---|
| Carbon Mapper API: plume query, fields, **footprint/coverage availability**, rate limits | Product guide + API docs after registration; one test pull at Newby Island | Phase 2, and phase 5 on real data |
| EMIT v2 collection short names; cloud mask availability | CMR search via `earthaccess` | Phase 2 |
| The open Sentinel-2 pipeline: inputs, license, what breaks | Clone it, run it on one scene near Newby Island, write notes | Phase 3 |
| The Air District's list of Rule 8-34 landfills | Air District site / permit search; LMOP as a cross-check | Screening tier |
| Data terms for derived tables | Read Carbon Mapper terms; ask if unclear | Publishing |
| POD curves per instrument | Literature for Tanager-1, EMIT, aircraft, Sentinel-2 (week 3) | Real-data fits |
| GHGRP subpart HH download path | FLIGHT / Envirofacts (week 8) | Operator comparison |

---

## 12. Build order

### 12.1 Dependency graph

The project plan says to finish each gate before starting the next phase, but its week ranges overlap. That works because the overlapping work does not depend on the earlier gate:

```
P0 setup ─┬─► P1 registry ─► P2 ingest + overpasses ─(Gate 1)─┬─► P5b real fits ─(Gate 4)─► P6b real repairs ─► P7 package
          │                       │                            │          ▲                          ▲
          │                       └─► P3 Sentinel-2 ◄─ P4 wind  │          │                          │
          │                               (Gate 2) ─► matched pairs        │                          │
          └─► P5a simulator + model on synthetic ─(Gate 3)─────────────────┘                          │
                     └─► P6a repair model + placebo on synthetic ─(Gate 5 on real schedules)──────────┘
```

- **P5a needs only the simulator,** so it runs in parallel with Sentinel-2 work.
- **P5b (real fits) needs Gates 1 and 3.**
- **P6b (real repair results) needs P5b, the `repairs.csv` entries, and Gate 5.**
- Sentinel-2 is off the critical path. If it slips, the core deliverable (persistence table + repair method) still ships.

### 12.2 Week by week (≈9 h/week)

| Week | Tasks | Hours | Gate / exit check |
|---|---|---|---|
| **1** | Repo skeleton, `uv`, ruff, pre-commit, CI (pytest); README + DATA_TERMS. Carbon Mapper registration + API spike (ADR 0001). Newby Island pull within 5 km → first date-vs-rate plot. Pilot polygons drafted. EMIT spike. **Long-lead asks:** file the Air District public records request for complaint reports; ask Carbon Mapper for acquisition lists (rung 1 of the coverage fallback) | 9 | First plot; spikes logged; requests sent |
| **2** | `plumes` normalization + attribution; EMIT v2 ingest; `coverage/` → `overpasses` v0; provenance manifests; screening list + OSM/buffer polygons. **Right after Gate 1:** `mw repair count --site sonoma-central` to decide whether that repair case is viable | 9 | **Gate 1**: plume + overpass counts per instrument per year, 5 pilot sites; Sonoma Central go/no-go |
| **3** | Clone/read S2 pipeline (ADR 0004); scene search + one MBMP retrieval at Newby. Wind ADR 0002 + `WindProvider`. Start `model/pod.py`, `grid.py`, `simulate.py`. **Email pilot operators asking only for repair logs**, prioritizing the sites the week-2 counts favor. This asks for data and publishes nothing | 9 | Wind product chosen and recorded; repair-log requests sent |
| **4** | S2 masks + detection + IME quantification with Monte Carlo; Gate 2 attempt (or fallback). POD curves from literature (ADR 0003). Start entering `repairs.csv` from public documents | 9 | **Gate 2** (or documented fallback) |
| **5** | `persistence.py` (grid likelihood, non-centered hierarchy), prior predictive check, first synthetic fits; unit tests for integrals vs Monte Carlo | 10 | Single synthetic fit recovers truth, clean diagnostics |
| **6** | `validate synthetic` at R=200 overnight; fix under/over-coverage; misspecification scenarios; matched-pairs script. **After Gate 3, send the model spec and synthetic results to the faculty sponsor for statistical review** | 9 | **Gate 3**: coverage 85–95%; sponsor packet sent |
| **7** | Real fits for 5 pilots + screening tier; `site_estimates`; insufficient-data rule; hold-out test | 9 | Hold-out passes |
| **8** | GHGRP ingest + crosswalk; operator comparison + gap notes; matched-pairs report; sensitivity runs (POD, release prob.). Fold in sponsor feedback | 9 | **Gate 4**: hold-out passed, gaps documented |
| **9** | Finish `repairs.csv` (public documents + any operator logs received); repair model on synthetic with injected drops; power analysis | 9 | Repair model recovers injected drops |
| **10** | Placebo test (≥200 pseudo-dates); then real repair results if Gate 5 passes; impact module + tests | 9 | **Gate 5**: placebo FPR ≤ 10% |
| **11** | Dashboard build + wording lint; end-to-end `make all` from clean cache; technical note + briefing drafts. **Send site-level findings privately to operators → Air District (two-week window starts)**. The sponsor has already reviewed the statistics | 10 | Review packet sent |
| **12** | Address review feedback; freeze `run_id`; tag release; publish dashboard + note after the window closes | 8 | Public outputs live |

Total ≈ 109 hours. If behind schedule, cut in this order: S2 quantification beyond Gate 2 → screening-tier polish → population context → dashboard extras. **Never cut** the synthetic test, the placebo test, or the review window.

### 12.3 First weekend → code

| Project-plan step | Code artifact |
|---|---|
| Register on Carbon Mapper, request API access | `.env` with key; `ingest/carbonmapper.py` stub + ADR 0001 |
| Pull every plume within 5 km of Newby Island; plot date vs rate | `mw ingest carbonmapper --site newby-island --radius-km 5` → `notebooks/scratch/newby_first_plot.ipynb` |
| Get the Air District's landfill list; pick 5 pilots | `data/registry/sites.geojson` (pilot points first; polygons in week 1–2) |
| Clone the open S2 pipeline; run on one scene near Newby | `docs/decisions/0004-s2-pipeline.md` with "what broke" |
| One-page note: hypotheses + expected detection rate per instrument | `docs/hypotheses.md`. These become the simulator's default overpass/POD assumptions |
| Repo + README on non-commercial use and data terms | `README.md`, `DATA_TERMS.md` |
| Email a faculty sponsor | (outside the code) |

---

## 13. Testing and CI

- **Unit tests (fast, every push):**
  - geometry attribution cases (inside, buffer, ambiguous, neighbor-closer)
  - schema validation on fixture tables
  - POD monotonicity (hypothesis)
  - grid integrals vs Monte Carlo (within 1%)
  - truncated-lognormal mean vs closed form
  - IME on a synthetic Gaussian plume
  - impact worked example (§9.2)
  - wording lint
- **Integration (CI, small):** `mw validate synthetic --quick`, plus a 3-site end-to-end run on fixture data checked into `tests/fixtures/`. No network in CI. API clients are tested against recorded responses.
- **Manual / nightly:** the full synthetic (R = 200), placebo (≥200), and real fits.
- **Run manifest:** every model run writes `run_id, git_sha, config_hash, input table hashes, sampler settings, diagnostics` to `data/processed/runs/<run_id>.json`. Published figures cite the `run_id`.

---

## 14. Engineering risks specific to the code

| Risk | Mitigation |
|---|---|
| No coverage data for Carbon Mapper instruments | Fallback ladder in §5 phase 2c; f from EMIT/S2 only; state it in outputs |
| MCMC divergences with few detections per site | Non-centered parameters, shared σ, tighter priors; report failure rather than force |
| Synthetic coverage outside 85–95% | Inspect which quantity fails. Usually σ or the floor `q_min`; adjust model, not threshold |
| Placebo FPR > 10% | Widen windows, require more overpasses, or report repairs as "method not yet reliable for this site" |
| API changes / rate limits | Cached raw pulls, `tenacity` backoff, idempotent incremental pulls |
| S2 pipeline doesn't run or is wrong | It's off the critical path; Gate 2 fallback; document |
| Scope creep in dashboard | Static pages only; one template per page type |

---

## 15. Definition of done (week 12)

- [ ] `make all` reproduces every published number from cached raw data on a clean checkout
- [ ] Gates 1–5 reports committed under `reports/validation/` with passing status (or documented fallback for Gate 2)
- [ ] `site_estimates` for all screened sites, with intervals or "insufficient data"
- [ ] Repair results for every documented repair at the 5 pilots: effect, interval, call, and minimum detectable effect
- [ ] Operator comparison table with gap explanations
- [ ] Dashboard, technical note, and two-page briefing published after the two-week review window
- [ ] README and DATA_TERMS state non-commercial use and credit every data source

---

## 16. Expansion: two regions and more measures (November 2026)

Decided on Nov 19, 2026. The reasons and the options turned down are in ADRs 0018 (regions), 0019 (measures), 0020 (wording for context) and 0021 (public scope, two fits, old copies). This section is the build plan.

**What does not change:** this is still a retrospective tracker. Outputs are screening indications, never compliance findings, never health claims. The persistence model, the repair test and the five gates stay as written above.

### 16.1 Regions

| Region | Counties |
|---|---|
| `bay-area` | Alameda, Contra Costa, Marin, Napa, San Francisco, San Mateo, Santa Clara, Solano, Sonoma |
| `north-valley` | San Joaquin, Stanislaus, Merced, Sacramento, Yolo |

- Regions are one list in `config/project.yaml`, read by one loader. No module keeps its own box or county list.
- Everything lies west of 120°W, so EPSG:32610 stays. The registry check rejects a site east of that line.
- Each site carries `region`, `air_district` and `swis_number`.

### 16.2 Sites

- **Pilot (5):** unchanged. Four gain real outlines from CalRecycle's boundary layer; Shoreline keeps a provisional outline until one is drawn.
- **Screen:** every permitted landfill, open or closed, on CalRecycle's list for the two regions. No transfer stations, exempt sites or waste-to-energy plants. The list is reviewed by hand before it enters the registry.
- **Deep-dive sites in the North Valley** are chosen after the first screening results.
- **Outlines:** hand-drawn, else CalRecycle's boundary layer by SWIS number, else a 750 m buffer marked provisional.
- **Neighbours:** a plume that Carbon Mapper tags with a sector other than waste is marked ambiguous and never assigned to a landfill.
- **Sentinel-2:** pilot and deep-dive sites only.

### 16.3 Measures

Everything that is not a methane estimate goes in one table, `site_metrics`, described by a catalogue in `config/metrics.yaml`. The methane tables get no gas column.

| Measure | Source | Kind |
|---|---|---|
| Reported CH4, CO2, biogenic CO2 and N2O per year | EPA GHGRP | reported |
| CO2 plumes seen near the site per year (a count) | Carbon Mapper | observed |
| Waste in place, gas collected and flared, energy projects | EPA landfill program database, CalRecycle | reported |
| Inspections, notices and repairs | air districts, CARB (the checks tables of ADR 0010) | reported |
| Nearest air monitors | EPA AQS | context |
| People nearby, CalEnviroScreen scores | Census, OEHHA | context |

- **CO2 is never modelled.** No instrument used here sees landfill CO2. It is shown as reported, or as a count of plumes found.
- **"Not reported" is not zero.** Most landfills file no combustion report.
- **Context is never attributed to the landfill** and never ranked (ADR 0020).

### 16.4 What the public site may show

- An allowlist of regions and tiers (`config/public_scope.json`), starting as the Bay Area pilot tier. It is enforced in the database, in the web build and in the public-output check.
- New sites and new regions go to the review copy first. The owner widens the allowlist after a review window.
- `official_model_run` supplies the figures for the sites it covers. An optional `screening_model_run` supplies estimates for the rest, marked provisional.
- A pooled fit becomes official only after Gate 3 passes at the real site count, with a region term and each region's own pass rates.

### 16.5 Build order

One pull request each, from `main`, merged before the next starts.

| # | Step | Changes the public site? |
|---|---|---|
| 1 | This amendment and ADRs 0018 to 0021 | No |
| 2 | Commit the registry as the scheduled run uses it | No |
| 3 | Make the scheduled run and fits safe for more sites (§16.4, two fits) | No |
| 4 | Public scope gate | No |
| 5 | Prune command for old review copies | No |
| 6 | Regions loader, Bay Area only; EPA county-name fix | No |
| 7 | Registry columns | SWIS number appears on pilot pages |
| 8 | Screening builder | No |
| 9 | Bay Area screening rows | No; review copy grows |
| 10 | North Valley: region, wider pulls, rows | No; review copy only |
| 11 | Real outlines for four pilots, the sector rule, refit and gates | When the owner promotes the new fit |
| 12 | `site_metrics`, the catalogue and EPA's gases | New section at the next promotion |
| 13 | Pages for many sites, neutral copy | Layout and wording |
| 14 | Regulators generalised | Label wording |
| 15 | Gate 3 at scale and the first screening fit | No; review copy only |
| 16+ | One source each: CO2 plume counts, site operations, CalEnviroScreen, air monitors | New sections as promoted |

If time runs short, cut from the end of step 16 backwards: air monitors, CalEnviroScreen, site operations, CO2 plume counts, then the screening fit. **Never cut** steps 3 to 5, the Gate 3 rerun, the wording check or the review window.

### 16.6 Checks for this work

- Step 3: the same publication tables as before for the five pilots.
- Step 4: a fixture with a site and a plume outside the allowlist must fail the public build and appear in the review build.
- Step 6: the Bay Area region reproduces the earlier box and county lists exactly.
- Steps 9 and 10: counts per county match the CalRecycle pull; the wider pulls reproduce the counts recorded in ADR 0018.
- Step 12: EPA's 2023 rows for Kiefer Landfill match the figures recorded in ADR 0019.
- Step 15: Gate 3 coverage inside 85 to 95% at the new site count.
- CO2 step: the methane plume and detection tables are unchanged with CO2 pulls present.

### 16.7 Regulators

Sites fall under five air districts (by CARB's 2004 outlines, unconfirmed): Bay Area, Northern Sonoma, Sacramento Metro, San Joaquin Valley Unified and Yolo-Solano.

- **A record names its regulator.** `checks.csv` has a `regulator` column. An air district inspection or notice must name its district, and that must be the district its site sits in; `mw publish build` stops otherwise.
- **Pages name the regulator from the site.** A record's label is built from its site's district ("Sacramento Metro AQMD inspection"), so nothing on a page says "the Air District". Because the build has checked the record against the site, no new database column is needed.
- **A district joins `config/data_terms.yaml` when its records arrive** and its terms have been checked, not before. Until then it is listed in `DATA_TERMS.md` only, so the website's list of sources names no district the project holds nothing from.
- **Still to do:** the map has a layer for county and air district lines, but no outlines are loaded into the website's database yet (checked 2026-11-23). The outlines are in `datasets/boundaries/`.

### 16.8 Out of scope

A CO2 emission model. Sources other than landfills, except as a reason to mark a plume ambiguous. Counties south of Merced or east of 120°W. Linking an air monitor to a site by wind direction.
