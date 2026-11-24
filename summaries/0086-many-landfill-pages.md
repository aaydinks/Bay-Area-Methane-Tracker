# PR #86: Pages that work for many landfills

**Status:** merged 2026-11-23 · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/86)

## In one sentence

The website's pages now work for dozens of landfills in more than one region, and their wording
no longer assumes five Bay Area sites.

## Why it was needed

The review copy grew from 5 landfills to 52 across two regions. The pages were written for five:
a card for each landfill, a map that opened on all of them at once, and sentences such as "five
Bay Area landfills" typed in by hand. With 52 landfills the cards ran for several screens, and a
screened landfill's page said "insufficient data" when the truth is that no estimate has been
made for it yet.

## What it adds

- **One table of landfills, in place of a card for each.** It can be sorted by any column and
  filtered by region and by how closely a landfill is followed. On a phone it becomes a list.
- **No rank without an estimate.** A landfill without a usable estimate shows the reason in place
  of a figure. However the table is sorted, those landfills stay after the ranked ones.
- **A region choice on the map.** It frames one region's landfills and leaves out the rest. A
  plume traced to a landfill goes with that landfill's region; any other plume goes with the
  region it lies in.
- **A home page that stays short.** It keeps cards for the landfills studied in depth, and one
  line says how many more are screened, with a link to all of them.
- **Counts and place names taken from the data.** A build names only the landfills and regions it
  holds. The "provisional" notice now says whether all, some or none of the outlines are
  placeholders.
- **Plain words for a screened landfill.** Its page says it has no estimate because no model run
  includes it yet, and that this says nothing about how much methane it gives off.
- **Methods and How to read.** They explain the two kinds of landfill (studied in depth, and
  screened) and the rule that a plume tagged with a sector other than solid waste is never
  counted for a landfill.
- **Sample data with two regions.** The test data gains four screened landfills, two in each
  region, so the new pages are checked on every change. A test keeps the website's region names
  the same as the project's settings.

## What we learned

- **The public site keeps its five landfills and its figures.** A public build from the sample
  data shows no region filter, no region column and no mention of the North Valley, because the
  public copy holds one region. What does change there: the landfills page becomes a table, and
  sentences are built from the data ("five landfills in the Bay Area").
- **It holds up on the real review copy.** A build from it lists 52 landfills, 33 in the Bay Area
  and 19 in the North Valley. The map's plume counts by region add up to the total (577 and 167
  of 744).
- **Two landfills have an estimate today.** The other three studied in depth show why they have
  none, and the 47 screened ones show "no estimate yet".

## Still to do

- Rebuild the locked review website so reviewers see the new pages (owner's go-ahead).
- Labels that still name one regulator ("Air District") are generalised in the next step.
- The project's name still says "Bay Area"; the owner decides the name later.
- The first estimates for screened landfills come with the screening model run (step 15).
