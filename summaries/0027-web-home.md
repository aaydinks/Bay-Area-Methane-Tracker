# PR #27: Home page with hero, counters and carousels

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/27)

## In one sentence

The home page now looks and moves like a finished site: an animated satellite pass over the Bay,
counters for the latest findings, and carousels for the method, the landfills and the latest
update, all usable from the keyboard and still under reduced motion.

## Why it was needed

The skeleton gave every page its framing and its empty states but no reason to linger. The home
page is where a reviewer, a reporter or a regulator decides whether to read on, so it needs to
explain the idea in one screen and show the latest numbers without a table.

## What it adds

- A hero drawing: a stylised Bay with the five landfills marked, a satellite swath sweeping across
  and a plume forming over one site. It is decorative; the text beside it says what the project
  does and that every result is a screening indication.
- "How it works" as six cards in a carousel: a pass, a plume or not, every pass counts, a 90%
  range per site, control sites for shared shifts, and the comparison with operator-reported EPA
  figures.
- Latest findings: landfills watched, usable passes, days with a plume seen and sites with an
  estimate, counting up as they scroll into view; a carousel of the five landfills with each one's
  estimate and latest check result; a carousel of what changed in the latest update.
- The limits stated plainly (Sentinel-2 sees about 2 t/hr or more; daytime and clear skies only;
  figures are above a floor, not totals; ambiguous plumes are never assigned) and the credits.
- Care for every reader: no autoplay, arrow keys move the strips, each slide announces its
  position, numbers are readable without the animation, and reduced-motion settings turn every
  animation off. Without JavaScript the page shows everything at once.

## What we learned

Nothing new about the data. The sample fixture made it obvious that the landfill cards need the
estimate's range in words, not just a number, which they now have.

## Still to do

The interactive map, the sortable checks table, the landfill pages with charts, and the downloads
page, each in its own pull request.
