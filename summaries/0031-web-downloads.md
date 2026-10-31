# PR #31: CSV downloads with a README of credits and run ids

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/31)

## In one sentence

The tables behind the website can now be downloaded as plain CSV files, each build writing them
fresh with a README that says which publication and runs they came from and who to credit.

## Why it was needed

A reviewer or a reporter should be able to check a figure without scraping a page, and anyone
reusing a number should carry the publication id and the credits with it. The plan asked for
downloads of the publishable tables only, with the run ids and the credits attached.

## What it adds

- Seven CSV files written at build time: sites, monthly passes per instrument, plumes, estimates,
  checks with their results and labels, operator-reported figures, and the method checks.
- A README naming the publication, the data refresh, the model and check runs, the data-through
  date and the source lag, the units, what the `_lo` and `_hi` columns mean, the row count and
  columns of each file, and a credit line per source.
- A downloads section on the data page listing the files with their row counts, README first.
- The same safety rule as the pages: only rows in the snapshot are written, so the public files
  can never hold a restricted row, and the public-output scan reads the CSV files as well.

## What we learned

Nothing new about the data.

## Still to do

The updates feed polish and per-site preview images, then the review and launch checklists.
