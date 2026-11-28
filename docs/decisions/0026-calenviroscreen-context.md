# 0026: CalEnviroScreen is shown as context for the census tracts around a landfill

- **Status:** accepted
- **Date:** 2026-11-28

## Context

0019 lists "CalEnviroScreen scores" among the measures that describe a landfill's surroundings,
and 0020 sets how such context is worded: in its own section, under one fixed sentence, never
attributed to the landfill and never ranked. 0020 left one thing to check: which CalEnviroScreen
version is final.

CalEnviroScreen is the state's screening tool. The Office of Environmental Health Hazard
Assessment (OEHHA) gives every census tract a score that combines measures of pollution with
measures of the people living there, and publishes each tract's percentile among California's
tracts. What was checked live on 2026-11-28:

- OEHHA released the final CalEnviroScreen 5.0 on 2026-07-01. Version 4.0 is superseded.
- Its data download is the state data portal's dataset `calenviroscreen-5-0`. The portal lists
  one geodatabase, `calenviroscreen50results_f_070126.gdb.zip` (about 22 MB, last modified
  2026-10-01).
- The geodatabase has one layer, `CES5_final_results`, with 9,106 census tracts on 2020 Census
  outlines. Each carries the overall percentile, the Pollution Burden percentile, the Population
  Characteristics percentile and the tract's population (2024 five-year ACS).
- 73 tracts have no overall score. OEHHA's data dictionary says a missing value usually means no
  population was reported or the estimate was unreliable.
- One of the pollution indicators counts solid waste sites near populated blocks. For the 52
  registry sites, the tract a landfill sits in has a median Solid Waste percentile of 93. A
  landfill is often part of its own tract's score.
- **No terms of reuse are stated.** The portal reads "License not specified". OEHHA's conditions
  of use (last updated 2020-07-22) cover liability and say nothing about reuse. OEHHA's questions
  page says the data "are publicly available for download".

## Decision

1. **One hand-run pull, `mw ingest calenviroscreen`.** It asks the data portal for the dataset,
   takes its one geodatabase, checks that the layer still has the columns used here, and only
   then writes the file to its own raw folder, `data/raw/calenviroscreen/`. Two geodatabases, none,
   or a changed layout stop the pull. `--offline` rebuilds the measures from the newest file,
   which is needed after an outline changes.
2. **A landfill's own tract is the one that holds the largest part of its outline.** The page
   names the tract by its Census number, so a reader can look it up.
3. **Eight measures per landfill, as published.** The tract and the number of people living in
   it; that tract's overall, Pollution Burden and Population Characteristics percentiles; the
   number of tracts with any part within 1 km of the outline; and the lowest and the highest
   overall percentile among those tracts.
4. **Nothing is averaged.** A landfill usually sits in a large tract with few homes, and the
   neighbours can live in another tract with a very different score. The lowest and highest
   show that spread without the project inventing a figure the state does not publish.
5. **No score is not zero.** A tract without a score gives no percentile row, and the page reads
   "no score".
6. **The period is the version, `5.0`.** The file is one edition of a tool, not a figure for
   each year.
7. **A provisional outline says so.** Rows for a landfill whose outline is still a placeholder
   circle are marked unchecked, and the page says the tract may change once the outline is drawn.
8. **Shown as context, under 0020.** The page gets a section "The area around this landfill"
   that opens with the fixed sentence: the figures describe the area and are not attributed to
   the landfill. The wording check now fails any page that shows a context section without that
   sentence. No colour, no ranking of landfills, no comparison with a threshold. The caveat on
   the overall percentile says a landfill can be part of its own tract's score.
9. **Review copies only, until the terms are confirmed.** With no stated terms of reuse the
   source is entered as unconfirmed, so its rows are restricted and a public build shows no
   section and no figure. The owner asks OEHHA; one line in `config/data_terms.yaml` opens it.

## What the first pull holds

| | Count |
|---|---|
| Registry sites whose outline lies on a census tract | 52 of 52 |
| Sites whose own tract has an overall score | 52 |
| Different tracts those sites sit in | 44 |
| Sites whose outline crosses more than one tract | 21 (for 10, the largest part is under 90%) |
| Sites with a provisional outline, marked unchecked | 23 |
| Tracts within 1 km of an outline | 1 to 13, median 3; one tract only for 13 sites |
| Sites where the nearby tracts differ by 25 percentile points or more | 24 (by 50 or more: 4) |

## Options turned down

- **A population-weighted average of the tracts nearby.** It would be a new figure that OEHHA
  does not publish, and an average hides the spread that matters.
- **The tract at the landfill's centre point.** For an outline that crosses several tracts the
  centre can fall in one that holds little of the landfill.
- **Every indicator behind the score (23 of them).** Too much for a landfill's page, and several
  are medical statistics that would read as a claim about the landfill. The page links to the
  source for a reader who wants them.
- **The state's "disadvantaged community" designation.** It is a separate decision by CalEPA
  with its own list and date, not a column of this file. It can follow as its own source.
- **Reading the tract outlines from the Census and the scores from OEHHA's spreadsheet.** Two
  downloads that must agree on the tract vintage. The geodatabase carries both.
- **Treating the data as open because it is a public download.** The project's rule is that
  terms are confirmed, not assumed.

## Consequences

- No new dependency and no database migration: the measures table and the catalogue of 0019
  already take context rows.
- The pull is not part of the twice-weekly run. The file changes only with a new version. The
  measures file stays in place between runs, so every later copy carries it.
- The step must be rerun (`--offline`) after an outline changes, like the CO2 counts.
- The website's list of sources is shared by every copy, so the public list gains a line for
  this source, marked "to confirm", and the footer gains its credit. No figure from it appears
  in public until the terms are confirmed.
- A new CalEnviroScreen version is a code change: the dataset name and the version are fixed in
  the module, so figures from two versions are never mixed.
- Still to do by the owner: ask OEHHA (CalEnviroScreen@oehha.ca.gov) whether the scores may be
  republished with credit.
