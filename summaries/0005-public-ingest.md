# PR #5: Pulling the public data that needs no login

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/5)

## In one sentence

Connected three public data sources (NASA's EMIT satellite, ESA's Sentinel-2
satellites, and the EPA's emissions reports) and checked each one with real
data.

## Why it was needed

The plan's first weeks call for confirming what each data source really
provides before anything depends on it. Three sources can be used without an
account; the others wait on registrations only the project owner can do.

## What it adds

- **NASA EMIT.** The outline of every EMIT image over the area, which records
  each pass, and the outlines of plumes NASA has reviewed and released. EMIT
  is the most reliable record of passes available today. Plume rates need a
  NASA login.
- **Sentinel-2.** The outline of every Sentinel-2 image over the area. These
  satellites pass every few days, but only see very large plumes, about
  2 tonnes an hour or more.
- **EPA Greenhouse Gas Reporting Program.** Operators' self-reported landfill
  methane, matched to the pilot sites. The EPA publishes CO2-equivalent, so it
  is converted back to methane with a factor (25) that still needs confirming.
- **A logged record of every download**, so each result can be traced back to
  its source.

## What we learned

- **Over the pilot area:** 156 EMIT images, 4 NASA-released EMIT plumes, and
  550 Sentinel-2 images in 2025. One EMIT plume, on August 7, 2024, sits near
  Newby Island.
- **What operators report** (2023):

  | Landfill | Reported methane, 2023 |
  |---|---|
  | Newby Island | about 7,950 t |
  | Sonoma Central | about 4,300 t |
  | Potrero Hills | about 4,220 t |
  | Shoreline | stopped reporting after 2018 |
  | Acme Fill | no record found |

  17 Bay Area landfills reported in 2023.
- **Not every satellite image that touches the area covers a landfill.** That
  is why coverage is measured per site.
- **The raw Sentinel-2 files on Amazon's cloud charge for downloads.** Image
  pixels will come from Europe's free Copernicus service or a free processed
  version instead.

## Still to do

- EMIT plume rates and cloud masks need a NASA Earthdata login.
- Carbon Mapper, the main plume source, needs API access.
- The methane conversion factor needs confirming.
