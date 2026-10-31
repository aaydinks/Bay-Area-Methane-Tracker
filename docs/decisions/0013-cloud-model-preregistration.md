# 0013: Pre-registered test of the Sentinel-2 cloud model

- **Status:** accepted
- **Date:** 2026-10-31

## Context

ADR 0012 chose a small per-pixel model (gradient-boosted trees) that classifies Sentinel-2 L1C
pixels as clear, cloud or cloud shadow, trained on CloudSEN12+ expert labels. The model's output
is published as a result only if it gives information the project can act on, better than what
it already has or could get without a model.

This record fixes the claims, the data, the measures and the pass/fail rules **before any
held-out number is computed**. It was merged before the first held-out evaluation. The
evaluation runs once. Any later change to it is a new ADR that says what changed and why, and
both sets of numbers are reported.

## Held-out data (fixed now)

- **Source.** CloudSEN12+ v1.1 (`tacofoundation/cloudsen12`, revision `f9490f7`): the L1C
  collection for pixels and labels, the `extra` collection for baseline masks.
- **Patches.** Expert-labelled (`high`) 509 px patches only.
- **Held-out sites.** Every site (ROI) in the official `test` split, plus every site whose
  centre lies in the US West Coast box (latitude 32 to 49 N, longitude 125 to 114 W),
  whatever its official split. Expected: about 219 sites and 1,095 patches.
- **Subsets.**
  - The West Coast sites are reported as a regional subset (about 31 sites, 155 patches).
  - The three Bay Area sites are listed one by one, but they are too few to test.
- **Training data.** Official `train` and `validation` sites only, minus the held-out sites,
  minus any patch whose Sentinel-2 tile also holds a held-out patch. Everything is split by
  site and tile, never by pixel.
- **Tuning.** Model settings are chosen on the validation sites only.
- **Grid.** Everything is computed at 20 m:
  - 10 m bands and labels are aggregated 2 x 2. A label takes the majority class, with ties
    going to the less clear class.
  - 60 m bands are repeated.
  - Padding (pixels where every band is 0) is ignored.

## Methods compared (fixed now)

| Method | Unusable pixel = | Settings |
|---|---|---|
| **Tile rule** (the current `valid_frac`) | the whole patch, when the tile's `eo:cloud_cover` is above 30% (that is, `valid_frac` below 0.7) | as in the pipeline. The tile figure is looked up by product name in the Copernicus Data Space catalogue; patches with no match are left out of this row only, and the count is reported |
| **Threshold mask** (`masks.py`) | cloud: B02 > 0.25 or B12 > 0.60; shadow: B12 < 0.05 with NDWI <= 0 | values in `config/sentinel2.yaml` today |
| **Sen2Cor** (`cloudmask_sen2cor`) | scene classes 8, 9, 10 (cloud) and 3 (shadow) | as shipped |
| **s2cloudless** (`cloudmask_s2cloudless`) | probability >= 40% (cloud); no shadow class | published default threshold, no dilation |
| **Model** | predicted class cloud or shadow | settings chosen on validation sites only |
| Reference: UNetMobV2-V2 (`cloudmask_unetmobv2_v2`) | labelled cloud or shadow | as shipped. Reported on the official test split only, because it was trained on the official train split, which includes West Coast sites |

"Unusable" in the labels means thick cloud, thin cloud or cloud shadow. Baselines use their
published settings and are not tuned. The water and dark-surface parts of `masks.py` that are
not about clouds (the NDWI water rule and the band 12 range) are applied identically to every
method in Claim 2.

## Claim 1: fewer cloudy passes wrongly counted as usable

