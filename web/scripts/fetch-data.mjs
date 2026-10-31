// Pulls one published snapshot and writes the static files the site is built from.
//
// Two settings decide what happens:
//   SITE_MODE    "review" shows review-and-public publications and restricted rows (needs the
//                secret key); "public" shows the newest public publication and no restricted
//                row, and refuses to run if a secret key is present.
//   DATA_SOURCE  "fixture" reads web/fixtures/snapshot.json (no keys, used in CI and for local
//                work); "supabase" reads the live database through its read views.
//
// Output: src/data/snapshot.json (imported by the pages) and public/data/*.geojson (for the map).
// Both are written at build time and never committed.

import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '..');

for (const envFile of [path.resolve(root, '..', '.env'), path.resolve(root, '.env')]) {
  if (existsSync(envFile)) {
    try {
      process.loadEnvFile(envFile);
    } catch {
      // Already-set variables win; a malformed line is reported by Node and ignored here.
    }
  }
}

const SITE_MODE = process.env.SITE_MODE ?? 'review';
const DATA_SOURCE = process.env.DATA_SOURCE ?? 'fixture';
const SITE_URL = process.env.SITE_URL ?? 'http://localhost:4321';

function fail(message) {
  console.error(`fetch-data: ${message}`);
  process.exit(1);
}

if (!['review', 'public'].includes(SITE_MODE)) fail(`SITE_MODE must be review or public, not "${SITE_MODE}"`);
if (!['fixture', 'supabase'].includes(DATA_SOURCE)) fail(`DATA_SOURCE must be fixture or supabase, not "${DATA_SOURCE}"`);
if (SITE_MODE === 'public' && process.env.SUPABASE_SECRET_KEY) {
  fail('a public build must not have SUPABASE_SECRET_KEY in its environment; remove it from the production settings');
}

const PUBLIC = SITE_MODE === 'public';
const VISIBLE = PUBLIC ? ['public'] : ['review', 'public'];

// Tables as the site uses them, the view that serves each, and a stable order for paging.
const SOURCES = {
  sites: { view: 'v_sites', order: ['site_id'] },
  neighbours: { view: 'v_neighbours', order: ['neighbour_id'] },
  plumes: { view: 'v_plumes', order: ['source', 'plume_id'] },
  pass_months: { view: 'v_pass_months', order: ['site_id', 'instrument', 'month'] },
  plume_days: { view: 'v_plume_days', order: ['site_id'] },
  site_estimates: { view: 'site_estimates', order: ['site_id', 'period'] },
  checks: { view: 'v_checks_with_results', order: ['site_id', 'date_start', 'check_id'] },
  operator_reports: { view: 'operator_reports', order: ['site_id', 'year', 'source'] },
  population: { view: 'population_context', order: ['site_id', 'radius_km'] },
  site_features: { view: 'site_features', order: ['site_id'] },
  validation_results: { view: 'validation_results', order: ['gate', 'report_id'] },
};

// Tables where a row can be restricted. In public mode these rows are dropped here as well as
// by the database, so a fixture build behaves like the live one.
const RESTRICTABLE = new Set(['plumes', 'pass_months', 'site_estimates']);

function newestVisible(publications) {
  return (
    publications
      .filter((p) => VISIBLE.includes(p.visibility) && !(PUBLIC && p.simulated))
      .sort((a, b) => (a.created_at < b.created_at ? 1 : -1))[0] ?? null
  );
}

function blankRestrictedResult(check) {
  if (!PUBLIC || !check.restricted) return check;
  // The check itself is a public record; only its measured result is held back.
  const kept = {};
  for (const key of [
    'publish_id', 'check_id', 'site_id', 'check_type', 'repair_kind', 'date_start', 'date_end',
    'date_confidence', 'description', 'source_doc', 'source_doc_title', 'source_url', 'source_page',
  ]) kept[key] = check[key];
  return { ...kept, call: null, evidence: null, size: null, colour: null, plain_reading: null, restricted: true, result_held: true };
}

function applyPublicRules(name, rows) {
  if (!PUBLIC) return rows;
  if (RESTRICTABLE.has(name)) return rows.filter((r) => r.restricted !== true);
  if (name === 'checks') return rows.map(blankRestrictedResult);
  return rows;
}

// ---- fixture -----------------------------------------------------------------------------

function monthOf(iso) {
  return `${iso.slice(0, 7)}-01`;
}

