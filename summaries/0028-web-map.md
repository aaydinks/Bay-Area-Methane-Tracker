# PR #28: Interactive map with heat map, passes and site markers

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/28)

## In one sentence

The map page now shows where plumes were seen as a heat map, how often each landfill was
observed, and the latest check at each site, with filters, a legend and a side panel, and the
same figures in a table for anyone who cannot use a map.

## Why it was needed

A list of plume counts misleads on its own: Newby Island was flown far more often than the other
sites, so it shows more plumes whether or not it leaks more. The map had to show plumes and
passes together, let a reader narrow by source, instrument and date, and point at each landfill's
latest check without turning a marker into an accusation.

## What it adds

- A map on free, keyless OpenFreeMap tiles in light and dark, with the basemap credit shown.
- Layers: plume density as a heat map, weighted by count or, where a rate is known, by rate;
  plume origins when zoomed in, hollow when a plume is ambiguous and ringed when it is new in the
  latest update; usable passes per site as sized circles; site outlines, dashed where the outline
  is still a provisional circle; neighbouring methane sources; county and Air District lines.
- Controls that work without the mouse: source, instrument and layer toggles, a from and to month
  range, and the heat-map weight. A legend, and a status line with the plume count and the
  data-through date.
- Markers: the shape says what the latest record was (inspection, notice, repair, plume notice);
  the colour says only what the statistical result was; grey means no check on record. Clicking
  a marker opens a panel with the estimate and its 90% range, the latest check, the plume count
  under the current filters, the pass counts and a link to the landfill page.
- The table under the map with the same figures per landfill, so screen-reader users lose nothing.
- On the public site the Carbon Mapper layer is held back until its terms are confirmed, and the
  page says so.

## What we learned

The public-output scan was too strict for the map's own script, which has to name every source
it can filter even when the data holds none of it; the scan now reads pages and data files only.
The accessibility scan was flaky while sections faded in, so it now runs with reduced motion.

## Still to do

The sortable checks table, the landfill pages with their pass timelines and charts, and the
downloads page. Real outlines will replace the dashed circles when they are traced.
