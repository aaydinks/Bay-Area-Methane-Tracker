# PR #50: Let the database loader save lists inside the check results

**Status:** merged 2026-11-06 · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/50)

## In one sentence

Loading a review copy into the database no longer fails on the check results.

## Why it was needed

The first real review copy (`pub-20261107T011826Z`) was the first one ever loaded
into the database. The load stopped with nothing saved. Some check results hold small
lists, such as the low and high ends of a range. Once a copy is saved to disk and read
back, those lists come back in a form the loader could not write out, and the loader
had never been tried on a copy read back from disk.

## What it adds

- The loader turns those lists back into plain lists and numbers before saving them.
- A test that saves a table with nested lists, reads it back and checks that every
  value comes out as plain data.

## What we learned

With the fix, the review copy loaded in full: 5 sites, 621 plumes, 2,171 passes, 5
estimates, 51 operator reports and 10 check results. It is now marked "review", so
only reviewers can see it once the reviewer lock is on. The estimates in the database
match the fit (Newby Island 14,100 t a year, range 11,300 to 17,700; Potrero Hills
750 t, range 310 to 1,470).

## Still to do

Load each future review copy the same way. The website shows it once Cloudflare and
the reviewer lock are set up.
