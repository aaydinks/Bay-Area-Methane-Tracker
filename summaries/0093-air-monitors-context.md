# PR #93: The air near each landfill, from EPA's monitors

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/93)

## In one sentence

A landfill's page can now name the nearest official air monitor for fine particles and for
nitrogen dioxide, with its distance, its year and its yearly average, as plainly labelled
context that is never attributed to the landfill.

## Why it was needed

The plan lists four kinds of information beside the methane estimate. Three were in place:
gases the operator reports, how the landfill is run, and the state's score for the area. The
fourth was the air nearby. Air agencies run monitors that measure the air people breathe, and
they report the readings to the US Environmental Protection Agency (EPA), which publishes them.

A monitor near a landfill also picks up traffic, wood smoke and wildfires, so a reading there
says nothing about the landfill. The project's rule for this kind of figure is that it is
context: shown in its own section, under one fixed sentence, never ranked and never compared
with a legal limit.

## What it adds

- **A new pull, `mw ingest aqs`.** It downloads EPA's yearly summary files for five years
  (2021 to 2025 today). No account is needed. If EPA changes a file's layout the pull stops
  and leaves nothing behind.
- **Ten figures per landfill.** For fine particles (PM2.5) and for nitrogen dioxide (NO2):
  the nearest monitor, its distance from the landfill's outline, the year of its figure, the
  number of days measured in that year, and the average over that year.
- **Only full, certified years.** A year counts when EPA marks it complete and the agency that
  runs the monitor has certified it. Each monitor is read at its newest such year.
- **A 25 km limit.** A monitor farther away is not listed, and the page reads "none close
  enough". The limit is one line in `config/project.yaml`.
- **The page section.** The figures sit in "The area around this landfill", which now words
  each source its own way. Distances and averages carry their units.
- **A written decision** (`docs/decisions/0027-air-monitors-context.md`) with the options
  turned down.

## What we learned

- **The Bay Area's recent years are missing from EPA's files.** The 2025 file has no
  fine-particle or NO2 rows for the nine Bay Area counties, and few of their 2023 and 2024 rows
  are certified. So most Bay Area figures are from 2022, while the North Valley's are mostly
  from 2025. The files do not say why. One year could not serve every landfill, which is why
  the page gives the year beside each figure.
- 41 of the 52 landfills have a fine-particle monitor within 25 km, 42 have an NO2 monitor, and
  9 have neither.
- The nearest monitor is typically about 11 km away. Only 18 landfills have a fine-particle
  monitor within 10 km, so for most landfills this is a rough picture of the wider area.
- Monitors differ in how often they measure. For 2 landfills the fine-particle figure rests on
  30 measured days in the year, which the page shows.
- EPA's terms are open, so these figures are not held back the way the state's scores are.

## Still to do

- Nothing changes on the public site until a newer copy is made public. Then the five studied
  landfills' pages gain this section. The public list of sources gains a line for EPA's Air
  Quality System, and the footer its credit, as soon as a copy is loaded.
- 18 landfills with a figure still have a placeholder outline, so their distances may shift
  once the outline is drawn.
- The pull is run by hand. EPA refreshes its files in June and December, so it is worth
  rerunning then.
- Find out why the Bay Area's 2023 to 2025 years are uncertified or missing in EPA's files.
- This was the last source of step 16. Regulatory records, the state's permit figures and the
  counts of people nearby are separate, later work.
