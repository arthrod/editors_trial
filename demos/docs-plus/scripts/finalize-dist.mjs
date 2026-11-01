/**
 * Post-build step: put the licence and the provenance of the bundled code next
 * to the demo, then report the size of `dist/`.
 */
import { copyFile, writeFile, readdir, stat } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const appDir = path.resolve(here, '..')
const distDir = path.resolve(appDir, '..', 'dist')
const repoDir = path.resolve(appDir, '..', 'src')

const REPO_URL = 'https://github.com/docs-plus/docs.plus'
const COMMIT = 'a9b0c69e8442702c6111c04a12319f61a995ccfc'

await copyFile(path.join(repoDir, 'LICENSE'), path.join(distDir, 'LICENSE'))

await writeFile(
  path.join(distDir, 'SOURCE.txt'),
  `docs.plus — DOCX editor demo
===========================

Source project : docs.plus
Repository      : ${REPO_URL}
Commit          : ${COMMIT}
Licence         : MIT (see LICENSE in this folder)

What this folder is
-------------------
A static, client-side build of the docs.plus DOCX editor. The DOCX import and
export code is the product's own:

  apps/hocuspocus.server/src/modules/document-conversion/domain/docxImport.ts
  apps/hocuspocus.server/src/modules/document-conversion/domain/docxExport.ts
  apps/hocuspocus.server/src/modules/document-conversion/domain/documentHtml.ts

They are imported unchanged. Only the platform edges were adapted for the
browser (mammoth's official browser build, the DOM instead of linkedom, and
fflate instead of node:zlib); see REPORT.md for the full list.

The editor is Tiptap with the docs.plus extensions the webapp uses
(extensions/extension-*), plus the webapp's own ParagraphStyle, TitleDocument
and Highlight extensions.
`
)

await writeFile(
  path.join(distDir, 'THIRD-PARTY.txt'),
  `Third-party code bundled in this demo
======================================

mammoth                BSD-2-Clause   https://github.com/mwilliamson/mammoth.js
@turbodocx/html-to-docx  MIT          https://github.com/TurboDocx/html-to-docx
@tiptap/*              MIT           https://github.com/ueberdosis/tiptap
prosemirror-*          MIT           https://github.com/ProseMirror/prosemirror
fflate                 MIT           https://github.com/101arrowz/fflate
buffer (feross)        MIT           https://github.com/feross/buffer
@floating-ui/dom       MIT           https://github.com/floating-ui/floating-ui
linkifyjs              MIT           https://github.com/nfrasser/linkifyjs
short-unique-id        MIT           https://github.com/aleicher/short-unique-id

The docs.plus extensions (@docs.plus/extension-hyperlink,
@docs.plus/extension-hypermultimedia, @docs.plus/extension-indent,
@docs.plus/extension-inline-code, @docs.plus/extension-mermaid,
@docs.plus/extension-placeholder) are MIT licensed, copyright 2023-2026
Hossein Marzban; see LICENSE.
`
)

const files = []
const walk = async (dir) => {
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) await walk(full)
    else files.push(full)
  }
}
await walk(distDir)
let total = 0
let largest = { file: '', size: 0 }
for (const file of files) {
  const info = await stat(file)
  total += info.size
  if (info.size > largest.size) largest = { file: path.relative(distDir, file), size: info.size }
}
console.log(`[finalize-dist] ${files.length} files, ${total} bytes total`)
console.log(`[finalize-dist] largest: ${largest.file} (${largest.size} bytes)`)
