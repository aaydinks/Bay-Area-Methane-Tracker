# PR #66: A month-by-month plume view and simpler inner pages

**Status:** merged 2026-11-19 · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/66)

## In one sentence

The map can now play through the plumes one month or one quarter at a time, and the map,
landfill, checks, data and methods pages each open with one plain sentence and their main
view, with the technical detail moved into closed "Details" sections.

## Why it was needed

The owner found the pages beyond the home page "too information dense" for the visitors that
outreach will bring: city staff, local groups and the press. They also asked for a way to see
the plumes over time on the map, "kind of like an animation". PR #65 had already simplified the
home page.

## What it adds

- **Map timeline.** Under the map: a Play button and a choice of "All dates", "By month" or
  "By quarter". Each step shows only the plumes seen in it, with the month and a count, for
  example "June 2026 · 3 plumes seen". The steps run through every month from the first plume
  to the last, empty months included, so playing never skips time. A note says that a month
  with few dots may have had few clear looks, not less methane.
- **Counts on the landfills.** At the map's starting zoom the landfill markers sit on top of
  their plume dots, so each marker now carries a red badge with its number of plumes for the
  dates shown. The map also opens fitted to the five landfills on any screen.
- **Map page.** The filters, the full key, notes about the map and the table move into
  closed sections under the map. Two lines that still said Carbon Mapper is held back are
  gone. The option to weight the heat map by plume rate shows only when some plume has a
  rate, which no public plume does.
- **Landfill pages.** One sentence ("A plume was seen in 24 of the 28 clear looks used for
  the estimate below"), then the estimate set large with its 90% range, then the monthly
  passes chart and the checks. The estimate in full, passes by instrument, the operator's
  reported figures and the site facts are in Details sections.
- **Other pages.** The landfills, checks, data and methods pages open with one short
  sentence. Their longer explanations, the publication run ids and the method-check table
  are in Details sections.
- On every page except home, both notices stay in full: figures are provisional, and Carbon
  Mapper figures are shown with its permission, without rates or downloads.

## What we learned

- Carbon Mapper's terms (ADR 0017) allow its plumes on the map as dots with "place, day,
  site and attribution", and the public map already gave each dot its day. Grouping the dots
  by month or quarter, and counting them, shows nothing finer than that and no rates, so the
  monthly view needed no coarser step.
- At the zoom that shows all five landfills, plumes within 500 m of a landfill are only a few
  pixels from its marker, so the dots alone cannot carry the animation. A count on the marker
  can.

## Still to do

- Pass counts per month are not shown beside the plume counts: most Sentinel-2 passes have
  not had a plume search yet, so a "clear looks this month" figure would mix searched and
  unsearched passes.
- The carousel and animation packages left over from PR #65 are still listed and unused.
