# PR #4: Sites, satellite passes and plume matching

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/4)

## In one sentence

Built the steps that turn raw satellite records into the table the model
needs: every time a satellite looked at each landfill, and whether it saw a
plume there.

## Why it was needed

The model can only judge how often a site leaks if it knows every time a
satellite looked, not just the times it saw something. Plume lists alone
make every landfill look like it is always leaking.

Two other questions need firm rules:
- **Where does each landfill begin and end?**
- **Which landfill does a plume belong to?** Newby Island, for example, sits
  next to a compost facility, an energy facility and a wastewater plant.

This is "Gate 1" in the plan: a table of plumes and passes per instrument per
year at the five pilot sites.

## What it adds

- **The site list and boundaries.** Each landfill's outline is checked
  before use: it must be a valid shape, sit inside the Bay Area and not overlap
  its neighbours. Working areas, closed areas and nearby non-landfill sources
  can be marked.
- **The pass table.** Satellite image outlines are laid over the landfill
  boundaries to record each pass, how much of the site it covered and how much
  was cloud-free. Several passes on the same day count once.
- **Plume matching.**
  - A plume is assigned to a landfill only if it starts inside the boundary or
    within 500 m of it.
  - A plume that could just as well come from a neighbouring facility is
    flagged as ambiguous and never assigned.
  - A plume never creates a pass on its own; doing so would inflate how often
    sites appear to leak.
- **The Gate 1 report.** It flags any pilot site with no boundary, or with
  plumes from a satellite that has no recorded passes there.

## What we learned

Nothing about real sites yet. The whole chain was tested end to end on a
small made-up example with two landfills and a neighbouring compost facility.

## Still to do

Gate 1 needs the five pilot boundaries drawn, and real satellite records from
the next pull request and from Carbon Mapper.
