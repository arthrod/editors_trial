import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { defineConfig } from '../src/node_modules/vite/dist/node/index.js';
import react from '../src/node_modules/@vitejs/plugin-react/dist/index.js';

const appDir = dirname(fileURLToPath(import.meta.url));
const repoDir = resolve(appDir, '../src');

export default defineConfig({
  root: appDir,
  base: './',
  publicDir: resolve(appDir, '../public'),
  plugins: [react()],
  resolve: {
    alias: [
      {
        find: /^@docx-editor\.dev\/react$/,
        replacement: resolve(repoDir, 'packages/react/dist/index.mjs'),
      },
      {
        find: /^@docx-editor\.dev\/core$/,
        replacement: resolve(repoDir, 'packages/core/dist/index.js'),
      },
      {
        find: /^@docx-editor\.dev\/core\/(.+)$/,
        replacement: resolve(repoDir, 'packages/core/dist/$1.js'),
      },
      {
        find: /^@docx-editor\.dev\/i18n$/,
        replacement: resolve(repoDir, 'packages/i18n/dist/index.mjs'),
      },
      {
        find: /^react-dom\/client$/,
        replacement: resolve(repoDir, 'node_modules/react-dom/client.js'),
      },
      {
        find: /^react-dom$/,
        replacement: resolve(repoDir, 'node_modules/react-dom/index.js'),
      },
      {
        find: /^react\/jsx-runtime$/,
        replacement: resolve(repoDir, 'node_modules/react/jsx-runtime.js'),
      },
      {
        find: /^react$/,
        replacement: resolve(repoDir, 'node_modules/react/index.js'),
      },
    ],
  },
  build: {
    outDir: resolve(appDir, '../dist'),
    emptyOutDir: true,
    minify: 'esbuild',
    sourcemap: false,
    target: 'es2022',
    chunkSizeWarningLimit: 2000,
  },
});
