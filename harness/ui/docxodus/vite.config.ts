import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vite';

/**
 * Docxodus rendering-study host.
 *
 * The editor under test is Docxodus itself (JSv4/Docxodus, v14.2.0) — the
 * published WebAssembly build of the .NET OOXML engine:
 *   - `convertDocxToPaginatedHtml()`  the materializer the `docxodus` CLI and
 *     `@docxodus/export` drive, so the page tree is the product's own;
 *   - `DocxEditor`                    the in-browser block editor;
 *   - `DocxSession`                   the package reader/writer.
 *
 * The .NET runtime assets are served from the package's own `dist/wasm/`
 * directory, at `/wasm/`, so nothing under `repos/` is touched and the host
 * adds no rendering logic of its own.
 */

const HERE = path.dirname(fileURLToPath(import.meta.url));
const PKG_ROOT = path.join(HERE, 'node_modules', 'docxodus');
const DIST = path.join(PKG_ROOT, 'dist');
const WASM = path.join(DIST, 'wasm');

const MIME: Record<string, string> = {
  '.wasm': 'application/wasm',
  '.js': 'text/javascript',
  '.json': 'application/json',
  '.dat': 'application/octet-stream',
  '.pdb': 'application/octet-stream',
  '.blat': 'application/octet-stream',
  '.br': 'application/octet-stream',
};

function wasmAssets() {
  return {
    name: 'docxodus-wasm-assets',
    configureServer(server: any) {
      server.middlewares.use((req: any, res: any, next: any) => {
        if (!req.url || !req.url.startsWith('/wasm/')) return next();
        const rel = decodeURIComponent(req.url.split('?')[0].replace(/^\/wasm\//, ''));
        let file = path.join(WASM, rel);
        const wasmCandidate =
          file.startsWith(WASM) && fs.existsSync(file) && !fs.statSync(file).isDirectory();
        if (!wasmCandidate) {
          file = path.join(DIST, rel);
          if (!file.startsWith(DIST) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
            return next();
          }
        }
        res.setHeader('Content-Type', MIME[path.extname(file)] || 'application/octet-stream');
        res.setHeader('Cache-Control', 'no-store');
        fs.createReadStream(file).pipe(res);
      });
    },
  };
}

export default defineConfig({
  plugins: [wasmAssets()],
  server: {
    host: '127.0.0.1',
    port: 5210,
    strictPort: true,
    fs: { allow: [HERE, PKG_ROOT, path.join(HERE, 'node_modules')] },
  },
  optimizeDeps: {
    // Prebundling inflates export-browser past export-assets.json byteLength (runtime verification fails).
    exclude: ['docxodus', 'docxodus/export-browser'],
  },
  worker: { format: 'es' },
});
