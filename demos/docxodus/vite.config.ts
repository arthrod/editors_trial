import { cpSync, mkdirSync, copyFileSync, writeFileSync, readdirSync, statSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { defineConfig, type Plugin } from 'vite';

const here = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.resolve(here, '../dist');
const wasmSrc = path.resolve(here, 'node_modules/docxodus/dist/wasm');
const documentSrc = process.env.DEMO_DOCX; // optional: sync:demos supplies document.docx
const licenseSrc = path.resolve(here, '../src/LICENSE');

function copyTree(src: string, dest: string): void {
  mkdirSync(dest, { recursive: true });
  for (const name of readdirSync(src)) {
    if (name.endsWith('.br') || name.endsWith('.map') || name.endsWith('.pdb')) continue;
    const from = path.join(src, name);
    const to = path.join(dest, name);
    if (statSync(from).isDirectory()) copyTree(from, to);
    else copyFileSync(from, to);
  }
}

function runtimeAssets(): Plugin {
  return {
    name: 'docxodus-runtime-assets',
    closeBundle() {
      copyTree(wasmSrc, path.join(outDir, 'wasm'));
      if (documentSrc) copyFileSync(documentSrc, path.join(outDir, 'document.docx'));
      copyFileSync(licenseSrc, path.join(outDir, 'LICENSE'));
      writeFileSync(
        path.join(outDir, 'SOURCE.txt'),
        [
          'Docxodus live demo for benchmarks.law',
          'Repository: https://github.com/JSv4/Docxodus',
          'Commit: ceb5cde',
          'License: MIT (see LICENSE)',
          'Demo host page and build configuration: https://github.com/arthrod/editors_trial/tree/main/demos/docxodus',
          'Runtime: npm docxodus@14.2.0 (published from commit ceb5cde), the package the trial measured.',
          '',
        ].join('\n'),
      );
    },
  };
}

export default defineConfig({
  base: './',
  plugins: [runtimeAssets()],
  build: {
    outDir,
    emptyOutDir: true,
    sourcemap: false,
    minify: true,
    cssCodeSplit: false,
    assetsInlineLimit: 0,
    rollupOptions: {
      output: {
        manualChunks: undefined,
      },
    },
  },
});
