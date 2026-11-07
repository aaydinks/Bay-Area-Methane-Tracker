# PR #54: Both cloud figures in the published passes

**Status:** open · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/54)

## In one sentence

The website database now keeps the whole-tile cloud figure next to Sen2Cor's per-site clear share
for every Sentinel-2 pass, and says which of the two decided whether the pass counts.

## Why it was needed

- **The switch in PR 51.** A Sentinel-2 pass now counts for a landfill when Sen2Cor's
  classification says at least 70% of the 5 km around it is clear, not when the 110 km tile is.
- **Comparison was lost on publication.** The pipeline's overpass table kept the old tile figure
  beside the new share, as the owner asked. The website database had room for only one figure,
  so a published update could not show what the switch changed for any pass.

## What it adds

- **Two new columns in the published pass table**, through a new database migration:
  - the whole-tile cloud-free share, for Sentinel-2 passes only;
  - which figure the pass's cloud-free share holds: Sen2Cor over the site, the tile figure (a
    Sentinel-2 pass Sen2Cor could not judge), or the scene figure (EMIT and Carbon Mapper).

  The database refuses a share outside 0 to 1 and any source other than those three.
- **Publishing carries them through** from the pipeline. Updates built before PR 51 have neither
  column; they are published as empty rather than guessed. Snapshot folders already written,
  such as the review copy loaded on November 6, still load.
- **The sample data the website is built from in testing** has both columns: empty in the older
  sample update, filled in the newer one. Nothing else in the sample changed.
- **No page changes.** The site's views and downloads only count passes by month, so they read
  the same. The new columns are in the database and the snapshot, ready for a comparison when one
  is wanted.

## What we learned

Nothing new about the data. The migration could only be checked in CI: no database runs on the
machine this was built on.

## Still to do

- **The owner must apply the migration before the next push.** Until it is applied to the live
  database, every `mw publish push`, including the scheduled run's, stops with an error that the
  column does not exist. Nothing is half-loaded: the push runs in one transaction. The earlier
  migrations were applied through the Supabase connector, so this one goes the same way, followed
  by the security and performance advisors.
- **Rebuild the review snapshot.** The copy reviewers see predates PR 51. A rebuild after the
  migration fills both columns for its Sentinel-2 passes.
