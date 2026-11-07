# 0016: An instrument enters a fit only once its plume search has run

- **Status:** accepted
- **Date:** 2026-11-06

## Context

The persistence model counts every usable pass without an attributed plume as a non-detection:
the instrument looked and saw nothing (PLAN 6.2). That is true only if some plume search ran on
the pass. `mw model fit` took every instrument in `data/interim/detections.parquet`, and the
coverage step lists a pass for every scene in a catalogue, searched or not.

Sentinel-2's own plume search (source `s2-local`, PLAN phase 3) has never run on the pilot
passes. A default fit would therefore have read 1,293 Sentinel-2 passes (Sen2Cor's clear share
over each site, ADR 0014) as "looked and saw nothing". The first real fit,
`fit-20261107T010105Z`, avoided this only because the Sentinel-2 rows were dropped by hand.

Where each instrument's plumes come from today:

| Instrument | Plume source | Plume table |
|---|---|---|
| Tanager-1, aircraft | Carbon Mapper | `plumes/carbonmapper.parquet` (614 plumes) |
| EMIT | Carbon Mapper republishes EMIT plumes with rates; NASA's own complexes have none and are only listed | `plumes/carbonmapper.parquet` (20 EMIT plumes) |
| Sentinel-2 | the project's own search, `s2-local` | none |

## Options considered

1. **A flag in config** (`plume_search_run: true` per instrument). Simple, but a person has to
   remember to set it, and nothing checks it against the data. Forgetting is the failure that
   the first fit only just avoided.
2. **At least one plume from a searching source.** Read from the data, so it can't drift. But a
   search that ran and found nothing looks the same as no search. For Sentinel-2 at these sites
   that is a likely outcome, because its detection curve is centred near 7 t/hr (ADR 0015).
   Sentinel-2 would then stay out forever.
3. **A plume table from a searching source exists, even if empty** (chosen). Config names the
   sources whose search covers each instrument's scenes. The data says whether one of them has
   run.
4. **A per-pass record of which scenes were searched.** The exact answer. It needs every search
   step to log its scenes, and Carbon Mapper publishes no such list. Left as a follow-up.

## Decision

- Each instrument in `config/instruments.yaml` lists its `plume_sources`:
  - Tanager-1 and aircraft: `carbonmapper`;
  - EMIT: `carbonmapper` and `emit-v2`;
  - Sentinel-2: `s2-local`.
- A real fit (`mw model fit`) takes an instrument's passes only if
  `data/interim/plumes/<source>.parquet` exists for at least one of its sources. A search step
  writes its table even when it finds nothing, as the Carbon Mapper ingest already does. So an
  empty table means "searched, nothing found", and a missing one means "not searched".
- `--include-unsearched <instrument>` keeps an unsearched instrument on purpose. It is named
  per instrument and can be repeated.
- The run manifest records:
  - `instruments_left_out`: reason, sources, usable passes and detections per instrument;
  - `included_unsearched`;
  - `sites_left_out`: sites whose only passes were left out;
  - `plume_tables`: rows per table.

  The saved `<run_id>-detections.parquet` holds only the rows the fit used.
- The run manifest travels with every publication (`runs` table). `mw publish build` prints
  the model's instruments and what was left out. Each site page names the instruments in the
  estimate and any left out, and why. The methods page states the rule.

## Consequences

- A default fit now leaves Sentinel-2 out with no hand editing. The first fit's rebuild recipe
  no longer needs its "drop the Sentinel-2 rows" step.
- When the Sentinel-2 search lands and writes `plumes/s2-local.parquet`, Sentinel-2 enters the
  next fit by itself. That is right only if the search covered every usable pass. A search over
  some passes (one year, say) would still let every pass in. Before the first such fit, either
  run the search over every pass or add the per-pass record (option 4).
- The plume tables are read when the fit runs. `mw coverage build` must run after the newest
  plume table, or the detections won't include its plumes. `mw refresh` runs the steps in that
  order.
- The same question applies within an instrument. EMIT passes come from NASA's granule list,
  while EMIT plumes with rates come from Carbon Mapper. If Carbon Mapper did not process every
  EMIT granule, some EMIT passes count as searched when they were not. This has not been
  checked.
- `mw repair run` and the real hold-out check (`mw validate holdout`) read the same detections
  table and still take every instrument. They should use the same selection before their next
  real run.
- The official run `fit-20261107T010105Z` predates this record. Its manifest has no
  `instruments_left_out`, so its pages say only that Sentinel-2's passes are not part of the run.
