# PR #70: One definition of where the project looks

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/70)

## In one sentence

The area the project covers is now written once, as a list of regions in the settings file, and
every part of the pipeline reads it from there.

## Why it was needed

The plan now adds a second region, the North Valley (decision record 0018). Until this change
"the Bay Area" was spelled out separately in six places: two boxes on the map and four lists of
the nine counties. Adding a region would have meant editing all six and hoping none was missed.
One of them, the check on site outlines, would have rejected every North Valley landfill.

## What it adds

- **A `regions` list in the project settings.** Each region has a name, its counties, a box on the
  map and the air-district codes whose outlines are downloaded. Today it holds one region, the
  Bay Area, with exactly the values the code used before.
- **Every consumer reads that list:** the site-outline check, the EPA facility list, the CalRecycle
  landfill list, the county and air-district outlines, the Census blocks, and the box that NASA
  EMIT and Carbon Mapper are asked for.
- **A guard on the map zone.** Distances and the Sentinel-2 code assume everything lies west of
  120°W. A region or a site outline east of that line is now refused with a clear message.
- **Tests** that the Bay Area region reproduces the earlier box, counties and district code, and
  that a second region widens the box and the county list as expected.

Nothing changes in what the pipeline pulls or publishes.

## What we learned

- The EPA county filter already ignored the word "County" in EPA's spelling, so the fix the plan
  called for was not needed. A test now pins that behaviour.
- The site-outline check used a slightly wider box than the data pulls. It is now the regions' box
  with a margin of 0.05 degrees, a little looser than before on every side. Its purpose is to
  catch swapped coordinates, which it still does.
- Two definitions were left alone on purpose: the box of the pre-registered cloud-model test
  (decision record 0013), which must stay as registered, and the Sentinel-2 search box, which
  stays on the pilot sites.

## Still to do

Add the North Valley region itself, with its counties, box and district codes (step 10 of the
expansion plan). The district outline's file name and caveat still name the Bay Area and are
generalised then.
