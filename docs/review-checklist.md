# Review build checklist (Dec 8, 2026)

The private review with the operators and the Air District runs Dec 9 to 23. This is what has to be
true of the review build on Dec 8, who does it, and how it is checked. Items marked **owner** can only
be done by the project owner.

## Data

- [ ] `mw refresh` has run within the last week and `data/interim/refresh/latest.json` names it.
- [ ] If detection curves and the emission floor are confirmed: `mw model fit` and `mw repair run`
      have run on real data, and their run ids are known. If not: the owner has chosen between a
      provisional fit behind its banner and no estimates at all, and that choice is written in the
      publication's notes.
- [ ] Every row of `data/registry/checks.csv` cites a source document; descriptions are in the
      project's own words; official titles sit in `source_doc_title`.
- [ ] `mw publish build` succeeded with no wording hit, and `mw publish check <id>` passes.
- [ ] `mw publish push <id>` loaded the snapshot, and `mw publish list` shows it as `draft`.
- [ ] `mw publish set-visibility <id> review` was run. The publication is not simulated.
- [ ] The Supabase security and performance advisors report nothing new (**owner** runs them, or
      asks for them to be run through the connector).

## Build and hosting

- [ ] The `review` branch is at the commit to be reviewed and its Cloudflare preview build is green.
- [ ] Preview environment variables: `SITE_MODE=review`, `DATA_SOURCE=supabase`, `SUPABASE_URL`,
      `SUPABASE_SECRET_KEY` (**owner**). Production variables use the publishable key only.
- [ ] Cloudflare Access is enabled for preview deployments, and the reviewers' email addresses are
      on the policy (**owner**). The owner has logged in through the one-time PIN flow once.
- [ ] The production deployment (public mode) is behind Access as well, on `*.pages.dev` and on the
      custom domain if one is attached (**owner**).
- [ ] CI is green on `main`: lint, types, both fixture builds, wording check, public-output check,
      accessibility scan, Lighthouse budgets.

## Pages (walk every one on a phone and on a desktop, light and dark)

- [ ] Every page shows the data-through date, the source lag, the publication id and the credits.
- [ ] No page shows the sample-data banner. The provisional banner shows only if the publication is
      provisional.
- [ ] Home: counters, landfill cards and the latest update match the publication; carousels work with
      the keyboard; the hero is still under reduced motion.
- [ ] Map: tiles load; the five markers show the right shape and colour; the side panel matches the
      landfill page; the table view matches the map.
- [ ] Checks: every row's plain reading reads correctly; sorting and filters work; the phone cards show
      the same rows.
- [ ] Landfill pages: estimate or the insufficient-data reason; timeline; checks; operator figures with
      the unconfirmed-GWP note; residents as context only.
- [ ] Methods: the gate results and their run ids match `reports/validation/`.
- [ ] Data: downloads open, and the README names the same publication as the footer.
- [ ] Shared link previews show the right landfill and figures.

## What the public build must not contain

- [ ] Open the production deployment through Access and confirm the map's source list shows NASA EMIT
      and Sentinel-2 only, no Carbon Mapper row appears in any download, and the banner says Carbon
      Mapper data is held back.
- [ ] `check-public-output` passed in the production build log.

## Sending the review

- [ ] A one-paragraph note to reviewers (**owner** sends it): what the site is, what it is not (a
      screening indication, not a finding), the review window, where to send comments, and that nothing
      is public before Jan 6.
- [ ] Late records: anything arriving after Dec 8 goes into a later publication as an update, not into
      the review build.
