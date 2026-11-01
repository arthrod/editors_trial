# Vendors

What each measured tool is, and trivia that is not a score. Lane results for Folio and eigenpal are in `extras/`. This page does not rank the tools.

The round-trip driver in `build/score_all.py` measures fourteen tools. `build/run_all.sh` runs the same set. Folio and eigenpal each have a second headless lane; those lanes are the same tools, not extra vendors. `repos/` is a local checkout of upstream trees. This page does not decide which of those trees are part of a published source drop, and it does not relicense any of them.

## Plate.js

Plate is a framework for building rich-text editors on the web. The package name on npm is `platejs`. The license is MIT, copyright Ziad Beyens, Dylan Schiemann, Joe Anderson, and Felix Feng, with a note that an individual package directory may carry its own license. The project's own keywords describe it as a plugin framework, and DOCX is one plugin path. The harness that this benchmark runs is `harness/plate`. Documentation lives at platejs.org.

## Docxodus

Docxodus calls itself a structure-aware OOXML engine: read a `.docx`, write it back, and expose it as HTML, markdown, a tracked-changes redline, or an in-browser editor. The tagline on the README is "Free your .docx files." The same engine is surfaced as a .NET library, a WebAssembly module, an npm package, a Python client, and command-line tools. The license is MIT, copyright Microsoft Corporation and 2025–2026 John Scrudato IV. The Python package name on PyPI is `docx-scalpel`. The NuGet and npm names are Docxodus. This benchmark drives it through `harness/ui/docxodus`.

## SuperDoc

SuperDoc's README calls it the document engine for DOCX files: render and edit in the browser, and use the same Document API for server-side automation and agent workflows. It says edits write back to the XML without an HTML conversion step, and that the engine is built directly on OOXML. The license is AGPL-3.0. The site is superdoc.dev.

## Folio

Folio describes itself as a browser editor and a framework-neutral engine for OOXML `.docx` documents. Callers can embed the React, Vue, or Nuxt editor, or use `folio-core` without that UI. The npm name is `@stll/folio-core`, under the stella project. The license is Apache-2.0. The README is published in English, Simplified Chinese, and Brazilian Portuguese. The headless prose lane in this benchmark is `toProseDoc` then `fromProseDoc`, which is not the browser UI. See `extras/folio.md`.

## GenOffice

GenOffice, from genspark-ai, describes itself as an open-source AI Office suite: Docs, Sheets, Slides, and PDF, plus Markdown and HTML, with the AI panel in the editor rather than beside it. The license is Apache-2.0. The README opens with a language switcher that lists English and twenty-one translations, from Spanish through Turkish. It also ships a command-line skill and an MCP server.

## eigenpal

The eigenpal DOCX editor (docx-editor.dev) is a document engine with React and Vue adapters. The README describes the Editor API as a supported subset of Word Office.js, including automation in a browser or on a server. The repository is Apache-2.0 except where a package says otherwise. `@docx-editor.dev/editor-api`, `@docx-editor.dev/pro`, `@docx-editor.dev/docx-to-pdf`, and `@docx-editor.dev/telemetry` use the EigenPal Pro License. `@docx-editor.dev/fonts` is open-licensed substitutes for Word fonts. This benchmark's editor lane calls `DocxEditor.createServer` from `editor-api`, which is one of the Pro-licensed packages, and that call is a DOM-free runtime rather than the browser UI. See `extras/eigenpal.md`. This page does not relicense that package.

## office-open

office-open, from Demo Macro, describes itself as AI-native Office documents for TypeScript and JavaScript: Word, Excel, PowerPoint, RTF, and OpenDocument, generated, parsed, and patched from JSON or typed APIs, with no Microsoft Office required. The license is MIT, copyright 2026 Demo Macro. The README states a coverage claim of its own, that all 2,273 elements and 1,969 attributes across the 21 OOXML Transitional schemas are implemented for generation and parsing. That sentence is the project's claim, not a measurement from this benchmark. json-to-office uses it through `@office-open/docx`. The playground is docx.json-to-office.com.

## Docen

Docen is also from Demo Macro, and its DOCX engine is powered by `@office-open/docx`. The README says it is built on TipTap, ProseMirror, and LeaferJS, and that its pagination follows Word's stacking rules, including the document grid, table headers that repeat, and text wrapping around floats. It warns that the project is not yet stable and should not be used in production. The license is MIT, copyright 2025 Demo Macro. The live demo is docen.office-open.com.

## WordCraft

WordCraft is a Rust word processor from the ArtCraft team (getartcraft.com). The README and `Cargo.toml` both say the license is MIT OR Apache-2.0, copyright 2026 ArtCraft Team and the WordCraft contributors. There is no single file named `LICENSE`; the README points at `LICENSE-MIT` and `LICENSE-APACHE`. The ArtCraft name, wordmark, and logos in `docs/brand/` are trademarks and are not covered by that license; the README says forks and modified versions must remove them. English hyphenation comes from Grady Ward's public-domain Moby Hyphenator II word list. The project's asset rule prefers icons drawn in code, in `crates/ui-egui/src/icons.rs`.

## Fidus Writer

The tree this benchmark measures is `@fiduswriter/document`, the schema, importer, and exporter package, not the whole Fidus Writer application. The license is AGPL-3.0. The README says a sample document can be exported to JATS, HTML, LaTeX, Pandoc JSON, EPUB, DOCX, and ODT, and that DOCX and ODT can take a custom template, with built-in templates named Classic and Free. The browser demo is fiduswriter.pages.fiduswriter.org.

## canvas-editor

canvas-editor, by hufe, is a Canvas/SVG rich-text editor. The README says that unlike a `contenteditable` editor it takes over the rendering pipeline so typography does not depend on the browser's editing host. The license is MIT, copyright 2021–present hufe. The npm package is `@hufe921/canvas-editor`. The harness imports that package and `@hufe921/canvas-editor-plugin-docx`, which is why the driver lists the tool as canvas-editor plus its plugin. The live demo is hufe.club/canvas-editor.

## docs.plus

docs.plus is a real-time collaborative editor. The README's distinguishing feature is that every heading has its own chatroom, and the table of contents shows who is in that room. The license is MIT, copyright 2023–2026 Hossein Marzban. The runtime is Bun. The editor is Tiptap on Next.js. An MCP path lets Claude or ChatGPT read documents the account can open and edit documents the account owns. The site is docs.plus.

## Apryse

Apryse WebViewer is a closed-source JavaScript document SDK, and the only commercial, closed-source tool in the round-trip lanes. Its DOCX Editor edits a Word file in the browser with Apryse's own office engine, compiled to WebAssembly, and saves it back as DOCX. The npm package keeps the company's former name, `@pdftron/webviewer`. The trial measures version {{ver.npm.apryse}} with a trial license key, which stamps a watermark picture into every file it saves. When it starts, the SDK posts its license key, a language code and its version to `pws-collect.pdftron.com`; the document's text and file name are not in that request. This benchmark drives it through `harness/apryse`.

## LibreOffice

LibreOffice is the baseline, and it is not a vendored tree under `repos/`. The driver converts the fixture with `soffice --headless --norestore --convert-to docx`. The binary is still named `soffice`, the StarOffice name that OpenOffice and then LibreOffice kept. This page does not invent a score for that history.
