import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { defineConfig, searchForWorkspaceRoot } from 'vite';

const exampleRoot = path.dirname(fileURLToPath(import.meta.url));
const superdocEntry = fileURLToPath(import.meta.resolve('superdoc'));
const engineEntry = createRequire(superdocEntry).resolve('@superdoc/docx-engine');

export default defineConfig({
  // The host site serves this folder at /demo-apps/superdoc/, so every URL
  // the page emits has to stay relative to the document.
  base: './',
  resolve: {
    alias: {
      // The bundled metric-compatible font pack (Carlito for Calibri, ...).
      // Read from source so every .woff2 becomes a local build asset.
      '@superdoc/fonts': path.resolve(exampleRoot, '../../packages/fonts/src/index.ts'),
    },
  },
  optimizeDeps: {
    exclude: ['@superdoc/docx-engine'],
  },
  server: {
    fs: {
      allow: [searchForWorkspaceRoot(exampleRoot), path.dirname(engineEntry)],
    },
  },
  worker: {
    // The DOCX engine ships module workers whose graph code-splits; the
    // default iife worker format cannot represent that in a build.
    format: 'es',
  },
  build: {
    // /tmp/demos/superdoc/dist - the deliverable folder.
    outDir: path.resolve(exampleRoot, '../../../dist'),
    emptyOutDir: true,
    target: 'es2022',
    minify: 'esbuild',
    sourcemap: false,
    chunkSizeWarningLimit: 64 * 1024,
    reportCompressedSize: false,
  },
});
