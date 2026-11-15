#!/usr/bin/env node
/**
 * Fidus Writer perf host — a same-origin pass-through to the Django app.
 *
 * The warm/cold probe (perf/runner/warm_cold_browser.mjs) does one `goto` and
 * one `waitForSelector(ready_selector)`; it cannot log in or import. Fidus
 * needs both (Report C §2.11): a session cookie and the overview's own DOCX
 * import. This host therefore presents the app on ONE origin and injects one
 * script — boot.js — into every HTML page it passes through, so that a plain
 * page load ends with a rendered, editable document.
 *
 * Why a proxy and not a static shim page: Fidus's session cookie and its CSRF
 * check are same-origin, so a shim on another port cannot log in. Serving the
 * app behind this proxy keeps every URL, cookie and POST on `localhost:<port>`.
 *
 * What it does, and nothing else:
 *   1. forwards every request to the Django upstream (Host header unchanged,
 *      so ALLOWED_HOSTS=["localhost"] and the CSRF origin check both pass);
 *   2. serves /corpus.docx from --corpus (the perf harness fulfils that path
 *      itself via `corpus_route`, so this is only the fallback for a manual run);
 *   3. serves /__fidus_host/boot.js;
 *   4. appends `<script src="/__fidus_host/boot.js" defer>` to HTML responses;
 *   5. passes WebSocket upgrades through untouched (EDITOR_SAVE_MODE is
 *      "collaborative", so the document page opens one).
 *
 * It rewrites no byte of any other response.
 *
 * Ready gate: Django's `runserver` binds its port for a MAINTENANCE page before
 * it runs `setup` (migrate + pnpm install + the first rspack transpile, minutes
 * on a cold checkout). Treating that socket as "up" served the browser the
 * maintenance page — which reloads itself every 5 s — for the whole setup, and
 * the probe's 120 s readiness budget expired on a page that was never the app:
 * the 2026-11-08 warm/cold run recorded `fidus` as a 120 s waitForSelector
 * timeout while the editor was never asked to render anything. So the proxy
 * listens at once (the runner polls this port) but only lets requests through
 * once `/` answers with something other than the setup page. Until then a
 * navigation is held (up to --nav-hold ms, then it gets a self-reloading boot
 * page) and everything else gets 503.
 *
 * usage:  node harness/ui/fidus-host/proxy.mjs [--port 5219] [--upstream 5209]
 *                [--corpus ../fixture/complex.docx] [--no-spawn] [--nav-hold 100000]
 */
import fs from 'node:fs';
import http from 'node:http';
import net from 'node:net';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const repo = path.resolve(here, '../../..');

const argv = process.argv.slice(2);
const opt = {};
for (let i = 0; i < argv.length; i++) {
  const a = argv[i];
  if (!a.startsWith('--')) continue;
  const key = a.slice(2);
  const next = argv[i + 1];
  if (next === undefined || next.startsWith('--')) opt[key] = true;
  else {
    opt[key] = next;
    i++;
  }
}

const PORT = Number(opt.port || 5219);
const UP_PORT = Number(opt.upstream || 5209);
const UP_HOST = '127.0.0.1';
const CORPUS = path.resolve(here, opt.corpus || path.join(repo, 'fixture/complex.docx'));
const BOOT = path.join(here, 'boot.js');
const BOOT_PATH = '/__fidus_host/boot.js';
const CORPUS_ROUTE = '/corpus.docx';
const DJANGO_CWD = path.join(repo, 'repos/fiduswriter/fiduswriter');
const FIDUS_PY = process.env.FIDUS_PY || '/tmp/fidusvenv2/bin/python';
const INJECT = `<script src="${BOOT_PATH}" defer></script>`;
// Django's setup page (base/setup_page/index.html), served on the same socket
// before `setup` returns. This string is the only difference between "the port
// is open" and "the app is there".
const MAINTENANCE_MARKER = 'currently being updated';
const NAV_HOLD_MS = Number(opt['nav-hold'] || 100000);

let appReady = false;

const say = (m) => console.log('[fidus-host]', m);

function djangoEnv() {
  // The three build blockers of Report C §2.11, in one place.
  const shim = '/tmp/capture_ui_gnucp';
  try {
    fs.mkdirSync(shim, { recursive: true });
    const cp = fs.existsSync('/opt/homebrew/bin/gcp') ? '/opt/homebrew/bin/gcp' : '/bin/cp';
    fs.rmSync(path.join(shim, 'cp'), { force: true });
    fs.symlinkSync(cp, path.join(shim, 'cp'));
  } catch (e) {
    say('cp shim skipped: ' + e.message);
  }
  return {
    ...process.env,
    PATH: `${shim}:/opt/homebrew/bin:${process.env.HOME}/Library/pnpm/bin:${process.env.PATH || ''}`,
    DYLD_FALLBACK_LIBRARY_PATH: '/opt/homebrew/opt/libmagic/lib',
  };
}

