# 0024: CO2 plumes are counted near each landfill, and the count is review-only

- **Status:** accepted
- **Date:** 2026-11-25

## Context

0019 decided that CO2 is shown as reported, or as a count of plumes found, and never modelled.
This record says how the count is made.

Carbon Mapper publishes CO2 plumes in the same list as methane plumes (`plume_gas=CO2`), and it
publishes the scenes it searched for CO2 in their own collections (`l2b-co2-…`), apart from the
methane scenes. So both halves of "searched N times, found M" can be read from its public lists.

What the lists hold, checked live on 2026-11-25:

| | Count |
|---|---|
| CO2 plumes in the wider box, all years | 92, every one tagged Energy Industries (1A1) |
| CO2 plumes in the registry's box since August 2022 | 27, every one tagged Energy Industries (1A1) |
| CO2 scenes in that box and window | 399 |
| Landfills covered by a CO2 scene on at least one day | 52 of 52 (2 to 41 days each, 903 landfill-days) |
| CO2 plumes on a landfill's outline or within 500 m, in the window | 0 |

The nearest CO2 plume to any landfill in the window starts about 1 km away, and 21 start within
5 km of one, in three clusters. In the earlier years of the list, one plume from 2017 lies within
500 m of a landfill.

The few CO2 scenes that state a detection limit put it at tens of tonnes of CO2 an hour. The
largest biogenic CO2 figure a landfill here reported to EPA for 2023 works out to under five
tonnes an hour. A landfill's engine or flare is likely too small for this search to see.

## Decision

1. **Two counts per landfill and year**, written as `site_metrics` rows of kind `observed`:
   `cm_co2_passes`, the days on which a CO2 scene covered the landfill, and `cm_co2_plumes`, the
   CO2 plumes that start on its outline or within 500 m.
2. **The same geometry as methane.** "Covered" is at least 80% of the outline inside the scene
   (`coverage.min_coverage_frac`), same-day scenes count once, and "beside" is
   `attribution.buffer_m`.
3. **A count is nearness, not attribution.** A plume is counted whatever sector tag it carries,
   and a plume beside two landfills counts for both. The step reports the tags of the plumes it
   counted. No plume is assigned to a landfill and nothing is estimated from a count.
4. **Zero means searched.** A year with a pass gets both counts, so a zero there reads "searched,
   none found". A year with no pass gets no row, which the pages show as not searched. A plume in
   a year with no listed pass keeps its count, with no pass count beside it.
5. **The same window as methane:** from `ingest.start` (August 2022).
6. **The scene collections are read from the API at each pull** and written into the pull's
   manifest, because each new processing version gets a new collection.
7. **CO2 pulls are a separate raw source.** They live under `data/raw/carbonmapper-co2/`, which no
   methane step reads, and their only output is `interim/site_metrics/carbonmapper-co2.parquet`.
   A pull whose plume list holds any other gas stops.
8. **The counts are review-only for now.** Their source is its own entry in
   `config/data_terms.yaml`, unconfirmed, so every row is restricted. Whether the display terms
   reported on 2026-11-08 also cover CO2 counts has not been asked. The owner asks Carbon Mapper;
   until then no count, and no CO2 section, reaches the public site.
9. **The pull is run by hand** (`mw ingest carbonmapper-co2`, or `--offline` to recount after the
   registry changes). It is not part of the scheduled run.

## Options turned down

- **Use the methane scenes as the denominator.** A scene searched for methane is not always
  searched for CO2, and the CO2 collections say which were.
- **Count only plumes tagged as waste.** None is, and a tag is Carbon Mapper's judgement. Counting
  everything nearby and saying so is plainer than a filter that would always return zero.
- **Reuse the `carbonmapper` source.** Its rows are display-only, and a later change that shows
  display-only measures in public would then release CO2 counts whose terms nobody has checked.
- **Add the pull to the scheduled run now.** A failed step marks the whole run as failed. The
  counts change slowly, so the methane run is not put at risk for them.

## Consequences

- Every landfill's page in a review copy gains a section with its yearly counts. Today every
  count of plumes is zero, and the page says a zero does not mean no CO2.
- The counts depend on each landfill's outline, so they are recounted when the registry changes.
- If a count ever stops being zero, the page shows a number with no sector beside it. The step's
  own report names the tags; showing them on the page is left until there is something to show.
