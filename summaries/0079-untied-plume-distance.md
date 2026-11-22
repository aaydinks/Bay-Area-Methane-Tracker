# PR #79: A plume with no site no longer carries a distance

**Status:** merged 2026-11-21 · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/79)

## In one sentence

A plume that is tied to no landfill is now published without a distance, so it cannot hint at a
landfill the public website does not show yet.

## Why it was needed

Every plume record had a "distance to the nearest landfill on the list" field. For a plume tied to
a landfill, that is useful. For a plume tied to none, the nearest landfill could be one still under
review, and the number would then say something about a site the public is not meant to see yet.
This was noticed when the North Valley landfills joined the list.

Nothing leaked. The website never showed the number, and the current public copy was made before
any landfill under review was on the list.

## What it adds

- The distance is left empty for a plume tied to no landfill.
- A test that fails if the number comes back.

Plumes tied to a landfill keep their distance exactly as before. The database is not changed.

## What we learned

- **The change touches only what it should.** A trial of the twice-weekly run on today's data (52
  landfills, 744 plumes) emptied the distance for the 55 plumes with no site. The other 689
  plumes, and every site, satellite pass and estimate, came out identical.
- **Copies made earlier keep the old number.** The two review copies made earlier on 2026-11-21
  were built before this fix. Only copies built after it should be made public.

## Still to do

- Nothing further for this fix. The next twice-weekly run builds a clean copy.
