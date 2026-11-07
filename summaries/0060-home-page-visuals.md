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
  satellite swath sweeping across it. The swath stops for visitors who ask for reduced motion.
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
- **A fix to the number counters.** The four headline counts stopped on their first frame and
  showed 0 (for example "0 usable passes"). They now count up to the real figure.

## What we learned

- The USGS service has no imagery over open water, so a regional view from it has holes in the
  Bay; Sentinel-2 covers the whole area and is one of the project's own instruments.
- The first cloud-free Sentinel-2 date tried covered only the edge of its tiles. Picking a date
  with no empty pixels in both tiles fixed it, and the script now refuses a mosaic with gaps.

## Still to do

Nothing for the home page. If the site list changes, the pictures are remade with the script
(see the website README).
