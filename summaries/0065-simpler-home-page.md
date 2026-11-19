# PR #65: A simpler home page for first-time visitors

**Status:** merged 2026-11-18 · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/65)

## In one sentence

The home page now has one plain sentence, one main button, three short steps on how the site works
and a still grid of the five landfills. The stat boxes, both rotating carousels and the technical
list of limits are gone.

## Why it was needed

New visitors are arriving from outreach to city staff, local groups and the press. The owner found
the home page "too cluttered" and hard for newcomers. It stacked two notices, a stat row with terms
like "usable passes", two carousels that moved on their own, and a list of limits written in the
method's own terms.

## What it adds

- A plainer line under the title: "A look back at what satellites have seen of methane coming from
  five Bay Area landfills." It replaces the line chosen in PR #62.
- One main button, "See the five landfills", with the map as a plain link beside it.
- "How it works" in three numbered steps with small drawings: satellites take pictures, we look
  for methane, we estimate with a range. Links point to How to read and Methods.
- The five landfills as a fixed grid of photo cards. Each card gives the town and one status:
  "Estimate available", "Not enough data yet" or "No estimate yet". The home page shows no
  figures. Each site page shows its estimate with its range, as before.
- On the home page only, the provisional and Carbon Mapper notices become one short line that
  links to How to read. Every other page keeps both notices in full. The header framing
  (retrospective, screening indication) is unchanged on every page.
- How to read gains two entries: "Detection floor" and "Display only". The limits that left the
  home page were already listed on the Methods page.
- The carousel and counter code, and their styles, are removed because nothing else used them.
  The tests now check the new cards and that the home page has one main button, three steps and
  no carousel.

## What we learned

The home page's required wording comes from the shared header, so the page body can be cut back
freely without failing the wording check.

## Still to do

- The carousel and animation packages are still listed in `web/package.json` but are no longer
  used. They can be removed in a small clean-up.
- If the owner prefers the PR #62 line under the title, it is a one-line change back.
