// Checks every built page against the shared word list in config/wording.json.
//
// Each page names its kind in <meta name="wording-kind" content="...">. Script and style
// contents are ignored, as is anything inside an element marked data-wording="source-title"
// (an official document title). Everything else, including alt text and labels, is scanned.
// Any hit fails the build.

import { readdir, readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '..');
const distDir = path.resolve(process.argv[2] ?? path.join(root, 'dist'));
const wordingPath = path.resolve(root, '..', 'config', 'wording.json');

const wording = JSON.parse(await readFile(wordingPath, 'utf8'));
const quoted = wording.quoted_source_title;
const quotedElement = new RegExp(
  `<([a-zA-Z][\\w-]*)\\b[^>]*\\b${quoted.html_attribute}\\s*=\\s*"${quoted.html_value}"[^>]*>[\\s\\S]*?</\\1\\s*>`,
  'gi',
);

const ENTITIES = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ', '#39': "'" };
function decode(text) {
  return text.replace(/&(#?\w+);/g, (m, name) => ENTITIES[name] ?? m);
}

function visibleText(html) {
  const withoutQuoted = html
    .replace(/<script[\s\S]*?<\/script>/gi, ' ')
    .replace(/<style[\s\S]*?<\/style>/gi, ' ')
    .replace(quotedElement, ' ');
  const attributes = [...withoutQuoted.matchAll(/\b(?:alt|title|aria-label|placeholder)="([^"]*)"/gi)].map((m) => m[1]);
  return decode(`${withoutQuoted.replace(/<[^>]+>/g, ' ')} ${attributes.join(' ')}`);
}

async function* htmlFiles(dir) {
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) yield* htmlFiles(full);
    else if (entry.name.endsWith('.html')) yield full;
  }
}

const problems = [];
let pages = 0;
for await (const file of htmlFiles(distDir)) {
  pages += 1;
  const html = await readFile(file, 'utf8');
  const rel = path.relative(distDir, file);
  const kindMatch = html.match(/<meta\s+name="wording-kind"\s+content="([^"]+)"/i);
  if (!kindMatch) {
    problems.push(`${rel}: no <meta name="wording-kind"> on the page`);
    continue;
  }
  const kind = kindMatch[1];
  const allowed = new Set(wording.allowances[kind] ?? []);
  const text = visibleText(html);
  for (const [name, entry] of Object.entries(wording.banned)) {
    if (allowed.has(name)) continue;
    if (new RegExp(entry.pattern, 'i').test(text)) problems.push(`${rel}: banned phrase: ${name}`);
  }
  for (const phrase of wording.required[kind] ?? []) {
    if (!new RegExp(phrase, 'i').test(text)) problems.push(`${rel}: missing required phrase: ${phrase}`);
  }
}

if (pages === 0) {
  console.error(`check-wording: no pages found under ${distDir}; build first`);
  process.exit(1);
}
if (problems.length) {
  console.error(`check-wording: ${problems.length} problem(s) in ${pages} page(s)`);
  for (const p of problems) console.error(`  ${p}`);
  process.exit(1);
}
console.log(`check-wording: ${pages} pages pass`);
