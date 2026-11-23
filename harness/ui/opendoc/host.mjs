/**
 * OpenDoc browser perf host (Report E2), port 5224.
 *
 *   cd harness/ui/opendoc && node host.mjs --port 5224
 *
 * Serves OpenDoc's own editor (repos/opendoc/webapp at the pinned commit, with
 * the engine fetch_engine.py put in webapp/pkg/) as it ships, at `/`, plus:
 *   - `/sample.docx`: the document. OpenDoc's editor opens `./sample.docx` on
 *     boot when its URL names no other document (webapp/src/editor_file_open.mjs
 *     `startupDocument`: "the plain editor ... open[s] sample.docx"), so the
 *     document goes in through the vendor's own startup path, not a file input.
 *     The lanes intercept this route with their own fixture; standalone it is
 *     CORPUS_DOCX (default: fixture/complex.docx).
 *   - `?doc=<path>`: another document from this host's `/fixture/` folder
 *     (e.g. `/?doc=/fixture/complex.docx`). The page is redirected to
 *     `/d/<path>/`, where the same editor is served and its `./sample.docx`
 *     resolves to that document. Nothing in the editor is changed for it.
 *   - host.js, added inline as one `<script>` element to editor.html before the
 *     editor's own scripts: publishes `window.__host.ready` / `.error` (see
 *     host.js; also served at `/_host/host.js`). No other byte of any response
 *     is rewritten.
 *
 * Nothing is cached (no-store), so a cold load is a cold load.
 */
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(here, '../../..');
const argPort = process.argv.indexOf('--port');
const PORT = Number(argPort > 0 ? process.argv[argPort + 1] : process.env.PORT || 5224);
const WEBAPP = path.resolve(process.env.OPENDOC_WEBAPP || path.join(REPO, 'repos/opendoc/webapp'));
const FIXTURES = path.join(REPO, 'fixture');
const CORPUS = () => path.resolve(process.env.CORPUS_DOCX || path.join(FIXTURES, 'complex.docx'));
const HOST_JS = fs.readFileSync(path.join(here, 'host.js'), 'utf8');
// Inline, so the shim costs the measured load no extra request.
const INJECT = `<script data-host="opendoc-perf">\n${HOST_JS}</script>`;

const TYPES = {
  html: 'text/html; charset=utf-8', js: 'text/javascript; charset=utf-8', mjs: 'text/javascript; charset=utf-8',
  css: 'text/css; charset=utf-8', json: 'application/json; charset=utf-8', wasm: 'application/wasm',
  svg: 'image/svg+xml', png: 'image/png', jpg: 'image/jpeg', gif: 'image/gif', webp: 'image/webp', ico: 'image/x-icon',
  woff2: 'font/woff2', woff: 'font/woff', ttf: 'font/ttf', otf: 'font/otf', txt: 'text/plain; charset=utf-8',
  xml: 'application/xml', map: 'application/json', webmanifest: 'application/manifest+json',
  docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
};

function send(res, status, type, body) {
  res.writeHead(status, { 'content-type': type, 'cache-control': 'no-store' });
  res.end(body);
}

/** A file under `dir`, by its real path (a link that leads out is not followed), or null. */
function inside(dir, rel) {
  const file = path.join(dir, rel);
  try {
    const real = fs.realpathSync(file), realDir = fs.realpathSync(dir);
    if (real !== realDir && !real.startsWith(realDir + path.sep)) return null;
    return fs.statSync(real).isFile() ? real : null;
  } catch {
    return null;
  }
}

function serveFile(res, file) {
  if (!file) { send(res, 404, 'text/plain; charset=utf-8', 'not found'); return; }
  fs.readFile(file, (err, buf) => {
    if (err) send(res, 404, 'text/plain; charset=utf-8', 'not found');
    else send(res, 200, TYPES[path.extname(file).slice(1).toLowerCase()] || 'application/octet-stream', buf);
  });
}

function serveEditor(res) {
  fs.readFile(path.join(WEBAPP, 'editor.html'), 'utf8', (err, html) => {
    if (err) { send(res, 500, 'text/plain; charset=utf-8', `missing ${WEBAPP}/editor.html`); return; }
    // Before the editor's own scripts, so the flag exists before its first module runs.
    const at = html.indexOf('<script');
    send(res, 200, TYPES.html, at < 0 ? `${INJECT}\n${html}` : `${html.slice(0, at)}${INJECT}\n${html.slice(at)}`);
  });
}

/** One path under the editor's folder: `/`, `/editor.html`, the document, or a vendor file. */
function serveApp(res, rel, documentFile) {
  if (rel === '' || rel === 'editor.html') { serveEditor(res); return; }
  if (rel === 'sample.docx') { serveFile(res, documentFile()); return; }
  serveFile(res, inside(WEBAPP, rel));
}

const server = http.createServer((req, res) => {
  let url, p;
  try {
    url = new URL(req.url, 'http://127.0.0.1');
    p = decodeURIComponent(url.pathname).replace(/\/{2,}/g, '/');
  } catch {
    send(res, 400, 'text/plain; charset=utf-8', 'bad path');
    return;
  }
  if (p === '/_host/host.js') { send(res, 200, TYPES.js, HOST_JS); return; }
  if (p === '/health') { send(res, 200, TYPES.json, JSON.stringify({ ok: true, webapp: WEBAPP })); return; }
  if (p.startsWith('/fixture/')) { serveFile(res, inside(FIXTURES, p.slice('/fixture/'.length))); return; }
  const doc = url.searchParams.get('doc');
  if ((p === '/' || p === '/editor.html') && doc) {
    if (!doc.startsWith('/fixture/') || !inside(FIXTURES, doc.slice('/fixture/'.length))) {
      send(res, 404, 'text/plain; charset=utf-8', `?doc= names no file under /fixture/: ${doc}`);
      return;
    }
    url.searchParams.delete('doc');
    const rest = url.searchParams.toString();
    res.writeHead(302, { location: `/d${doc}/${rest ? `?${rest}` : ''}`, 'cache-control': 'no-store' });
    res.end();
    return;
  }
  // `/d/fixture/<name>.docx/<editor path>`: the editor again, with that document as its sample.
  const m = /^\/d\/fixture\/(.+?\.docx)\/(.*)$/.exec(p);
  if (m) { serveApp(res, m[2], () => inside(FIXTURES, m[1])); return; }
  serveApp(res, p.slice(1), () => (fs.existsSync(CORPUS()) ? CORPUS() : null));
});

server.listen(PORT, '127.0.0.1', () => {
  process.stderr.write(`opendoc host on http://127.0.0.1:${PORT}/  webapp=${WEBAPP}\n`);
});
