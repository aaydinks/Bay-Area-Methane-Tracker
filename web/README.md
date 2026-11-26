# Website

The public face of Bay Area Landfill Methane Watch: a static site built with Astro from one
published snapshot of the project's database. Nothing is queried at run time. The browser never
holds a key.

## How a build works

1. `scripts/fetch-data.mjs` pulls one publication and writes `src/data/snapshot.json` and the
   GeoJSON files under `public/data/`. Two settings control it:
   - `SITE_MODE`: `review` (restricted rows and review-visibility publications; needs the secret
     key) or `public` (the newest public publication, no restricted row; refuses to run if a
     secret key is present).
   - `DATA_SOURCE`: `fixture` (sample rows from `fixtures/snapshot.json`, no keys) or `supabase`
     (the live database, through its read views).
2. Astro renders the pages. Every page names its kind in a `wording-kind` meta tag.
3. `scripts/check-wording.mjs` checks every page against the shared word list in
   `../config/wording.json` and fails the build on a hit.
4. `scripts/check-public-output.mjs` fails a public build if any restricted row, restricted
   source or instrument, simulated-data banner or key reached the output.

`npm run build` runs all four. `npm run dev` fetches and serves with live reload.

## Local work

```
cd web
npm ci
npm run fixture                 # (re)write the sample data; deterministic
cp .env.example .env            # defaults to fixture data in review mode
npm run dev
```

To build from the live database, put `SUPABASE_URL` and either `SUPABASE_PUBLISHABLE_KEY`
(public) or `SUPABASE_SECRET_KEY` (review) in the repository's root `.env` or in `web/.env`, and
set `DATA_SOURCE=supabase`. The secret key is never used by a public build.

Checks: `npm run lint`, `npm run check` (types), `npm run build` (includes the wording and
public-output checks), `npm run test:a11y` (axe, against the built site; run
`npx playwright install chromium` once), `npm run lighthouse` (budgets in `lighthouserc.json`,
against the built site; set `CHROME_PATH` to a Chrome or Chromium binary).

## Hosting (Cloudflare Pages)

Project settings, entered by the owner:

- Build command `npm run build`, build output `dist`, root directory `web`. Node version comes
  from `web/.node-version`.
- Production (the `main` branch): `SITE_MODE=public`, `DATA_SOURCE=supabase`, `SUPABASE_URL`,
  `SUPABASE_PUBLISHABLE_KEY`, `SITE_URL=https://<domain>`.
- Preview (every other branch, including `review`): `SITE_MODE=review`, `DATA_SOURCE=supabase`,
  `SUPABASE_URL`, `SUPABASE_SECRET_KEY`.
- Access: enable the access policy for preview deployments, then add policies for the
  `*.pages.dev` hostname and the custom domain until launch day.

Rebuild after a publication changes: trigger a deploy from the dashboard, or call a deploy hook.

## Layout

- `src/layouts/Base.astro`: header with the framing, banners (sample data, simulated, no data
  yet, provisional, Carbon Mapper held back), footer with credits and run ids. One light theme:
  white, black, red and a light green, set as tokens at the top of `src/styles/global.css`.
- `src/components/`: badges, tags, ranges, empty states, and `ReportedMeasures.astro`, the table
  of figures an operator or agency reported for a landfill. Its labels and caveats come from the
  published catalogue (`config/metrics.yaml`); a year with no figure reads "not reported". The
  section is left out for a copy published before the measures existed. `ObservedMeasures.astro` is its
  twin for counts the project made in a source's lists (today, CO2 plumes near a landfill): a
  year with no count reads as not searched, and the section appears only when the copy holds
  such a count, which a public build does not while the source's terms are unsettled.
- `src/pages/`: home, map, updates, checks, landfills, methods, how to read, data, 404.
- `src/lib/data.ts`: the typed snapshot and the helpers pages use; `database.types.ts` is
  generated from the live schema. Counts and region names in the text come from here
  (`landfillsText`, `regionsText`, `studiedSites`), so a build names only the landfills and
  regions it holds. Region labels are in `src/config.ts` and must match `config/project.yaml`.
- `src/islands/SitesTable.tsx`: every landfill in one sortable table, with a region filter when
  the build holds more than one region. A landfill without a usable estimate shows no figure and
  stays after the ranked ones however the table is sorted. The home page shows cards for the
  landfills studied in depth only.
- Records name their regulator: `checkLabel` in `src/lib/data.ts` builds "Sacramento Metro AQMD
  inspection" from the air district of the record's landfill, with the district names in
  `src/config.ts`.
- Two fits can sit side by side (decision record 0021): the update's main fit and a screening
  fit that supplies figures for the screened landfills. An estimate row names its fit;
  `fromScreeningFit` and `screeningFit` in `src/lib/data.ts` read that, and a figure from the
  screening fit says so on the landfill's page, in the landfills table, under the chart, on the
  methods page and in the glossary.
- `src/islands/MethaneMap.tsx`: the map. Its region choice frames one region's landfills and
  leaves out the rest.
- `fixtures/make-fixture.mjs`: writes the sample snapshot. Nothing in it is a real result. The
  review update holds four screened landfills in two regions beside the five studied in depth,
  and a screening fit with rows for two of them; the public update holds the five only.
- `src/islands/Carousel.tsx`: the home page carousels. Two slides in view; it moves on by one
  every 5 seconds and loops, and pauses on hover, on keyboard focus, when its pause button is
  pressed, while the tab is hidden and under reduced motion.
- `src/assets/imagery/`: the home page pictures (the Bay from Sentinel-2 and an aerial close-up of
  each landfill), with their credits and marker positions in `imagery.json`. They are committed,
  not fetched at build time. To remake them after the site list changes, run `npm run fetch`, then
  from the repository root `uv run --with pillow python web/scripts/make-imagery.py`.
