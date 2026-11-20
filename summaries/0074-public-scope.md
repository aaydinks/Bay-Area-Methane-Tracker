# PR #74: A gate on what the public website may show

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/74)

## In one sentence

The public website now shows only the regions and kinds of site on a short written list, so new
landfills can be added and reviewed in private without appearing in public.

## Why it was needed

Until now a set of results was either public or not, as a whole. The plan adds several dozen
landfills, and the project owner decided that new sites go to the locked review copy first and
become public only after their operators and regulators have had a look. Without a gate, adding
one new landfill to the site list would have put its page, its plumes and its figures on the
public site at the next update.

## What it adds

- **A written list of what may be public.** It names regions and kinds of site. It starts as
  exactly what is public today: the Bay Area, and the five sites studied in depth. Only the
  project owner changes it.
- **A stamp on every row.** When a set of results is built, each row is marked as inside or
  outside that list.
- **Three independent checks of the stamp:**
  - the database refuses to hand a row outside the list to the public site's key;
  - the website build drops such rows again when it reads the data;
  - a last check reads the list itself, looks at what was built, and stops the build if anything
    outside the list got through.
- **Plumes near a site under review stay on the map as plain dots.** They were already public as
  unassigned dots, so they do not disappear; they just do not say which site they belong to.
- **Tests** with one sample site held back: it gets no page and no rows in the public build, and
  the last check fails when an outside site is put back by hand.

## What we learned

One plume already on the public map does not belong to the Bay Area at all. It is a NASA plume a
few hundred metres east of the Bay Area's box, near Manteca in the North Valley. Under the new
rule it lies in no listed region, so it leaves the public map until the North Valley is reviewed
and added to the list. Every other row shows as before.

## Still to do

- The database change must be applied to the live database before this is merged. That needs the
  project owner's go-ahead.
- The review site does not yet mark which sites are held back from the public (planned with the
  pages for many sites).
- The website's database type file is out of date and is regenerated separately.
