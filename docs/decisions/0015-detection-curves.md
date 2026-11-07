# 0015: Detection curves per instrument and the emission floor

- **Status:** proposed
- **Date:** 2026-11-06

## Context

The persistence model (PLAN section 6, ADR 0005) needs, for each instrument, a detection curve
POD(q) = Phi((ln q - ln q50) / w) with a rate `q50` (kg/hr) where half of plumes are seen and a
width `w`, plus a fallback measurement error `meas_sigma_log`. It also needs the emission floor
`q_min`, which PLAN section 6.1 puts near the most sensitive instrument's 10% detection point.
None of these had a source, so no fit on real data could run. This record was planned as ADR
0003 and is written here as 0015.

The instruments in the pass table are Carbon Mapper's Tanager-1 satellite, Carbon Mapper's
aircraft (the Global Airborne Observatory, GAO, and AVIRIS-3; 18 passes, 14 of them over Newby
Island), NASA's EMIT, and Sentinel-2.

Every figure below was read in the source itself (table, section or figure named). A probit
needs two points on the curve. Where a source gives only one, the width is borrowed from another
instrument and the row says so. Nothing here is fitted to this project's data, so every value
stays `confirmed: false` and every fit that uses them is stamped provisional.

## Sources

| Instrument | Source | Figure as published | Conditions |
|---|---|---|---|
| Tanager-1 | Duren et al., "Expansion of the Carbon Mapper tiered observing system", IWGGMS-22 slides, slide 3 ([PDF](https://atmosphere.copernicus.eu/sites/default/files/custom-uploads/IWGGMS%2022%20event/Day1/1.06_Duren.pdf)); not peer reviewed | 90% POD at 200 kg/hr in Standard sensitivity mode; about 100 kg/hr in Maximum mode; "minimum detection 50 kg/hr" in a blind test | Fit to about 350 oil and gas plumes, wind at most 3 m/s, column precision at most 2% |
| Tanager-1 | Duren et al. 2025, AMT 18:6933, [doi:10.5194/amt-18-6933-2025](https://doi.org/10.5194/amt-18-6933-2025), Sect. 2.1 and 4.1 | Detection limits of 64 and 126 kg/hr; pre-launch goal of 90% POD at or above 100 kg/hr | 30 m pixels, 3 m/s wind, 25% albedo |
| Tanager-1, EMIT | Reuland et al. 2026, Nature 658:673-681, [doi:10.1038/s41586-026-11115-0](https://doi.org/10.1038/s41586-026-11115-0), abstract only | Built-for-purpose instruments: 92-100% detected, slope 0.83-1.00, 44% mean absolute percentage error. Repurposed instruments: 62-88% detected, 46% error | Year-long single-blind test, 481 releases of 9.5-1,183.7 kg/hr |
| EMIT | Ayasse et al. 2024, ES&T 58:21536, [doi:10.1021/acs.est.4c06702](https://doi.org/10.1021/acs.est.4c06702), Sect. "POD" and Fig. 1 | 90% POD at 1,060 kg/hr; the mass-balance detection limit, 244 kg/hr, sits at 2% POD | 3 m/s wind; Permian, Aug 2023; GAO flights at the same time as EMIT passes; 55 GAO plumes |
| Aircraft (GAO) | Ayasse et al. 2023, AMT 16:6065, [doi:10.5194/amt-16-6065-2023](https://doi.org/10.5194/amt-16-6065-2023), Sect. 3.4, Fig. 7 | 90% POD 45 kg/hr (2021) and 10 kg/hr (2022); 17-68 kg/hr across wind speeds | Controlled releases at about 3 km altitude; mean wind 2.5 m/s and albedo 24.5% (2021), 1.78 m/s and 42% (2022) |
| Aircraft (AVIRIS-NG) | Conrad et al. 2023, RSE 288:113499, [doi:10.1016/j.rse.2023.113499](https://doi.org/10.1016/j.rse.2023.113499), Sect. 4, Table 2 | 50% POD at 21 kg/hr and 90% at 33 kg/hr (8.1 and 16 kg/hr if partial detections count) | 3000 m altitude, 3 m/s wind at 3 m height; 143 non-blinded releases (Thorpe et al. 2016) |
| Aircraft (Carbon Mapper) | El Abbadi et al. 2024, ES&T 58:9591, [doi:10.1021/acs.est.4c02439](https://doi.org/10.1021/acs.est.4c02439), Tables 2 and 3 | Stage 1: 68% of 71 estimates within 50% of metered; smallest quantified 10.9 kg/hr; largest missed 6.6 kg/hr | Single-blind, Casa Grande AZ, Oct 2022, 3,050-3,230 m |
| Sentinel-2 | Gorroño et al. 2023, AMT 16:89, [doi:10.5194/amt-16-89-2023](https://doi.org/10.5194/amt-16-89-2023), Table 2 | Permian Basin in summer: 0, 0, 15, 52, 87, 97% detected at 1,500, 2,500, 5,000, 7,500, 10,000, 12,500 kg/hr | Simulated plumes (221 per level) on real scenes; mixed vegetated and bare ground |
| Sentinel-2 | Sherwin et al. 2023, Sci. Rep. 13:3836, [doi:10.1038/s41598-023-30761-2](https://doi.org/10.1038/s41598-023-30761-2), Results | 75% of satellite estimates within 50% of metered (all satellites pooled); smallest Sentinel-2 detection 1.4 t/hr | Arizona desert; 4.3 m/s wind on Sentinel-2 days |
| Sentinel-2 | Mateo-Garcia et al., arXiv:2511.21777v3 (preprint), "Detection limit on Sentinel-2 and Landsat" | 90% POD at 2.46 t/hr | Logistic fit to 2024 analyst-checked plumes, mostly arid and semi-arid basins |

## Decision

All curves are for a wind of about 3 m/s. z(0.9) = 1.2816 and z(0.02) = -2.0537 are standard
normal quantiles.

| Instrument | q50 (kg/hr) | w | How it was derived |
|---|---|---|---|
| Tanager-1 | 114 | 0.44 | 90% point 200 kg/hr (slides, Standard mode). No second point is published, so the width is EMIT's. q50 = 200 / exp(0.44 x 1.2816) |
| EMIT | 603 | 0.44 | Probit through 90% at 1,060 and 2% at 244: w = ln(1060/244) / (1.2816 + 2.0537); q50 = 1060 / exp(0.44 x 1.2816) |
| Aircraft | 28.6 | 0.353 | 90% point 45 kg/hr (GAO, 2021). Width from AVIRIS-NG: w = ln(33/21) / 1.2816. q50 = 45 / exp(0.353 x 1.2816) |
| Sentinel-2 | 7,070 | 0.312 | Least-squares probit on ln q through Gorroño's four points between 0 and 100% (Table 2, Permian, summer) |

Fallback measurement error, assuming lognormal error with no bias:

| Instrument | meas_sigma_log | From |
|---|---|---|
| Tanager-1 | 0.51 | 44% mean absolute percentage error (Reuland 2026, built-for-purpose group) |
| EMIT | 0.53 | 46% mean absolute percentage error (Reuland 2026, repurposed group) |
| Aircraft | 0.53 | 68% within 50% of metered (El Abbadi 2024) |
| Sentinel-2 | 0.46 | 75% within 50% of metered (Sherwin 2023, all satellites); the old 0.4 placeholder cited the same figure |

These matter only for a detection without its own error; every detection in the current pass
table has one.

**Emission floor.** `q_min` = 18 kg/hr, the 10% point of the aircraft curve:
28.6 x exp(-0.353 x 1.2816) = 18.2. It is recorded in `config/model.yaml` with its source and
`q_min_confirmed: false`, and `mw config check` keeps listing it until it is confirmed.

Choices between sources:
- Aircraft: the 2021 GAO point (45 kg/hr) rather than 2022 (10 kg/hr), because 2022 had very low
  wind over a bright desert. The darker 2021 surface is closer to a Bay Area landfill.
- Sentinel-2: Gorroño's mixed-vegetation case rather than the desert cases or the arid
  observational fit, because no Bay Area pilot site is desert.

## Consequences

- `mw model fit --allow-unconfirmed` can run on real data. Its output is stamped provisional
  until each curve is confirmed against controlled releases or the data.
- Below about 100 kg/hr only the aircraft can see anything. Acme Fill and Shoreline have no
  aircraft passes and Sonoma Central has one, so for those sites the share of time above the
  floor rests mostly on the prior. Expect wide ranges or `insufficient_data` there. Raising the
  floor to tighten them would be tuning to the answer; it is not done.
- PLAN section 6's sensitivity run (q50 x 0.5, 1 and 2) brackets most of the doubts below.

## Open doubts

- **Every test site is bright desert or Wyoming range.** No controlled release has been flown
  over a vegetated or urban scene for any of these instruments. Bay Area landfills are darker and
  more varied, so all four curves are probably optimistic.
- **Wind.** All figures are at about 3 m/s and the model has no wind term. At windier passes
  the curves overstate detection, which biases the emitting share low.
- **Aircraft curve is a hybrid.** It uses GAO's 90% point with AVIRIS-NG's width. AVIRIS-3,
  which flew 6 of the 14 Newby Island passes, has no published detection curve. Flight altitude
  for the Bay Area passes is not known; Conrad's curve moves the 90% point from 33 to 84 kg/hr
  between 3,000 and 8,000 m.
- **Tanager-1 is from conference slides.** The 200 kg/hr point is not peer reviewed. Whether each
  pilot pass was in Standard or Maximum mode is not known; Maximum mode would halve the 90% point.
  Duren 2025 pairs 64 kg/hr with Standard and 126 kg/hr with Maximum mode, which contradicts its
  own noise figures (12.09 against 6.11 mmol/m2); it looks transposed and is not used.
- **EMIT's width is applied to Tanager-1.** A curve as wide as EMIT's gives Tanager-1 about 3%
  POD at 50 kg/hr, while the blind test reports detections down to 50 kg/hr (mostly Maximum mode).
- **EMIT's curve is a probit through a Burr curve.** Ayasse fits a Burr distribution. Its Fig. 1
  10% contour at 3 m/s reads, by eye, near 400 kg/hr, against 343 from the probit, so the true
  curve may be narrower.
- **Published plumes go through review.** In El Abbadi 2024 the operator's quality check removed
  31 of 121 aircraft observations. The curve for published plumes is lower than for raw
  detections. `release_prob` stays 1.0 here; the planned sensitivity runs at 0.7 and 0.85 cover it.
- **Sentinel-2.** Gorroño's mixed-vegetation result (about 7 t/hr at 50%) is a simulation on one
  scene. The same scene in winter reached 82% at 1.5 t/hr, and the arid observational fit puts 90%
  at 2.46 t/hr. The plan says "~2 t/hr"; for vegetated scenes that is likely optimistic.
  Sentinel-2 is not in the first fit, because its plume search has not run.
- **Reuland 2026 was read in abstract only.** The group figures are not per instrument. Which
  instruments are in each group comes from the preprint supplement (Research Square rs-9110475),
  not checked against the published paper.
- **Error figures are pooled or group values,** and errors near the detection limit are biased
  high (Gorroño, Sherwin 2023). A single symmetric spread understates that.
