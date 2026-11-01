# 0014: Checking the cloud model on recent pilot passes

- **Status:** proposed
- **Date:** 2026-10-31

## Context

The Sentinel-2 cloud model passed its one held-out test (ADR 0013). Every training and test
image in that test dates from 2017 to 2020. They were taken by Sentinel-2A and 2B and
processed with baselines N0206 to N0209.

The pilot passes the model would sort are different in three ways:

- **Processing baselines.** They run from N0400 to N0513.
- **A new satellite.** Since 2024 they include Sentinel-2C.
- **A new offset.** Since baseline 04.00, the digital numbers carry an offset of -1000
  (`RADIO_ADD_OFFSET`). An image read without that offset looks about 0.1 brighter in every
  band, which a cloud model would read as haze.

The model may also meet surfaces it rarely saw in training. The salt ponds beside Newby Island
and Shoreline and bare landfill cover are bright and can look like cloud.

This is a **transfer check, not a second run of the ADR 0013 test**.

- There are no expert labels for the pilot passes, so it cannot measure error rates.
- It asks whether the model behaves on recent passes the way it behaved on the test images.
- Its yardsticks are:
  - Sen2Cor's scene classification (SCL);
  - a map of where false clouds keep appearing;
  - a blind look at a sample of passes by eye.

The criteria below were written and committed before any pilot number was computed.

## The check (fixed before the run)

**Sample.** Every Sentinel-2 site-day in 2025 at the five pilot sites in the overpass table
(`data/interim/overpasses.parquet`): about 500 site-days on about 160 acquisition days.

**Window.**
- Centre: the site polygon's centroid in EPSG:32610.
- Size: a 6 km square, snapped to the tile's 60 m grid, so that:
  - 10 m bands are an exact 2 x 2 mean;
  - 60 m bands are exact 3 x 3 repeats, as in ADR 0013.
- Scored area: the central 254 x 254 pixels at 20 m (5.08 km), the unit of the held-out test.
  The outer ring only gives the model's local filters their context.

**Pixels.**
- **Source.** All 13 L1C bands, from Google's public mirror.
- **Product.** The site-day's scene is the one whose footprint holds the whole window. Ties go
  to the first scene id.
- **No data.** A pixel with a digital number of 0 in any band is no data, marked before any
  offset.
- **Reflectance.** `(DN + RADIO_ADD_OFFSET) / QUANTIFICATION_VALUE`, read from each product's
  metadata. It is floored at 0.0001, the lowest value the old baselines could hold.
- **Partial windows.** A window with more than 1% no data in its scored area is listed but
  not scored.

**Clear share per window.**
- **Model.** The share of scored pixels it calls clear.
  - The weights are `data/processed/s2cloud/cloud-model.pkl`, sha256
    `da8c9552b6d606095a71198961cfffa41cdbe738f49a2c3ab8a97bb6b5eed3f0`.
  - The weights are not retrained or retuned.
- **Sen2Cor.** One minus the share of SCL classes 3, 8, 9 and 10, as in ADR 0013.
  - The SCL comes from Earth Search `sentinel-2-c1-l2a`, matched on platform, tile and sensing
    time from the product name.
  - Where that collection has no match (most of 2022), the older `sentinel-2-l2a` is used and
    labelled.
  - SCL class 0 is no data.
- **Tile rule.** The site-day's `valid_frac` in the overpass table, reported alongside.
- A window is called usable when its clear share is at least 0.7 (`min_valid_frac`).

**Intervals.** A 90% percentile bootstrap that resamples acquisition days, 2,000 replicates,
seed 20261031. The five sites on one day share the same weather, so days, not site-days, are
the independent units.

**Reference values.** These come from the published held-out windows
(`reports/validation/s2-cloud-model/*.windows.csv`, all 1,095 patches, Sen2Cor masks from the
dataset):
- **R1 = 5.8%.** P(model calls unusable | Sen2Cor clear share >= 0.99), over 243 patches.
- **R2 = 8.7%.** P(model calls usable | Sen2Cor clear share < 0.3), over 230 patches.

These two rates, unlike raw agreement, do not depend on how cloudy a year was.

### Criteria (all must hold)

1. **Reflectance scale.** On windows that Sen2Cor calls at least 99% clear, the median band
   12 reflectance of Sen2Cor water pixels (SCL class 6) is between -0.02 and 0.03. Read
   without the offset, it would be near 0.1.
2. **Clear passes kept (cost side).** P(model unusable | Sen2Cor >= 0.99) on the pilot
   windows is at most R1 + 10 points, that is 15.8%.
3. **Cloudy passes rejected (the error ADR 0013 protects against).** P(model usable |
   Sen2Cor < 0.3) is at most R2 + 10 points, that is 18.7%.
4. **No Sentinel-2C effect.**
   - The measure: the mean of (model clear share − Sen2Cor clear share), taken on Sentinel-2C
     windows and on Sentinel-2A and 2B windows.
   - The rule: the two means differ by at most 0.05.
5. **No fixed false clouds.**
   - The sample: windows Sen2Cor calls at least 99% clear.
   - For each pixel, count how often the model calls it cloud or shadow on those days.
   - At every site, at most 1% of the scored area is flagged on more than 20% of those days.
   - At every site, at most 5% of the site polygon is flagged on more than 20% of those days.
6. **Blind look by eye.**
   - **The draw.** At random (seed 20261031):
     - up to 8 windows where the model says usable and Sen2Cor does not;
     - up to 8 where Sen2Cor says usable and the model does not;
     - 4 where both say usable;
     - 4 where both say unusable.
   - **The thumbnails.**
     - True colour (bands 4, 3, 2), linear stretch from 0 to 0.3 reflectance.
     - The scored area is outlined.
     - They are shuffled and numbered.
   - **The labels.** Each is labelled usable (at least about 70% of the scored area clear) or
     not, before the key is opened.
   - **The rule.**
     - On the disagreements, the model matches the eye at least as often as Sen2Cor does.
     - On the agreements, at most 1 of 8 contradicts the eye.

Point estimates decide criteria 2 to 4. Their 90% ranges are reported beside them.

### What follows

- **All six hold.** The model's per-site clear share may replace the tile rule in `valid_frac`,
  and per-site usable-pass counts under the three methods may be published (ADR 0013), as
  descriptive figures.
- **Criterion 5 fails at some sites only.** Those sites use the Sen2Cor share instead; the
  others use the model.
- **Any other criterion fails.**
  - The model does not decide which pilot passes count.
  - `valid_frac` moves to the per-site Sen2Cor share instead. In the held-out test, Sen2Cor
    beat the tile rule on both errors:
    - too-cloudy windows counted usable: 35.7% against 36.9%;
    - clear windows thrown away: 9.2% against 26.2%.
  - Sen2Cor needs no new software. s2cloudless scored better (30.3%, 3.4%), but would need a
    new dependency and band 10.
  - The model's numbers stay a method check only.

## Results

To be filled in after the run, with the code version and the files under
`reports/validation/s2-cloud-recent/`.

## Decision

To be filled in after the run.

## Consequences

To be filled in after the run.
