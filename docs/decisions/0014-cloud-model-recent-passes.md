# 0014: Checking the cloud model on recent pilot passes

- **Status:** accepted
- **Date:** 2026-10-31 (criteria); 2026-11-07 (result)

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

One run, `s2-cloud-recent-20261107T010417Z`, from commit `422d14a`, clean tree. The files are
in `reports/validation/s2-cloud-recent/`.

**Order.**
- **Criteria first.** The criteria were committed on Oct 31 (`9367577`), before any pilot
  window was scored.
- **Commits between the criteria and the run.** These changed only how failed reads are
  retried and reported, not what is measured.
- **The blind labels.** The 24 thumbnails were labelled by eye before the key or any result
  was opened.
- **Changes after the run.** None changed a number:
  - the report no longer lists per-site counts when the check fails (see Consequences);
  - the two thumbnail sheets were saved again as JPEG to stay under the repository's 1 MB file
    limit.

**Windows.**
- 501 site-days on 157 days: 203 Sentinel-2C, 202 2B, 96 2A, all baseline N0511.
- 493 were scored.
- **2 read errors.** On 2025-08-21 the overpass table merges a Sentinel-2A and a 2B pass. The
  2B scene was chosen, as the rule says, for Newby Island and Shoreline. That product is missing
  from Google's mirror.
- **6 partial windows.** These are at swath edges.
- **18 without Sen2Cor.** The report counts 20, including the two read errors.
  - 2 are at swath edges.
  - 16 come from a matching error, found after the run (see "Found after the run").

| Criterion | Result | 90% range | Limit | |
|---|---|---|---|---|
| 1. Band 12 of Sen2Cor water on clear windows | 0.014 (1.77 million pixels) | | -0.02 to 0.03 | pass |
| 2. Model unusable when Sen2Cor >= 99% clear | 0.0% of 261 windows (held-out 5.8%) | 0.0 to 0.0 | 15.8% | pass |
| 3. Model usable when Sen2Cor < 30% clear | 2.9% of 140 windows (held-out 8.7%) | 0.6 to 6.1 | 18.7% | pass |
| 4. Sentinel-2C minus 2A/2B, mean (model − Sen2Cor) clear share | +0.015 | −0.012 to +0.042 | ±0.05 | pass |
| 5. No fixed false clouds | fails at all five sites (below) | | 1% of area, 5% of site | **fail** |
| 6. Blind look by eye | disagreements: model right 12 of 16, Sen2Cor 4 of 16; agreements against the eye: 0 of 8 | | model >= Sen2Cor; at most 1 | pass |

Criterion 5. These are the pixels the model flags as cloud or shadow on more than 20% of
Sen2Cor-clear days. Each site polygon is still the provisional 500 m circle around its
CalRecycle point. The right-hand column is from the false-cloud map laid over a clear true-colour
image:

| Site | Sen2Cor-clear days | Share of scored area | Share of site circle | What they are |
|---|---|---|---|---|
| Acme Fill | 45 | 6.58% | 2.24% | a long dark basin to the north-east and the edges of a pond to the south-west (called shadow); refinery tanks and roofs |
| Newby Island | 47 | 23.24% | 4.64% | rooftops to the east; the dark rectangular ponds to the south (called shadow); the edges of the salt pond to the north-west |
| Potrero Hills | 44 | 1.01% | 3.72% | the bright active area at the east end of the landfill; a few small ponds |
| Shoreline | 44 | 14.55% | 1.73% | rooftops of the built-up area to the south |
| Sonoma Central | 81 | 0.85% | 10.29% | two patches on the landfill surface and a bright roof at its east edge |

**What it shows.**
- **No problem with the newer images themselves:**
  - the -1000 offset is handled;
  - the model treats Sentinel-2C like 2A and 2B;
  - on 2025 passes its calls on clear and cloudy windows agree with Sen2Cor as closely as on
    the test images.
- **What fails is the surface risk named in the Context, in a wider form.** On clear days the
  model keeps flagging the same places:
  - bright rooftops and landfill surfaces, as cloud;
  - dark ponds and basins, as shadow.
  - This seldom changes a whole window's call (criterion 2).
  - But it is the error the pre-registered rule does not allow, and at Sonoma Central it covers
    a tenth of the circle around the site.
- **How often they agree.** The model and Sen2Cor agreed on whether a window was usable for 455
  of 477 windows. The tile rule and Sen2Cor disagreed on 76.

### Found after the run

Both findings came from checking the result before publishing it. Neither changes the run's
verdict. Both are reported here with their numbers.

**1. The eye check could not see thin cirrus.**
- **The windows.** Sen2Cor set aside 13 windows the model kept. In all 13, most of the
  unusable pixels were Sen2Cor's thin-cirrus class (10).
- **The evidence.** Band 10, the cirrus band, read 0.003 to 0.014 on average over those windows,
  2 to 10 times its level on clear days (about 0.0013).
