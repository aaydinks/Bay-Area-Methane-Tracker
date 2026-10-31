# PR #32: Preview images for shared links and a labelled update feed

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/32)

## In one sentence

A link to any page now unfurls with a preview card, each landfill with its own figures, and the
update feed says what kind of change each item is.

## Why it was needed

Pages will be shared in email and messages during the review and after launch. A preview that
repeats the framing and the latest figures travels with the link; a bare link does not. The feed
also needed a glance-level label per item, because "three new plumes" and "a new method check"
should not read alike.

## What it adds

- Preview images drawn at build time: one for the site and one per landfill, with the latest
  estimate and its 90% range (or the reason there is none), the pass and plume-day counts, the
  data-through date, and the line that results are screening indications. They are regenerated
  with every build, so they always match the published snapshot.
- Share tags on every page, each landfill page pointing at its own image.
- The update feed, in the latest update and in the log, with a kind label and icon per item and
  the data-through date beside the event date.

## What we learned

Nothing new about the data.

## Still to do

The review and launch checklists.
