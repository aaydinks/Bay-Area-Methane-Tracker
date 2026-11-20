# PR #68: Widen the plan to two regions and more than methane

**Status:** merged 2026-11-19 · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/68)

## In one sentence

The plan now covers the Bay Area and five North Valley counties around Stockton and Sacramento,
and adds reported CO2, site operations, regulatory records and context about each landfill's
surroundings beside the methane estimate.

## Why it was needed

The project owner decided on Nov 19, 2026 to scale the tracker up: more gases and measures per
landfill, and a reach into the Central Valley. Before any code changed, the plan had to say
exactly what that means, what public data can support, and how to do it without disturbing the
live public site.

## What it adds

- **A new section 16 in the coding plan**, with the regions, the site tiers, the new measures, the
  rule for what the public site may show, and a build order of sixteen steps.
- **Four decision records:**
  - *Regions (0018).* The North Valley is San Joaquin, Stanislaus, Merced, Sacramento and Yolo
    counties. All of it lies west of 120°W, so the map projection the code relies on still holds.
  - *Measures (0019).* Everything that is not a methane estimate goes in one new table. CO2 is
    shown as reported by operators, or as a count of plumes found. It is never estimated.
  - *Wording (0020).* Air-monitor readings, population and state burden scores are shown as
    context, never tied to the landfill and never used to rank sites.
  - *Public scope (0021).* New sites go to the locked review copy first. The pilots' public
    figures cannot move because the site list grew.
- **A scope paragraph in the README.**

No code, data or page changes.

## What we learned

- **The screening tier was never loaded.** The plan speaks of about 38 screened landfills, but the
  registry and the live site hold only the five pilots.
- **No instrument here sees landfill CO2.** Carbon Mapper lists 92 CO2 plumes across the two
  regions and none is tagged as waste.
- **Reported CO2 exists for a minority of sites.** Of 23 landfills in the two regions that reported
  to EPA for 2023, only 7 filed a combustion report. Elsewhere the pages must say "not reported".
- **A public state layer has real landfill outlines** for four of the five pilots and for the
  North Valley sites checked. That removes a long-standing blocker, but real outlines change which
  plumes count, so the Bay Area fit must be redone when they go in.
- **The pipeline is not yet safe for more sites.** Adding sites today would stop the review copy,
  pull every new site into the next refit, and let new sites reach the public build. Those are the
  first things fixed.

## Still to do

Everything in the build order after step 1. The owner's part: ask Carbon Mapper whether its terms
cover CO2 plume counts and the wider area, file records requests with the North Valley air
districts once deep-dive sites are chosen, set a North Valley review window, and decide on the
project's name.
