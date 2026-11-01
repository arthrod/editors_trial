import { copyFileSync, existsSync, readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';

import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';
import { nodePolyfills } from 'vite-plugin-node-polyfills';

const APP = resolve(import.meta.dirname);
const SRC = resolve(APP, '../src/packages');
const DIST = resolve(APP, '../dist');

const REPO_URL = 'https://github.com/udecode/plate';
const COMMIT = '08b1571f2df0c377923ace3a90f994a482decfba';

/**
 * The licence and the provenance note travel with the build. They are
 * written into the output folder after the bundle is emitted, so the served
 * site carries the MIT licence of the plate repository it was built from.
 */
function licencePlugin() {
  return {
    name: 'plate-demo-licence',
    apply: 'build' as const,
    closeBundle() {
      const licence = resolve(SRC, '../LICENSE');

      if (existsSync(licence)) {
        copyFileSync(licence, resolve(DIST, 'LICENSE'));
      }

      writeFileSync(
        resolve(DIST, 'SOURCE.txt'),
        [
          'Plate.js DOCX live demo',
          '',
          `Source repository: ${REPO_URL}`,
          `Commit: ${COMMIT}`,
          'Commit: 08b1571',
          '',
          'Licence: MIT (see LICENSE in this folder).',
          'Copyright (c) Ziad Beyens, Dylan Schiemann, Joe Anderson, Felix Feng',
          '',
          'The editor bundle in this folder is built from the plate monorepo at',
          'the commit above. The DOCX document opened by the demo is the',
          'benchmark fixture document.docx, copied here unchanged.',
          '',
        ].join('\n'),
        'utf8'
      );
    },
  };
}

/**
 * The plate repo is a pnpm workspace whose packages publish from `dist/`.
 * Nothing here is built, so every workspace entry point is mapped back to its
 * TypeScript source. The map is derived from each package's own `exports`
 * field, so it stays in step with the source at commit 08b1571.
 */
const workspaceAliases = (packageDir: string, name: string) => {
  const pkg = JSON.parse(
    readFileSync(resolve(packageDir, 'package.json'), 'utf8')
  );
  const aliases: { find: string; replacement: string }[] = [];

  for (const [key, value] of Object.entries(pkg.exports ?? {})) {
    const target =
      typeof value === 'string'
        ? value
        : (value.import ?? value.default ?? value.require);
    if (!target || key === './package.json') continue;

    const relative = target.replace(/^\.\/dist\//, './src/').replace(/\.js$/, '');
    const candidates = [
      `${relative}.ts`,
      `${relative}.tsx`,
      `${relative}/index.ts`,
      `${relative}/index.tsx`,
    ];
    const found = candidates.find((candidate) =>
      existsSync(resolve(packageDir, candidate))
    );
    if (!found) continue;

    const specifier = key === '.' ? name : `${name}/${key.slice(2)}`;

    aliases.push({
      find: specifier,
      replacement: resolve(packageDir, found),
    });
  }

  // Longest specifier first so `platejs/docx/import` wins over `platejs`.
  return aliases.sort((a, b) => b.find.length - a.find.length);
};

export default defineConfig({
  base: './',
  plugins: [
    react(),
    // The DOCX engine pulls in xmlbuilder2, mime-types and htmlparser2, which
    // reach for Node's `events`, `url`, `path` and `buffer`. The browser
    // builds of those four are bundled from the plugin's own shims, so the
    // page makes no request outside its own folder.
    nodePolyfills({
      include: ['events', 'url', 'path', 'buffer', 'util', 'stream'],
      globals: {
        Buffer: true,
        global: true,
        process: false,
      },
    }),
    licencePlugin(),
  ],
  resolve: {
    alias: [
      ...workspaceAliases(resolve(SRC, 'platejs'), 'platejs'),
      ...workspaceAliases(resolve(SRC, 'plitejs'), 'plitejs'),
      {
        find: '@/registry/components/editor/',
        replacement: resolve(APP, 'src/kit/') + '/',
      },
      { find: '@/lib/utils', replacement: resolve(APP, 'src/kit/lib-utils.ts') },
      {
        find: '@/components/ui/button',
        replacement: resolve(APP, 'src/kit/ui-button.tsx'),
      },
      // Plate's static renderer picks react-dom/server.edge or
      // react-dom/server.browser at runtime. In a browser `globalThis.process`
      // is undefined, so the edge build is unreachable - but the dynamic
      // import still ships both. Pointing the edge specifier at the browser
      // build removes a duplicate ~290 KiB React server bundle from the
      // output without changing what the page runs.
      {
        find: 'react-dom/server.edge',
        replacement: 'react-dom/server.browser',
      },
    ],
  },
  define: {
    'process.env.NODE_ENV': JSON.stringify('production'),
  },
  build: {
    target: 'es2022',
    sourcemap: false,
    chunkSizeWarningLimit: 4096,
    outDir: DIST,
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined;
          if (id.includes('mammoth')) return 'vendor-mammoth';
          if (id.includes('juice') || id.includes('cheerio')) return 'vendor-css';
          if (id.includes('katex')) return 'vendor-katex';
          if (id.includes('lowlight') || id.includes('highlight.js')) {
            return 'vendor-highlight';
          }
          // React, react-dom and scheduler stay together and are the LAST
          // chunk to be emitted. Splitting react out of the main vendor chunk
          // made the chunk graph circular (vendor -> vendor-react -> vendor),
          // which produced a "Cannot access 'hr' before initialization"
          // ReferenceError at runtime: the vendor chunk read the react binding
          // while the react chunk was still initialising.
          return 'vendor';
        },
      },
    },
  },
});
