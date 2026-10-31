// Host app for the Canvas-Editor DOCX rendering study.
// Lives OUTSIDE repos/ so that nothing under repos/ is modified.
//
// - '@hufe921/canvas-editor' resolves to the editor CORE SOURCE in
//   repos/canvas-editor/src/editor/index.ts (v1.0.6), i.e. the repo under
//   study, not the npm build.
// - '@docx-plugin' resolves to the official DOCX import routine of
//   @hufe921/canvas-editor-plugin-docx (repos/canvas-editor-plugin).
//
// `vite` is intentionally not imported here so this config resolves without a
// local vite install; it is a plain ESM default export.

import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const repos = path.resolve(here, '../../../repos')

// CANVAS_CORE=repo  (default) -> editor core SOURCE from repos/canvas-editor (v1.0.6)
// CANVAS_CORE=npm             -> the published build the official plugin demo uses (v1.0.2)
// The latter exists only to tell a core regression apart from a plugin defect.
const coreTarget =
  process.env.CANVAS_CORE === 'npm'
    ? path.resolve(
        repos,
        'canvas-editor-plugin/demo/node_modules/@hufe921/canvas-editor/dist/canvas-editor.js'
      )
    : path.resolve(repos, 'canvas-editor/src/editor/index.ts')

export default {
  resolve: {
    alias: {
      '@hufe921/canvas-editor': coreTarget,
      '@docx-plugin': path.resolve(
        repos,
        'canvas-editor-plugin/packages/docx/src/docx/importDocx.ts'
      )
    }
  },
  server: {
    host: '127.0.0.1',
    port: 5204,
    strictPort: true,
    fs: {
      allow: [path.resolve(here, '../../..')]
    }
  }
}
