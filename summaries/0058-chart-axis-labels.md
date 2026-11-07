# PR #58: Axis numbers on the landfill chart no longer overlap

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/58)

## In one sentence

The chart on the Landfills page that compares each site's estimate now labels its scale at a
regular, readable spacing, and has its own layout on phones, so the numbers along the bottom no
longer run into each other.

## Why it was needed

The estimates and their ranges run from about 8 to about 18,000 t/yr, so the scale spans five
powers of ten (1 to 100,000), and the chart put a number at 1, 2 and 5 of every power of ten:
sixteen labels in a row. On a laptop "5,000", "10,000" and "20,000" ran into each other, and on
a phone the whole chart shrank until its text was about half its normal size.

## What it adds

- Gridlines stay at 1, 2 and 5 of each power of ten while there is room, but labels appear only
  at a step where every label clears its neighbours: every power of ten on a laptop, every second
  one on a phone.
- A narrower layout of the same chart for phone screens, so the site names and numbers stay at a
  readable size.
- A scan of every page at laptop and phone widths for text that overlaps other text found no other
  case.

## What we learned

Nothing new about the data.

## Still to do

Nothing for this chart.
