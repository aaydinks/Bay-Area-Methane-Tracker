# 0019: Measures beyond the methane estimate: one table, and no CO2 model

- **Status:** accepted
- **Date:** 2026-11-19

## Context

The project owner asked for CO2 and other measures per landfill, beside the methane estimate.

Nothing in the pipeline carries a gas. Rates are plain kg/hr, a pass is keyed by site, instrument
and day, and the step that builds detections adds up every plume attributed to a site. A CO2 plume
placed in the same folder would be added into the methane rate without any error.

What the data can support, checked live on 2026-11-19 over the two regions of 0018:

- **Carbon Mapper has no landfill CO2 here.** It lists 92 CO2 plumes in the box, and none is tagged
  as waste. Its CO2 product is aimed at power plants and cement works.
- **EPA's reports hold more than methane, for some sites.** The project already downloads every
  row for each matched facility and then keeps only landfill methane. The rows it drops are
  combustion figures (subpart C): CO2, biogenic CO2, N2O and a little methane. In 2023 only 7 of
  the 23 reporting landfills in the two regions filed a combustion report. Gas burnt in engines
  appears mostly as biogenic CO2 (Kiefer Landfill, 2023: 40,518 t CO2e).
- EPA's gas codes: 1 CO2, 2 CH4, 3 N2O, 8 biogenic CO2.

## Options considered

1. **Add a gas to every table and to the model.** It touches the pass key, the detections, the
   model inputs, the estimates, the database keys and every public view. It would also need
   detection curves and priors for CO2 that do not exist. Rejected: a large risk to the validated
   methane path for a gas no instrument here sees at landfills.
2. **Convert methane to CO2-equivalent only.** Cheap, but it adds no new information.
3. **One long table for everything that is not a methane estimate** (chosen).

## Decision

- **A new table, `site_metrics`.** One row per site, measure, period and source, with:
  - a number or a text value, and a unit;
  - `kind`: `reported` (an operator or agency says so), `observed` (the project counted it in public
    data) or `context` (describes the surroundings, not the landfill);
  - `confirmed`, and the same `restricted` and `display_only` flags the other tables use.
- **A catalogue, `config/metrics.yaml`.** Each measure has an id, label, unit, kind, source and the
  caveat shown beside it. The catalogue is published as a table, so its labels pass the wording
  check like any other page text.
- **The methane model and its tables get no gas column.** Nothing that has been validated changes.
- **CO2 is never modelled.** It appears in two ways only:
  - *Reported:* EPA's per-gas rows, in t CO2e as EPA publishes them, labelled as combustion. A site
    with no combustion report shows "not reported", never zero.
  - *Observed:* a count per site and year of Carbon Mapper CO2 plumes inside the outline or its
    buffer, with the plain statement that the search ran. Carbon Mapper CO2 pulls are a separate
    raw source in their own folder, so they cannot reach the methane plume or detection tables.
- **The existing operator comparison is unchanged.** `operator_reports.reported_ch4_t` stays as it
  is for the methane comparison; the per-gas rows are additional.
- **Other feeds use the same table:** site operations (EPA's landfill program database and
  CalRecycle), nearby air monitors, and CalEnviroScreen scores. Population keeps the table it
  already has. Dated regulatory records keep the checks tables of 0010.

## Consequences

- A new measure is a catalogue entry and an ingest step, not a schema change.
- Reported CO2 will be missing for most sites. The pages must say why (no combustion report), so a
  gap is not read as "none emitted".
- Only facilities matched to a site are pulled from EPA, so each new site needs a hand-checked match
  or a recorded "no EPA report".
- Carbon Mapper's terms were confirmed verbally for methane figures. Whether they cover CO2 plume
  counts is not known; the counts stay restricted until the owner has asked.
- **Still to check:** the column names in EPA's landfill program file; which years each feed covers.
