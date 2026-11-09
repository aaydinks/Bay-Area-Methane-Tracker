# 0017: Display-only data on the public website

- **Status:** accepted
- **Date:** 2026-11-08

## Context

Until now a source was either open or hidden. Rows from a source whose terms were not confirmed
(Carbon Mapper) were marked `restricted`; row-level security kept them away from the publishable
key, and the public build dropped every figure built from them. Because the first real fit used
Tanager-1 and aircraft passes, that meant every site estimate as well.

On 2026-11-08 the project owner reported Carbon Mapper's verbal confirmation: figures built from
its data may be shown on the website, but the data may not be republished. No downloads, no data
tables, no individual values. The written terms are still to be checked.

A static site gives away anything its browser can load, and the publishable key ships inside the
site, so anyone can read through it whatever the database lets that key read. "Shown but not
republished" therefore has to be enforced in the database and at build time, not in the page.

## Options considered

1. **Mark Carbon Mapper `derived_publishable`.** One line of config. But it clears `restricted`
   on every Carbon Mapper row, so plume rates reach `plumes.csv`, the map file and the
   publishable key. Rejected.
2. **Give the public build the secret key and filter there.** It needs no database change. But a
   build that holds the key can leak through any bug, and the launch checklist keeps every
   secret out of production. Rejected.
3. **A display-only level in the database** (chosen). Rows keep `restricted = true` and gain
   `display_only = true`. Five read views serve the public build only what the pages show, each
   through a function that runs with its owner's rights and returns rows of public publications
   only:
   - plumes become dots, with place, day, site and attribution, and no rate, uncertainty, id or
     data version;
   - passes become monthly counts per site and instrument, and plume days per site;
   - site estimates and check results are returned as they are.

## Decision

- **Config:** `config/data_terms.yaml` gains `display_publishable`. A source that is confirmed
  and display-publishable, but not derived-publishable, is display-only.
- **Build:** `mw publish build` marks its plumes and passes `display_only`. It also marks an
  estimate or check result `display_only` when every restricted instrument behind it comes from
  a display-only source. If any instrument behind a figure is still fully hidden, the figure
  stays hidden.
- **Database (migration 0007):** the columns, plus `v_public_plumes`, `v_public_pass_months`,
  `v_public_plume_days`, `v_public_site_estimates` and `v_public_checks_with_results`. The
  existing row-level rules are unchanged: the base tables still never show a restricted row to
  the publishable key.
- **Public build:** it reads the `v_public_*` views and keeps every restricted row out of the CSV
  downloads. `check-public-output` fails the build if:
  - a display-only plume carries a rate;
  - a download holds a Carbon Mapper instrument or source;
  - a download holds a restricted estimate or result;
  - any restricted row appears while the terms say hidden.
- **Review build:** unchanged. It still reads every row with the secret key behind Cloudflare
  Access.

## Consequences

- The public site shows the site estimates, monthly pass counts and map dots that use Carbon
  Mapper data, and says those figures are left out of the downloads.
- The downloads hold only open data: the estimates CSV is empty while every estimate uses Carbon
  Mapper passes.
- If the written terms differ from the verbal confirmation, change `config/data_terms.yaml` and
  rebuild. Setting `display_publishable: false` returns to hiding everything.
- Supabase's security advisor flags the five functions as `SECURITY DEFINER` functions the
  publishable key can call (lint 0028). That is intended: calling one returns exactly what its
  view returns, which is only what the public pages show.
