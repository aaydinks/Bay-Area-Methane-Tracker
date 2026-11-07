# PR #49: The cloud model checked on 2025 landfill passes

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/49)

## In one sentence

On every 2025 Sentinel-2 pass over the five landfills, the cloud model told clear views from
cloudy ones well, but it kept calling the same rooftops, ponds and parts of the landfills cloud
on clear days, so by the rules written beforehand it does not decide which passes count.

## Why it was needed

- **The gap.** The cloud model passed its held-out test (PR 44), but every image in that test
  dates from 2017 to 2020.
- **What is different now.** The landfill passes since 2022 use newer processing, which shifts
  every brightness value. They also include a new satellite, Sentinel-2C.
- **The plan.** Decision record 0014 fixed six rules before any landfill number existed. The
  model would decide which passes count only if all six held.

## What it adds

- **The check, run once.** 501 site-days on 157 days in 2025. Each one is a 6 km window of all
  13 Sentinel-2 bands around the site, scored over the central 5 km. Sen2Cor's scene
  classification for the same window is the yardstick.
- **Five rules held:**
  - the brightness scale of the newer images matches the training images;
  - the model threw away none of 261 views Sen2Cor saw as clear;
  - it kept 2.9% of views Sen2Cor saw as cloudy (90% range 0.6 to 6.1%; the limit was 18.7%);
  - Sentinel-2C behaves like the older satellites;
  - in a blind look by eye at 24 views, where the model and Sen2Cor disagreed, the eye sided
    with the model 12 times and with Sen2Cor 4 times.
- **One rule failed, at every site: no fixed false clouds.** On clear days the model kept
  flagging the same places:
  - rooftops at Newby Island and Shoreline;
  - dark ponds at Newby Island and Acme Fill, called shadow;
  - parts of the landfills themselves, at Sonoma Central (a tenth of the circle around the site)
    and Potrero Hills.
- **On the website.** The cloud model page gains a section showing all six rules and the
  per-site false-cloud shares.

## What we learned

- **The newer images were not the problem.** The worry about new processing and a new
  satellite did not come true.
- **Fixed surfaces were.** Bright roofs and dark ponds near landfills fool the model on clear
  days. This seldom changes whether a whole pass counts.
- **It still rules the model out for masking before plume detection.** It would mask parts of
  the landfills, which is where a plume starts.
- **Sen2Cor has its own errors here.** In all 8 views where only the model said usable, the eye
  agreed with the model. Following the rule therefore costs a few clear passes a year at each
  site.
- **Downloads cost more than they occupy.** Reading a 6 km window of all 13 bands downloads
  about 35 MB, because the archive stores the bands in large compressed blocks. Sen2Cor's layer
  needs about 0.1 MB per window.

## Still to do

- **Switch `valid_frac`.** As decided in advance, the whole-tile cloud figure gives way to
  Sen2Cor's share over each site, and the tile figure is kept beside it. This needs Sen2Cor's
  layer for every pass from 2022 to 2026, about 0.15 GB, which waits on the user's approval.
- **Count usable passes per site** under the whole-tile rule and Sen2Cor. The model's counts
  are not published.
- **A later model** with training examples of roofs, ponds and landfill surfaces would need its
  own decision record and its own check, with both results reported.
