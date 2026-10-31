# PR #44: The cloud model passed its test, and a page that shows how

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/44)

## In one sentence

The cloud model passed both tests that were written down in advance, on 1,095 images it never
saw, and a new technical page on the website explains how it tells clouds from methane plumes
and how well it did.

## Why it was needed

- **What the project is for.** It only publishes a method's output as a result when there is
  proof it helps.
- **What the plan said.** Decision record 0013 fixed two claims and their pass rules before
  any result existed, and said the test would run once.
- **What was left.** This change records that one run and shows it.

## What it adds

- **The result.** Measured on expert-labelled patches of about 5 km, from 219 places the model
  never trained on.
- **Fewer cloudy views counted as usable.**
  - The model counted 8.5% of too-cloudy views as usable (90% range 6.8 to 10.2%).
  - The whole-tile figure the project uses now counts 36.9%.
  - The best published cloud product (s2cloudless) counts 30.3%.
  - The model threw away 4.9% of clear views. The whole-tile figure throws away 26.2%.
- **Fewer false detections caused by clouds.**
  - About 8 per image pair with the model, against 12 to 16 for the other methods.
  - Simulated plumes were found as often as with any other method.
- **One caveat.** A larger network from the dataset's authors did better still on the same
  test. It was shown for reference only and needs extra software to run.
- **The page** (Methods, then "Clouds in Sentinel-2 images"):
  - why clouds matter;
  - a chart of how clouds, shadows and plumes each change the 13 Sentinel-2 bands;
  - how the test was set up;
  - both results, with charts and tables;
  - the 15 test images from the Bay Area;
  - the one correction made before the test, and why.

## What we learned

- **Judging clouds over each site, not the whole tile, matters most.** The whole-tile figure
  wrongly kept more than a third of the cloudy views and wrongly dropped a quarter of the
  clear ones.
- **The plume part of the test is weak.** Image pairs months apart are noisy, so only about a
  quarter of the simulated plumes were found by any method.
  - In the rehearsal on tuning images, the model lost a few points of plumes, which would have
    failed.
  - Read the second result as a sign that the model does not hide plumes, not as proof.

## Still to do

- Use the model, or another per-site cloud mask, to decide which Sentinel-2 passes count for
  each landfill. That will change the usable-pass counts on the site pages.
- Decide whether the larger network is worth its extra software.
- Mask clouds before Sentinel-2 detection.