- **Why the eye missed it.** Thin cirrus hardly shows in true colour. All 8 such windows in the
  eye check looked clear, so criterion 6 was scored with a looser idea of "clear" than the
  project uses: thin cloud counts as unusable.
- **What follows.**
  - The eye check does not show that Sen2Cor was wrong on these windows. It may well have been
    right.
  - If it was, the model counts some thin-cirrus passes as usable. That is the error the project
    guards against most.
  - Criterion 6 stands as scored, but its "model 12, Sen2Cor 4" says less than it seems.

**2. Sen2Cor was matched to an empty granule for 16 windows.**
- **The cause.** For seven Sentinel-2C dates on tile 10SEH, Earth Search holds two L2A granules
  of the same pass. The code took the first, which was 72 to 97% empty. Those 16 windows had no
  Sen2Cor share and were left out of criteria 2 to 6.
- **The fix.** The code now takes the fullest granule. Only the Sen2Cor layer was read again
  for these windows, about 85 to 120 KB each.
- **Criteria 2 to 5 with the 16 windows included** (a sensitivity, not the result):

| Criterion | As run | With the 16 windows |
|---|---|---|
| 2. Model unusable when Sen2Cor >= 99% clear | 0.0% of 261 | 0.0% of 265 |
| 3. Model usable when Sen2Cor < 30% clear | 2.9% of 140 | 2.7% of 149 |
| 4. Sentinel-2C minus 2A/2B | +0.015 | +0.009 |
| 5. Acme Fill: area / circle | 6.58% / 2.24% fail | 6.72% / 2.50% fail |
| 5. Newby Island | 23.24% / 4.64% fail | 23.24% / 4.64% fail |
| 5. Potrero Hills | 1.01% / 3.72% fail | **0.92% / 3.26% pass** |
| 5. Shoreline | 14.55% / 1.73% fail | 14.55% / 1.73% fail |
| 5. Sonoma Central | 0.85% / 10.29% fail | 0.90% / 10.64% fail |

- **What it means.** With correct matching, Potrero Hills would have passed criterion 5. Under
  the rule above it would then have used the model, while the other four used Sen2Cor.

## Decision

The check does not hold, so the pre-registered fallback applies. The verdict is the one from
the single run; the findings above are reported, not used to change it.

- **Which passes count.** The model does not decide this at any pilot site.
- **`valid_frac`.** For Sentinel-2 passes it moves from the tile figure to the **per-site
  Sen2Cor share**, at all five sites. Sen2Cor beat the tile rule on both errors in the held-out
  test.
- **The tile figure.** It is kept beside the new share so the two can be compared.
- **What is not published.** The model's per-site usable-pass counts are not published as a
  result. Its numbers here stay a method check, shown as failed.
- **No re-run.** The test is not re-run with new settings or limits. A model change must:
  - come under a new ADR;
  - report both runs.

  A model change could mean training examples of roofs, ponds and landfill surfaces, or a
  per-site mask of pixels that are flagged on clear days again and again.
- **Potrero Hills stays on Sen2Cor.** Moving it to the model would need a new ADR, which is
  not recommended:
  - it passes criterion 5 only narrowly, 0.92% against a 1% limit;
  - the thin-cirrus finding suggests the model may count thin-cirrus passes as usable;
  - one rule for all five sites keeps the results comparable.

## Consequences

- **Pixels needed.** Applying the Sen2Cor share to all 2022-08 to 2026-10 passes needs only
  the SCL layer per window, not the 13 L1C bands. So the bulk L1C download is not needed for
  `valid_frac`. The two costs:
  - **An L1C window downloads about 35 MB**, because Google's mirror stores the bands as tiled
    JPEG 2000.
  - **An SCL window downloads about 0.1 MB.** A whole SCL tile is about 1.4 MB, in 512-pixel
    blocks, and a window touches at most 4 of its 121 blocks.
- **Thin cirrus.** Sen2Cor's thin-cirrus class counts as unusable in the per-site share, as in
  ADR 0013. Whether such thin cirrus matters for plumes of 2 t/hr or more is not tested here.
- **No Sen2Cor share.** A pass with no Sen2Cor share keeps the tile figure, and that is marked.
  This covers no L2A match, no data over the window, or a product missing from a mirror.
- **Masking before detection.**
  - ADR 0013's Claim 2 allowed the model mask before Sentinel-2 detection.
  - This check shows it would mask parts of the landfill on clear days: 10% of Sonoma Central's
    circle and 4% of Potrero Hills'. That is where a plume starts.
  - So the model mask is not used before detection at the pilot sites without a new ADR.
- **What is published.** The check's own numbers are published as a method check:
  - one website row, `s2_cloud_recent`, with result "fail";
  - the per-site counts are left out.
- **Files kept.** The windows file keeps the per-window shares as evidence of the check.
- **Limits of the thumbnails.**
  - The eye labels are one person's reading of 24 thumbnails.
  - Four were close to the 70% line (5, 12, 14 and 19 in `eye-labels.csv`). Reversing all four
    would not change criterion 6.
  - Thin cirrus cannot be seen in them (see "Found after the run").
