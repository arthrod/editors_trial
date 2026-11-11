/**
 * Tiny static server for the office-open browser perf host (port 5212).
 * Serves only files inside this directory, plus /corpus.docx.
 *
 *   cd harness/ui/officeopen && node server.mjs
 *
 * The corpus route answers with the generated warm_cold fixture (corpus.docx,
 * see make_corpus.py). The perf driver also intercepts the same route, so the
 * measured bytes are the runner's own fixture.
 */
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const PORT = Number(process.env.PORT || 5212);
const CORPUS = process.env.CORPUS_DOCX
  ? path.resolve(process.env.CORPUS_DOCX)
  : path.join(here, "corpus.docx");

const DOCX_TYPE =
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document";

const TYPES = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".docx": DOCX_TYPE,
};

function sendFile(res, file, type) {
  fs.readFile(file, (err, buf) => {
    if (err) {
      res.writeHead(404, { "content-type": "text/plain" }).end("not found");
      return;
    }
    res.writeHead(200, { "content-type": type, "cache-control": "no-store" });
    res.end(buf);
  });
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);
  const p = decodeURIComponent(url.pathname);
  if (p === "/corpus.docx") {
    sendFile(res, CORPUS, DOCX_TYPE);
    return;
  }
  const file = path.join(here, p === "/" ? "/index.html" : p);
  if (!file.startsWith(here)) {
    res.writeHead(403).end("forbidden");
    return;
  }
  sendFile(res, file, TYPES[path.extname(file)] || "application/octet-stream");
});

server.listen(PORT, "127.0.0.1", () => {
  const corpusState = fs.existsSync(CORPUS) ? CORPUS : `${CORPUS} (missing — run make_corpus.py)`;
  console.log(`office-open host app on http://127.0.0.1:${PORT}/`);
  console.log(`corpus route /corpus.docx -> ${corpusState}`);
});
