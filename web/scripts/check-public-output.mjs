// Proves that a public build contains nothing it must not.
//
// Runs after every build and does nothing for a review build. For a public build it fails if
// the snapshot the pages were built from holds any restricted row, if its publication is not
// public or is simulated, or if the output files mention a restricted source, a restricted
// instrument in data files, the simulated-data banner, or a secret key. A public build from fixture data
// is allowed only when ALLOW_FIXTURE_PUBLIC=1 (set in CI, never on a host).
//
// Display-only data (ADR 0017): when the terms record Carbon Mapper as display-only, its rows may
// reach the pages and the map, marked display_only, but a display-only plume must carry no rate,
// uncertainty or data version, and no download (CSV) may hold a restricted row, a Carbon Mapper
// instrument or the source code "carbonmapper".

import { readdir, readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '..');
const distDir = path.join(root, 'dist');
const snapshotPath = path.join(root, 'src', 'data', 'snapshot.json');

const snapshot = JSON.parse(await readFile(snapshotPath, 'utf8'));
const { meta } = snapshot;

if (meta.site_mode !== 'public') {
  console.log(`check-public-output: skipped (${meta.site_mode} build)`);
  process.exit(0);
}

const problems = [];
const displayOnly = (snapshot.data_terms ?? []).some(
  (t) => t.source === 'carbonmapper' && t.confirmed && t.display_publishable && !t.derived_publishable,
);

if (meta.data_source === 'fixture' && process.env.ALLOW_FIXTURE_PUBLIC !== '1') {
  problems.push('a public build was made from fixture data; set DATA_SOURCE=supabase on the host');
}
if (snapshot.publication) {
  if (snapshot.publication.visibility !== 'public') problems.push(`publication ${snapshot.publication.publish_id} is ${snapshot.publication.visibility}, not public`);
  if (snapshot.publication.simulated) problems.push(`publication ${snapshot.publication.publish_id} is simulated`);
}
for (const [name, rows] of Object.entries(snapshot)) {
  if (!Array.isArray(rows) || name === 'data_terms') continue; // terms describe sources; they hold no data
  for (const row of rows) {
    if (row && typeof row === 'object') {
      const shownAsDisplay = displayOnly && row.display_only === true;
      if (row.restricted === true && row.result_held !== true && !shownAsDisplay) problems.push(`${name}: a restricted row reached the snapshot`);
      if (row.includes_restricted === true) problems.push(`${name}: an aggregate that includes restricted passes reached the snapshot`);
      if (row.source === 'carbonmapper' && !shownAsDisplay) problems.push(`${name}: a Carbon Mapper row reached the snapshot`);
      if (['tanager1', 'aircraft'].includes(row.instrument) && !shownAsDisplay) problems.push(`${name}: a restricted-instrument row reached the snapshot`);
      if (name === 'plumes' && (row.restricted === true || row.display_only === true)) {
        for (const key of ['q_kg_hr', 'q_sigma_kg_hr', 'data_version', 'overpass_id']) {
          if (row[key] !== null && row[key] !== undefined) problems.push(`plumes: a display-only plume carries ${key}`);
        }
      }
    }
  }
}

const DATA_FILE = /\.(json|geojson|csv)$/i;
const SCAN_FILE = /\.(html|json|geojson|csv|js|mjs|txt|xml)$/i;
async function* files(dir) {
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) yield* files(full);
    else if (SCAN_FILE.test(entry.name)) yield full;
  }
}

for await (const file of files(distDir)) {
  const text = await readFile(file, 'utf8');
  const rel = path.relative(distDir, file);
  // Pages and data files must not name the restricted source; the map's script may, because it
  // lists every source it knows how to filter (the control only shows for sources in the data).
  const isCsv = /\.csv$/i.test(file);
  const mayNameSource = displayOnly && !isCsv;
  if (!/\.(js|mjs)$/i.test(file) && !mayNameSource && /\bcarbonmapper\b/i.test(text)) problems.push(`${rel}: contains the restricted source code "carbonmapper"`);
  if (DATA_FILE.test(file) && !mayNameSource && /"instrument"\s*:\s*"(tanager1|aircraft)"/i.test(text)) problems.push(`${rel}: contains a restricted instrument`);
  if (isCsv && /(^|,)(tanager1|aircraft)(,|$)/im.test(text)) problems.push(`${rel}: a download contains a restricted instrument`);
  if (/\.geojson$/i.test(file)) {
    for (const f of JSON.parse(text).features ?? []) {
      const pr = f.properties ?? {};
      if ((pr.source === 'carbonmapper' || ['tanager1', 'aircraft'].includes(pr.instrument)) && pr.q_kg_hr != null) {
        problems.push(`${rel}: a display-only plume carries a rate`);
      }
    }
  }
  if (/data-banner="simulated"/.test(text)) problems.push(`${rel}: shows the simulated-data banner`);
  if (/sb_secret_|service_role/i.test(text)) problems.push(`${rel}: contains what looks like a secret key`);
}

// No download may hold a restricted row: estimates and check results built from display-only
// data are counted against the rows the snapshot marks open.
const downloadsDir = path.join(distDir, 'data');
async function csvRows(name) {
  try {
    const text = await readFile(path.join(downloadsDir, name), 'utf8');
    return parseCsv(text);
  } catch {
    return null;
  }
}
function parseCsv(text) {
  const out = [];
  let row = [];
  let field = '';
  let quoted = false;
  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i];
    if (quoted) {
      if (ch === '"' && text[i + 1] === '"') { field += '"'; i += 1; } else if (ch === '"') quoted = false; else field += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === ',') { row.push(field); field = ''; }
    else if (ch === '\n') { row.push(field); out.push(row); row = []; field = ''; }
    else field += ch;
  }
  if (field || row.length) { row.push(field); out.push(row); }
  const [header, ...body] = out;
  return (body ?? []).map((r) => Object.fromEntries((header ?? []).map((h, i) => [h, r[i] ?? ''])));
}
const openEstimates = (snapshot.site_estimates ?? []).filter((r) => r.restricted !== true).length;
const estimatesCsv = await csvRows('site_estimates.csv');
if (estimatesCsv && estimatesCsv.length !== openEstimates) {
  problems.push(`data/site_estimates.csv: ${estimatesCsv.length} rows, but only ${openEstimates} estimates are open`);
}
const openResults = new Set((snapshot.checks ?? []).filter((c) => c.call && c.restricted !== true).map((c) => c.check_id));
for (const r of (await csvRows('checks.csv')) ?? []) {
  if (r.call && !openResults.has(r.check_id)) problems.push(`data/checks.csv: check ${r.check_id} carries a result that is not open`);
}
const openPlumes = new Set((snapshot.plumes ?? []).filter((p) => p.restricted !== true).map((p) => p.plume_id));
for (const r of (await csvRows('plumes.csv')) ?? []) {
  if (!openPlumes.has(r.plume_id)) problems.push(`data/plumes.csv: plume ${r.plume_id} is not open`);
}
for (const r of (await csvRows('passes_monthly.csv')) ?? []) {
  if (r.restricted === 'true') problems.push('data/passes_monthly.csv: a restricted month reached the download');
}

if (problems.length) {
  console.error(`check-public-output: ${problems.length} problem(s); the public build is not safe to publish`);
  for (const p of [...new Set(problems)]) console.error(`  ${p}`);
  process.exit(1);
}
console.log('check-public-output: clean (no restricted row, source, instrument, simulated data or key in the output)');
