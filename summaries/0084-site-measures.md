# PR #84: A place for measures beside the methane estimate, starting with EPA's gases

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/84)

## In one sentence

The project can now carry figures that are not methane estimates, and the first ones are the
gases each studied landfill reports to the EPA.

## Why it was needed

The owner asked for more than one measure per landfill: CO2 and other gases, site operations,
nearby air monitors and community context. None of these is a methane estimate, and the tables
built so far have no place for them. Adding a gas to every existing table would have put the
checked methane results at risk for a gas no instrument used here can see at a landfill.

The EPA download also already held more than was used. For each matched landfill it includes the
figures filed for burning fuel on site, such as landfill gas burnt in engines. Only the landfill
methane row was kept; the rest was thrown away.

## What it adds

- **One table for every other measure.** Each row is one landfill, one measure, one period and one
  source, with a number or a text value and its unit. It also says whose statement the figure is:
  reported by an operator or agency, counted by the project in public data, or context about the
  surroundings.
- **A catalogue of measures.** A short config file gives each measure its label, unit, source and
  the caveat shown beside it. A new measure later is an entry there plus a step that fetches it,
  not a change to the database.
- **EPA's gases, kept as published.** Five measures: methane from the landfill, biogenic CO2 from
  burning fuel (landfill gas is counted here), other CO2 from burning fuel, and the methane and
  nitrous oxide from burning fuel. All are in tonnes of CO2 equivalent, exactly as EPA lists
  them. Nothing is converted.
- **Checks that stop a bad copy.** A copy is not built if a row names a measure the catalogue
  does not have, or disagrees with its unit or source. The catalogue's labels go through the
  same banned-words check as the pages.
- **A database change (migration 0010).** Two new tables with the same access rules as the rest:
  the public key reads only rows of public copies, for landfills on the public list, from sources
  whose terms allow it. Nothing existing is changed.

Nothing on the website changes with this step. No page reads the new tables yet; the section
that shows them comes next.

## What we learned

- **Reported CO2 exists for three of the five studied landfills, and is current for one.** Sonoma
  Central files a combustion report every year (10,379 t of biogenic CO2 in 2023). Shoreline and
  Potrero Hills filed one only up to 2018. Newby Island files the landfill report alone, and no
  EPA record was found for Acme Fill.
- **A gap is not a zero.** A year without a combustion report has no row, so a page can say
  "not reported" and never show 0.
- **The figures match the source.** Kiefer Landfill's 2023 biogenic CO2 reads 40,518 t, the figure
  recorded when the measures were planned. The landfill methane rows equal the ones the operator
  comparison already uses.
- **23 landfills in the two regions reported to EPA for 2023**, the count expected. Only the four
  matched by hand are downloaded, giving 147 rows.
- **EPA's codes were checked against its own lookup tables** on Nov 23, 2026, as was its rule that
  CO2 from burning landfill gas counts as biogenic.

## Still to do

- Apply migration 0010 to the live database before this is merged (owner's go-ahead). Until
  then the twice-weekly run on `main` is unaffected, because `main` does not write these tables.
- Show the measures on each landfill's page, with "not reported" where a report is missing.
- Match the 47 screening landfills to their EPA records by hand, so their gases can be added.
- The EPA download is a manual step (`mw ingest ghgrp`), not part of the twice-weekly run. EPA
  publishes once a year.
- Later measures use the same table: CO2 plume counts, site operations, air monitors and
  CalEnviroScreen scores.
