# PR #90: CO2 plumes counted near each landfill

**Status:** merged 2026-11-26 · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/90)

## In one sentence

For each landfill and year, the project now counts how many days Carbon Mapper searched it for
CO2 and how many CO2 plumes it found on or beside it; so far that second number is zero
everywhere.

## Why it was needed

The expansion plan adds more gases beside the methane estimate. For CO2 there are two honest
things to show: what operators report to EPA (already on the pages), and whether anyone has seen
a CO2 plume at the landfill. Nothing the project uses can measure a landfill's CO2, so the second
is a plain count, "searched this many times, found this many", and never an estimate.

## What it adds

- **A new pull.** `mw ingest carbonmapper-co2` downloads Carbon Mapper's CO2 plume list and the
  list of scenes it searched for CO2.
- **Two counts per landfill and year.** Days on which a CO2 scene covered the landfill, and CO2
  plumes that start on its outline or within 500 m. These are the same distances the methane
  work uses.
- **A zero only where someone looked.** A year with a pass shows both counts. A year with no pass
  has no entry and reads as not searched.
- **A section on each landfill's page** with the yearly counts and a plain caveat.
- **A wall between CO2 and methane.** CO2 downloads sit in their own folder, which no methane
  step reads. A test checks the methane tables come out identical with a CO2 pull present.
- **A decision record (0024)** with the rules and the options turned down.

## What we learned

- **No CO2 plume starts within 500 m of any of the 52 landfills** in the project's window
  (August 2022 onward). The nearest is about 1 km away.
- **Every landfill was searched:** between 2 and 41 days each, 903 landfill-days in all, from 399
  CO2 scenes.
- **Every CO2 plume in the area is tagged as an energy plant.** There are 27 in the project's box
  and window, and 92 in the wider area over all years. None is tagged as waste.
- **A zero says little.** The few scenes that state a detection limit put it at tens of tonnes of
  CO2 an hour. The largest CO2 figure a landfill here reported to EPA for 2023 is under five
  tonnes an hour. This search is unlikely to see a landfill's engine or flare, and the page says
  so.
- **The plan's figure of 92 plumes was for all years.** Inside the project's window the count is
  27, which is what the pull returns.

## Still to do

- **Nothing public changes.** Whether Carbon Mapper's display terms cover CO2 counts has not been
  asked. Until the owner hears back, the counts are in review copies only, and a public build
  shows no count and no CO2 section.
- **The pull is run by hand** and is not part of the twice-weekly run. The counts also need a
  recount (`--offline`) when a landfill's outline changes.
- **If a count ever stops being zero,** the page will show a number without the source Carbon
  Mapper tagged the plume with. The pull's own report names the tags.
- Next sources of this step: site operations, CalEnviroScreen and air monitors.
