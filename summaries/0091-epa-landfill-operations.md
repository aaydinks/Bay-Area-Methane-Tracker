# PR #91: How each landfill is run, from EPA's landfill gas file

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/91)

## In one sentence

A landfill's page can now say how much waste it holds, whether it has a gas collection system,
how much gas that system collects and burns off, and whether an energy project runs on the gas,
as EPA lists them.

## Why it was needed

The methane estimate says how much a landfill seems to leak. It does not say anything about how
the landfill is run. Two landfills of similar size can differ a lot: one draws its gas out through
wells and burns it in engines, another has no system at all. A reader, or a regulator deciding
where to look first, needs that beside the estimate.

EPA keeps a public file of exactly this for most municipal landfills, through its Landfill
Methane Outreach Program. The plan lists it as one of the sources to add.

## What it adds

- **A new pull, `mw ingest lmop`.** It downloads EPA's workbook for California into its own
  folder. It stops if EPA's page shows two editions of the file, no file, or a file whose layout
  has changed, so a figure is never read from the wrong column.
- **Seven facts per landfill, in EPA's own units:** waste in place and the year of that figure,
  whether a gas collection system is in place, landfill gas collected, landfill gas flared, how
  many energy projects are running, and what types they are.
- **A list of matches kept by hand** (`data/registry/lmop_crosswalk.csv`). EPA's file has its own
  landfill numbers and no state permit numbers, so each registry landfill is paired with EPA's
  entry by a person, with the reason written beside it.
- **A list on each landfill's page,** under "Gases and other figures reported for this landfill".
  It is a list of facts, not a table of years, because the file gives one current value each.
- **Decision record 0025.**

Three rules keep the list honest:

- A figure EPA leaves blank reads "not listed". It is never shown as zero. The one true zero is
  "no energy project running" for a landfill EPA does list.
- Nothing is converted. The gas figures are volumes of landfill gas, which is only partly
  methane, and the page says they are not the amount the landfill makes or lets escape.
- A match made by name and place is marked unchecked, and the page says so beside its figures.

## What we learned

- **EPA's newest file is from September 2024.** EPA also says it does not update every figure
  each year. Of the 33 matched landfills whose waste figure has a year, 20 are dated 2020 or
  later and 13 are dated before 2015.
- **47 of the 52 landfills in the registry are in EPA's file.** All five studied in depth are
  matched, and those five matches rest on something already checked. The other 42 were matched by
  name, county and location and wait on a hand check.
- **Of the 47, EPA lists a gas collection system at 39** and a running energy project at 18.
- **EPA's coordinates cannot be trusted for matching.** For three matched landfills its point is
  more than a kilometre from the outline, which is why the matching is not left to code.
- **Four EPA landfills in the project's counties are in no registry line.** They are written to a
  file on every run for the next look at the list of landfills.

## Still to do

- **Hand-check the 42 unchecked matches.** The same file gives EPA's greenhouse-gas facility
  number for 27 of them, which would also let those landfills show their reported gases.
- **Two neighbouring San Jose sites need a second look.** EPA's entry carries the address
  CalRecycle gives for one, but that point falls on the registry outline of the other.
- **The public list of sources gains one line** for this source the next time a copy is loaded,
  because that list is shared by every copy. The figures themselves reach the public site only
  for the five landfills studied in depth, and only when a newer copy is made public.
- **The pull is run by hand.** It is not part of the twice-weekly run; the file changes two to
  three times a year.
- **CalRecycle's permit figures** (capacity and permitted tonnage) are a separate source and are
  not in this change.
