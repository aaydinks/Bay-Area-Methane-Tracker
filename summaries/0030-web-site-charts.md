# PR #30: Site comparison chart and pass timelines

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/30)

## In one sentence

The landfills page now compares the sites in one chart, and each landfill page shows, month by
month and instrument by instrument, how often it was observed and when a plume was seen.

## Why it was needed

Two of the project's main messages are visual: how the sites' estimates compare, with their
ranges, and how uneven the observation record is between sites and instruments. Numbers in a
table do not make the point; a reader should see at a glance that one site was flown far more
often than the others before reading its plume count.

## What it adds

- A dot-and-whisker chart on the landfills page: each site's annual methane above the floor
  (the median) and its 90% range, on a log scale so large and small sites both read. Provisional
  estimates are starred. Sites without enough data stay in their own list and are not ranked.
- A timeline on each landfill page, one row per instrument: a bar per month whose height is the
  number of usable passes, and a red dot in months with at least one detection. It is built from
  the monthly counts the database already publishes, so no per-pass data had to be added.
- Both charts are plain SVG drawn at build time, with no chart library; each has a spoken
  description, and the timeline's figures are repeated in a table for screen readers.

## What we learned

A chart that is an image must not contain links, so the chart labels are plain text and the
cards beneath link to each site; the accessibility scan caught that before review.

## Still to do

The methods and data pages (downloads with credits), the update feed, per-site preview
images, and the review and launch checklists.
