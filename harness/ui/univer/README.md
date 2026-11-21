# Univer: no host

Univer's document editor (`@univerjs/presets` + `@univerjs/preset-docs-core`,
1.5.2, Apache-2.0) is not hosted for Report C because its open-source packages
cannot open a `.docx`. This folder only pins those packages, so the claim can be
checked against their bytes (`pnpm install`, then the commands below).

Evidence, read on 2026-11-21 against the pinned 1.5.2 (16 `@univerjs/*`
packages installed by the two above):

- No reader: none of the 16 packages' builds mentions `word/document.xml`, and
  none contains or depends on a zip library (`jszip`, `fflate`):
  `grep -rlE "word/document\.xml|jszip|fflate" node_modules/.pnpm/@univerjs+*/node_modules/@univerjs/*/lib/es`
  prints nothing.
- The one mention of the Word MIME type is a table in `@univerjs/drawing` that
  maps a file's MIME type to a unit type; it reads no file.
- No import call: `importDocToSnapshotAsync` / `importDocToUnitIdAsync`, the
  calls Univer documents for `.docx`, are in none of the 16 packages.
- Univer's own documentation puts `.docx` import and export in
  `@univerjs-pro/exchange-client` and `@univerjs-pro/docs-exchange-client`
  (https://docs.univer.ai/guides/docs/features/import-export), which are not
  open source and talk to Univer's server.

What the open-source editor does take is its own document model
(`univerAPI.createDocument(data)`). The sister site (editors.benchmarks.law)
reads a `.docx` with a reader of its own and hands Univer the text; that shows
the site's reader, not how Univer renders a `.docx`, so it is not captured here.
