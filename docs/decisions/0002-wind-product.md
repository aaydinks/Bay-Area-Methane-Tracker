# 0002: Wind product and U_eff calibration

- **Status:** proposed (needs one live HRRR check and the U_eff source verified)
- **Date:** 2026-10-04

## Context

Plume rates from integrated mass enhancement use `Q = U_eff · IME / L`, with
`U_eff = a · U10 + b`. U10 comes from a reanalysis or analysis product. The
Bay Area has a sea breeze and complex terrain, so grid spacing matters.

## Options considered

| Product | Grid | Cadence | Access |
|---|---|---|---|
| HRRR analysis (fxx=0) | about 3 km | hourly | public cloud archive; `herbie` byte-range downloads, no account |
| ERA5 single levels | about 31 km | hourly | Copernicus CDS account and `~/.cdsapirc` |

## Decision (proposed)

- **HRRR as the primary product**, nearest grid point, nearest hour.
- **ERA5 as a cross-check.** Report the U10 difference at the pilot sites on
  plume dates.
- Both are implemented behind `WindProvider` (`methanewatch.wind`), and
  `mw wind get` fetches one value.

U_eff for Sentinel-2 is set to `a = 0.33`, `b = 0.45 m/s` in
`config/quantify.yaml`. It is marked **unconfirmed**: check it against Varon et
al. 2021 before use. Rate outputs carry `confirmed_calibration = false` until
then.

## Consequences

- To finalize this ADR: one live HRRR value at Newby Island on a Sentinel-2
  date, and the U_eff coefficients checked against the paper.
- Quantification uncertainty includes U10 (±1.5 m/s default), a 15% log-normal
  spread on U_eff, and background noise in the IME.
