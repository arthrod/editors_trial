/**
 * Static server for the WordCraft browser perf host (port 5219).
 *
 *   cd harness/ui/wordcraft-host && node server.mjs
 *
 * Serves the Trunk output of apps/wordcraft-web (repos/wordcraft/dist/web) at `/`, with
 * `/_host/host.js` injected into its index.html: the shim opens `/corpus.docx` through the app's
 * own drop path and publishes the ready signal (see host.js).
 *
 * The perf driver intercepts `/corpus.docx` too, so the measured bytes are the runner's own
 * fixture; this route only matters for a standalone open.
 *
 *   PORT=5219  WC_DIST=...  CORPUS_DOCX=/abs/corpus.docx node server.mjs
 */
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(here, "../../..");
const PORT = Number(process.env.PORT || 5219);
const DIST = path.resolve(process.env.WC_DIST || path.join(REPO, "repos/wordcraft/dist/web"));
const CORPUS = path.resolve(
  process.env.CORPUS_DOCX || path.join(REPO, "fixture/complex.docx"),
);

const DOCX_TYPE =
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document";

const TYPES = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".wasm": "application/wasm",
  ".ico": "image/x-icon",
  ".png": "image/png",
  ".svg": "image/svg+xml",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
  ".ttf": "font/ttf",
};

const HOST_JS = fs.readFileSync(path.join(here, "host.js"), "utf8");
const INJECT = '<script src="/_host/host.js"></script>';

function send(res, status, type, body, extraHeaders = {}) {
  res.writeHead(status, {
    "content-type": type,
    "cache-control": "no-store",
    ...extraHeaders,
  });
  res.end(body);
}

function serveAppHtml(res) {
  const file = path.join(DIST, "index.html");
  fs.readFile(file, "utf8", (err, html) => {
    if (err) {
      send(res, 500, "text/plain; charset=utf-8", `missing ${file}\nbuild it first: see BUILD.md\n`);
      return;
    }
    const patched = html.includes("</body>")
      ? html.replace("</body>", `${INJECT}\n</body>`)
      : `${html}\n${INJECT}\n`;
    send(res, 200, "text/html; charset=utf-8", patched);
  });
}

function serveDist(res, relPath) {
  const file = path.join(DIST, relPath);
  if (!file.startsWith(DIST)) {
    send(res, 403, "text/plain; charset=utf-8", "forbidden");
    return;
  }
  fs.readFile(file, (err, buf) => {
    if (err) {
      send(res, 404, "text/plain; charset=utf-8", `not found: ${relPath}`);
      return;
    }
    const ext = path.extname(file).toLowerCase();
    const headers = ext === ".wasm" ? { "cross-origin-resource-policy": "same-origin" } : {};
    send(res, 200, TYPES[ext] || "application/octet-stream", buf, headers);
  });
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url, `http://127.0.0.1:${PORT}`);
  const p = decodeURIComponent(url.pathname);

  if (p === "/health") {
    send(res, 200, "application/json; charset=utf-8", JSON.stringify({ ok: true, dist: DIST }));
    return;
  }
  if (p === "/corpus.docx") {
    fs.readFile(CORPUS, (err, buf) => {
      if (err) send(res, 404, "text/plain; charset=utf-8", `missing ${CORPUS}`);
      else send(res, 200, DOCX_TYPE, buf);
    });
    return;
  }
  if (p === "/_host/host.js") {
    send(res, 200, "text/javascript; charset=utf-8", HOST_JS);
    return;
  }
  if (p === "/" || p === "/index.html") {
    serveAppHtml(res);
    return;
  }
  if (p === "/favicon.ico") {
    res.writeHead(204).end();
    return;
  }
  serveDist(res, p);
});

server.listen(PORT, "127.0.0.1", () => {
  process.stderr.write(`wordcraft-host on http://127.0.0.1:${PORT}/  dist=${DIST}\n`);
});
