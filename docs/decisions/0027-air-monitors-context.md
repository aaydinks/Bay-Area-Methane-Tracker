# 0027: The nearest air monitors are shown as context, each at its own newest certified year

- **Status:** accepted
- **Date:** 2026-11-28

## Context

0019 lists "nearby air monitors" among the measures that describe a landfill's surroundings.
0020 sets how they are shown: the nearest monitor per pollutant with its name, its distance and
the period, none farther away than a limit set in config, no comparison with a standard, no
colour, no trend arrow. 0020 left one thing to check: whether EPA's files can be read without an
account.

EPA's Air Quality System (AQS) holds the readings that state and local air agencies take at
their regulatory monitors. What was checked live on 2026-11-28:

- **No account is needed.** EPA's AirData page of pre-generated files lists one file a year,
  `annual_conc_by_monitor_<year>.zip` (about 4 MB each). The 2025 file has 65,709 rows for the
  whole country: one per monitor, pollutant, way of summarising the year and treatment of event
  days.
- The page says the files are refreshed twice a year, "once in June to capture the complete
  data for the prior year" and once in December. The files were dated 2026-06-25.
- Each row says whether the year met EPA's completeness rule and whether the monitor's agency
  has certified it. EPA's description of the files gives May 1 of the following year as the
  certification deadline.
- **The Bay Area's recent years are not there.** In the 2025 file the nine Bay Area counties
  have no fine-particle and no NO2 rows. Their 2023 and 2024 rows are in those files, but most
  read "Certification not required" where a certified year reads "Certified". 2022 is the newest
  year most of their monitors are certified for. The project's other air districts have
  certified rows for 2025.
- A monitor can have several rows for one year. Where a year had event days (wildfire smoke,
  for example) EPA gives one row that includes them and others that leave them out.
- An advisory beside the files (posted 2024-08-26) says to leave out fine-particle data from the
  Teledyne T640 and T640X instruments under their original method names, and to use the same
  instruments' "Network Data Alignment" or "(Corrected)" rows.
- EPA's website terms say its documents "may be freely distributed and used for non-commercial,
  scientific and educational purposes", the same basis as the project's other EPA sources.

## Decision

1. **One hand-run pull, `mw ingest aqs`.** It downloads EPA's annual file for the newest year
   EPA holds in full and the four years before it (2021 to 2025 today), checks each file's
   layout, and only then writes them to their own raw folder, `data/raw/epa-aqs/`. A missing
   column, a file holding another year, or a pollutant without the summary read here stops the
   pull. `--offline` rebuilds the measures from the files on disk, which is needed after an
   outline changes. `--year` names another newest year.
2. **Two pollutants: fine particles (PM2.5, EPA parameter 88101) and nitrogen dioxide (NO2,
   42602).** They are the two the plan names. Only regulatory monitors are read.
3. **A year can be listed when EPA marks it complete and the monitor's agency has certified
   it.** The annual average is read from the row that counts every measured day, event days
   included, so the project makes no judgement about which days to leave out. Instruments named
   in EPA's advisory are left out.
4. **Each monitor is read at its own newest year that can be listed.** One year for every
   landfill is not possible: the newest year would drop every Bay Area monitor, and the oldest
   would throw away three years of the North Valley's. The page gives the year beside each
   figure.
5. **The nearest monitor is the closest station to the landfill's outline with such a year.**
   Where a station ran two instruments in that year, the one with more measured days is read.
6. **No monitor farther than 25 km is listed.** The limit is `context.monitor_limit_km` in
   `config/project.yaml`, as 0020 requires. Beyond it the page reads "none close enough", which
   the caption says is not a reading. 25 km is a judgement: it keeps a monitor in the same
   stretch of valley or bay shore and drops one in another county's air basin.
7. **Ten measures per landfill, as published.** For each pollutant: the monitor's name and EPA
   number, its distance from the outline, the year of its figure, the days measured in that
   year, and the average over that year in EPA's unit (micrograms per cubic metre, parts per
   billion).
8. **Nothing is averaged across monitors and nothing is compared with a standard.** EPA's file
   also counts days above its standards; those columns are not read.
9. **The period is the span of years searched, `2021-2025`.** The year of each figure is a
   measure of its own, because it differs between the two pollutants at one landfill.
10. **A provisional outline says so.** Rows for a landfill whose outline is still a placeholder
    circle are marked unchecked, and the page says the distance may change.
11. **Shown as context, under 0020.** The figures go in the section "The area around this
    landfill", under the fixed sentence that they are not attributed to the landfill. The
    caveats say a monitor measures the air where it stands and name the usual sources of each
    pollutant.
12. **The source is open.** It is entered as confirmed, so its rows are not restricted: a
    public copy shows them for the landfills the public site may show.

## What the first pull holds

| | Fine particles | Nitrogen dioxide |
|---|---|---|
| Registry sites with a monitor within 25 km | 41 of 52 | 42 of 52 |
| Different monitors those sites are read from | 20 | 21 |
| Distance to that monitor | 1.4 to 24.9 km, median 11.0 | 1.2 to 24.9 km, median 11.9 |
| Sites with a monitor within 10 km | 18 | 16 |
| Bay Area sites by year of the figure | 2021: 2, 2022: 16, 2024: 7 | 2022: 25, 2025: 1 |
| North Valley sites by year of the figure | 2025: 16 | 2021: 2, 2023: 1, 2024: 1, 2025: 12 |

40 sites have a monitor for both pollutants, 3 for one and 9 for neither. 18 of the 43 sites
with a figure have a provisional outline and are marked unchecked. For 2 sites the
fine-particle figure rests on 30 measured days in the year, which the page shows.

## Options turned down

- **One year for every landfill.** See decision 4.
- **Reading uncertified years.** It would give the Bay Area 2024 figures, from rows the agency
  has not vouched for, and no 2024 NO2 figure at all (every Bay Area NO2 row for 2024 is marked
  incomplete).
- **The nearest monitor whatever its distance.** A monitor 50 km away is in another air basin.
  Listing it under "the area around this landfill" would mislead.
- **An average of the monitors within the limit.** A new figure EPA does not publish, and it
  would hide that monitors a few kilometres apart can read very differently.
- **Daily or hourly readings, or a chart over time.** 0020 rules out a trend arrow, and a
  day-by-day series beside a landfill invites the reading that the landfill caused it.
- **Linking a monitor to a landfill by wind direction.** Out of scope under 0020: it would turn
  context into an attribution claim.
- **Low-cost sensor networks and non-regulatory monitors.** Different quality rules; not in
  the plan.
- **EPA's data API.** It needs an account and a key. The files hold the same annual figures.

## Consequences

- No new dependency and no database migration: the measures table and the catalogue of 0019
  already take context rows.
- The pull is not part of the twice-weekly run. EPA refreshes the files in June and December;
  the pull is worth rerunning after each. The measures file stays in place between runs, so
  every later copy carries it.
- The step must be rerun (`--offline`) after an outline changes.
- The website's list of sources is shared by every copy, so the public list gains a line for
  this source and the footer gains its credit as soon as a copy is loaded.
- When a newer copy is made public, the five studied landfills' pages gain the context section
  with these figures. Until then the public pages are unchanged.
- The year beside a Bay Area figure will stay old until the Bay Area's agency certifies newer
  years. Once the five-year span moves past a monitor's last certified year, that monitor drops
  out and the landfill may read "none close enough".
- Still to check: why the Bay Area's 2023 to 2025 years are uncertified or missing in EPA's
  files. The files do not say.
