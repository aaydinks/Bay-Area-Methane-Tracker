# PR #69: Put the site registry the scheduled run uses into the repository

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/69)

## In one sentence

The outlines of the five pilot landfills, and the note that each one is provisional, are now in
the repository instead of only on the machine that runs the twice-weekly refresh.

## Why it was needed

Every figure on the site depends on each landfill's outline: a plume counts towards a site only
if it falls inside the outline or within 500 m of it. The outline file had never been committed.
Anyone cloning the repository could not rebuild the published numbers, and the coming work on
the registry (more sites, real outlines) would have collided with the uncommitted copy.

## What it adds

- **The outline file.** Five outlines, one per pilot site. Each is a circle of 500 m radius
  around the site's CalRecycle reference point, and each says in its own record that it is
  provisional and not a traced outline.
- **The source note in the site list.** Each of the five rows now names that provisional source,
  which is what makes the website mark the outline as provisional.
- **A line in the registry's README** saying the outlines are provisional for now.

Nothing changes in the pipeline's output: these are the same files the scheduled run has been
reading since late October.

## What we learned

The first real fit and every publication so far were built on files that were not in version
control. The run records a "dirty checkout" flag for exactly this reason; it should now clear for
the registry.

## Still to do

Replace the circles with real outlines for the four pilots that have one in CalRecycle's public
boundary layer, and redo the fit when that happens (step 11 of the expansion plan).
