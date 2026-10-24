# PR #16: Repair outcomes with the smallest detectable drop

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/16)

## In one sentence

Turns the repair test into a single outcome table, one row per documented repair, saying whether measured
emissions fell after the repair and how large a drop the data could have seen.

## Why it was needed

The project asks one question about each repair: after the dated repair, did measured emissions drop, and how
sure are we? The test for that already existed, but it ran one repair at a time and printed its answer. Nothing
stored the answers, ran them over every repair on record, or said what an "inconclusive" result means at a
particular site. With few satellite passes, inconclusive is the common answer, and without a size attached it is
easy to misread as "the repair didn't work".

## What it adds

- **The outcome table.** For each repair: the change after the repair relative to what control sites suggest
  would have happened anyway (median and 90% range), the chance it was a decrease, the call (drop, rise,
  inconclusive, or insufficient data), the change in tonnes per year, and how many passes were used.
- **The smallest detectable drop.** For each repair, the model re-simulates the site's own passes with a 25%,
  50% and 75% drop and reruns the test. The smallest drop it catches 80% of the time is recorded. If none
  reaches 80%, the table says so.
- **Roughly dated repairs.** A repair known only to the week or month drops an extra 7 or 31 days of passes on
  both sides, so a wrong date cannot mix "after" passes into "before".
- **One command,** `mw repair run`, over every row of the repairs list. It stops with a clear message while the
  list is empty or the detection limits are unconfirmed.
- **A "Documented repairs" table on each site page** of the dashboard, worded as a screening indication.

## What we learned

Nothing new about the landfills yet: the repairs list is still empty and the site boundaries are not drawn. On
simulated sites the whole path runs end to end.

## Still to do

- Fill the repairs list from Air District records, operator logs and public documents, each with its source.
- Run the placebo check (Gate 5) on the real pass schedule before publishing any outcome.
