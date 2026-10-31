# PR #39: Deciding how the cloud model will be judged, before testing it

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/39)

## In one sentence

This writes down, before any test result exists, exactly what the Sentinel-2 cloud model must
achieve on images it has never seen, and what happens if it falls short.

## Why it was needed

- **The risk.** A model can always be made to look good by choosing the test after seeing the
  results.
- **The task.** The model is meant to tell clouds apart from methane plumes in Sentinel-2
  images, and it will be published only if it gives information the project can act on.
- **The fix.** Fixing the test in advance makes a pass believable, and a failure reportable
  without argument.

## What it adds

A decision record (ADR 0013) that fixes these:

- **The test images.** Expert-outlined Sentinel-2 patches from places the model never trains
  on:
  - the dataset's own test sites;
  - every site on the US West Coast, including three in the Bay Area.
- **What the model is compared with:**
  - the whole-tile cloud figure the project uses now;
  - the current brightness rule;
  - the cloud map that comes with Sentinel-2's processed product;
  - a widely used published cloud model.
- **Claim 1: fewer cloudy passes wrongly counted as usable.**
  - **Why it matters.** A cloudy pass counted as clear looks like a day with no leak, which
    would make a site seem cleaner than it is.
  - **Pass rule.** The model must make this mistake less often than every alternative, and
    must not throw away more than 5 extra percentage points of genuinely clear passes.
- **Claim 2: fewer false Sentinel-2 detections caused by clouds.**
  - **How it is tested.** Simulated plumes are added to the test images.
  - **Pass rule.** The model must leave fewer cloud-made false detections than every
    alternative, while still finding the simulated plumes at least as often (within 2
    percentage points).
- **How sure we must be.** Each comparison uses a 90% range. The comparison passes only if the
  whole range favours the model.
- **What happens either way:**
  - A claim that passes allows that use of the model in the published results.
  - A claim that fails is not published as a result. The numbers still appear on the technical
    page as a check the model did not pass.

## What we learned

Nothing new yet: no test has been run. The test will be run once.

## Still to do

- Build and train the model on the training sites only.
- Run the held-out test once and report the numbers, whether they pass or fail.
- Show the results on a technical page of the website.