- **Unit.** One held-out patch, which is a 5 km window like a site window.
- **Truth.** The patch is usable when at least 70% of its pixels are labelled clear (the
  pipeline's `min_valid_frac`).
- **Each method.** The patch is called usable when its predicted clear share is at least 0.7.
  The tile rule calls it usable when the tile's cloud cover is 30% or less.
- **Primary measure: false-usable rate.** The share of truly unusable patches a method calls
  usable. This is the error that biases the persistence model: a cloudy window counted as
  usable becomes a false Sentinel-2 non-detection.
- **Paired measure: false-unusable rate.** The share of truly usable patches a method throws
  away. This is the cost in lost passes.
- **Intervals.** 90% percentile bootstrap over sites: 2,000 replicates, seed 20261031,
  resampling sites with all their patches.
- **Pass rule.** For **each** of the tile rule, the threshold mask, Sen2Cor and s2cloudless:
  - the 90% interval of (model false-usable rate − baseline false-usable rate) lies entirely
    below 0; **and**
  - the upper end of the 90% interval of (model false-unusable rate − baseline false-unusable
    rate) is at most 0.05.

  Claim 1 passes only if both hold against all four.
- **Also reported, not part of the rule:**
  - pixel-level accuracy and confusion tables;
  - results on the West Coast subset;
  - the number of truly usable patches each method recovers.

## Claim 2: fewer false Sentinel-2 detections caused by clouds

**Pairs.**
- For each held-out site, the reference is the date with the highest labelled clear share,
  provided it is at least 99% clear. Sites without such a date are skipped.
- Every other date of the site is a target.

**Retrieval and detection.** The project's code, unchanged:
- multi-band multi-pass retrieval (`sentinel2/retrieval.py`);
- detection (`sentinel2/detect.py`): median + 2 robust sigma, at least 5 connected pixels,
  8-neighbour, run over the whole patch.

Each method's unusable pixels, in the target or the reference, are removed before detection.
"No cloud mask" is reported as a reference row.

**Cloud-caused candidate.** A candidate with at least half its pixels labelled cloud or shadow
in the target or the reference.

**Injected plumes.**
- Three per target, placed at random in pixels labelled clear on both dates.
- Each is a Gaussian plume: random direction, length 0.6 to 2 km, widening downwind.
- Band 12 is multiplied by (1 − a · shape). Band 11 is left unchanged, which slightly overstates
  the signal for a given amount of methane.
- **The peak absorption `a` is fixed on validation sites, before the test run.** It is the
  smallest value in {0.02, 0.03, 0.05, 0.08, 0.12} at which, with no cloud mask, at least 80%
  of injected plumes are detected on validation targets that are at least 99% clear.
- A plume counts as detected when one candidate covers at least 30% of its pixels whose shape
  value is 0.5 or more.
- Strength stays in fractional absorption. It is not converted to t/hr (ADR 0004 is open).

**Measures.**
- **Primary:** cloud-caused candidates per target.
- **Paired:** the share of injected plumes detected.
- Both use the same site bootstrap as Claim 1.

**Pass rule.** For **each** of the threshold mask, Sen2Cor and s2cloudless:
- the 90% interval of (model − baseline) cloud-caused candidates per target lies entirely below
  0; **and**
- the lower end of the 90% interval of (model − baseline) plume detection share is at least
  −0.02.

## What gets published

- **Claim 1 passes.** Per-site usable passes from the model may replace the tile rule in
  `valid_frac`, and the model's per-site usable-pass counts may be published.
- **Claim 2 passes.** The model mask may be used before Sentinel-2 detection, and the change in
  candidate counts may be published.
- **A claim fails.** That use is not published as a result. The technical page still shows the
  held-out numbers, marked as a method check that the model did not pass. If Claim 1 fails, the
  recommended per-site mask is the baseline with the lowest false-usable rate whose
  false-unusable rate is no worse than the tile rule's.

Either way:

- Every figure keeps the project's rules: 90% ranges, and `confirmed: false` for anything
  unsourced.
- Any row derived from Carbon Mapper stays restricted. None is used here.
- Anything pilot-specific is a screening indication, never a compliance finding.

## Not pre-registered (descriptive only)

- **Usable passes per pilot site,** 2022-08 to 2026-10, under the tile rule, Sen2Cor and the
  model, on the real Bay Area passes. There are no labels there, so this shows what changes,
  not whether it is right.
- **Effect on the 90% ranges and the smallest detectable drop.** Only in simulation, because
  there is no real fit and the Sentinel-2 detection curve is unsourced. If shown, it is
  labelled simulated.
- **Sentinel-2 candidates near known EMIT or Carbon Mapper plumes.** Too few to test (ADR
  0012). Any Carbon Mapper-based row is restricted.

## Consequences

- The evaluation command writes one results file with the code version, data revision and the
  numbers above, committed under `reports/validation/`. The website reads it.
- **Negative results are reported the same way as positive ones.** They are not hidden, and the
  test is not re-run with new settings.
