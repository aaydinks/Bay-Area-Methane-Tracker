# PR #88: The coverage test at 52 landfills, and the first screening fit

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/88)

## In one sentence

The model was tested on simulated data shaped like all 52 landfills, passed on the second try, and
then run on the real data to give the screened landfills their first, provisional estimates.

## Why it was needed

Only the five landfills studied in depth had estimates. The other 47 had their passes and plumes
counted and nothing more. Fitting all 52 together is a bigger job than the model had been checked
on: five times the sites, two regions that satellites cover differently, and many landfills where
no plume has ever been seen. The project's own rule (decision record 0021) says such a fit must
first pass the coverage test at its real size. That test asks one question: when the model says
"90% range", does the range hold the true value about 90% of the time?

## What it adds

- **A coverage test in the shape of the real data.** It simulates 52 made-up landfills, each in a
  real landfill's region and with that landfill's real number of passes, and checks the ranges
  against the simulated truth. Each region has to pass on its own, not just the total.
- **A region term in the model.** A fit that pools the Bay Area and the North Valley lets the two
  regions differ instead of assuming one typical landfill for both. A pooled fit without the term
  refuses to run.
- **Longer runs for a pooled fit.** The model's sampler now takes three times as many draws when it
  pools regions. The first test run showed this was needed (below).
- **The first screening fit.** All 52 landfills fitted together. It supplies figures only for the
  47 screened landfills, always marked provisional. The five studied in depth keep the figures of
  their own fit.
- **A decision record (0023)** with the rules, the options turned down and both test runs.

## What we learned

- **The ranges are honest at this size.** Over 200 simulated worlds, the 90% ranges held the truth
  90.2% of the time for the annual total, 90.2% for how often a landfill emits and 90.7% for its
  typical rate. The Bay Area and the North Valley each came out between 89.6% and 90.8%. The target
  is 85 to 95%.
- **The first run failed, on a different rule.** The test also requires that at most 10% of fits
  end outside the sampler's own quality checks. With the usual run length, 18% did. None had gone
  wrong in the serious way (no divergences); they needed more draws. With three times the draws,
  0.5% did. The run length was changed after seeing the failure, so both reports are kept.
- **13 of the 47 screened landfills have enough data for a provisional estimate:** 6 in the Bay
  Area and 7 in the North Valley. The other 34 do not. Eight have fewer than eight usable passes;
  at the rest no plume has been seen, which leaves a range too wide to call an estimate.
- **No sign yet that the regions differ.** The region term's range includes zero.
- **Landfills differ from each other more than the model assumed.** They look like two groups:
  some where plumes are seen on many passes, and many where none has been seen. The model
  describes them with one spread. This is a reason for caution about the pooled fit, and it is
  not settled here.
- **The two studied landfills with estimates barely move in the pooled fit:** 8% higher for Newby
  Island and 2% lower for Potrero Hills. Their published figures are unchanged.

## Still to do

- **Nothing public changes.** Screened landfills are outside what the public site may show. Their
  estimates go to the locked review copy only.
- **The website has to say which fit a figure comes from** before reviewers see these numbers. That
  is the next pull request.
- **Before the pooled fit could become the official one:** the hold-out check on it, and a look at
  whether two groups of landfills fit better than one. That decision is the owner's.
- **The test uses made-up detection settings,** as the ten-landfill test does. It shows the method
  behaves at this size, not that real landfills follow the model.
- Every estimate is still provisional: the detection curves are not confirmed.
