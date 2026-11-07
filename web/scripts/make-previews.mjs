// Preview images for shared links: one for the site and one per landfill, drawn as SVG and
// rasterised to PNG at build time. Written to public/og/, never committed.

import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import sharp from 'sharp';
import snapshot from '../src/data/snapshot.json' with { type: 'json' };

const here = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.resolve(here, '..', 'public', 'og');
await mkdir(outDir, { recursive: true });

const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const num = (x) => (x == null ? '–' : Number(x).toLocaleString('en-US', { maximumSignificantDigits: 3 }));

// Long lines are wrapped by hand: the raster has no text layout engine.
function wrap(text, max) {
  const words = String(text).split(' ');
  const lines = [''];
  for (const w of words) {
    if ((lines[lines.length - 1] + ' ' + w).trim().length > max) lines.push(w);
    else lines[lines.length - 1] = (lines[lines.length - 1] + ' ' + w).trim();
  }
  return lines.slice(0, 3);
}

function card({ title, headline, detail, footer }) {
  // The site's four colours: white, black, red and a light green.
  const head = wrap(headline, 44).map((l, i) => `<text x="72" y="${300 + i * 54}" font-family="Helvetica, Arial, sans-serif" font-size="42" fill="#c8102e">${esc(l)}</text>`).join('');
  const det = wrap(detail, 70).map((l, i) => `<text x="72" y="${440 + i * 38}" font-family="Helvetica, Arial, sans-serif" font-size="28" fill="#4f4f4f">${esc(l)}</text>`).join('');
  return `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
  <rect width="1200" height="630" fill="#ffffff"/>
  <rect x="0" y="0" width="1200" height="14" fill="#c8102e"/>
  <rect x="0" y="606" width="1200" height="24" fill="#cfe8d5"/>
  <text x="72" y="118" font-family="Helvetica, Arial, sans-serif" font-size="30" fill="#4f4f4f">Bay Area Landfill Methane Watch · retrospective tracker</text>
  <text x="72" y="210" font-family="Helvetica, Arial, sans-serif" font-size="${String(title).length > 26 ? 52 : 66}" font-weight="700" fill="#111111">${esc(title)}</text>
  ${head}
  ${det}
  <text x="72" y="570" font-family="Helvetica, Arial, sans-serif" font-size="24" fill="#4f4f4f">${esc(footer)}</text>
</svg>`;
}

const p = snapshot.publication;
const through = p?.data_through ? `Data through ${p.data_through}` : 'No data published yet';
const framing = 'Screening indications for investigation, never compliance findings.';
const files = [];

files.push(['default.png', card({
  title: 'Landfill methane, seen from above',
  headline: p ? `${snapshot.sites.length} landfills · ${snapshot.pass_months.reduce((n, r) => n + (r.n_usable ?? 0), 0)} usable passes` : 'Five Bay Area landfills',
  detail: 'How often each site leaks, whether repairs were followed by a drop, and how satellites compare with reported figures.',
  footer: `${through} · ${framing}`,
})]);

for (const s of snapshot.sites) {
  const e = snapshot.site_estimates.find((x) => x.site_id === s.site_id && x.period === 'all');
  // A site marked insufficient data shows no figure, even when its row carries a median.
  const headline = e?.status === 'insufficient_data'
    ? 'Not enough data for an estimate yet'
    : e && e.e_t_yr_med != null
      ? `About ${num(e.e_t_yr_med)} t/yr above the floor (90% range ${num(e.e_t_yr_lo)} to ${num(e.e_t_yr_hi)})`
      : 'No estimate in this update';
  const pd = snapshot.plume_days.find((x) => x.site_id === s.site_id);
  files.push([`${s.site_id}.png`, card({
    title: s.name ?? s.site_id,
    headline,
    detail: pd ? `${pd.usable_passes} usable passes, ${pd.plume_days} days with a plume seen${s.provisional ? ' · provisional outline' : ''}` : `${s.city ?? ''}, ${s.county ?? ''} County`,
    footer: `${through} · ${framing}`,
  })]);
}

for (const [name, svg] of files) {
  await writeFile(path.join(outDir, name), await sharp(Buffer.from(svg)).png().toBuffer());
}
console.log(`make-previews: wrote ${files.length} preview images to public/og/`);
