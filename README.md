# Bay Area Landfill Methane Watch

A retrospective tracker that ranks Bay Area (and surrounding) landfills by how persistently they emit methane, and
tests whether recorded repairs are followed by a measurable drop, using only public satellite and
aircraft data. It solves three central issues that aren't currently addressed:
**Persistence.** Previous and current efforts fail to register persistent detections within 
landfills and casually forget how often one emits. This dashboard takes note of past issues
and saves them for later.
**Repair verification.** A before/after test for repairs against control sites, anchored to 
  documented repair dates and calibrated with placebo dates. No fingers are pointed, but a
  supposed repair that did not reduce the rate and size of methane emissions is dubious.
**Reality check.** Site-by-site comparison with operator-reported emissions (EPA GHGRP).

Results are screening indications for investigation, and data arrives with about a 10-30 day lag, 
so this is not real-time monitoring; it's more so retrospective reasoning.

## Setup

Requires [uv](https://docs.astral.sh/uv/). uv installs Python 3.12 itself.

```bash
make setup            # uv sync --all-extras + pre-commit hooks
cp .env.example .env  # add API credentials
uv run mw --help
make check            # lint, tests, config check
```

Credentials:
- **Carbon Mapper:** `CARBON_MAPPER_API_KEY` in `.env`.
- **NASA Earthdata:** `~/.netrc`, used by `earthaccess` for EMIT.
- **Copernicus Data Space:** `.env`, for Sentinel-2.
- **ERA5:** `~/.cdsapirc`, if ERA5 is the chosen wind product.

## Layout

```
config/             project, instrument, model and impact settings (with citations)
data/registry/      hand-curated sites, repairs and ID crosswalk (tracked)
data/{raw,interim,processed}/   pulls and derived tables (not tracked)
src/methanewatch/   the package; `mw` CLI in cli.py
tests/              fast tests run in CI
notebooks/          00_end_to_end.ipynb reruns the pipeline; scratch/ for exploration
reports/validation/ gate and validation reports
docs/               plan, decision records, technical note, briefing
```

## Pipeline

| Phase | Command | Gate |
|---|---|---|
| Site registry | `mw sites build` | — |
| Ingest | `mw ingest carbonmapper / emit / ghgrp` | — |
| Overpasses | `mw coverage build` | `mw validate gate1` |
| Sentinel-2 | `mw s2 search …` | `mw validate gate2` |
| Persistence model | `mw model fit` | `mw validate synthetic` (85–95% coverage), `mw validate holdout` |
| Dashboard preview | `mw model demo`, then `mw report build --run-id demo-…` | — (SYNTHETIC, labelled) |
| Repair verification | `mw repair count …` | `mw validate placebo` (false-positive rate ≤ 10%) |
| Report | `mw report build --run-id …` | every page passes the wording check |

Unbuilt steps exit with code 2 and say which week of the plan they belong to.

## Data use

This project is **non-commercial**. Carbon Mapper data are free for non-commercial use only, and
raw pulls are not redistributed in this repository. See [DATA_TERMS.md](DATA_TERMS.md) for terms.

## License

Code: MIT (see [LICENSE](LICENSE)). Data remain under their providers' terms.
