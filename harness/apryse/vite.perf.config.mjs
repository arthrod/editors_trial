// Browser perf host config for harness/apryse (port 5213).
//
//   cd harness/apryse && pnpm exec vite --config vite.perf.config.mjs \
//     --port 5213 --strictPort --host 127.0.0.1
//
// Differences from vite.config.mjs (the round-trip / Report C host on 5210):
//   - a different port, so both hosts can run at once;
//   - /corpus.docx is served from fixture/complex.docx when nothing upstream
//     intercepts it (the warm/cold probe fulfils that route with its own
//     generated fixture), so the page also opens by hand.
// The COOP/COEP headers, envDir and envPrefix are the ones WebViewer's
// WebAssembly threads and the trial's APRYSE_API_KEY need.
import { defineConfig } from 'vite';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FALLBACK_DOCX = path.resolve(HERE, '../../fixture/complex.docx');

function corpusFallback() {
  return {
    name: 'apryse-perf-corpus',
    configureServer(server) {
      server.middlewares.use('/corpus.docx', (_req, res) => {
        if (!fs.existsSync(FALLBACK_DOCX)) {
          res.statusCode = 404;
          res.setHeader('Content-Type', 'text/plain');
          res.end('no fixture/complex.docx; the probe fulfils this route itself\n');
          return;
        }
        res.setHeader(
          'Content-Type',
          'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        );
        res.setHeader('Cache-Control', 'no-store');
        res.end(fs.readFileSync(FALLBACK_DOCX));
      });
    },
  };
}

export default defineConfig({
  envDir: '../..',
  envPrefix: 'APRYSE_',
  cacheDir: process.env.APRYSE_VITE_CACHE || 'node_modules/.vite-perf',
  plugins: [corpusFallback()],
  server: {
    port: 5213,
    strictPort: true,
    host: '127.0.0.1',
    headers: {
      'Cross-Origin-Opener-Policy': 'same-origin',
      'Cross-Origin-Embedder-Policy': 'require-corp',
    },
  },
});
