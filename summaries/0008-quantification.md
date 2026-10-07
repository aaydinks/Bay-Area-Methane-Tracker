# PR #8: Measuring a plume's size from a picture

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/8)

## In one sentence

Added the step that turns a satellite picture of a plume into a leak rate in
kilograms per hour, using local wind data, with a range for the uncertainty.

## Why it was needed

Carbon Mapper and NASA publish rates for their own plumes, but plumes the
project finds itself in Sentinel-2 images arrive only as pictures. To compare
them with other satellites, which is Gate 2, they need a rate too.

The standard method adds up all the extra methane in the plume, then works
out how fast the wind is clearing it away. That needs wind at the site at the
time of the image. The plan says to choose a wind source in week 3 and record
why.

## What it adds

- **The rate calculation.** It totals the methane in the plume, divides by
  the plume's length and multiplies by an effective wind speed. The range
  reflects uncertainty in the wind, in the published calibration, and in
  background noise in the image.
- **Two wind sources:**
  - NOAA's HRRR: about 3 km detail, hourly, free with no account. Proposed as
    the main source, because the Bay Area's sea breeze and hills need fine
    detail.
  - Europe's ERA5: coarser, needs an account. Kept as a cross-check.
- **A one-line command** to look up the wind at any site and time.

## What we learned

On a simulated plume of known size, the method recovered the plume's methane
to within 2%. The wind-calibration numbers come from the Sentinel-2 method
paper (Varon et al. 2021). They are marked unconfirmed until checked against
the paper, and every rate says whether its calibration is confirmed.

## Still to do

- One live wind lookup to finish the wind decision. It downloads a small file
  and is waiting for the owner's OK.
- Confirming the calibration numbers.
- Real Sentinel-2 plumes to measure.
