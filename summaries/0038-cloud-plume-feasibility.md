# PR #38: What is feasible for a model that tells clouds from plumes

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/38)

## In one sentence

Before building a model that separates clouds from methane plumes in Sentinel-2 images, this
records which labelled data exist, which can be used and published, and which results could
be tested at all.

## Why it was needed

- **What the method sees.** The Sentinel-2 method looks for methane by comparing two infrared
  bands on a target day and a clean earlier day.
- **What clouds do to it.** Clouds, thin high cloud and cloud shadows change that comparison
  and can look like a plume.
- **How the project screens clouds now:**
  - A fixed brightness rule.
  - A whole-tile cloud percentage, about 110 km across, to decide whether a pass over a site
    is usable.
- **How wrong the tile figure can be.** One pass over Newby Island in August 2025 is listed as
  42% cloudy and so is thrown away. The 6 km around the site was in fact clear.
- **Why check first.** A model could help, but only if there are labels to learn from, terms
  that let the result be published, and a fair way to test it.

## What it adds

A decision record (ADR 0012) with these findings, each checked against its source on
October 31, 2026:

- **Cloud labels are open and plentiful.**
  - CloudSEN12+ holds 10,000 Sentinel-2 patches outlined by experts, and it is public domain.
  - Three of its sites are in the Bay Area, one on the same tile as Newby Island.
  - It comes with the standard cloud products already computed, so comparisons are fair and
    cheap.
- **Real plume labels are scarce.**
  - Every real-label Sentinel-2 plume collection allows only non-commercial use.
  - None covers a California landfill.
  - Plumes big enough for Sentinel-2 to see (about 2 tonnes an hour) are rare near the pilot
    sites: 14 in the Carbon Mapper catalog.
- **Carbon Mapper data stay out of the model.** A model trained on them could not be
  published, so they are used for neither training nor testing.
- **Pixels can be fetched.**
  - The Copernicus account works: one file was fetched.
  - Google's public mirror already works.
  - The missing table that converts the signal to methane amounts is still open.
- **What the model must beat:**
  - The current brightness rule.
  - The cloud map that ships with Sentinel-2's processed product.
  - A widely used published cloud model (s2cloudless).
- **The plan.** A small, fast model, tested on sites and tiles it never saw in training.

## What we learned

- Two of the four hoped-for benefits can be tested now:
  - fewer cloudy passes wrongly counted as usable;
  - fewer false Sentinel-2 detections.
- Two cannot be tested on real Bay Area data:
  - Confirmation by EMIT or Carbon Mapper: too few large plumes to test.
  - Narrower ranges in the site estimates: there is no real model fit yet, so this can only be
    shown on simulated data.
- Much of the gain may come from judging clouds over each site instead of over the whole tile,
  which needs no model at all.

## Still to do

- Write down the exact claim and pass/fail rule before looking at any held-out results
  (ADR 0013).
- Build and test the model.
- Replace the whole-tile cloud figure with a per-site one, as a separate change.
- Confirm the CloudSEN12+ licence; older copies of the dataset state different terms.
