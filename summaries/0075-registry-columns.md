# PR #75: Each site records its region, state site number and air district

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/75)

## In one sentence

Every landfill in the project's list now says which region it is in, what California's waste
agency calls it, and which air district regulates it, ready for the many sites still to be added.

## Why it was needed

With five Bay Area landfills these facts were obvious and lived in people's heads. The project is
about to add dozens more sites, in two regions and under several air districts. Three things then
have to be written down per site:

- **Region**, because the public website shows only some regions for now.
- **The state site number** (CalRecycle's "SWIS number"), because it is the key that links a
  site to the state's list and to its drawn outline.
- **The air district**, because records requests and repair records come from the district, and
  some counties are split between two districts.

## What it adds

- **Three facts per site in the site list**, plus one renamed column (the district's own facility
  number, which used to assume the Bay Area district).
- **The region is worked out from the county.** If the list says something else, or the county is
  in no region, the build stops and says which site.
- **The state site number is filled in for the five pilot sites**, from the table checked against
  CalRecycle on 2026-10-17. The build checks the number's form and that no two sites share one.
- **The air district is read from a map.** A new download fetches the outline of every air
  district that touches the project's regions from the state air board (CARB). Each site gets the
  district that holds most of its outline.
- **That answer is marked "not confirmed".** CARB's outlines date from March 2004. Once a person
  has checked a site with its district and written the district into the list, the build uses
  that value and marks it confirmed.
- **A short list of sites to check first**: any site within 500 m of a district edge, or in no
  district outline.
- **A database change** (three added columns on the sites table) so the website's data can carry
  the district.

## What we learned

- All five pilot sites sit wholly inside the Bay Area district on CARB's map, and none is closer
  than 1.6 km to its edge.
- Asking CARB's map for "every district that touches this box" avoids guessing district codes.
  One code already guessed in an old test (for the San Joaquin Valley) was wrong.
- The website already had a place for the state site number on each site page, but the number was
  never filled in. It will appear on the five pilot pages with the next published update.

## Still to do

- The database change must be applied to the live database before this is merged. That needs the
  project owner's go-ahead.
- Nobody has yet confirmed any site's air district with the district itself.
- The website does not show the air district yet; that comes with the wording for several
  regulators.
- The district facility numbers are still blank; they come from permits.
