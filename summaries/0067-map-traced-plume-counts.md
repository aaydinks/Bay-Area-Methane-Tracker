# PR #67: Count only plumes traced to each landfill on the map

**Status:** merged 2026-11-19 · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/67)

## In one sentence

The plume counts on the map now count only plumes traced to a landfill, and the map's opening
line no longer says every dot is near one.

## Why it was needed

PR #66 added a month-by-month view to the map, with a red badge on each landfill giving its
number of plumes. Its badge counted every plume listed against the nearest landfill, including
plumes that start more than 500 m away, which the method never assigns to a site. On the
public map that added, for example, six such plumes to Acme Fill. The opening line also said
each dot was a plume seen "near a landfill", but about half of the public map's 623 dots start
away from all five landfills.

## What it adds

- The badge on each landfill, and the landfill summary that opens when it is selected, count
  only plumes that start inside the site's outline or within 500 m of it: the same rule the
  estimates use.
- The line under the timeline gives two counts, for example "June 2026 · 31 plumes seen,
  12 traced to the landfills".
- The map's opening line: "Each red dot is a methane plume a satellite or aircraft saw over the
  Bay Area, and the number on each landfill counts the plumes traced to it." "About this map"
  explains the 500 m rule.
- Landfill pages show their large estimate only when the home page and the landfills list would
  show one too, so the three pages cannot disagree.
- On a landfill without enough data for an estimate, the opening line no longer repeats the
  reason given just below it.
- PR #66's summary is marked merged.

## What we learned

A count drawn on a landfill reads as "this landfill's plumes", so it has to follow the same
attribution rule as the estimates, not the looser "nearest landfill" label kept for listing.

## Still to do

Nothing new.
