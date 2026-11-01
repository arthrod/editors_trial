import { cpSync, mkdirSync, copyFileSync, writeFileSync, readdirSync, statSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { defineConfig, type Plugin } from 'vite';

const here = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.resolve(here, '../dist');
const wasmSrc = path.resolve(here, 'node_modules/docxodus/dist/wasm');
const documentSrc = '/tmp/demos/docxodus.docx';
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
      copyFileSync(documentSrc, path.join(outDir, 'document.docx'));
      copyFileSync(licenseSrc, path.join(outDir, 'LICENSE'));
      writeFileSync(
        path.join(outDir, 'SOURCE.txt'),
        [
          'https://github.com/JSv4/Docxodus',
          'commit 97c304f7af8f07247eba5c042f0be9f07f8b133b',
          '',
          'Browser runtime is the published npm package docxodus@15.0.0',
          '(registry gitHead 34eb9a3354fa81a9f670fa0bec13b4f641adacee).',
          'That package does not match trial commit 97c304f.',
          'No NOTICE file is present in the repository.',
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
