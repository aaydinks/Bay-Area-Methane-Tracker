# 0025: How each landfill is run comes from EPA's landfill gas file, as a list of facts

- **Status:** accepted
- **Date:** 2026-11-27

## Context

0019 set up one table for every measure that is not a methane estimate, and the plan lists "waste
in place, gas collected and flared, energy projects" among them. These describe how a landfill is
run. They help a reader see why two landfills of similar size can differ: one has an active gas
collection system and an energy project, another has neither.

EPA's Landfill Methane Outreach Program (LMOP) publishes these for most municipal landfills. What
was checked live on 2026-11-27:

- EPA's page of state files links one workbook for California,
  `/system/files/documents/2024-09/lmopdataca.xlsx`. The folder is the edition. September 2024 was
  the newest edition that day; EPA says it updates the files two to three times a year.
- The sheet `LMOP Database` has 409 rows for 299 California landfills: one row per landfill and
  energy project, with the landfill's own columns repeated on each of its rows. Every landfill
  has at least one row, even with no project.
- 51 of those landfills are in the project's fourteen counties.
- A landfill is keyed by EPA's own landfill number. The file carries EPA's greenhouse-gas
  facility number for some landfills, and no SWIS number for any.
- EPA's own notes say the file is compiled from several sources and that not every figure is
  updated each year. Of the 33 matched landfills with a dated waste figure, 20 are dated 2020 or
  later and 13 are dated before 2015.
- EPA's website terms say its documents "may be freely distributed and used for non-commercial,
  scientific and educational purposes".

## Decision

1. **One hand-run pull, `mw ingest lmop`.** It reads EPA's page, follows the one link to the
   California workbook, checks that the sheet still has the columns used here, and only then
   writes the file to its own raw folder, `data/raw/epa-lmop/`. Two editions on the page, no link,
   or a changed layout stop the pull.
2. **Seven measures per landfill, in EPA's units.** Waste in place (short tons) and the year of
   that figure; whether a gas collection system is in place; landfill gas collected and flared
   (million standard cubic feet a day); the number of energy projects EPA lists as operational;
   and their types. Nothing is converted and nothing is estimated.
3. **The period is the file's edition.** The file is a list of current facts, not a figure for
   each year, so every row carries the edition (`2024-09`) as its period. The year a waste figure
   refers to is its own measure, because EPA gives it for some landfills and not others.
4. **A blank is not a zero.** A figure EPA leaves blank gives no row, and the page reads "not
   listed". The one true zero is the count of running projects for a landfill EPA lists with none.
5. **Landfills are matched by hand**, in `data/registry/lmop_crosswalk.csv`, one line per registry
   site with the reason. A match is marked checked only where it rests on something already
   checked: EPA's file carries the greenhouse-gas facility number on record for the landfill, or
   the address and owner on record. Every other match was made by name, county and location, is
   marked unchecked, and the page says so beside its figures.
6. **The page shows a list, not a yearly table.** A source whose rows carry an edition gets a
   table of measure and figure, with EPA's caveats beneath. The yearly tables of 0019 are
   unchanged.
7. **The source is open.** EPA's terms allow the use, so these rows follow the public scope like
   EPA's reported gases: the five landfills studied in depth when a copy is made public, every
   landfill in review copies.

## What the first pull holds

| | Count |
|---|---|
| Registry sites matched to an EPA landfill | 47 of 52 (all 5 studied in depth, 42 screened) |
| Matches marked checked | 5 (the landfills studied in depth) |
| Registry sites with no match | 5 |
| EPA landfills in the project's counties matched to no site | 4 |
| Matched landfills with a waste figure / with its year | 47 / 33 |
| Matched landfills EPA lists with a gas collection system | 39 yes, 8 no |
| Matched landfills with a gas-collected / gas-flared figure | 33 / 28 |
| Matched landfills with at least one running energy project | 18 (23 projects) |

The four unmatched EPA landfills are written to `data/interim/lmop_unmatched.csv` on every run,
for the inclusion list's next hand check.

## Options turned down

- **A yearly table like EPA's reported gases.** The file gives one current value per landfill.
  Putting it under a year would claim a reporting year EPA does not state.
- **Matching by name and distance in code.** EPA's coordinates are rounded or wrong for some
  landfills: for three matched landfills its point is more than 1 km from the outline, and one
  landfill's point is about 11 km away. A match is a judgement, so it is kept in a file a person
  can read and correct.
- **Converting gas volumes to methane.** That needs a methane share for each landfill, which the
  file does not give. The page says the figure is all landfill gas, not methane alone.
- **EPA's "emission reductions" columns.** They are EPA's own estimates for each energy project,
  not something the operator reported. They are left out.
- **CalRecycle's permit figures (capacity, permitted tonnage) in the same step.** They are a
  different source with its own pull. They can follow as their own step.

## Consequences

- A new dependency, `openpyxl`, reads the workbook.
- The pull is not part of the twice-weekly run. The file changes two to three times a year, and a
  failed download must not stop the methane run. The measures file stays in place between runs,
  so every later copy carries it.
- The public list of sources gains a line for this source the next time a copy is loaded, because
  that list is shared by every copy.
- The 42 unchecked matches wait on the owner's hand check, together with EPA's greenhouse-gas
  facility numbers for the screened landfills, which the same file offers for 27 of the 42.
- One match needs a second look: EPA's entry for one of two neighbouring San Jose sites carries
  the address and point CalRecycle gives for that site, but the point falls on the registry
  outline of the other. The outlines of those two sites may need checking.
