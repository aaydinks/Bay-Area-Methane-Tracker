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
  yet, provisional, Carbon Mapper held back), footer with credits and run ids, dark mode.
- `src/components/`: badges, tags, ranges, empty states, the theme toggle.
- `src/pages/`: home, map, updates, checks, landfills, methods, how to read, data, 404.
- `src/lib/data.ts`: the typed snapshot and the helpers pages use; `database.types.ts` is
  generated from the live schema.
- `fixtures/make-fixture.mjs`: writes the sample snapshot. Nothing in it is a real result.
