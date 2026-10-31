// Proves that a public build contains nothing it must not.
//
// Runs after every build and does nothing for a review build. For a public build it fails if
// the snapshot the pages were built from holds any restricted row, if its publication is not
// public or is simulated, or if the output files mention a restricted source, a restricted
// instrument in data files, the simulated-data banner, or a secret key. A public build from fixture data
// is allowed only when ALLOW_FIXTURE_PUBLIC=1 (set in CI, never on a host).

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
      if (row.restricted === true && row.result_held !== true) problems.push(`${name}: a restricted row reached the snapshot`);
      if (row.includes_restricted === true) problems.push(`${name}: an aggregate that includes restricted passes reached the snapshot`);
      if (row.source === 'carbonmapper') problems.push(`${name}: a Carbon Mapper row reached the snapshot`);
      if (['tanager1', 'aircraft'].includes(row.instrument)) problems.push(`${name}: a restricted-instrument row reached the snapshot`);
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
  if (!/\.(js|mjs)$/i.test(file) && /\bcarbonmapper\b/i.test(text)) problems.push(`${rel}: contains the restricted source code "carbonmapper"`);
  if (DATA_FILE.test(file) && /"instrument"\s*:\s*"(tanager1|aircraft)"/i.test(text)) problems.push(`${rel}: contains a restricted instrument`);
  if (/data-banner="simulated"/.test(text)) problems.push(`${rel}: shows the simulated-data banner`);
  if (/sb_secret_|service_role/i.test(text)) problems.push(`${rel}: contains what looks like a secret key`);
}

if (problems.length) {
  console.error(`check-public-output: ${problems.length} problem(s); the public build is not safe to publish`);
  for (const p of [...new Set(problems)]) console.error(`  ${p}`);
  process.exit(1);
}
console.log('check-public-output: clean (no restricted row, source, instrument, simulated data or key in the output)');
