# PR #89: Pages say which fit a figure comes from

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/89)

## In one sentence

Wherever the website shows an estimate that came from the screening fit, it now says so.

## Why it was needed

Two model fits now sit side by side (PR 88). The five landfills studied in depth have figures from
their own fit, which has been through more checks. The screened landfills have figures from a
screening fit of all 52 landfills together. Without a label, a reader would take the two kinds of
figure as the same thing, and the pages still told readers that a screened landfill "has no
estimate until a model fit includes it", which is no longer true for 13 of them.

## What it adds

- **On a landfill's page:** under a figure from the screening fit, a sentence says it comes from
  one model fitted to all 52 landfills together, that it is provisional, and that it is not the fit
  behind the landfills studied in depth. The details section names the fit's run.
- **In the landfills table:** such a figure is marked "screening fit" beside "provisional".
- **Under the chart of estimates:** one line says the screened landfills' figures come from the
  screening fit.
- **On the methods page and in the glossary:** a short account of the two fits, written only when
  a copy of the data actually holds a screening fit.
- **The right instruments for each fit.** A landfill's page lists the instruments used by the fit
  its own figure came from.

## What we learned

- Read against the real review copy, 13 screened landfills show a figure with the new note, and 34
  show "insufficient data" with the reason, in place of "no estimate yet".
- The website's database did not have to change: each estimate already carried the name of the fit
  it came from.

## Still to do

- **Nothing public changes.** The public copy holds no screening fit, so none of this wording
  appears there; three public builds on sample data confirmed it.
- **The locked review site shows these pages only after it is rebuilt,** which is the owner's call.
- The chart ranks figures from both fits on one axis. If reviewers find that misleading, the
  screened landfills could get a chart of their own.
- The header and the name still say "Bay Area".
