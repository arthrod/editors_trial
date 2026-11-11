// Warm/cold browser host for docen (@docen/editor).
// Lives OUTSIDE repos/ so that nothing under repos/ is modified.
//
// The aliases mirror the repo's own demo config
// (repos/docen/packages/editor/vite.config.ts): the editor, its core, the
// layout engine and pptx serve from SOURCE, and every other @docen package is
// aliased to source too instead of its (unbuilt) dist/, so the host runs
// straight off the pinned checkout with no build step. Subpaths get their own
// exact-match entry ahead of the bare package: Vite's string aliases
// prefix-match, and a bare "@docen/docx" entry would rewrite
// "@docen/docx/core" into "<index.ts>/core".
//
// `vite` is intentionally not imported here so this config resolves without a
// local vite install; it is a plain ESM default export.

import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const trial = path.resolve(here, '../../..')
const repo = path.resolve(trial, 'repos/docen')
const pkg = (...p) => path.resolve(repo, 'packages', ...p)
const exact = (name, replacement) => ({
  find: new RegExp(`^${name.replace(/[/@.]/g, (c) => `\\${c}`)}$`),
  replacement
})

export default {
  resolve: {
    alias: [
      // Subpaths first (exact matches, so order is only for readability).
      exact('@docen/core/geometry', pkg('core/src/geometry/index.ts')),
      exact('@docen/core/paint', pkg('core/src/paint/index.ts')),
      exact('@docen/docx/core', pkg('docx/src/core.ts')),
      exact('@docen/docx/editor', pkg('docx/src/editor.ts')),
      exact('@docen/docx/layout', pkg('docx/src/layout/index.ts')),
      exact('@docen/pretext/rich-inline', pkg('pretext/src/rich-inline.ts')),
      // Bare packages.
      exact('@docen/core', pkg('core/src/index.ts')),
      exact('@docen/docx', pkg('docx/src/index.ts')),
      exact('@docen/editor', pkg('editor/src/index.ts')),
      exact('@docen/layout', pkg('layout/src/index.ts')),
      exact('@docen/markdown', pkg('markdown/src/index.ts')),
      exact('@docen/pptx', pkg('pptx/src/index.ts')),
      exact('@docen/pretext', pkg('pretext/src/layout.ts')),
      // leafer-x-metafile ships dist-only, but @docen/docx (aliased to source)
      // imports it for EMF/WMF media — serve it from source as well.
      exact('leafer-x-metafile', pkg('leafer-x-metafile/src/index.ts'))
    ]
  },
  server: {
    host: '127.0.0.1',
    port: 5214,
    strictPort: true,
    fs: {
      allow: [trial]
    }
  }
}
