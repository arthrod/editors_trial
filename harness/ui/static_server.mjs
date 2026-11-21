/**
 * A static file server for the UI hosts that are not bundled (a vendor's own
 * application or archive served as it ships): OnlyOffice, OpenDoc, Nutrient.
 *
 * usage: node static_server.mjs <port> <root> [<url prefix>=<directory> ...]
 *
 * Serves <root> on 127.0.0.1:<port>; each extra argument mounts a directory
 * under a URL prefix (longest prefix wins). Runs of slashes in a path count
 * as one (OnlyOffice asks for its fonts at "fonts//fonts/<name>"). Nothing is
 * cached, nothing is rewritten, and a path that leaves its directory is a 404.
 */
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';

const [port, root, ...mountArgs] = process.argv.slice(2);
if (!port || !root) {
  console.error('usage: node static_server.mjs <port> <root> [<url prefix>=<directory> ...]');
  process.exit(2);
}
const mounts = mountArgs
  .map((m) => { const i = m.indexOf('='); return [m.slice(0, i).replace(/\/*$/, '/'), path.resolve(m.slice(i + 1))]; })
  .concat([['/', path.resolve(root)]])
  .sort((a, b) => b[0].length - a[0].length);

const TYPES = {
  html: 'text/html; charset=utf-8', js: 'text/javascript; charset=utf-8', mjs: 'text/javascript; charset=utf-8',
  css: 'text/css; charset=utf-8', json: 'application/json; charset=utf-8', wasm: 'application/wasm',
  svg: 'image/svg+xml', png: 'image/png', jpg: 'image/jpeg', gif: 'image/gif', webp: 'image/webp', ico: 'image/x-icon',
  woff2: 'font/woff2', woff: 'font/woff', ttf: 'font/ttf', otf: 'font/otf', txt: 'text/plain; charset=utf-8',
  xml: 'application/xml', map: 'application/json',
  docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
};

function handle(req, res) {
  let pathname;
  try {
    pathname = decodeURIComponent(new URL(req.url, 'http://x').pathname).replace(/\/{2,}/g, '/');
  } catch {
    res.writeHead(400).end('bad path');
    return;
  }
  const [prefix, dir] = mounts.find(([p]) => pathname.startsWith(p));
  let file = path.join(dir, pathname.slice(prefix.length));
  if (file !== dir && !file.startsWith(dir + path.sep)) { res.writeHead(404).end('not found'); return; }
  if (fs.existsSync(file) && fs.statSync(file).isDirectory()) file = path.join(file, 'index.html');
  if (!fs.existsSync(file)) { res.writeHead(404).end('not found'); return; }
  res.writeHead(200, {
    'content-type': TYPES[path.extname(file).slice(1).toLowerCase()] || 'application/octet-stream',
    'content-length': fs.statSync(file).size,
    'cache-control': 'no-store',
  });
  if (req.method === 'HEAD') { res.end(); return; }
  fs.createReadStream(file).pipe(res);
}

const server = http.createServer(handle);
server.listen(Number(port), '127.0.0.1', () => console.log(`serving ${root} on http://127.0.0.1:${server.address().port}/`));
