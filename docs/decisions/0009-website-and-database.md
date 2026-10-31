# 0009: Public website and publishing database

- **Status:** accepted
- **Date:** 2026-10-30

## Context

The project needs a public website: the operators and the Air District review a private build from
Dec 9 to 23, 2026, and the public launch is Jan 6 to 8, 2027. The Jinja dashboard (`mw report build`) was
a stop-gap for local review. The website must:

- show every figure with its 90% range, tied to a named run, and never a made-up number;
- carry the project's framing on every page: a retrospective tracker, screening indications, never
  compliance findings, real-time monitoring or health claims;
- keep Carbon Mapper data private until Carbon Mapper confirms what may be published (non-commercial, not for
  redistribution; `DATA_TERMS.md`), while EMIT and Sentinel-2 data may be shown;
- be reachable by reviewers who have no developer accounts, and by nobody else, before Jan 6;
- stay fast on phones and work from the keyboard.

Most tables are empty today: there is no real model fit (detection curves and the emission floor are not
sourced), `data/registry/repairs.csv` has only a header, and the site outlines are provisional 500 m circles.
The first real refresh exists (PR #20): 2,171 passes over the five pilot sites, 1,286 usable; 614 Carbon
Mapper plumes; 28 plume days.

## Options considered

**Hosting and the review gate** (checked against current pricing pages on 2026-10-30):

1. Vercel Hobby. Free. Rejected for the review window: no password protection on
   Hobby, Vercel Authentication admits only Vercel accounts with project access, and the one alternative is a
   single "anyone with the link" shareable link per account, with no per-person list.
2. Vercel Pro with Password Protection. About $40 a month ($20 seat plus $20 per protected project). One shared
   password for every reviewer. Rejected on cost and control.
3. **Cloudflare Pages with Cloudflare Access. Chosen.** Free; Access is free for teams under 50 users. A
   reviewer enters their email and receives a one-time PIN; no account needed. The allowed-email list is the
   owner's. Access can protect preview deployments, the `*.pages.dev` hostname and the custom domain, so the
   public site can be built early and unlocked on Jan 6 by removing a policy. Trade-off: the dashboard steps are
   the owner's; deploys run from GitHub.

**Framework:**

1. Next.js. Vercel's framework; heavier pages, static export drops features, needs an adapter on Cloudflare.
2. **Astro with React islands. Chosen.** Static pages with small interactive islands: MapLibre GL for the map
   (built-in heat maps, no token), Embla for carousels, Motion for animation, hand-built SVG for the
   dot-and-whisker and timeline charts. Plain CSS with custom properties. Fewest bytes on phones.

**Where the data comes from at run time:**

1. The browser queries Supabase read-only views with the publishable key. Rejected: a key in the browser, a
   live dependency on a free-plan project that pauses after about a week without queries, and a leak that
   depends on the views being right.
2. **The build pulls from Supabase and writes static JSON and GeoJSON. Chosen.** Data is under 1 MB; filters
   and the date slider run in the browser. The browser holds no key, the site keeps serving if the project
   pauses, and a post-build scan can prove what the public output contains.

**Where the app lives:**

1. A separate repository. Rejected: the word list and the summaries would have to be copied between repos.
2. **`web/` in this repository. Chosen.** One shared word list, one summaries folder, one CI.

## Decision

1. **Store:** a Supabase Postgres database (project "Bay Area Methane Watch", Postgres 17, PostGIS) is the
   single publishing store. Migrations live in `supabase/migrations/` and are applied only with the owner's
   OK. The free plan has no branches, so CI tests them on a PostGIS container.
2. **Publications:** `mw publish` snapshots one run (sites, passes, plumes, estimates, checks and their
   results, operator figures, residents nearby, method checks, update log) and loads it in one transaction.
   Each snapshot has a visibility: draft, review or public. A simulated run can never be public; the database
   refuses it. Promotion to public asks for confirmation.
3. **Restricted rows:** plumes, passes, estimates and check results derived from a source whose terms are
   unconfirmed carry `restricted = true`, driven by `config/data_terms.yaml`. Row-level security hides them
   from the publishable key. Until Carbon Mapper confirms, the public build shows EMIT and Sentinel-2 passes
   and plumes only, and estimates that used Carbon Mapper passes stay restricted.
4. **Three safeguards against a leak:** row-level security on the publishable key; the public build refuses
   to run if a secret key is present in its environment; a post-build scan of the output fails on any
   restricted plume id, the string "carbonmapper", a Tanager or aircraft pass, or a simulated-data banner.
5. **Environments:** local (fixture data, or keys from the git-ignored `.env`); review (the `review` branch
   and pull-request previews, built with the secret key at build time, which the owner enters only in
   Cloudflare's preview environment variables, behind Access); public (production from `main`, built with the
   publishable key, behind Access until Jan 6). The publishable key may appear in the build; the secret key
   and the database password never leave `.env` and the host's own settings.
6. **Labels are computed in Python at publish time, not in the browser.** Evidence: strong when the call is
   "drop" (P(decrease) at least 0.975) or "rise" (at most 0.025), weak when inconclusive, none when
   insufficient data (ADR 0006). Size: on the log scale, cutoffs 1.33x and 2x (slight, moderate, severe),
   stored in `config/project.yaml` as `confirmed: false` until the owner confirms them. Colour: red for strong
   evidence of a severe increase, orange for strong moderate, yellow for a strong slight increase or any
   increase with weak evidence, grey for insufficient data, green otherwise. Colour never carries meaning
   alone: every result has an icon and a text label, and the shades pass WCAG AA in light and dark modes.
7. **Checks, not only repairs.** The before/after test runs on dated records of five types: Air District
   inspection, Air District notice, operator repair (with its kind), CARB plume notice, other. The result is
   "the change after this record", never a cause. The placebo check applies to every type (ADR 0010).
8. **Map symbols:** icon shape shows the record type; colour comes only from the statistical result of the
   latest check; a site with no check on record gets a neutral grey marker. No alarm icons anywhere.
9. **Wording:** one shared list (`config/wording.json`) read by the Python check and the web build. Banned
   everywhere: saved, real-time, violation, non-compliant, illegal, lives, health impact. Required:
   "retrospective" in the home page header and "screening indication" on every site page. An official
   document title that contains a banned word may appear only inside a marked source-document quotation. A
   build with any other hit fails.
10. **Empty states everywhere:** every view says what is missing and when the first real results are
    expected. Simulated data is never shown without a persistent banner, and never in the public build.
11. **`mw report build` stays** as the offline local preview and is not published.
12. **Basemap:** OpenFreeMap vector tiles (free, no key, attribution automatic). Its terms are "as-is" and the
    service may stop without notice; the fallback is a Protomaps extract on Cloudflare R2.

## Consequences

- **The owner's tasks:** create the Cloudflare account and Pages project, the Access policies and the
  reviewer email list; buy the domain through Cloudflare Registrar so the DNS zone and Access sit together;
  enter every key; approve each migration before it is applied; ask Carbon Mapper whether derived counts and
  model estimates may be published; source detection curves and the emission floor.
- **A thin public launch if Carbon Mapper has not confirmed by Jan 6:** methods, a two-source map, the checks
  registry and operator figures. The ask to Carbon Mapper goes out now.
- **Supabase free plan:** about 500 MB (a snapshot is a few MB) and a pause after about seven quiet days. The
  static site is unaffected; `mw publish` reports a paused project plainly and the owner resumes it. A daily
  scheduled read or the Pro plan ($25 a month) removes the pause.
- **Content depends on upstream facts:** without confirmed detection curves and `q_min` there is no real
  estimate and no check result; the review build then shows real passes, plumes and method checks, and empty
  states for the rest, or a provisional fit behind its banner if the owner chooses.
- **Carbon Mapper scenes give the Tanager and aircraft passes**, so those passes are restricted like the
  plumes. Public pass counts and plume days per usable pass are EMIT and Sentinel-2 only until terms are
  confirmed, and the map says so.
- **New dependencies:** `psycopg` (Python, for `mw publish` and the migration tests); in `web/`, Astro, React,
  MapLibre GL, Embla, Motion and the Supabase client, with the list kept short on purpose.
- **Order of work:** ADR; shared word list; database schema; checks registry; `mw publish`; web skeleton with
  CI and the protected deploy; then the home page, map, checks page, site pages, methods and data pages, and
  the update feed; finally the review and launch checklists. Each is its own pull request from `main`.
