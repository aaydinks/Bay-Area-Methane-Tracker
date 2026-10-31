# PR #34: Load the map library lazily

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/34)

## In one sentence

The map page now loads its large map library only when the map is about to be seen, which lifts
the page's speed score from 66 to 100 without changing what the reader gets.

## Why it was needed

The Lighthouse budgets added with the checklists showed every page clearing its targets except the
map, where the map library alone weighs about a megabyte. Slimming the library is not an option; not
loading it until it is needed is.

## What it adds

- A small placeholder in the map's place that loads the map when it scrolls near the viewport, with
  a button for anyone who wants it at once.
- A fix for a nullable value on the updates page that the type check flagged.

## What we learned

On a phone the map sits below the filter controls, so most phone visits start loading the library
only after the first screen is painted; on a desktop it is visible at once and loads immediately.

## Still to do

Nothing on this page. The checklists run on the real dates.
