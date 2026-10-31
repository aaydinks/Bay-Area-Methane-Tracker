# PR #43: A small model that recognises clouds in Sentinel-2 images

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/43)

## In one sentence

This adds a small model that labels each part of a Sentinel-2 image as clear, cloud or cloud
shadow, trained on public expert-labelled images, together with the one-time test written down
in advance (decision record 0013).

## Why it was needed

- **The problem.** Clouds and their shadows can look like methane plumes to the Sentinel-2
  method. They also decide which satellite passes count for a site.
- **What the project used before:**
  - a fixed brightness rule;
  - the cloud figure for a whole image tile, about 110 km across.
- **Decision record 0012** found plenty of open cloud labels to learn from. It also chose the
  smallest kind of model worth trying.

## What it adds

- **The model.** A set of decision trees that looks at all 13 Sentinel-2 bands, a few band
  ratios, and how bright and varied the surroundings are.
  - It never labels anything a plume. Methane changes only one band, so a model that is right
    about clouds should leave plumes alone. The test checks that.
- **Training data.** 3,000 image patches from 600 places in CloudSEN12+, a public-domain
  collection where experts outlined clouds and shadows by hand.
  - No Bay Area landfill images were used.
  - No Carbon Mapper data were used.
- **Commands** to download the images, train the model, and run the test.
  - The test refuses to run a second time.
  - A rehearsal mode runs the same code on separate tuning images, so mistakes can be found
    without touching the test images.

## What we learned

- **First rehearsal, on tuning images only:** the model was too cautious. It threw away 16% of
  clear views. It had been trained on equal numbers of clear, cloud and shadow examples, which
  overstates how common clouds are.
- **The correction.** The model's answers are now re-weighted to the real shares (about 64%
  clear, 30% cloud, 7% shadow).
- **After the correction**, on tuning images: it calls 8% of too-cloudy views usable, against
  30 to 56% for the other methods, and throws away 7% of clear views.
- **The plume part of the test is weak.** The image pairs are months apart, so even with no
  mask only about a quarter of the simulated plumes are found. A perfect cloud mask does not
  lose plumes under this measure, so the measure itself is fair.

## Still to do

- Run the held-out test once, from the merged code, and report the result whether it passes
  or fails.
- Show the results on the website's technical page.
