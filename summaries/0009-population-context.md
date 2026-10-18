# PR #9: How many people live nearby

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/9)

## In one sentence

Added a count of residents within 1, 3 and 5 km of each landfill, shown as
context alongside the emissions estimates.

## Why it was needed

The plan's impact section asks for the number of people near each persistent
emitter, so readers can see who lives close to a site. It is context, not a
health finding. Landfill gas carries other pollutants too, but this project
measures methane only and makes no health claims.

## What it adds

- **Resident counts** from the US Census Bureau's American Community Survey,
  using its smallest published areas (block groups).
- **Partial overlaps handled.** Where a block group falls partly inside a
  circle, only that share of its population is counted, assuming people are
  spread evenly within it.
- **A label on every figure:** "residents nearby (context, not a health
  effect)".
- **API keys read automatically** from the project's private settings file.
  Until now, keys placed there were never picked up.

## What we learned

The Census boundary data is free and needs no account. Since this project
began, the Census population service requires a free API key, which the
owner needs to register for.

## Still to do

It needs the landfill boundaries and a Census API key before it can produce
real counts.
