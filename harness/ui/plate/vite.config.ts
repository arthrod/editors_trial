import path from 'node:path';
import { fileURLToPath } from 'node:url';

import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

const here = path.dirname(fileURLToPath(import.meta.url));
const WORKSPACE = path.resolve(here, '../../..');
const PLATE_SRC = path.join(WORKSPACE, 'repos/plate/packages/platejs/src');
const PLITE_SRC = path.join(WORKSPACE, 'repos/plate/packages/plitejs/src');

/**
 * `platejs` ships as a built package (`dist/`), but the repo checkout has no
 * build output.  Point every published subpath at the TypeScript source in
 * `packages/platejs/src` so the dev server compiles it on the fly.
 */
const PLATE_ALIASES: Record<string, string> = {
  'platejs/react': `${PLATE_SRC}/react/index.tsx`,
  'platejs/static': `${PLATE_SRC}/static/index.ts`,
  'platejs/table': `${PLATE_SRC}/features/table/index.ts`,
  'platejs/table/react': `${PLATE_SRC}/react/features/table/index.ts`,
  'platejs/media': `${PLATE_SRC}/features/media/index.ts`,
  'platejs/media/react': `${PLATE_SRC}/react/features/media/index.ts`,
  'platejs/comments': `${PLATE_SRC}/features/comments/index.ts`,
  'platejs/comments/react': `${PLATE_SRC}/react/features/comments/index.ts`,
  'platejs/footnote': `${PLATE_SRC}/features/footnote/index.ts`,
  'platejs/footnote/react': `${PLATE_SRC}/react/features/footnote/index.ts`,
  'platejs/math': `${PLATE_SRC}/math/index.ts`,
  'platejs/math/react': `${PLATE_SRC}/math/react/index.ts`,
  'platejs/link': `${PLATE_SRC}/features/link/index.ts`,
  'platejs/link/react': `${PLATE_SRC}/react/features/link/index.ts`,
  'platejs/list': `${PLATE_SRC}/features/list/index.ts`,
  'platejs/code-block': `${PLATE_SRC}/features/code-block/index.ts`,
  'platejs/toc': `${PLATE_SRC}/features/toc/index.ts`,
  'platejs/mention': `${PLATE_SRC}/features/mention/index.ts`,
  'platejs/details': `${PLATE_SRC}/features/details/index.ts`,
  'platejs/details/react': `${PLATE_SRC}/react/features/details/index.ts`,
  'platejs/callout': `${PLATE_SRC}/features/callout/index.ts`,
  'platejs/layout': `${PLATE_SRC}/features/layout/index.ts`,
  'platejs/date': `${PLATE_SRC}/features/date/index.ts`,
  'platejs/upload': `${PLATE_SRC}/features/upload/index.ts`,
  'platejs/html': `${PLATE_SRC}/html/index.ts`,
  'platejs/markdown': `${PLATE_SRC}/markdown/index.ts`,
  'platejs/docx/import': `${PLATE_SRC}/docx/import/index.ts`,
  'platejs/docx/export': `${PLATE_SRC}/docx/export/index.ts`,
  'platejs/docx/paste': `${PLATE_SRC}/docx/paste/index.ts`,
  'platejs': `${PLATE_SRC}/index.tsx`,
};

/** `platejs` is built on top of the headless `plitejs` package. */
const PLITE_ALIASES: Record<string, string> = {
  'plitejs/internal': `${PLITE_SRC}/internal/index.ts`,
  'plitejs/dom': `${PLITE_SRC}/dom/index.ts`,
  'plitejs/authored': `${PLITE_SRC}/authored/index.ts`,
  'plitejs/history': `${PLITE_SRC}/history/index.ts`,
  'plitejs/hyperscript': `${PLITE_SRC}/hyperscript/index.ts`,
  'plitejs/annotations': `${PLITE_SRC}/annotations/index.ts`,
  'plitejs/diff': `${PLITE_SRC}/diff/index.ts`,
  'plitejs/testing': `${PLITE_SRC}/testing/index.ts`,
  'plitejs/react': `${PLITE_SRC}/react/index.ts`,
  'plitejs/pagination': `${PLITE_SRC}/pagination/index.ts`,
  'plitejs': `${PLITE_SRC}/index.ts`,
};

const escape = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: [
      ...Object.entries(PLATE_ALIASES).map(([find, replacement]) => ({
        find: new RegExp(`^${escape(find)}$`),
        replacement,
      })),
      ...Object.entries(PLITE_ALIASES).map(([find, replacement]) => ({
        find: new RegExp(`^${escape(find)}$`),
        replacement,
      })),
    ],
    // the repo's node_modules is a symlink to harness/plate/node_modules, which
    // carries its own react copy - force a single instance.
    dedupe: ['react', 'react-dom'],
  },
  server: {
    host: '127.0.0.1',
    port: 5208,
    strictPort: true,
    fs: {
      // the editor source lives outside this host's root
      allow: [WORKSPACE],
    },
  },
  optimizeDeps: {
    include: ['mammoth', 'react', 'react-dom', 'react-dom/client'],
  },
});
