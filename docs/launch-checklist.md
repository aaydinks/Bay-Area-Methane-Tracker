# Launch checklist (Jan 6 to 8, 2027)

Nothing is public before Jan 6. Items marked **owner** can only be done by the project owner.

## Before Jan 6

- [ ] Reviewer comments from Dec 9 to 23 are answered or recorded; changes are merged to `main` and CI
      is green.
- [ ] Carbon Mapper's reply is recorded in `config/data_terms.yaml` (`confirmed`,
      `derived_publishable`, `checked_on`, `credit_line`). If derived tables may be published, the
      restricted flags clear on the next `mw publish build`; if not, the public site launches with
      EMIT and Sentinel-2 only and the launch note says so.
- [ ] Credit lines for every source are the ones the sources asked for.
- [ ] A fresh publication is built, pushed and checked (`mw publish check`), with the data-through date
      the launch note will quote.
- [ ] The domain is attached to the Cloudflare project and has a certificate (**owner**).
- [ ] Production environment variables: `SITE_MODE=public`, `DATA_SOURCE=supabase`, `SUPABASE_URL`,
      `SUPABASE_PUBLISHABLE_KEY`, `SITE_URL=https://<domain>` (**owner**). No secret key anywhere in
      production settings.
- [ ] A production build has run against that publication while it was still `review`, so the public
      pages could be checked behind Access: empty states read correctly, the Carbon Mapper notice shows
      when it should, downloads contain no restricted row, `check-public-output` passed.
- [ ] Lighthouse on the production build: accessibility at or above 95 on every page; performance at
      or above 90 on home, checks and landfill pages and at or above 80 on the map, or the gap is
      written down.

## Launch day

- [ ] `mw publish set-visibility <id> public --yes` after the confirmation prompt has been read. A
      simulated publication is refused; that is expected.
- [ ] Trigger the production build (deploy hook or the dashboard) and wait for it to finish.
- [ ] Open the production site through Access one last time: footer publication id, data-through date,
      credits, map sources, downloads README.
- [ ] Remove the Access policies for the custom domain and `*.pages.dev`; keep the policy on preview
      deployments (**owner**).
- [ ] Open the site from a phone that is not signed in to anything. Check a shared link preview.
- [ ] Send the launch note (**owner**): what the site shows, what it does not claim, the data-through
      date, where the data comes from, and how to report an error.

## After launch

- [ ] Schedule the refresh and publish cadence (monthly is enough with a 30-day source lag), each
      publication going `draft` to `review` to `public` with the same checks.
- [ ] Keep the Supabase project active (a publish a month does it on the free plan) or move it to a
      paid plan.
- [ ] Record what changed in each publication's notes; the update feed is built from the diff.
