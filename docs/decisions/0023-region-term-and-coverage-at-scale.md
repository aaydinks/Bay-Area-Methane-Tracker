# 0023: The region term, and the coverage test at the real site count

- **Status:** accepted
- **Date:** 2026-11-24

## Context

0021 decided that a fit pooling the pilot and screening sites must first pass the synthetic coverage
test "at the real site count, with a region term and each region's own pass rates". It did not say
what the region term is or how the test takes the shape of the real data. This record does.

The coverage test so far (PLAN section 8.1) simulates ten sites with made-up pass rates and no
regions. The registry now has 52 sites, and the two regions are observed differently. Usable passes
of the instruments a fit uses today, per site, through 2026-10-08:

| Region | Sites | Aircraft | EMIT | Tanager-1 | Fewest at a site | Most at a site |
|---|---|---|---|---|---|---|
| Bay Area | 33 | 2.8 | 7.8 | 4.8 | 4 | 35 |
| North Valley | 19 | 2.2 | 17.1 | 1.6 | 15 | 31 |

The persistence model pools sites: each site's emitting share and typical rate are drawn around one
shared centre (0005). Pooled over both regions without a region term, that centre would be one
"typical landfill" for the Bay Area and the North Valley alike.

## Decision

**The region term**

- One yes/no site covariate, `north_valley`, inside the covariate machinery of 0008. It shifts the
  centre of the emitting share and of the typical rate for North Valley sites, each by a
  coefficient with the usual Normal(0, 0.5) prior on the centred indicator.
- A further region would add one more term of the same kind. `features.REGION_TERMS` lists them,
  and a test checks each names a region in `config/project.yaml`.
- A fit whose sites lie in several regions must carry the term. `mw model fit` stops without it,
  the same way it stops when the sites are of several tiers and no choice was made.
- A fit names its covariates on the command line (`--covariate north_valley`). The list in
  `config/model.yaml` stays empty, so a pilot-only fit is the model it was. The run manifest
  records the term, as it already does for any covariate.

**The coverage test at scale** (`mw validate synthetic --at-scale`)

- The simulated sites take the shape of a fit of every registry site: as many sites, each in its
  real region, each with the number of passes per instrument that the real table has for it. Only
  those counts are read. Site ids are made up, so a report names no landfill.
- Instruments are the ones a real fit would use today (0016 leaves Sentinel-2 out). Their detection
  settings are still the SYNTHETIC ones in `config/synthetic.yaml`.
- Truths are drawn from the model's priors, the region coefficients included, as in the ten-site
  test.
- Chains are as long as the real fit's, not the shorter ones of the ten-site test: this test stands
  in for one particular fit.
- **A fit that pools regions draws 3,000 per chain** (`covariates.pooled_draws` in
  `config/model.yaml`), three times the usual. The first full run of this test showed why; see the
  result below. The run manifest records the sampler a fit used.
- **Pass:** coverage of the 90% ranges inside 85 to 95% for the emitting share, the typical rate and
  the annual total, pooled over all sites **and within each region**, and at most 10% of fits
  failing their sampler checks.
- The report goes to `reports/trials/synthetic-scale/`. Everything under `reports/validation/` is
  published as a method check (0021), and this is a trial of a fit that is not official.

**The first screening fit**

- It fits all 52 sites, both tiers, with the region term. `publish.screening_model_run` names it.
- It supplies estimates only for the 47 sites the official fit does not cover, always marked
  provisional (0021). The five pilots keep the official fit's figures.

## Options turned down

- **No region term.** Simpler, and with 19 North Valley sites the term is weakly informed. But it
  would build in the assumption that the two regions share one typical landfill, which is the thing
  a wider screen should be able to show is wrong.
- **Separate centres and spreads per region.** Two more spreads to estimate from 19 sites, most of
  them with no plume seen. The single shift is the smallest change that lets the regions differ.
- **Fitting the screening sites on their own.** The pilots are among the best-observed sites, and
  leaving them out would make every screening estimate lean more on the priors.
