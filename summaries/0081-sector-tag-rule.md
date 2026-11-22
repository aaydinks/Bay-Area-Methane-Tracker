# PR #81: A plume tagged as another kind of source no longer counts for a landfill

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/81)

## In one sentence

A methane plume that starts on or beside a landfill, but that Carbon Mapper tags as coming from
something other than solid waste, is now marked "ambiguous" and not counted for the landfill.

## Why it was needed

A plume counts for a landfill when it starts on the landfill's outline or within 500 m. The only
guard against counting a neighbour's plume was a hand-written list of neighbouring sources. That
list names neighbours for one landfill, and none of them has been drawn on the map yet, so the
guard was not working anywhere. With 52 sites, and dairies and other methane sources close to
several North Valley landfills, a second guard was needed.

Carbon Mapper already labels each plume with the kind of source it believes produced it. The
project carried that label and did not use it.

## What it adds

- **The rule.** On or beside a landfill, a plume labelled as another sector (livestock, oil and
  gas, or "other") is marked ambiguous. It stays on the map beside the site and is never counted.
- **A plume with no label is treated as before.** A missing label is not evidence of another
  source. NASA's own plume outlines carry no label and are unaffected.
- **One setting** that says which label means landfill.
- **A decision record (0022)** with the reasoning and the numbers.

## What we learned

- **Almost every plume near a site is labelled solid waste**: 641 of the 653 that were counted.
- **Twelve plumes change**, all at landfills still under review: Kiefer 7, Altamont 4, Vasco
  Road 1. Five passes at those sites now count fewer plumes; each still has one that counts.
- **The five studied landfills are untouched.** No plume there carries another label, so the
  official estimates and the public website do not change.
- **Eleven of the twelve are labelled "other" and start on the landfill's own outline.** They may
  come from something on the property, such as a compost pad or a gas engine. Holding them back is
  the cautious choice for a screening list, since it can only lower a landfill's count. The owner
  can reverse it.

## Still to do

- Say on the methods page that a plume can be ambiguous because of its label (with the other
  wording changes for many sites).
- Check whether Carbon Mapper documents how it assigns the "other" label.
