# PR #63: Show Carbon Mapper figures on the public site without republishing its data

**Status:** merged 2026-11-08 · [pull request](https://github.com/aaydinks/Bay-Area-Methane-Tracker/pull/63)

## In one sentence

The public website can now show figures built from Carbon Mapper data, such as each landfill's
yearly estimate, monthly pass counts and plume dots on the map. It never offers that data as a
download or shows a plume's rate.

## Why it was needed

Carbon Mapper told the project owner (verbally, reported Nov 8, 2026) that its data may be
displayed but not republished: no downloads, no data tables, no individual values. The site knew
only two levels, hidden or fully open. Hidden would have left the public site with no estimates,
because the first real fit used Carbon Mapper's passes. Fully open would have put every plume's
rate in the downloads and within reach of anyone using the site's public database key.

## What it adds

- **A third level, "display only".** Carbon Mapper's rows stay hidden in the database tables and
  are marked display-only.
- **Five new read views.** They give the public site only what its pages show:
  - plume dots with place, day and site, but no rate;
  - counts of passes per month and plume days per site;
  - the site estimates and check results.
- **Downloads.** The CSV files leave out every Carbon Mapper row and every figure built from one.
  The site says so in a banner and on the data page.
- **The safety check.** It runs after every public build and fails if a dot carries a rate, or if
  a download holds a Carbon Mapper row. A test build checks this in CI.
- **The live database.** The change was applied before merging. It only adds columns and views,
  so the existing site and the twice-weekly refresh were unaffected.

## What we learned

Supabase's security advisor flags the five helper functions behind the views as callable with
the public key. That is intended: each returns exactly what its view returns.

## Still to do

Get Carbon Mapper's terms in writing and record them in `config/data_terms.yaml`. If they differ,
change the setting and rebuild.
