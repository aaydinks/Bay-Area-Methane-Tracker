# PR #48: Say which part of the rule makes an estimate insufficient

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/48)

## In one sentence

When the website says a landfill's estimate is "insufficient data", it now gives the true
reason instead of one fixed sentence that was often wrong.

## Why it was needed

An estimate is held back for any of three reasons:
- the site has fewer than 8 usable passes;
- its 90% range is more than 100 times wide;
- the model's convergence checks failed.

The published snapshot gave every such site the same text: "too few usable passes or a fit that
failed its diagnostics". In the first fit on real data, Acme Fill had 18 usable passes and the
fit passed every check. Its range was simply too wide. So were those of Shoreline and Sonoma
Central. Operators and the Air District would have read a reason that was false.

## What it adds

- Each held-back estimate names every part of the rule that applies, for example "the 90%
  range is too wide (its top is more than 100 times its bottom)" or "too few usable passes (5;
  at least 8 needed)".
- A test covering each reason, two reasons together, and an estimate that is not held back.

## What we learned

All three uncertain sites in the first real run are held back for width alone. They had enough
passes, but no plume was seen at any of them.

A correction to PR 47's summary: it said the estimates moved "about 1%" when the sampler
setting changed. That holds for Newby Island (0.6%). Potrero Hills moved about 3%, and the
middle values of the three uncertain sites moved by up to 10%.

## Still to do

Rebuild the review snapshot from `main` with this change, then load it for reviewers once the
database connection string is in place.
