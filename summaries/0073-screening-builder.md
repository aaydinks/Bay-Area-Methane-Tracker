# PR #73: A tool that proposes the screening sites and their outlines

**Status:** merged 2026-11-19 · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/73)

## In one sentence

One command now turns CalRecycle's list of landfills into a proposed set of screening sites, each
with an outline, for a person to review before any of it enters the project's site list.

## Why it was needed

The plan has always spoken of a screening tier of a few dozen landfills beside the five studied in
depth, but it was never built: the site list holds only the five. The wider plan (decision record
0018) needs that tier for the Bay Area and for the North Valley. Drawing several dozen outlines by
hand was the obstacle.

## What it adds

- **A download of CalRecycle's landfill outlines.** A public state map layer holds 153 outlines
  drawn by CalRecycle staff from permit maps, each tagged with the landfill's state site number.
- **`mw sites screen`.** It reads the landfill list and writes three files for review: the
  proposed sites, their outlines, and a table of every landfill considered with the reason it was
  or was not chosen.
- **The choosing rule.** Permitted landfills, open or closed. Unpermitted and exempt units are left
  out. A person can overrule the rule for a single site by adding a line with a reason.
- **The outline rule.** The state's drawn outline where there is one. Otherwise a circle of 750 m
  around the site's reference point, marked provisional. Circles never overlap a neighbour: a
  circle gives way to a drawn outline, and two circles that would overlap are cut along the line
  halfway between them.
- **Nothing is guessed.** Two sites on the same point, a point inside another site's outline, a
  repeated name, or a county outside the project's regions are reported for a person to settle.

The project's site list is not changed by this command.

## What we learned

On the real Bay Area list of 36 landfills:

- 32 are permitted. Four of those are pilot sites already in the list, so 28 are proposed.
- 14 of the 28 have a drawn outline in the state layer; 14 get a provisional circle.
- Nothing needed settling by hand.
- Shoreline, one of the five pilots, is recorded by CalRecycle as unpermitted. It stays a pilot;
  the note is for its page.

Two cautions about the state layer: its outlines were last edited in 2021, and no terms of reuse
were found on it. No outline from it is committed yet.

## Still to do

- Check the layer's terms of reuse, then review the 28 proposed Bay Area sites and add them to the
  site list (step 9). This must wait for the run hardening and the public scope gate.
- Run the same command for the North Valley once that region is added (step 10).
- Each site's air district, by overlaying the state's district outlines (step 7).