function passMonths(passes) {
  const groups = new Map();
  for (const p of passes) {
    const key = [p.publish_id, p.site_id, p.instrument, p.restricted, monthOf(p.acquired_utc)].join('|');
    const g = groups.get(key) ?? {
      publish_id: p.publish_id, site_id: p.site_id, instrument: p.instrument, restricted: p.restricted,
      month: monthOf(p.acquired_utc), n_passes: 0, n_usable: 0, n_detected: 0,
    };
    g.n_passes += 1;
    if (p.usable) g.n_usable += 1;
    if (p.usable && p.detected) g.n_detected += 1;
    groups.set(key, g);
  }
  return [...groups.values()];
}

function plumeDays(passes) {
  const groups = new Map();
  for (const p of passes) {
    const key = `${p.publish_id}|${p.site_id}`;
    const g = groups.get(key) ?? { publish_id: p.publish_id, site_id: p.site_id, usable: 0, days: new Set(), restricted: false };
    if (p.usable) g.usable += 1;
    if (p.usable && p.detected) g.days.add(p.acquired_utc.slice(0, 10));
    if (p.restricted) g.restricted = true;
    groups.set(key, g);
  }
  return [...groups.values()].map((g) => ({
    publish_id: g.publish_id, site_id: g.site_id, usable_passes: g.usable, plume_days: g.days.size,
    plume_days_per_usable_pass: g.usable ? g.days.size / g.usable : null, includes_restricted: g.restricted,
  }));
}

async function fromFixture() {
  const fixturePath = path.join(root, 'fixtures', 'snapshot.json');
  if (!existsSync(fixturePath)) fail('fixtures/snapshot.json is missing; run `npm run fixture` first');
  const fx = JSON.parse(await readFile(fixturePath, 'utf8'));
  const publication = newestVisible(fx.publications);
  const inPub = (rows) => (publication ? rows.filter((r) => r.publish_id === publication.publish_id) : []);
  // The database hides restricted passes from the publishable key before it aggregates them;
  // do the same here so counts in a public fixture build are the public counts.
  const passes = PUBLIC ? fx.passes.filter((p) => !p.restricted) : fx.passes;
  const checks = inPub(fx.checks).map((c) => {
    const r = fx.check_results.find((x) => x.publish_id === c.publish_id && x.check_id === c.check_id);
    return { ...c, ...(r ?? { call: null, evidence: null, size: null, colour: null, plain_reading: null, restricted: false }) };
  });
  const tables = {
    sites: inPub(fx.sites),
    neighbours: inPub(fx.neighbours),
    plumes: inPub(fx.plumes),
    pass_months: inPub(passMonths(passes)),
    plume_days: inPub(plumeDays(passes)),
    site_estimates: inPub(fx.site_estimates),
    checks,
    operator_reports: inPub(fx.operator_reports),
    population: inPub(fx.population),
    site_features: inPub(fx.site_features),
    validation_results: inPub(fx.validation_results),
  };
  const visibleIds = new Set(fx.publications.filter((p) => VISIBLE.includes(p.visibility)).map((p) => p.publish_id));
  return {
    publication,
    publications: fx.publications.filter((p) => visibleIds.has(p.publish_id)),
    runs: fx.runs,
    data_terms: fx.data_terms,
    boundaries: fx.boundaries,
    update_log: fx.update_log.filter((u) => visibleIds.has(u.publish_id)),
    tables,
  };
}

// ---- supabase ----------------------------------------------------------------------------

async function fromSupabase() {
  const url = process.env.SUPABASE_URL;
  const key = PUBLIC ? process.env.SUPABASE_PUBLISHABLE_KEY : process.env.SUPABASE_SECRET_KEY;
  if (!url) fail('SUPABASE_URL is not set');
  if (!key) fail(PUBLIC ? 'SUPABASE_PUBLISHABLE_KEY is not set' : 'SUPABASE_SECRET_KEY is not set (review builds need it)');
  const { createClient } = await import('@supabase/supabase-js');
  const client = createClient(url, key, { auth: { persistSession: false, autoRefreshToken: false } });

  async function all(view, order, filter = (q) => q) {
    const page = 1000;
    const rows = [];
    for (let from = 0; ; from += page) {
      let q = client.from(view).select('*');
      for (const col of order) q = q.order(col, { ascending: true });
      q = filter(q).range(from, from + page - 1);
      const { data, error } = await q;
      if (error) {
        fail(`${view}: ${error.message}. If the project is paused, resume it from the Supabase dashboard and retry.`);
      }
      rows.push(...data);
      if (data.length < page) break;
    }
    return rows;
  }

  const current = await client.from(PUBLIC ? 'v_current_publication' : 'v_current_review_publication').select('*').maybeSingle();
  if (current.error) fail(`current publication: ${current.error.message}. If the project is paused, resume it from the Supabase dashboard and retry.`);
  const publication = current.data ?? null;
  const publications = await all('publications', ['created_at'], (q) => q.in('visibility', VISIBLE));
  const tables = {};
  for (const [name, { view, order }] of Object.entries(SOURCES)) {
    tables[name] = publication ? await all(view, order, (q) => q.eq('publish_id', publication.publish_id)) : [];
  }
  const runIds = publication ? [publication.refresh_id, publication.model_run_id, publication.check_run_id].filter(Boolean) : [];
  return {
    publication,
    publications,
    runs: runIds.length ? await all('runs', ['run_id'], (q) => q.in('run_id', runIds)) : [],
    data_terms: await all('data_terms', ['source']),
    boundaries: await all('v_boundaries', ['boundary_id']),
    update_log: await all('update_log', ['publish_id', 'item_order']),
    tables,
  };
}

