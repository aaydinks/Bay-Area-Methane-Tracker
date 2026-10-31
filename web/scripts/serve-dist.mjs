// A small static server for the built site, used by the accessibility tests. It stays in the
// foreground (Astro's preview server backgrounds itself), serves dist/, maps directory URLs to
// their index.html and answers unknown paths with the 404 page.

import { createReadStream, existsSync, statSync } from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const dist = path.resolve(here, '..', 'dist');
const port = Number(process.argv[2] ?? 4321);
const host = process.argv[3] ?? '127.0.0.1';

const TYPES = {
  '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8', '.json': 'application/json', '.geojson': 'application/geo+json',
  '.svg': 'image/svg+xml', '.png': 'image/png', '.ico': 'image/x-icon', '.txt': 'text/plain; charset=utf-8',
  '.xml': 'application/xml', '.csv': 'text/csv; charset=utf-8', '.woff2': 'font/woff2',
};

function resolveFile(urlPath) {
  const clean = decodeURIComponent(urlPath.split('?')[0]).replace(/\.\./g, '');
  let file = path.join(dist, clean);
  if (existsSync(file) && statSync(file).isDirectory()) file = path.join(file, 'index.html');
  if (!existsSync(file) && existsSync(`${file}.html`)) file = `${file}.html`;
  if (existsSync(file) && statSync(file).isFile()) return { file, status: 200 };
  return { file: path.join(dist, '404.html'), status: 404 };
}

http
  .createServer((req, res) => {
    const { file, status } = resolveFile(req.url ?? '/');
    if (!existsSync(file)) {
      res.writeHead(404, { 'content-type': 'text/plain' });
      res.end('not found');
      return;
    }
    res.writeHead(status, { 'content-type': TYPES[path.extname(file)] ?? 'application/octet-stream' });
    createReadStream(file).pipe(res);
  })
  .listen(port, host, () => console.log(`serve-dist: http://${host}:${port}/ from ${dist}`));
