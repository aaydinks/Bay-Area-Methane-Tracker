# PR #61: Sites without an estimate are no longer ranked

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/61)

## In one sentence

The Landfills page, the map and the link-preview pictures now show a figure only for sites with a
usable estimate; the three sites the model marks as insufficient data are listed apart with the
reason and are never ranked or charted.

## Why it was needed

In the first real fit, three sites (Acme Fill, Shoreline and Sonoma Central) have 90% ranges whose
top is more than 100 times their bottom, so the model marks them "insufficient data". Their rows
still carry a middle value. The Landfills page used that value to rank and chart them under
"Sites with an estimate", the map's pop-ups showed it as the site's latest estimate, and the
preview pictures used when a page is shared quoted it. The home page was already fixed in PR 60.
A figure the model itself does not stand behind should not be shown as an estimate anywhere.

## What it adds

- **One rule for every page.** A site has an estimate only when the model did not mark it as
  insufficient data and a middle value exists. The Landfills page, the map, the home page and the
  preview pictures all use that one rule, so they cannot disagree again.
- **The Landfills page** now ranks and charts only Newby Island and Potrero Hills. The other three
  appear under "Not enough data yet" with the model's reason ("the 90% range is too wide").
- **The map's pop-ups** say "Insufficient data" for those three sites instead of a number.
- **The preview pictures** say "Not enough data for an estimate yet" for them. The old wording
  said there were too few passes, which was not the reason.
- **A test.** The sample data used by the automated checks now gives Acme Fill a middle value with
  a too-wide range, like the real data, and a browser test checks that it is listed apart and not
  ranked.

## What we learned

The sample data had blank values for every insufficient-data site, so the automated checks could
not have caught this. The real data differs: a site can be insufficient because its range is too
wide, not only because it has too few passes.

## Still to do

Nothing for this change.
