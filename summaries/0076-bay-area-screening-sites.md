# PR #76: The Bay Area screening sites join the site list

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/76)

## In one sentence

The project's site list grows from the five landfills studied in depth to 33, by adding 28 other
permitted Bay Area landfills that will be watched more lightly.

## Why it was needed

The plan has always had two tiers: a few landfills studied in depth, and a wider "screening" tier
that shows where else satellites and aircraft have seen methane. Until now only the five in-depth
sites existed. The earlier steps of the expansion made the project safe for more sites and built a
tool that proposes them. This step is the first one that adds real sites.

## What it adds

- **28 landfills**, taken from the list kept by CalRecycle, California's waste agency. They are
  the permitted landfills in the nine Bay Area counties, open or closed, that were not already in
  the project.
- **An outline for each.** Fourteen use the outline CalRecycle's staff drew from permit maps (as
  of September 2021). The other fourteen, all closed, have a provisional circle of 750 m around
  CalRecycle's reference point, marked as provisional.
- **Short names.** Each site has a short name and web address chosen by hand, such as "Altamont
  Landfill". The name CalRecycle uses is kept beside it.
- **A record of the outline's terms of reuse.** The map layer states none. CalRecycle's own policy
  treats information on its website as public domain unless marked otherwise, so the outlines are
  used with credit. Written confirmation from CalRecycle is still to come.

Nothing on the public website changes. It is still limited to the five in-depth sites. The new
sites appear only on the locked review copy, with satellite passes and plume dots and no estimates.

## What we learned

- **Seven of the new sites already have plumes on record**, counted on the outline or within
  500 m of it: Altamont (127), Vasco Road (60), Keller Canyon (45), Recology Hay Road (18), Kirby
  Canyon (4), Ox Mountain (3) and Redwood (2). The other 21 have none.
- **Not every site answers to the Bay Area air district.** Read from the state's 2004 district
  map, two sites fall in the Northern Sonoma district (Annapolis, Healdsburg) and two in the
  Yolo-Solano district (Recology Hay Road, Rio Vista). All 33 readings are unconfirmed.
- **The in-depth sites keep their estimates.** A trial of the twice-weekly run with 33 sites
  carried the official model fit as before.
- **Two plumes changed hands.** Two plumes that were loosely tied to Newby Island, outside its
  outline, are now nearer to newly added neighbours. Neither counted towards Newby Island's
  figures.
- **One landfill is missing.** Davis Street in San Leandro reports methane to EPA, but CalRecycle
  files it under a different activity name, so the choosing rule leaves it out.

## Still to do

- Send CalRecycle the short email asking it to confirm the outlines may be reused (owner).
- Check each new site's operator, its EPA facility number and its air district.
- Decide whether to widen the choosing rule to take in Davis Street and similar closed sites.
- Fix the proposing tool, which stops with an error once nothing is left to propose.
- The North Valley sites are the next step.
