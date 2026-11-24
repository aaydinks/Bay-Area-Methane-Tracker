# PR #87: Each record names its own regulator

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/87)

## In one sentence

Nothing on the website says "the Air District" any more: a record is labelled with the air
district its landfill falls under, and each landfill's page names that district.

## Why it was needed

The project began with five landfills under one regulator, the Bay Area's air district, and the
labels were written that way: "Air District inspection", "Air District notice". The 52 landfills
now fall under five air districts. A label that says "the Air District" would be wrong for 23 of
them.

## What it adds

- **Labels that name the regulator.** An inspection at Kiefer Landfill reads "Sacramento Metro
  AQMD inspection"; a notice at Sonoma Central reads "Bay Area AQMD notice". Where a landfill's
  district is not known, the label reads "Air district inspection".
- **The air district on each landfill's page.** It also says when the district was read from the
  state's 2004 district map and has not been checked with the district itself, which is the case
  for all 52 landfills today.
- **A place to record who issued a record.** The table of dated records gains a "regulator"
  column. An air district's record must name its district.
- **A check that stops a wrong label.** A copy of the data is not built if a record names a
  different district from the one its landfill sits in, or names none. Because of that check, the
  page can safely take the name from the landfill, and the website's database did not have to
  change.
- **The four other districts, written down.** Northern Sonoma County APCD, Sacramento Metro AQMD,
  San Joaquin Valley APCD and Yolo-Solano AQMD are listed with the data sources, with their terms
  marked as not yet checked.

## What we learned

- **Where the 52 landfills fall,** by the state's 2004 district map: Bay Area 29, San Joaquin
  Valley 11, Sacramento Metro 6, Yolo-Solano 4, Northern Sonoma 2. Two of the Yolo-Solano
  landfills and both Northern Sonoma ones are in Bay Area counties, so a county does not tell you
  the regulator.
- **District names were checked, not remembered.** They are written as the state air board's own
  list of districts writes them, read on Nov 23, 2026.
- **Almost nothing changes on the public site today.** No dated records are published yet, so no
  record label appears. The visible changes are the map's key ("County and air district lines")
  and one sentence ("from regulators and operators"). The public copy was made before landfills
  carried a district, so its pages show no district until a newer copy is promoted.
- **The map has no county or district lines to draw.** The layer exists, but no outlines have been
  loaded into the website's database.
- **A district is not listed on the website before it has given us anything.** The four new
  districts stay in the project's own notes until records from them are in hand and their terms
  are checked.

## Still to do

- Check each landfill's air district with the district, starting with the ones near a boundary.
- Load county and air district outlines so the map's layer has something to draw.
- Records requests to the North Valley districts, once the landfills to study there are chosen
  (owner).
