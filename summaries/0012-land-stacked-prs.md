# PR #12: Land the stacked pull requests on main

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/12)

## In one sentence

Brings the work from pull requests #4 to #10 onto the main branch, where it was meant to be, and adds the
plain-language summaries that were still sitting on the old branches.

## Why it was needed

Those seven pull requests were built one on top of another. When they were merged, each one went into the branch
below it, not into main, because GitHub only redirects a stacked pull request to main when the branch below it is
deleted, and those branches had been kept. GitHub showed all of them as merged, but main only had the first few
changes. Nothing was lost: the top branch of the stack still held all the work.

## What it adds

Everything those pull requests described, in one step:

- **Sites and passes (#4):** the site registry, the table of every time a satellite looked, plume matching, and
  the Gate 1 report.
- **Public data (#5):** live connections to NASA EMIT, the Sentinel-2 satellites and the EPA's emissions reports.
- **Dashboard (#6):** running the model on data and building the static dashboard.
- **More validation tests (#7):** hold-out prediction, the comparison with operators' reports and the
  Sentinel-2 matched-pairs check.
- **Plume rates and wind (#8):** turning a plume picture into a leak rate, with wind data.
- **People nearby (#9):** resident counts near each site.
- **Sentinel-2 detection (#10):** spotting large plumes in Sentinel-2 images.
- **Summaries:** the plain-language files for #4 to #9, which were not on the top branch.

## What we learned

A stack of pull requests needs one of two things: each pull request opens against main, or the branch below is
deleted when it merges. Repository settings can delete merged branches automatically. Future pull requests are
opened against main so this cannot happen again.

## Still to do

Merge this pull request into main. After that, the old stacked branches can be deleted.
