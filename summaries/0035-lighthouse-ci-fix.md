# PR #35: Fix the Lighthouse step on the CI runner

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/35)

## In one sentence

The speed-and-accessibility measurement added with the checklists now runs on the shared runner,
and it reports rather than blocks.

## Why it was needed

The measurement worked on a laptop but never got a browser on the shared runner, which left the
website job red on the main branch after the checklists were merged. A measurement that cannot start
should not stop other work from landing.

## What it adds

- The browser for the measurement starts headless and without a sandbox, which is what shared
  runners need.
- The step reports its scores in the log and no longer fails the job. The separate accessibility
  scan is still the gate; the speed targets are read from the log and in the checklists.

## What we learned

Two merges landed while the website job was red: one carried the fix for a type error the other had
introduced, and this measurement step hid behind it. The merge step is now gated on every check
passing, and a branch protection rule on main would make that a setting rather than a habit.

## Still to do

Nothing for the website code. The real dates and the owner's steps remain.