// ---- write -------------------------------------------------------------------------------

function featureCollection(features) {
  return { type: 'FeatureCollection', features };
}

const raw = DATA_SOURCE === 'fixture' ? await fromFixture() : await fromSupabase();
const tables = Object.fromEntries(Object.entries(raw.tables).map(([name, rows]) => [name, applyPublicRules(name, rows)]));

const counts = Object.fromEntries(Object.entries(tables).map(([k, v]) => [k, v.length]));
const snapshot = {
  meta: {
    site_mode: SITE_MODE,
    data_source: DATA_SOURCE,
    fetched_at: new Date().toISOString(),
    site_url: SITE_URL,
    counts,
  },
  publication: raw.publication,
  publications: raw.publications,
  runs: raw.runs,
  data_terms: raw.data_terms,
  boundaries: raw.boundaries,
  update_log: raw.update_log,
  ...tables,
};

const dataDir = path.join(root, 'src', 'data');
const publicDir = path.join(root, 'public', 'data');
await mkdir(dataDir, { recursive: true });
await mkdir(publicDir, { recursive: true });
await writeFile(path.join(dataDir, 'snapshot.json'), JSON.stringify(snapshot, null, 1));

await writeFile(
  path.join(publicDir, 'sites.geojson'),
  JSON.stringify(featureCollection(
    tables.sites.filter((s) => s.outline_geojson).map((s) => ({
      type: 'Feature',
      geometry: s.outline_geojson,
      properties: { site_id: s.site_id, name: s.name, provisional: s.provisional, polygon_source: s.polygon_source, lon: s.lon, lat: s.lat },
    })),
  )),
);
await writeFile(
  path.join(publicDir, 'plumes.geojson'),
  JSON.stringify(featureCollection(
    tables.plumes.map((p) => ({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [p.lon, p.lat] },
      properties: {
        plume_id: p.plume_id, source: p.source, instrument: p.instrument, acquired_utc: p.acquired_utc,
        q_kg_hr: p.q_kg_hr, site_id: p.site_id, attribution: p.attribution, new_in_update: p.new_in_update,
      },
    })),
  )),
);
await writeFile(
  path.join(publicDir, 'neighbours.geojson'),
  JSON.stringify(featureCollection(
    tables.neighbours.filter((n) => n.geojson).map((n) => ({
      type: 'Feature', geometry: n.geojson,
      properties: { neighbour_id: n.neighbour_id, name: n.name, kind: n.kind, nearest_site_id: n.nearest_site_id, distance_m: n.distance_m },
    })),
  )),
);
await writeFile(
  path.join(publicDir, 'boundaries.geojson'),
  JSON.stringify(featureCollection(
    raw.boundaries.filter((b) => b.geojson).map((b) => ({
      type: 'Feature', geometry: b.geojson, properties: { boundary_id: b.boundary_id, kind: b.kind, name: b.name, as_of: b.as_of },
    })),
  )),
);

// ---- CSV downloads ----------------------------------------------------------------------
// The publishable tables as plain CSV, plus a README naming the publication, the runs, the
// data-through date and the credits. Only what is in the snapshot gets written, so a public
// build never writes a restricted row.