- **Pass rates per region drawn at random.** A draw around a region's mean would not include the
  sites with four to seven passes, which are the ones whose estimates rest most on the pooling.
- **The shorter chains of the ten-site test.** In a three-fit trial at 52 sites, one fit ended just
  over the r-hat limit (1.014 against 1.01).
- **Changing how the model is written so the shared spreads mix faster.** That would be a different
  model from the one every earlier check was run on. Longer chains cost seconds per fit.
- **Loosening the sampler checks for large fits.** The checks are what make a fit's ranges
  trustworthy; a fit that needs more draws should get them.

## Result

Both runs: 200 simulated worlds of 52 sites (10,400 site fits), reports in
`reports/trials/synthetic-scale/`. The per-site tables are not committed; each run can be made
again from its commit and seed.

| Run | Draws per chain | Emitting share | Typical rate | Annual total | Fits outside the sampler checks | Result |
|---|---|---|---|---|---|---|
| `synthetic-20261125T041949Z` | 1,000 | 90.1% | 90.7% | 90.2% | 18.0% (36 of 200) | **fail** |
| `synthetic-20261125T045756Z` | 3,000 | 90.2% | 90.7% | 90.2% | 0.5% (1 of 200) | **pass** |

- **Coverage was on target both times,** pooled and in each region. In the passing run the Bay
  Area's three figures were 90.3%, 90.8% and 90.6%, and the North Valley's 90.1%, 90.7% and 89.6%.
- **The first run failed on the sampler checks alone.** None of its 36 failing fits had a
  divergence. They ended just outside the limits: r-hat up to 1.027 against 1.01, or a smallest
  effective sample down to 284 against 400. Replaying eight of them showed the slow parameters are
  the ones shared across sites (the two spreads and the centre of the typical rate), and that
  longer chains cleared most of them. Coverage in the failing fits was no worse (90.4% for the
  annual total).
- **The chain length was changed after seeing that failure,** and the second run is the test of
  the changed setting. Both reports are kept so the order of events is on record.

The first screening fit, `fit-20261125T045806Z`, run from the same commit as the passing test:

- 52 sites, 909 usable passes, 135 with a detection; r-hat 1.003, smallest effective sample 621, no
  divergences.
- 15 sites have an estimate: 2 pilots and 13 screening sites (6 Bay Area, 7 North Valley). The
  other 37 are marked insufficient data: 8 have fewer than eight usable passes, and at the rest no
  plume was seen, which leaves a range wider than a hundredfold.
- **The region term found no difference.** The 90% ranges of both coefficients span zero (emitting
  share: -0.60 to 0.92; typical rate: -0.81 to 0.46).
- **Sites differ from each other more than the prior expected.** The spread of the emitting share
  across sites came out at 2.6 (90% range 1.7 to 3.5) on the logit scale, against a prior with 95%
  of its mass below 2.0. The data look like two groups, sites where plumes are seen often and
  sites where none has been seen, which one bell-shaped spread describes poorly.
- For the two pilots with an estimate, the pooled fit's annual total is 8% higher (Newby Island)
  and 2% lower (Potrero Hills) than the official fit's. Their published figures stay the official
  fit's.

## Consequences

- The test at scale reads local data, so it does not run in CI. Unit tests cover the layout, the
  per-region pass rule and the report with made-up counts.
- It shows that the model and its sampler behave at this size and shape when the world is the one
  the model assumes. It does not show that real landfills follow the model; the hold-out check
  does that job, and it has not been run on the pooled fit.
- It should be rerun before a pooled fit becomes official, and whenever the registry grows or an
  instrument joins the fits.
- The longer chains are tied to the region term, which is what marks a pooled fit today. A large
  fit within one region would not get them and should be checked the same way first.
- The wide spread between sites is a reason not to make the pooled fit official on this test
  alone. The hold-out check on the pooled fit, and a look at whether two groups of sites fit
  better than one, come first.
- A site page must say which fit a figure comes from while two fits sit side by side (0021).
