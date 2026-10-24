# 0008: Site traits as covariates in the persistence model

- **Status:** accepted
- **Date:** 2026-10-23

## Context

The persistence model treats every site as exchangeable. A site's emitting share and typical rate are drawn
around one Bay Area mean. Some site traits plausibly move those means:

- a closed landfill has no working face;
- a larger footprint has more surface to leak from.

With few passes at most sites, letting the traits inform the shared mean should tighten the estimates for thin
sites without forcing them.

The sample is small: 5 pilot sites and about 36 in the screening tier. Remediation outcomes are fewer still, a
handful of dated repairs.

## Options considered

1. **No covariates.** This was the default before this decision. Safe, but ignores what we know about each site.
2. **A separate predictive model** (for example gradient boosting) that predicts outcomes from traits. Rejected:
   dozens of rows at best. It would overfit, and it would have no honest uncertainty to show on the dashboard.
3. **Site-level covariates inside the hierarchical model.** Chosen:
   ```
   logit f_s = alpha_f  + X_s . beta_f  + tau_f  z_f[s]
   mu_s      = alpha_mu + X_s . beta_mu + tau_mu z_mu[s]
   ```
   `beta ~ Normal(0, 0.5)` per standardized covariate. The site-level spread (`tau`) stays, so a covariate
   explains part of the variation and never all of it.

## Decision

- **Covariates available** (`methanewatch.features`):
  - `closed`: closed or closing per the registry, else CalRecycle;
  - `log_area`: boundary area;
  - `ghgrp_reporter`;
  - `log_dist_neighbor`: distance to the nearest other methane source or site.
- **Encoding:** binary covariates are centred over the sites in the fit; continuous ones are standardized.
  Missing values or a covariate that does not vary stop the fit rather than letting the prior pose as evidence.
- **At most two or three covariates.** Start with `closed` and `log_area` once polygons exist.
- **Default is empty** (`config/model.yaml: covariates.names: []`). With an empty list the model is exactly the
  model without covariates: no extra variables are created.
- **Descriptive only:** county and operator. Too many levels for the number of sites.
- **Never a model input:** nearby population. It is context only, by project rule.
- **Repair test:** the same covariates shift each site's baseline in both periods, so they never enter the
  repair effect.
- **Run manifest:** each real fit records the covariate names, centres and scales, so coefficients can be read
  in real units.

## Evidence

Gate 3 with `closed` and `log_area`, simulated and fitted: 200 replicates of 10 sites. Covariate values are
made up; coefficients are drawn from their prior.

| Run | target_accept | f | Qbar | E | Fits failing diagnostics | Result |
|---|---|---|---|---|---|---|
| `synthetic-20261024T010329Z` | 0.90 | 0.902 | 0.886 | 0.885 | 11.5% (20 of 23 from divergences) | FAIL |
| `synthetic-20261024T013708Z` | 0.95 | 0.898 | 0.888 | 0.889 | 4.5% | PASS |

For comparison, the model without covariates (`synthetic-20261003T223204Z`, 0.90) failed diagnostics in 7% of
fits, mostly r-hat and ESS, not divergences.

The covariates added divergences, almost always 1 or 2 per fit. A 40-replicate comparison gave 3 divergent fits
at 0.90 and 1 at 0.95, with the same coverage. Covariate fits therefore use
`covariates.target_accept: 0.95` (smaller steps, somewhat slower); fits without covariates keep the
sampler's 0.90.

## Consequences

- **Deferred: a seasonal effect.** It would need a per-pass covariate. The model counts passes per (site,
  instrument), so a season term needs a per-season cell and parameter. Not done here.
- **Inputs:** `mw features build` writes `data/interim/site_features.parquet` from the registry. It needs the
  site polygons.
- **Re-checks:** any change to the covariate list or `beta_sd` means rerunning the prior predictive check
  (ADR 0005), Gate 3 and the hold-out test.
