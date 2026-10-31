# PR #26: mw publish, loading one run into the website's database

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/26)

## In one sentence

A new command takes one run of the pipeline, labels its results, checks its wording, marks what
may not yet be shown in public, and loads it into the website's database as a draft that can
then be promoted to the review build or the public site.

## Why it was needed

The website never computes anything; it displays one published snapshot. Something has to build
that snapshot from the pipeline's files, decide the labels the checks page shows, enforce the
project's wording rules on every piece of text, keep Carbon Mapper data out of the public site
until its terms are confirmed, and make the loading safe to repeat. Doing all of that in one
tested command means the website cannot drift from the pipeline.

## What it adds

- `mw publish build`: a snapshot of one run under `data/processed/publications/`, with the
  sites, every pass and plume, the estimates, the dated checks with their results, operator
  figures, residents nearby, site traits and the method checks read from the committed reports.
- Labels computed once, here: strength of evidence from the call rule, size of change on the
  log scale (slight below 1.33x, moderate below 2x, severe beyond; marked unconfirmed in the
  configuration until the owner confirms), the colour rule with its two gaps settled, and a
  plain one-sentence reading for every result.
- A new terms file that says, per source, whether derived tables may be published. Rows from a
  source that is not confirmed are marked restricted; estimates and check results that used a
  restricted instrument are restricted too. On the current data that is the 56 Tanager and
  aircraft passes and all 614 Carbon Mapper plumes; NASA EMIT and Sentinel-2 rows are open.
- The wording check over every text field before anything is written; registry notes are never
  loaded at all.
- `mw publish push`: one transaction, as a draft, with the latest-update feed written by
  comparing with the previous publication (new plumes per landfill, new records, a new model or
  check run, new method checks, changed outlines). `mw publish set-visibility`: review or
  public, with a confirmation for public and a refusal for simulated runs.
- Tests: label tables, the report parser against the real committed reports (Gate 3 coverage
  0.910 / 0.900 / 0.895, hold-out 98%, placebo false-positive rate 0.020 and the superseded
  0.129 run), the feed, the builder with its two refusals, and the full load against a PostGIS
  container in CI. 198 fast tests pass.

## What we learned

Reading the method checks from the reports rather than retyping them caught nothing wrong, but
it did settle how each number is traced: every row on the methods page now carries the run id
of the report it came from. The first real snapshot has no estimates and no check results,
because no real model fit has run yet; the website will show its empty states.

## Still to do

Confirm the severity cutoffs and the Carbon Mapper terms. Run the first real model fit once the
detection curves are sourced, then build, push and promote the first publication for the
review build.