function listening(port) {
  return new Promise((resolve) => {
    const s = net.connect({ port, host: UP_HOST });
    s.setTimeout(600);
    s.once('connect', () => {
      s.destroy();
      resolve(true);
    });
    s.once('error', () => resolve(false));
    s.once('timeout', () => {
      s.destroy();
      resolve(false);
    });
  });
}

async function ensureUpstream() {
  if (await listening(UP_PORT)) {
    say(`django already listening on ${UP_HOST}:${UP_PORT}`);
    return null;
  }
  if (opt['no-spawn']) throw new Error(`nothing listening on ${UP_HOST}:${UP_PORT}`);
  say(`starting django: ${FIDUS_PY} manage.py runserver ${UP_HOST}:${UP_PORT} (cwd ${DJANGO_CWD})`);
  const child = spawn(
    FIDUS_PY,
    ['manage.py', 'runserver', `${UP_HOST}:${UP_PORT}`],
    { cwd: DJANGO_CWD, env: djangoEnv(), stdio: ['ignore', 'inherit', 'inherit'], detached: false },
  );
  child.on('exit', (code) => {
    say(`django exited (${code})`);
    process.exit(1);
  });
  for (let i = 0; i < 180; i++) {
    if (await listening(UP_PORT)) {
      say(`django socket up after ${i}s (setup may still be running behind it)`);
      return child;
    }
    if (child.exitCode !== null) break;
    await new Promise((r) => setTimeout(r, 1000));
  }
  child.kill('SIGTERM');
  throw new Error(`django did not listen on ${UP_HOST}:${UP_PORT}`);
}

// Is the APP behind the socket, or only Django's setup page? `runserver` answers
// every path with the setup page until `setup` (migrate, pnpm install, the first
// rspack transpile) returns, so a path check cannot tell them apart — the body
// can. Host: localhost because ALLOWED_HOSTS is ["localhost"].
function appAnswers() {
  return new Promise((resolve) => {
    const req = http.get(
      {
        host: UP_HOST,
        port: UP_PORT,
        path: '/',
        headers: { host: `localhost:${UP_PORT}`, accept: 'text/html', 'accept-encoding': 'identity' },
        timeout: 5000,
      },
      (res) => {
        const chunks = [];
        res.on('data', (c) => chunks.push(c));
        res.on('end', () => {
          const body = Buffer.concat(chunks).toString('utf8');
          // 2xx/3xx: the app answers (only the real app redirects — the setup
          // server answers every path with the same 200 page).
          resolve(res.statusCode >= 200 && res.statusCode < 400 && !body.includes(MAINTENANCE_MARKER));
        });
      },
    );
    req.on('timeout', () => req.destroy());
    req.on('error', () => resolve(false));
  });
}

async function waitForApp() {
  const t0 = Date.now();
  let nextNote = 0;
  for (;;) {
    if (await appAnswers()) {
      appReady = true;
      say(`app ready after ${((Date.now() - t0) / 1000).toFixed(1)}s`);
      return;
    }
    const elapsed = Date.now() - t0;
    if (elapsed >= nextNote) {
      say(`waiting for the app (${Math.round(elapsed / 1000)}s): the port answers with Django's setup page until the first transpile finishes`);
      nextNote = elapsed + 30000;
    }
    await new Promise((r) => setTimeout(r, 500));
  }
}

function proxy(req, res) {
  const headers = { ...req.headers };
  // Identity keeps the injected HTML a plain buffer, never a gzip stream.
  headers['accept-encoding'] = 'identity';
  const up = http.request(
    { host: UP_HOST, port: UP_PORT, method: req.method, path: req.url, headers },
    (upRes) => {
      const type = String(upRes.headers['content-type'] || '');
      if (!type.includes('text/html')) {
        res.writeHead(upRes.statusCode || 502, upRes.headers);
        upRes.pipe(res);
        return;
      }
      const chunks = [];
      upRes.on('data', (c) => chunks.push(c));
      upRes.on('end', () => {
        let body = Buffer.concat(chunks).toString('utf8');
        const at = body.lastIndexOf('</body>');
        body = at === -1 ? body + INJECT : body.slice(0, at) + INJECT + body.slice(at);
        const out = Buffer.from(body, 'utf8');
        const h = { ...upRes.headers };
        delete h['content-length'];
        delete h['content-encoding'];
        delete h.etag;
        h['content-length'] = String(out.length);
        res.writeHead(upRes.statusCode || 200, h);
        res.end(out);
      });
    },
  );
  up.on('error', (e) => {
    if (!res.headersSent) res.writeHead(502, { 'content-type': 'text/plain' });
    res.end('fidus-host upstream error: ' + e.message);
  });
  req.pipe(up);
}

