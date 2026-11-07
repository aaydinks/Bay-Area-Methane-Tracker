# PR #60: A home page built around pictures

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/60)

## In one sentence

The home page now leads with a real satellite picture of the Bay with the five landfills marked,
shows each landfill from the air, and explains the method in short illustrated steps, with
carousels that move on their own two slides at a time.

## Why it was needed

The owner found the home page wordy and plain: a long introduction, a drawn map, text-only cards
and paragraphs of caveats. The project is about what can be seen from above, so the page should
show it.

## What it adds

- **The Bay from space.** A Sentinel-2 true-colour picture of the Bay Area from 17 June 2025 (two
  cloud-free tiles from the same pass), with a red marker and name for each landfill and a faint
  satellite swath that sweeps across it once. Visitors who ask for reduced motion see no sweep.
- **Each landfill from the air.** An aerial close-up of every site from the US Geological
  Survey's public image service, centred on the site's location. No outline is drawn on them,
  since the outlines are still placeholders.
- **Carousels that rotate.** Two slides are in view; every 5 seconds the strip moves on by one and
  loops back to the start. Arrows on the left and right move it by hand, as do the dots and the
  arrow keys. It pauses while the pointer or keyboard is on it, has a pause button, and does not
  move at all for visitors who ask for reduced motion.
- **Fewer words.** The introduction is two sentences; the six method steps have a drawing each and
  a line of text; the four limits of satellite data are short tiles with an icon. The full text
  stays on the Methods page.
- **Credits** under each picture and on the Data page. The pictures are made once by a script in
  the website folder and committed, so a build never depends on the image services being up.
- **No figure for sites without an estimate.** The landfill cards showed a median for every site,
  including the three the model marks as insufficient data because their 90% range spans more
  than a hundredfold (Acme Fill, Shoreline, Sonoma Central). They now say "Not enough data for an
  estimate", matching the count of two sites with an estimate.
- **A fix to the number counters.** The four headline counts stopped on their first frame and
  showed 0 (for example "0 usable passes"). They now count up to the real figure.

## What we learned

- The USGS service has no imagery over open water, so a regional view from it has holes in the
  Bay; Sentinel-2 covers the whole area and is one of the project's own instruments.
- The first cloud-free Sentinel-2 date tried covered only the edge of its tiles. Picking a date
  with no empty pixels in both tiles fixed it, and the script now refuses a mosaic with gaps.

## Still to do

- The Landfills page still ranks and charts the three insufficient-data sites under "Sites with an
  estimate"; that is a separate fix.
- The pictures are remade with the script when the site list changes (see the website README).
  The committed close-ups came from the same image request the script makes; the script's own
  last full run could not finish its USGS part because that service kept timing out.
