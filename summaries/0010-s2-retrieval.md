# PR #10: Finding methane plumes in Sentinel-2 images

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/10)

## In one sentence

Built the method that spots large methane plumes in free Sentinel-2
satellite images and decides whether a plume belongs to a landfill.

## Why it was needed

Sentinel-2 passes every few days and its images are free, but it was never
designed for methane. It only sees very large plumes, about 2 tonnes an hour
or more, and dark or shiny surfaces can fake a plume. The plan therefore
treats it as a check on big events, never the main detector: a Sentinel-2
plume never counts against a site unless EMIT or Carbon Mapper saw it too.
"Gate 2" asks the method to reproduce a plume Carbon Mapper also saw.

## What it adds

- **The published method** (Varon et al. 2021). Methane absorbs one band of
  infrared light more than a neighbouring band. Comparing the two bands, then
  comparing against a clean image of the same place from another day, leaves
  only what changed: the plume.
- **Filters for false plumes.** Water, shadows, very dark or very bright
  surfaces and clouds are masked out first.
- **Plume detection.**
  - Unusually strong patches of signal are grouped into plumes; tiny specks
    are ignored.
  - A plume counts for a landfill only if it starts inside that landfill's
    area.
  - With wind data, the plume's upwind end is taken as its source.
- **Starting thresholds** in the settings, to tune against real cases.

## What we learned

On simulated images, the method recovered a planted plume's strength to
within 20%, found it at the right site, ignored sites elsewhere, and raised no
false plume on noise alone.

## Still to do

- **A choice of image source.** The Amazon copy charges for downloads, so the
  choice is Europe's free Copernicus service (account needed) or a free
  processed version.
- **A conversion table** from the signal to methane concentration, which
  comes from whichever published processing pipeline is adopted.
- **One plume seen by Carbon Mapper** on a day Sentinel-2 also passed, to
  pass Gate 2.
