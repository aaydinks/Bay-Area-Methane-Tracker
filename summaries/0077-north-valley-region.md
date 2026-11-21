# PR #77: The project now looks at the North Valley

**Status:** merged 2026-11-21 · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/77)

## In one sentence

The area the project watches grows from the nine Bay Area counties to take in five North Valley
counties (Merced, Sacramento, San Joaquin, Stanislaus and Yolo), and every source is now asked for
the wider area.

## Why it was needed

The owner decided on 2026-11-19 to widen the tracker towards Stockton. The earlier steps made that
safe: new sites cannot disturb the five studied landfills, and the public website shows only what
has been cleared for it. This step switches the wider area on. It adds no landfills yet. The
North Valley landfills are proposed in a list for the owner to check by hand first.

## What it adds

- **A second region.** "North Valley" is defined in one place, with its five counties and a box
  drawn around them from the Census county outlines. It stops just short of 120°W, the limit the
  project's map calculations assume.
- **Wider satellite and aircraft pulls.** The twice-weekly refresh now asks NASA and Carbon Mapper
  for the whole area. That adds 111 plume records, all east or south of the Bay Area box.
- **Wider reference lists.** CalRecycle's landfill list now covers fourteen counties (62 landfills,
  up from 36). The air district outlines now cover the wider area (17 districts, up from 10).

Nothing on the public website changes. The new plumes are marked as North Valley and appear only
on the locked review copy.

## What we learned

- **Twenty North Valley landfills fit the choosing rule.** CalRecycle lists 26; 20 are permitted.
  Eleven have a drawn outline and nine would get a provisional circle. All six that report to EPA
  are among them.
- **Four of them already have several plumes on record**, counted on the outline or within 500 m:
  Yolo County Central (52), Kiefer (29), Forward (18) and Highway 59 (4).
- **The existing sites are untouched.** A trial of the twice-weekly run gave the same passes,
  estimates and site details for all 33 sites, and the same plumes for the public map.
- **The two boxes overlap.** The Bay Area box has always reached Sacramento, Stockton and Davis, so
  plumes there were already on the public map as plain dots. They stay there. Whether they should
  leave the public map until the North Valley has had its review is for the owner to decide.
- **An earlier count was for a different question.** The 1,196 waste plumes noted on 2026-11-19
  counted every year back to 2016 over a slightly larger box. The project pulls from August 2022,
  which gives 657 over the final box.

## Still to do

- Check the list of 20 proposed landfills by hand, then add them to the site list (owner).
- Decide about the plumes in the overlap (owner).
- The committed copies of the NASA scene list still cover the Bay Area box; the wider copies are
  written at each refresh and are the owner's to commit.