// What a browser gets while the app is still being built. It reloads itself,
// so a navigation that arrived early still ends on the editor; boot.js ignores
// it (see boot.js isStartingPage).
const BOOT_PAGE = `<!doctype html>
<html data-fidus-host-booting="1"><head><meta charset="utf-8">
<title>Fidus Writer — starting</title>
<meta http-equiv="refresh" content="1">
<style>body{font:14px/1.5 -apple-system,system-ui,sans-serif;margin:3rem;color:#333}</style>
</head><body><h1>Fidus Writer is starting</h1>
<p>The host is up; the application is still building (migrate + first transpile).
This page reloads every second. Waited {{waited}} s.</p></body></html>`;

function isNavigation(req) {
  return (
    (req.method === 'GET' || req.method === 'HEAD') &&
    (req.headers['sec-fetch-mode'] === 'navigate' ||
      String(req.headers.accept || '').includes('text/html'))
  );
}

function serveBootPage(res, waitedMs) {
  const body = Buffer.from(BOOT_PAGE.replace('{{waited}}', String(Math.round(waitedMs / 1000))));
  res.writeHead(200, {
    'content-type': 'text/html; charset=utf-8',
    'cache-control': 'no-store',
    'content-length': String(body.length),
  });
  res.end(body);
}

function holdForApp(req, res) {
  if (!isNavigation(req)) {
    // The runner polls `/` with urllib (no Accept: text/html): a 503 keeps it
    // waiting and is honest about the state, where a 200 boot page would let it
    // fire the probe at a page that is not the app yet.
    res.writeHead(503, {
      'content-type': 'text/plain; charset=utf-8',
      'retry-after': '1',
      'cache-control': 'no-store',
    });
    res.end('fidus-host: application still starting; retry in a second\n');
    return;
  }
  const started = Date.now();
  let timer = null;
  const tick = () => {
    if (res.writableEnded || res.destroyed) return;
    if (appReady) {
      proxy(req, res);
      return;
    }
    if (Date.now() - started >= NAV_HOLD_MS) {
      serveBootPage(res, Date.now() - started);
      return;
    }
    timer = setTimeout(tick, 500);
  };
  res.on('close', () => {
    if (timer) clearTimeout(timer);
  });
  tick();
}

const server = http.createServer((req, res) => {
  const url = req.url.split('?')[0];
  if (url === BOOT_PATH) {
    const body = fs.readFileSync(BOOT);
    res.writeHead(200, {
      'content-type': 'application/javascript; charset=utf-8',
      'cache-control': 'no-store',
      'content-length': String(body.length),
    });
    res.end(body);
    return;
  }
  if (url === CORPUS_ROUTE && fs.existsSync(CORPUS)) {
    const body = fs.readFileSync(CORPUS);
    res.writeHead(200, {
      'content-type': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'cache-control': 'no-store',
      'content-length': String(body.length),
    });
    res.end(body);
    return;
  }
  if (!appReady) {
    holdForApp(req, res);
    return;
  }
  proxy(req, res);
});

// EDITOR_SAVE_MODE="collaborative" opens ws://<page origin>/ws/document/<id>/.
server.on('upgrade', (req, socket, head) => {
  const up = net.connect({ host: UP_HOST, port: UP_PORT }, () => {
    const lines = [];
    for (let i = 0; i < req.rawHeaders.length; i += 2) {
      lines.push(`${req.rawHeaders[i]}: ${req.rawHeaders[i + 1]}`);
    }
    up.write(`${req.method} ${req.url} HTTP/1.1\r\n${lines.join('\r\n')}\r\n\r\n`);
    if (head && head.length) up.write(head);
    socket.pipe(up).pipe(socket);
  });
  up.on('error', () => socket.destroy());
  socket.on('error', () => up.destroy());
});

const child = await ensureUpstream();
server.listen(PORT, '127.0.0.1', () => {
  say(`http://localhost:${PORT}/  ->  ${UP_HOST}:${UP_PORT}   (corpus ${CORPUS})`);
});
// The port is open before the application is: keep the runner polling (it sees
// 503) and hold browser navigations, instead of handing either of them Django's
// setup page.
waitForApp().catch((e) => say('readiness check failed: ' + e.message));

for (const sig of ['SIGINT', 'SIGTERM']) {
  process.on(sig, () => {
    if (child && child.exitCode === null) child.kill('SIGTERM');
    server.close(() => process.exit(0));
  });
}