function csv(rows, columns) {
  const esc = (v) => {
    if (v === null || v === undefined) return '';
    const s = typeof v === 'object' ? JSON.stringify(v) : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return [columns.join(','), ...rows.map((r) => columns.map((c) => esc(r[c])).join(','))].join('\n') + '\n';
}

const DOWNLOADS = {
  'sites.csv': { rows: tables.sites, columns: ['site_id', 'name', 'city', 'county', 'operator', 'tier', 'status', 'swis_number', 'ghgrp_facility_id', 'polygon_source', 'provisional', 'area_km2', 'lon', 'lat'] },
  'passes_monthly.csv': { rows: tables.pass_months, columns: ['site_id', 'instrument', 'month', 'n_passes', 'n_usable', 'n_detected', 'restricted'] },
  'plumes.csv': { rows: tables.plumes, columns: ['plume_id', 'source', 'instrument', 'acquired_utc', 'lon', 'lat', 'q_kg_hr', 'q_sigma_kg_hr', 'site_id', 'attribution', 'distance_m', 'new_in_update'] },
  'site_estimates.csv': { rows: tables.site_estimates, columns: ['site_id', 'period', 'model_run_id', 'n_usable_overpasses', 'n_detections', 'f_med', 'f_lo', 'f_hi', 'qbar_kg_hr_med', 'qbar_kg_hr_lo', 'qbar_kg_hr_hi', 'e_t_yr_med', 'e_t_yr_lo', 'e_t_yr_hi', 'status', 'provisional'] },
  'checks.csv': { rows: tables.checks, columns: ['check_id', 'site_id', 'check_type', 'repair_kind', 'date_start', 'date_end', 'date_confidence', 'description', 'source_doc', 'source_doc_title', 'source_url', 'source_page', 'call', 'change_pct_med', 'change_pct_lo', 'change_pct_hi', 'de_t_yr_med', 'de_t_yr_lo', 'de_t_yr_hi', 'p_decrease', 'mde_pct', 'n_before', 'n_after', 'evidence', 'size', 'colour', 'plain_reading'] },
  'operator_reports.csv': { rows: tables.operator_reports, columns: ['site_id', 'year', 'source', 'reported_ch4_t', 'reported_co2e_t', 'gwp_used', 'gwp_confirmed', 'facility_id', 'url'] },
  'validation_results.csv': { rows: tables.validation_results, columns: ['report_id', 'gate', 'run_id', 'result', 'metrics', 'superseded', 'note', 'created_at'] },
};
const downloads = [];
for (const [name, { rows, columns }] of Object.entries(DOWNLOADS)) {
  await writeFile(path.join(publicDir, name), csv(rows, columns));
  downloads.push({ file: `/data/${name}`, name, rows: rows.length, columns });
}
const credits = raw.data_terms.filter((t) => t.credit_line).map((t) => `- ${t.display_name}: ${t.credit_line}`);
const p = raw.publication;
await writeFile(
  path.join(publicDir, 'README.txt'),
  [
    'Bay Area Landfill Methane Watch: data downloads',
    '',
    'Every figure is a screening indication from a retrospective tracker, never a compliance',
    'finding, live monitoring or a health claim. Non-commercial use only.',
    '',
    p ? `Publication: ${p.publish_id} (${p.visibility})` : 'Publication: none yet',
    p ? `Data through: ${p.data_through ?? 'unknown'}; sources publish about ${p.source_lag_days ?? 30} days after an observation` : '',
    p?.refresh_id ? `Data refresh: ${p.refresh_id}` : '',
    p?.model_run_id ? `Model run: ${p.model_run_id}` : '',
    p?.check_run_id ? `Checks run: ${p.check_run_id}` : '',
    p?.git_sha ? `Code: ${p.git_sha}` : '',
    `Built: ${snapshot.meta.fetched_at} (${SITE_MODE} build from ${DATA_SOURCE})`,
    '',
    'Files:',
    ...downloads.map((d) => `- ${d.name}: ${d.rows} rows; columns ${d.columns.join(', ')}`),
    '',
    'Units: rates in kg/hr, annual totals in t/yr (methane above the detection floor in daytime,',
    'clear-sky conditions), times in UTC. Columns ending in _lo and _hi are the 90% range.',
    'Rows from sources whose publication terms are unconfirmed are not included in a public build.',
    '',
    'Credits:',
    ...credits,
    '',
  ].filter((line) => line !== undefined).join('\n'),
);
snapshot.meta.downloads = downloads.map(({ file, name, rows }) => ({ file, name, rows }));
await writeFile(path.join(dataDir, 'snapshot.json'), JSON.stringify(snapshot, null, 1));

const label = raw.publication ? `${raw.publication.publish_id} (${raw.publication.visibility})` : 'no publication yet; the site will show empty states';
console.log(`fetch-data: ${SITE_MODE} build from ${DATA_SOURCE}; publication ${label}`);
console.log(`fetch-data: ${Object.entries(counts).map(([k, v]) => `${k} ${v}`).join(', ')}`);
