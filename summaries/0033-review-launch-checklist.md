# PR #33: Review and launch checklists, with Lighthouse budgets in CI

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/33)

## In one sentence

Two checklists say exactly what has to be true of the review build on Dec 8 and of the public site
on Jan 6, who does each step, and how it is checked, and the site's speed and accessibility are now
measured on every change.

## Why it was needed

The review window and the launch have fixed dates and a long list of conditions spread across the
pipeline, the database, the host and the pages. Writing them down once means nothing depends on
memory on the day, and it separates the steps only the owner can take (keys, access policies, the
domain, the notes to reviewers) from the ones that run from the repository.

## What it adds

- A review checklist: the data refresh and publication steps, the hosting switches and access
  policy, a page-by-page walk on phone and desktop in both themes, the proof that the public build
  holds no restricted row, and the note to reviewers.
- A launch checklist: closing the review, recording Carbon Mapper's answer, the domain and production
  settings, a last check of the public pages behind the access gate, promoting the publication,
  removing the gate, the launch note, and the monthly cadence after launch.
- A Lighthouse step in CI on the built site. Accessibility below 95 fails; performance, best practices
  and SEO below their targets warn. Today's scores on the sample build: home 99, checks 100, a
  landfill page 100, and the map 66 because of the map library's size.

## What we learned

The map page is the one place the speed budget is not met. The rest of the site is lighter than
the targets, so the fix is to load the map library only when the map is needed, not to slim the
pages.

## Still to do

Load the map script more lazily so the map page clears its budget. Then the checklists run on the
real dates.
