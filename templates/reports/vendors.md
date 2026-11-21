# Vendors

One section per tool: what it is, what the benchmark runs, trivia that is not a score, and what the measurements mean for someone choosing an editor. This page does not rank the tools. The benchmark is independent: it is not affiliated with, sponsored by, or endorsed by any of the projects or companies it measures, and their names are their owners' trademarks.

The round-trip driver in `build/score_all.py` measures {{count.participants:w}} tools, and `build/run_all.sh` runs the same set and one more: OnlyOffice (CryptPad build), whose converter did not return from the test document and so wrote nothing to measure. Folio, eigenpal and BetterOffice each have a second headless lane; those lanes are the same tools, not extra vendors. react-docx, OpenDoc, BetterOffice and OnlyOffice joined in v0.11.0. Two more tools have a section and no round-trip lane: Univer, whose open-source packages cannot read a `.docx`, and Nutrient, a viewer that Report C captures. That makes twenty sections in all. `repos/` is a local checkout of upstream trees. This page does not decide which of those trees are part of a published source drop, and it does not relicense any of them.

**How to read the Pros and Cons.** Each bullet rests on a measurement or on a quoted finding, and names its source in parentheses. "Main report" is the round-trip report at the root of this repository. Reports A to E2 are in this folder. "Editors site" is editors.benchmarks.law and "viewers site" is viewers.benchmarks.law: two sister sites, by the same owner, that open the same three sample files in every engine in a real browser. Their figures are from the pass of 2026-11-20 unless a bullet gives another date. "Test document" means the trial's own `fixture/complex.docx`, one deliberately difficult file of 6 pages.

Three limits apply to every bullet. The trial's fidelity figures come from one document, so they describe that document and not every file. The browser timings in Report E2 and on the sister sites were taken on shared cloud machines with no graphics processor, except where a bullet names another machine; they compare engines on such a machine and are not the times on your computer. A tool that a benchmark did not measure has no bullet for it; a missing bullet is not a result.

One finding is true of every tool that keeps a document faithfully, and is written as a bullet on only some of them: no editor in the trial repairs a damaged file. A tool that keeps the document also keeps its defects, and Word then refuses the result (Report B §4).

## Plate.js

Plate is a framework for building rich-text editors on the web. DOCX is one plugin path inside that framework, and the benchmark drives that path, not the whole Plate UI kit. The package name on npm is `platejs`. The license is MIT, copyright Ziad Beyens, Dylan Schiemann, Joe Anderson, and Felix Feng, with a note that an individual package directory may carry its own license. Documentation lives at platejs.org.

### What the benchmark runs

`build/score_all.py` measures Plate.js from `out/plate`. `build/run_all.sh` runs `harness/plate` with Bun. The harness calls Plate's own `importDocx` and `exportDocx` with the loss policy set to `'allow'`, so that an output exists to measure; Plate's default policy refuses the test document.

### Trivia

The project's keywords include `plugin` and `contentEditable`.

### Pros

- It tells you what it could not keep. Importing the test document produced 38 typed messages, one per lost item, and with its default setting it refuses the file instead of saving a damaged copy. No other editor in the trial reported its losses (main report, "What each project actually lost").
- It refused the damaged test document before writing anything, so no broken file was left behind (Report B §4.2).
- It set a named size limit on three of the ten hostile test files and removed the outside links from a fourth (Report D, grade {{bomb.plate.grade:.2f}}).
- Microsoft Word opens the file it saves (Report B, Word {{word.version}}).
- Typing stays quick as the document grows: 25 ms per character at 500 words and 133 ms at 250,000 words (Report E2, typing).

### Cons

- It has the lowest round-trip score in the trial. {{parts.plate.dropped}} of {{parts.plate.total}} parts of the file are gone after saving, among them every header, footer, footnote, comment, the picture and the chart (main report, round trip {{rt.plate.weighted}}%).
- Tracked changes do not survive. Insertions become ordinary text and deleted words are dropped (Report C §3; editors site, redline sample).
- It has no pages. The 6-page test document becomes one continuous scroll on screen, and its saved file is 2 pages in Word (Report C §3.2 and §6.1).
- It is slow on long documents: 64.8 s to open the 500-page sample in the browser, and 26.5 s for a headless open and save of 250,000 words (editors site, 3 of 3 runs; Report E, round trip).

## Docxodus

Docxodus calls itself a structure-aware OOXML engine: read a `.docx`, write it back, and expose it as HTML, markdown, a tracked-changes redline, or an in-browser editor. The same engine is surfaced as a .NET library, a WebAssembly module, an npm package, a Python client, and command-line tools. The license is MIT, copyright Microsoft Corporation and 2025–2026 John Scrudato IV.

### What the benchmark runs

`build/score_all.py` measures Docxodus from `out/docxodus`. `build/run_all.sh` runs `harness/ui/docxodus`, which opens the file in a Docxodus session from the npm package (version {{ver.npm.docxodus}}) and saves it.

### Trivia

The tagline on the README is "Free your .docx files." The Python package name on PyPI is `docx-scalpel`. The NuGet and npm names are Docxodus.

### Pros

- It saved the test document with nothing lost and nothing changed: every check passed and every part of the file came back (main report, round trip {{rt.docxodus.weighted}}%, {{parts.docxodus.kept}} of {{parts.docxodus.total}} parts, {{parts.docxodus.changed}} changed).
- Saving its own output a second time gives the same file, byte for byte (main report, second pass).
- Word opens the saved file and draws it exactly like the original: {{wpx.docxodus.diff_px}} differing pixels over 6 pages (Report C §6.1).
- On screen it lays the test document out on Word's 6 pages, including the landscape page, and shows tracked insertions and deletions and the comment with its text (Report C §3 and §3.2).
- Typing stays quick in a long document: under 17 ms per character up to 5,000 words and 28 ms at 250,000 words (Report E2, typing).

### Cons

- It draws a labelled box in place of two things it cannot draw: "[MATH]" for the equation and "[SMARTART]" for the diagram. The chart has no axis ticks (Report C §3).
- Long documents open slowly in the browser: 46.3 s at 250,000 words, and undoing one character there took 16.6 s (Report E2, opening and undoing).
- It kept six of the ten hostile test files in what it saved (Report D, grade {{bomb.docxodus.grade:.2f}}).
- It does not repair a damaged file. It saved all ten defects of the damaged test document, and Word refused the result (Report B §4).
- It edits one block at a time; typed text is committed when the block loses focus or on Enter (editors site README, "Known limitations").

## SuperDoc

SuperDoc's README calls it the document engine for DOCX files: render and edit in the browser, and use the same Document API for server-side automation and agent workflows. It says edits write back to the XML without an HTML conversion step, and that the engine is built directly on OOXML. The license is AGPL-3.0. The site is superdoc.dev.

### What the benchmark runs

`build/score_all.py` measures SuperDoc from `out/superdoc`. `build/run_all.sh` runs `harness/superdoc.mjs`, which opens and saves the file through the published `@superdoc/sdk` (version {{ver.npm.superdoc_sdk}}, engine {{ver.npm.superdoc_engine}}).

### Trivia

The npm package name of the browser editor is `superdoc`.

### Pros

- It saved the test document with nothing lost: every check passed and every part of the file was kept (main report, round trip {{rt.superdoc.weighted}}%, {{parts.superdoc.kept}} of {{parts.superdoc.total}} parts).
- Saving its own output a second time gives the same file, byte for byte (main report, second pass).
- Word opens the saved file and draws it exactly like the original: {{wpx.superdoc.diff_px}} differing pixels over 6 pages (Report C §6.1).
- On screen it shows the picture, chart, footnotes, comment and tracked changes of the test document, on the same 6 pages as Word (Report C §3 and §3.2).
- In the redline sample it draws insertions, deletions and comments, each with a card in its review rail (editors site, redline sample, seen 2026-11-15).

### Cons

- The license is AGPL-3.0, which the editors site's README calls "a real constraint for a closed product" (editors site README, "Licenses").
- It kept five of the ten hostile test files in what it saved, and named no size limit on any of them (Report D, grade {{bomb.superdoc.grade:.2f}}).
- Typing slows as the document grows: 135 ms per character at 500 words and 553 ms at 250,000 words (Report E2, typing).
- It does not repair a damaged file. It saved all ten defects of the damaged test document, and Word refused the result (Report B §4).
- Its compare-and-apply feature refuses documents with inline images, fields or comments (main report, per-repository findings, citing the project's issue #4012; read in the project, not run by the trial).

## Folio

Folio describes itself as a browser editor and a framework-neutral engine for OOXML `.docx` documents. Callers can embed the React, Vue, or Nuxt editor, or use `folio-core` without that UI. The npm name is `@stll/folio-core`, under the stella project. The license is Apache-2.0.

### What the benchmark runs

`build/score_all.py` measures the Folio model lane from `out/folio`. `build/run_all.sh` also runs an editor lane to `out/folio-editor`.

The model lane parses with `parseDocx` and repacks with `repackDocx`.

The editor lane is the headless prose conversion. It parses, calls `toProseDoc`, calls `fromProseDoc` with `stylesheetSource` set to `{ type: 'package' }`, and repacks. That is the call the project's editor round-trip invariant makes. The browser UI is a separate entry, and this lane did not start it.

### This run

```
[folio:model] wrote 25355 bytes
weighted: 97.5%
features: 97/99
failed-check-ids: tc.moveFrom mx.unknownAttr
```

```
[folio:editor] wrote 25373 bytes
weighted: 95.5%
features: 95/99
failed-check-ids: tc.moveFrom mx.unknownAttr fmt.hyphens text.exact
```

The editor lane fails `tc.moveFrom`, `mx.unknownAttr`, `fmt.hyphens`, and `text.exact`. The model lane fails `tc.moveFrom` and `mx.unknownAttr`. The checks that differ are `fmt.hyphens` and `text.exact`.

### Trivia

The README is published in English, Simplified Chinese, and Brazilian Portuguese.

### Pros

- It kept every part of the test document and every word of its text, and it returned {{parts.folio.passthrough}} of the {{parts.folio.total}} parts exactly as they were (main report, round trip {{rt.folio.weighted}}%; Report A2 §6.2).
- Saving its own output a second time gives the same file, byte for byte (main report, second pass).
- In the redline sample it shows insertions and deletions with change bars, and a card per change and per comment with author and date (editors site, redline sample).
- It lays the 500-page sample out on 500 pages, as Word does, in 14.0 s (editors site, 3 of 3 runs).
- A headless open and save is quick: 52 ms at 500 words and 1.5 s at 250,000 words (Report E, round trip).
- It set a named size limit on three of the ten hostile test files (Report D, grade {{bomb.folio.grade:.2f}}).

### Cons

- Microsoft Word refuses the file it saves from the test document. The cause was isolated: Folio writes the text of a tracked move as deleted text. Correcting that one element makes Word open the file (Report B §3.2).
- On screen it does not draw the chart or the equation of the test document (Report C §3).
- Placing the caret and typing slow down in a long document: 1.9 s for a click and 430 ms per character at 250,000 words (Report E2, clicking and typing).
- It kept three of the ten hostile test files in what it saved: the outside links, the script and the layout bomb (Report D).
- Its document-comparison code was read in the source and was not run by the trial, so its redlining is not measured here (main report, "Rankings" §2).

## GenOffice

GenOffice, from genspark-ai, describes itself as an open-source AI Office suite: Docs, Sheets, Slides, and PDF, plus Markdown and HTML, edited in the native formats with the AI panel in the editor rather than beside it. The license is Apache-2.0. The site is genoffice.ai.

### What the benchmark runs

`build/score_all.py` measures GenOffice from `out/genoffice`. `build/run_all.sh` runs `harness/genoffice.cts` against the genspark-ai tree.

### Trivia

The README opens with a language switcher that lists English and twenty-one translations, from Spanish through Turkish. The project also documents a command-line skill and an MCP server.

### Pros

- It kept every part of the test document and failed one check of {{rt.genoffice.total}} (main report, round trip {{rt.genoffice.weighted}}%).
- Saving its own output a second time gives the same file, byte for byte (main report, second pass).
- Word opens the saved file and draws it almost exactly like the original: {{wpx.genoffice.pct}}% of the page's ink differs (Report C §6.1).
- Opening stays quick in the browser as the document grows: 689 ms at 500 words and 3.2 s at 500,000 words (Report E2, opening).
- On screen it shows the picture, the chart, the comment and both kinds of tracked change, on Word's 6 pages (Report C §3 and §3.2).

### Cons

- It lost text: the words inside two vertically merged table cells are gone after saving (main report, text kept {{rt.genoffice.text_pct}}%).
- It kept seven of the ten hostile test files in what it saved, and set a named size limit on one (Report D, grade {{bomb.genoffice.grade:.2f}}).
- Pasting and undoing slow down in a very long document: 2.8 s to paste and 2.6 s to undo at 250,000 words (Report E2, pasting and undoing).
- It draws a labelled placeholder with the diagram's texts where Word leaves the diagram's band blank (Report C §3).
- It is not on the sister sites. It ships as an Electron desktop application with nothing on npm, so it could not be run there (editors site README, "Not in the bench").

## eigenpal

The eigenpal DOCX editor (docx-editor.dev) is a document engine with React and Vue adapters. The README describes the Editor API as a supported subset of Word Office.js, including automation in a browser or on a server. The repository is Apache-2.0 except where a package says otherwise. `@docx-editor.dev/editor-api`, `@docx-editor.dev/pro`, `@docx-editor.dev/docx-to-pdf`, and `@docx-editor.dev/telemetry` use the EigenPal Pro License. `@docx-editor.dev/fonts` ships open-licensed substitutes for Word fonts. This page does not relicense any package.

### What the benchmark runs

`build/score_all.py` measures the eigenpal store lane from `out/eigenpal`. `build/run_all.sh` also runs an editor lane to `out/eigenpal-editor`.

The store lane calls `readOoxmlPackage` and `writeOoxmlPackage`.

The editor lane calls `DocxEditor.createServer` and then `save()`. `index.ts` does not export a bare `createServer`; the harness imports `DocxEditor` from `packages/editor-api`. That runtime is DOM-free. The browser UI is a separate entry, and this lane did not start it. `editor-api` is under the EigenPal Pro License in the vendored tree. Running the lane does not relicense that package.

### This run

```
[eigenpal:store] wrote 23989 bytes
weighted: 100.0%
features: 99/99
failed-check-ids: 
```

```
[eigenpal:editor] wrote 24635 bytes
weighted: 100.0%
features: 99/99
failed-check-ids: 
```

Both lanes pass every check. The package sizes differ: the store line and the editor line above are the sizes the harness wrote.

**Correction.** An earlier edition reported both lanes failing `text.exact` (98.5%). That failure was the scorer's, not eigenpal's, as eigenpal's team pointed out. The fixture's text box says one thing in its DrawingML branch (`mc:Choice`) and another in its VML branch (`mc:Fallback`). On save, eigenpal rewrites the fallback from the DrawingML content, which Microsoft Word also does. Saved unedited from Word for Mac, the fixture failed the same check. The scorer counted the fallback as visible text, and it counted text-box paragraphs twice. It now reads the visible text once, from `mc:Choice` (arthrod/editors_trial#24). No visible text was ever lost.

### Trivia

On editors.benchmarks.law the tool is listed under its site's name, docx-editor.dev.

### Pros

- It saved the test document with nothing lost, in both of its lanes: every check passed and every part of the file was kept (main report, round trip {{rt.eigenpal.weighted}}%, {{parts.eigenpal.kept}} of {{parts.eigenpal.total}} parts).
- Saving its own output a second time gives the same file, byte for byte (main report, second pass).
- Word opens the saved file and draws it exactly like the original: {{wpx.eigenpal.diff_px}} differing pixels over 6 pages (Report C §6.1).
- It stays quick in the browser as the document grows: opening took 547 ms at 500 words and 3.9 s at 500,000 words, and typing 46 ms and 76 ms per character at 500 and 250,000 words (Report E2, opening and typing).
- A headless open and save is quick: 32 ms at 500 words and 980 ms at 250,000 words (Report E, round trip).
- It set a named size limit on three of the ten hostile test files (Report D, grade {{bomb.eigenpal.grade:.2f}}).

### Cons

- With the open packages alone it does not show deleted words in a redline: the editors site saw the accepted text with inserted words coloured, and the full review view needs the paid `@docx-editor.dev/pro` package (editors site, redline sample). The trial's own screen capture, built from the repository, shows both insertions and deletions (Report C §3).
- The server-side Editor API that the trial's editor lane calls is under the EigenPal Pro License, not Apache-2.0 (this page, "What the benchmark runs").
- On screen it draws the landscape page of the test document as a portrait page, a grey "Unsupported diagram" box for the diagram, and the comment as plain text with no marker (Report C §3 and §3.2).
- It kept three of the ten hostile test files in what it saved: the outside links, the script and the layout bomb (Report D).
- It does not repair a damaged file. It saved all ten defects of the damaged test document, and Word refused the result (Report B §4).

## office-open

office-open, from Demo Macro, describes itself as AI-native Office documents for TypeScript and JavaScript: Word, Excel, PowerPoint, RTF, and OpenDocument, generated, parsed, and patched from JSON or typed APIs, with no Microsoft Office required. It is a library and has no editing screen. The license is MIT, copyright 2026 Demo Macro.

### What the benchmark runs

`build/score_all.py` measures office-open from `out/officeopen`. `build/run_all.sh` runs `harness/officeopen/roundtrip.mts`, which parses the file with the library and generates it again.

### Trivia

The README states a coverage claim of its own, that all 2,273 elements and 1,969 attributes across the 21 OOXML Transitional schemas are implemented for generation and parsing. That sentence is the project's claim, not a measurement from this benchmark. json-to-office uses the library through `@office-open/docx`. The playground is docx.json-to-office.com.

### Pros

- It kept every word of the test document's text and all {{parts.officeopen.total}} parts of the file (main report, text kept {{rt.officeopen.text_pct}}%, round trip {{rt.officeopen.weighted}}%).
- A headless open and save is quick: 34 ms at 500 words and 630 ms at 250,000 words (Report E, round trip).
- Its saved file breaks no rule of the format's schema (Report B, {{xsd.officeopen.real}} schema violations).

### Cons

- Microsoft Word refuses the file it saves from the test document. Five links inside the file point at nothing, and the chart never draws. Rewriting those five links makes Word open it (Report B §3.6; Report A2 §5.4).
- It cannot read its own output back: the second save is not valid XML (main report, second pass {{p2.officeopen.weighted}}%).
- It kept seven of the ten hostile test files in what it saved and ran out of stack on an eighth, the lowest grade in Report D's table, shared with Docen (Report D, grade {{bomb.officeopen.grade:.2f}}).
- It has nothing to show on screen, so no browser measurement applies to it (Report C §2.6; Report E2, Appendix F).

## Docen

Docen is also from Demo Macro, and its DOCX engine is powered by `@office-open/docx`. The README says it is built on TipTap, ProseMirror, and LeaferJS, and that its pagination follows Word's stacking rules, including the document grid, table headers that repeat, and text wrapping around floats. The license is MIT, copyright 2025 Demo Macro. The live demo is docen.office-open.com.

### What the benchmark runs

`build/score_all.py` measures Docen from `out/docen`. `build/run_all.sh` runs `harness/docen/roundtrip.mts`. Headless Markdown and DOCX conversion in Docen goes through one Tiptap JSON model.

### Trivia

The README warns that the project is not yet stable and should not be used in production.

### Pros

- It kept all {{parts.docen.total}} parts of the test document and nearly all of its text (main report, text kept {{rt.docen.text_pct}}%, round trip {{rt.docen.weighted}}%).
- On screen it lays the test document out on Word's 6 pages (Report C §3.2).
- Short files open quickly in the browser: 317 ms for the 3-page rich sample (editors site, 3 of 3 runs).
- A headless open and save is quick: 37 ms at 500 words and 743 ms at 250,000 words (Report E, round trip).

### Cons

- Microsoft Word refuses the file it saves from the test document, for the same five broken links as office-open (Report B §3.6).
- It cannot read its own output back: the second save is not valid XML (main report, second pass {{p2.docen.weighted}}%).
- A long document makes it wait. It opens the 500-page sample and counts Word's 500 pages, but the tab then stops responding for minutes (editors site, measured on a Mac on 2026-11-21, not on the cloud machine). Typing one character at 250,000 words took 7.3 s (Report E2, typing).
- It draws the test document's chart with three coloured series where Word draws one, and shows no comment, equation or embedded object (Report C §2.5 and §3).
- It kept six of the ten hostile test files in what it saved and ran out of stack on two more, the lowest grade in Report D's table, shared with office-open (Report D, grade {{bomb.docen.grade:.2f}}).
- Its own README advises against production use (project README).

## WordCraft

WordCraft is a Rust word processor from the ArtCraft team (getartcraft.com). The README and `Cargo.toml` both say the license is MIT OR Apache-2.0, copyright 2026 ArtCraft Team and the WordCraft contributors. There is no single file named `LICENSE`; the README points at `LICENSE-MIT` and `LICENSE-APACHE`. The ArtCraft name, wordmark, and logos in `docs/brand/` are trademarks and are not covered by that license; the README says forks and modified versions must remove them.

### What the benchmark runs

`build/score_all.py` measures WordCraft from `out/wordcraft`. `build/run_all.sh` runs the Rust harness under `harness/wordcraft`, which round-trips the file through the program's own reader and writer.

### Trivia

English hyphenation comes from Grady Ward's public-domain Moby Hyphenator II word list. The project's asset rule prefers icons drawn in code, in `crates/ui-egui/src/icons.rs`.

### Pros

- Its headless open and save is measured in milliseconds: 1.7 ms for 500 words and 271 ms for 250,000 words, with a peak of 66 MiB of memory at 50,000 words (Report E, round trip and process cost).
- Word opens the file it saves, and draws it close to the original: {{wpx.wordcraft.pct}}% of the page's ink differs, in the chart (Report C §6.1).
- It kept the chart, the diagram, the embedded object, the embedded workbook and the picture of the test document (main report, "What each project actually lost").
- It set a named size limit on three of the ten hostile test files and cleaned three more (Report D, grade {{bomb.wordcraft.grade:.2f}}).
- Opening barely slows in the browser as the document grows: 1.3 s at 500 words and 4.5 s at 500,000 words (Report E2, opening).
- In the redline sample it shows insertions, deletions and comment balloons (editors site, redline sample).

### Cons

- It lost part of the test document's change history: tracked changes to table rows and one of three insertion and deletion pairs. It scored below the LibreOffice baseline (main report, round trip {{rt.wordcraft.weighted}}% against {{rt.lo_baseline.weighted}}%).
- It lost text: the two paragraphs of an embedded HTML chunk are gone after saving (main report, text kept {{rt.wordcraft.text_pct}}%).
- It kept three of the ten hostile test files in what it saved: the decompression bomb, the script and the layout bomb (Report D).
- In a browser it needs WebGPU or WebGL2 and a download of 22 MB compressed (editors site README, "Known limitations").
- The project's own documents rate its `.docx` reading and writing at about 65 percent and call it "Untested on a real-world corpus" (main report, per-repository findings, quoting `docs/file-format-parity.md`).

## Fidus Writer

Fidus Writer is an editor for academic writing. The tree this benchmark measures is `@fiduswriter/document`, the schema, importer, and exporter package, not the whole Fidus Writer application. The license is AGPL-3.0. The README says a sample document can be exported to JATS, HTML, LaTeX, Pandoc JSON, EPUB, DOCX, and ODT.

### What the benchmark runs

`build/score_all.py` measures Fidus Writer from `out/fidus`. `build/run_all.sh` runs `harness/fidus/roundtrip.mts` inside the `@fiduswriter/document` tree. The harness uses the DOCX importer and the DOCX exporter from that package.

### Trivia

DOCX and ODT export accept an uploaded template; the built-in defaults are named Classic (DOCX) and Free (ODT). A browser demo of the package, including a schema viewer, is at fiduswriter.pages.fiduswriter.org.

### Pros

- It has the highest grade on hostile files in the trial: it cleaned seven of the ten and set a named limit on an eighth (Report D, grade {{bomb.fidus.grade:.2f}}).
- It exports to academic publishing formats, JATS, LaTeX and EPUB among them (main report, "Rankings" §4; project README, not run by the trial).
- A headless open and save completed on every test size, from 220 ms at 500 words to 6.7 s at 250,000 words (Report E, round trip).

### Cons

- Its DOCX import has no table handling. Both tables of the test document were gone before saving (main report, "What each project actually lost").
- It kept the least text of any tool measured and dropped {{parts.fidus.dropped}} of {{parts.fidus.total}} parts of the file (main report, text kept {{rt.fidus.text_pct}}%, round trip {{rt.fidus.weighted}}%).
- Microsoft Word refuses the file it saves, which breaks {{xsd.fidus.real}} rules of the format's schema (Report B §3.3).
- On screen the test document shows no table, chart, text box, equation or embedded object, and a "please wait" cover stays over the page (Report C §2.11).
- Tracked changes are not kept: the importer skips insertions, deletions and moves (main report, per-repository findings).
- It is not in the browser speed report or on the sister sites, because it runs only as an application with its own server (Report E2, Appendix F).

## canvas-editor

canvas-editor, by hufe, is a rich-text editor that draws the document on Canvas and SVG. The README says that unlike a `contenteditable` editor it takes over the rendering pipeline so typography does not depend on the browser's editing host. The license is MIT, copyright 2021–present hufe. The npm package is `@hufe921/canvas-editor`. The live demo is hufe.club/canvas-editor.

### What the benchmark runs

`build/score_all.py` lists this tool as canvas-editor plus its plugin, and scores `out/canvas`. `build/run_all.sh` runs the Vitest harness under `harness/canvas`. That harness imports `@hufe921/canvas-editor` and `@hufe921/canvas-editor-plugin-docx`; the plugin is what imports and exports DOCX.

### Trivia

The DOCX plugin is a separate package from the editor, which is why the driver lists the tool as canvas-editor plus its plugin.

### Pros

- Short files open quickly in the browser: 427 ms for the 3-page rich sample and 344 ms for 500 words (editors site, 3 of 3 runs; Report E2, opening).
- Scrolling stays within one screen redraw at every document size tested (Report E2, scrolling).
- Microsoft Word opens the file it saves (Report B).
- It cleaned six of the ten hostile test files (Report D, grade {{bomb.canvas.grade:.2f}}).

### Cons

- It crashes on the test document. A table that combines a vertical merge with a horizontal span stops the import, and only the header and footer are drawn (Report C §2.8; main report).
- It keeps little of a Word file: {{parts.canvas.dropped}} of {{parts.canvas.total}} parts of the test document are gone after saving (main report, round trip {{rt.canvas.weighted}}%).
- It has no model of tracked changes. Its DOCX plugin skips inserted and deleted words alike, so both vanish unless the file is rewritten first (editors site, redline sample, `plugin-docx@1.0.0`).
- Its DOCX export writes lists as plain text and drops hyperlinks (editors site README, "Assessment").
- Long documents overwhelm it. The 500-page sample took 18.4 s and 678 MB of JavaScript memory and came out as 661 pages; typing one character at 250,000 words took 16.5 s; the headless run failed at that size (editors site, confirmed by hand on 2026-11-20; Report E2, typing; Report E, exceptions).
- It hung on three of the ten hostile test files (Report D).

## docs.plus

docs.plus is a real-time collaborative editor. The README's distinguishing feature is that every heading has its own chatroom, and the table of contents shows who is in that room. The license is MIT, copyright 2023–2026 Hossein Marzban. The editor is Tiptap on Next.js, and the runtime is Bun. The site is docs.plus.

### What the benchmark runs

`build/score_all.py` measures docs.plus from `out/docsplus`. `build/run_all.sh` runs `harness/docsplus/roundtrip.ts` with Bun. The DOCX round trip in this benchmark is a headless pass through the project's own import and export functions, not the multi-user site.

### Trivia

An MCP path lets Claude or ChatGPT read documents the account can open and edit documents the account owns.

### Pros

- Microsoft Word opens the file it saves, from the clean test document and from the damaged one (Report B §4.2).
- It cleaned six of the ten hostile test files (Report D, grade {{bomb.docsplus.grade:.2f}}).
- It kept most of the test document's words (main report, text kept {{rt.docsplus.text_pct}}%).
- A headless open and save takes 115 ms at 500 words and 4.1 s at 250,000 words (Report E, round trip).

### Cons

- Tracked changes are destroyed on import, with no warning. Insertions become ordinary text, deletions are dropped, and no author or date survives (main report, per-repository findings).
- It keeps little of a Word file: {{parts.docsplus.dropped}} of {{parts.docsplus.total}} parts of the test document are gone after saving (main report, round trip {{rt.docsplus.weighted}}%).
- Its saved file is 2 pages in Word where the original is 6. Sections, page borders and columns do not survive (Report C §6.1; Report B §3.5).
- On screen it shows the wrong text in the text box, moves footnotes to the end of the document and shows no comment (Report C §3).
- It ran out of stack on one hostile test file and kept another (Report D).
- It is not in the browser speed report or on the sister sites, because it runs only as an application with its own servers (Report E2, Appendix F; editors site README, "Not in the bench").

## Apryse

Apryse WebViewer is a closed-source JavaScript document SDK, and the only commercial, closed-source tool in the round-trip lanes. Its DOCX Editor edits a Word file in the browser with Apryse's own office engine, compiled to WebAssembly, and saves it back as DOCX. The trial measures version {{ver.npm.apryse}} with a trial license key, which stamps a watermark picture into every file it saves. When it starts, the SDK posts its license key, a language code and its version to `pws-collect.pdftron.com`; the document's text and file name are not in that request.

**Who makes it.** Apryse Software Inc., formerly PDFTron, sells document SDKs to software developers — WebViewer, and PDF, Office and CAD SDKs — and the Xodo apps to end users. Its company page names Thoma Bravo and Silversmith Capital Partners as investors ([apryse.com/company](https://apryse.com/company), read 2026-11-01).

**No affiliation.** This benchmark is independent. It is not affiliated with, sponsored by, or endorsed by Apryse, or by any other vendor it measures. Apryse WebViewer was measured from the published npm package with a trial license key; the watermark that key stamps into every saved file is labelled in the results, not removed. Apryse, WebViewer, PDFTron and Xodo are trademarks of their owner.

### What the benchmark runs

`build/score_all.py` measures Apryse WebViewer from `out/apryse`. `build/run_all.sh` runs `harness/apryse`: the published npm package `@pdftron/webviewer@{{ver.npm.apryse}}`, opened with `enableOfficeEditing` (the DOCX Editor) in Chromium, exported with `getFileData({ downloadType: 'office' })`.

### Trivia

The npm scope is still `@pdftron`, the company's former name, and so is the host the SDK calls when it starts. A file it saves names its writer in `docProps/app.xml` as "Apryse DOCX Editor". With a trial key, every saved file carries a watermark picture named `trn_d_stamp`. The installed package is 179 MB.

### Pros

- On screen it draws Word's pages: the test document on 6 pages, with the header, the page numbers, the footnote at the foot of its page and the landscape page where Word puts them (Report C §2.14).
- Word opens the file it saves and draws it almost exactly like the original, stamp included: {{wpx.apryse.pct}}% of the page's ink differs (Report C §6.1).
- It kept every word of the test document's text (main report, text kept {{rt.apryse.text_pct}}%, round trip {{rt.apryse.weighted}}%).
- It shows tracked insertions and deletions in the text (Report C §2.14; editors site, redline sample).

### Cons

- Every figure here is for a stamped file. The trial key writes a watermark into each saved file and onto each page, and {{stamp.apryse.parts}} added parts carry it (main report, "Round-trip scorecard").
- It dropped {{parts.apryse.dropped}} of the {{parts.apryse.total}} parts of the test document; {{stamp.apryse.own}} of its failed checks are its own and not the stamp's (main report, "Round-trip scorecard").
- On hostile files it named no size limit, ran past the time limit on three and kept three (Report D, grade {{bomb.apryse.grade:.2f}}).
- It shows a comment only in a side panel that is closed until opened, with no marker on the page (Report C §2.14).
- It printed "Page 1 of 1" in the footer of the three-page rich sample (editors site README, "Proprietary viewers").
- Its speed is not measured by the trial. It has no headless entry, and its license key is not placed on the measuring machines (Report E, "Not measured"; Report E2, Appendix F).

## LibreOffice

LibreOffice is the baseline: a full office suite, here to give the editor lanes a mature word processor to stand next to. It is not a vendored tree under `repos/`, and it is not a candidate in the trial.

### What the benchmark runs

`build/score_all.py` measures LibreOffice from `out/lo_baseline`. `build/run_all.sh` converts the fixture with `soffice --headless --norestore --convert-to docx`, through the installed LibreOffice binary.

### Trivia

The binary is still named `soffice`, the StarOffice name that OpenOffice and then LibreOffice kept. The history of the name is not a score.

### Pros

- It reproduces Word's page layout of the test document: 6 pages, with header, footer, page numbers, footnote and landscape page in place (Report C, TL;DR and §3.2).
- Word opens the file it saves and draws it close to the original: {{wpx.libreoffice.pct}}% of the page's ink differs (Report C §6.1).
- It kept every word of the test document's text (main report, text kept {{rt.lo_baseline.text_pct}}%).
- It cleaned seven of the ten hostile test files (Report D, grade {{bomb.lo_baseline.grade:.2f}}).

### Cons

- It rewrites the file as its own: {{parts.lo_baseline.dropped}} of the {{parts.lo_baseline.total}} parts of the test document are gone after saving (main report, round trip {{rt.lo_baseline.weighted}}%).
- On screen it hides tracked deletions, so the test document reads as if the changes were accepted, and it shows where the comment is but not its text (Report C §3).
- It hung on one hostile test file, kept another, and on a third it wrote nothing and still reported success (Report D).
- It is a desktop program, not a browser editor, so no browser measurement applies; only its whole conversion is timed, 405 ms at 500 words and 4.6 s at 250,000 words (Report E, "LibreOffice").

## react-docx

react-docx (`@extend-ai/react-docx`) is a DOCX viewer and editor for JavaScript and React. Its README lists pagination, editing, import and export, document review and thumbnails. A Rust parser compiled to WebAssembly reads the file, and the pages are laid out in the DOM. The license is MIT. The source is at github.com/extend-hq/react-docx.

The trial measures `@extend-ai/react-docx@{{ver.npm.reactdocx}}` since v0.11.0.

### What the benchmark runs

`build/score_all.py` measures react-docx from `out/reactdocx`. `build/run_all.sh` runs `harness/reactdocx`: the published npm package `@extend-ai/react-docx@{{ver.npm.reactdocx}}`, opened in Chromium through its `/vanilla` entry and saved with the package's own export, which exists only in a browser. Report C captures the same package on screen. The sister sites run the same version, served from their own origin because the package starts a Worker from its own files.

### Trivia

The package ships with its review marks and review cards hidden; a page that wants them has to turn them on.

### Pros

- It lays the 500-page sample out on 500 pages, as Word does, in 8.70 s (editors site, 3 of 3 runs).
- Once its review marks are turned on, it shows insertions underlined and a margin card per deletion and per comment with author, date and Accept and Reject (editors site, redline sample, seen 2026-11-18).
- It reads and writes `.docx` itself, and it passed all ten checks and every hard case of the editors site's formatting probe (editors site README, probes of 2026-11-20).
- Word opens the file it saves, and it kept all {{parts.reactdocx.total}} parts of the test document (main report, round trip {{rt.reactdocx.weighted}}%).
- Saving its own output a second time gives the same bytes (main report, second pass).
- On screen it lays the test document out on 6 pages, as Word does, with the table, the picture and the chart drawn (Report C §2.15).

### Cons

- It has no command that replaces a whole document inside its own undo history, so an assistant edit there opens a new document and cannot be undone (editors site README, "How fairness to each vendor is decided").
- It runs only in a browser: it breaks pages by measuring text on screen, so it cannot render on a server (viewers site README, "No server route, and why"; read from the package, not run).
- It lost {{rt.reactdocx.text_lost}} of the test document's {{rt.reactdocx.text_tokens}} pieces of text and failed {{rt.reactdocx.failed}} of {{rt.reactdocx.total}} checks (main report, text kept {{rt.reactdocx.text_pct}}%).
- On hostile files it named no size limit, kept the weapon in five of the ten and ran past the time limit on one (Report D, grade {{bomb.reactdocx.grade:.2f}}).
- It does not repair a damaged file: Word refuses what it saves from the broken test document (Report B §4).
- Its speed is not measured by the trial: it has no entry that runs without a browser (Report E, "Not measured").

## Univer

Univer is an open-source office SDK for spreadsheets and documents that draws on a canvas. The open-source core is Apache-2.0. Its open-source packages cannot read or write `.docx`: the editors site's README places that import and export in Univer's separately licensed Server SDK. The source is at github.com/dream-num/univer and the site is univer.ai.

Univer has no round-trip lane in the trial: a probe of its {{probe.univer.packages}} installed open-source packages found no `.docx` reader or writer (`harness/univer/probe.mjs`, since v0.11.0).

### What the benchmark runs

`build/run_all.sh` runs `harness/univer/probe.mjs` over `@univerjs/presets@{{ver.npm.univer}}` with `preset-docs-core`. The probe looks in every installed package for a zip library, a WordprocessingML part name or namespace, and a `.docx` import or export call. It found none, so there is no document to round-trip. The sister sites run the same version. Because the package has no `.docx` reader, the site's own reader hands it the text and headings of each sample. What Univer shows there is not its reading of the file.

### Trivia

Its documents preset has no read-only switch, so on the viewers site it stays editable.

### Pros

- It started and showed the text it was given in every run, 3 of 3 on each of the three samples (editors site).
- It keeps paragraphs, headings, bold, italic and typed list markers of the text it is given (editors site README, "Known limitations").
- Its empty page loads quickly in Google's page test: performance 93 on desktop and 85 on mobile (editors site README, Lighthouse, measured 2026-11-20).

### Cons

- It is not a `.docx` editor as published in open source: it cannot open or export a Word file without its Server SDK (editors site README, "The editors").
- Tracked changes are not drawn, and tables, pictures, fonts and page set-up do not carry over (editors site, redline sample; "Assessment").
- The text of the 500-page sample alone took 29.3 s and 880 MB of JavaScript memory after a clean-up. The README notes this is what Univer does with that text, not a `.docx` figure (editors site, 3 of 3 runs).
- The trial has no round-trip, Word, rendering or hostile-file result for it, because there is no `.docx` path to run: the probe of its {{probe.univer.packages}} packages found none (main report, the Univer probe).

## OpenDoc

OpenDoc, from Casual Office, describes itself as an Apache-2.0, embeddable, local-first editor for Word documents with a Rust engine underneath. The engine is compiled to WebAssembly and draws on a canvas. The project is pre-release. The source is at github.com/CasualOffice/opendoc.

The trial measures OpenDoc's engine at commit `{{ver.opendoc.commit}}` ({{ver.opendoc.date}}) since v0.11.0.

### What the benchmark runs

`build/score_all.py` measures OpenDoc from `out/opendoc`. `build/run_all.sh` runs `harness/opendoc`: a small Rust program built against the engine crate of the pinned checkout (`repos/opendoc/crates/opendoc`), which reads the file and writes it back. Report C captures the project's editor application at the same commit. The sister sites run the project's whole editor application, a snapshot of 2026-11-05 (commit `5ac261c`), in a frame on their own origin. They open a file through the application's own file input and catch its export on the way to the download.

### Trivia

The application is published as a website; its npm package is only a frame mount.

### Pros

- It lays the 500-page sample out on 500 pages, as Word does. It loaded in 3.54 s and settled at 7.01 s (editors site, 3 of 3 runs).
- In the redline sample it shows insertions and deletions in the text, and a card per change and per comment with author, date and Accept and Reject (editors site, redline sample, seen 2026-11-18).
- It reads and writes `.docx` itself, and it passed all ten checks and every hard case of the editors site's formatting probe (editors site README, probes of 2026-11-20).
- Its viewer package draws pages on a server: 204 ms for the rich sample and 1.57 s for the 500-page sample (viewers site, server render, 3 runs each, 2026-11-21).
- It kept every part of the test document and all but {{rt.opendoc.text_lost}} of its {{rt.opendoc.text_tokens}} pieces of text, and saving its own output a second time gives the same bytes (main report, round trip {{rt.opendoc.weighted}}%, second pass).
- On screen it draws the test document on 6 pages, as Word does, with the chart, the footnote and the deleted table row marked (Report C §2.16).

### Cons

- Its server render draws a redline as the accepted text, with no marks. That package is an older build than the application, which shows them (viewers site, server render, `@casualoffice/opendoc-viewer@0.1.0-alpha.1`).
- It is hard to embed today. It opens files only from its own file input and exports only by download, and a newer snapshot can break a page that drives it (editors site README, "Known limitations").
- It is a pre-release, measured from a dated snapshot and not from a released version (editors site README, "The editors").
- Word refuses the file it saves from the test document, and the schema check finds {{xsd.opendoc.real}} violations in it (main report, Word verdicts; Report B §3).
- On hostile files it named no size limit and kept the weapon in three of the ten (Report D, grade {{bomb.opendoc.grade:.2f}}).
- Its speed is not measured by the trial: timing it needs the cloud machines, which this release did not use (Report E, "Not measured").

## BetterOffice

BetterOffice, from the OpenOOXML Project, describes itself as Rust-native OOXML engines with collaboration and agent editing at the core, compiled to WebAssembly for browsers. Its DOCX editor runs the engines in a Worker, draws pages on a canvas and has a React interface. The license is Apache-2.0. The source is at github.com/openooxml/betteroffice and the site is betteroffice.dev.

The trial measures `@betteroffice/docx@{{ver.npm.betteroffice}}` since v0.11.0, through two lanes: its document model and an editor session.

### What the benchmark runs

`build/score_all.py` measures BetterOffice from `out/betteroffice` (the document model: parse, then save) and from `out/betteroffice-editor` (an editor session opened on the file, then saved). Both run in Node from `harness/betteroffice`, with no browser. Report C captures `@betteroffice/docx-react` on screen. The sister sites run `@betteroffice/docx-react@0.5.1` with `@betteroffice/docx@0.5.1` and `@betteroffice/fonts@0.4.2`, served from their own origin because the package starts a Worker from its own files.

### Trivia

The React package imports its core by 30 subpaths, each of which a page without a bundler has to name.

### Pros

- It lays the 500-page sample out on 500 pages, as Word does, in 8.05 s (editors site, 3 of 3 runs).
- In the redline sample it shows deletions struck and insertions underlined, and a card per change and per comment with author, date and accept and reject (editors site, redline sample, seen 2026-11-18).
- It reads and writes `.docx` itself, and it passed all ten checks and every hard case of the editors site's formatting probe (editors site README, probes of 2026-11-20).
- Through an editor session it gave the test document back whole: every check passed, every part was kept, and Word opens the file (main report, editor lane {{rt.betteroffice-editor.weighted}}%).
- It also draws pages on a server, with its own layout and painter: 275 ms for the rich sample and 3.97 s for the 500-page sample, and the redline keeps its marks (viewers site, server render, 3 runs each, 2026-11-21).

### Cons

- Its editing call takes plain-text steps and refuses a full replacement, so an assistant edit there opens a new document and clears the undo history (editors site README, "Assessment").
- On a server its engine's memory reached about 0.5 GB on the 500-page sample and was not given back afterwards (viewers site, server render; measured locally by the route's author on a loaded machine).
- Through its document model the result is weaker: {{rt.betteroffice.failed}} of {{rt.betteroffice.total}} checks failed, and Word refuses that file (main report, model lane {{rt.betteroffice.weighted}}%).
- Its save returns a list of warnings, and for the test document the list was empty although checks failed (main report, harness log of the model lane).
- On hostile files it named no size limit and kept the weapon in three of the ten; in the editor lane the process aborted on one (Report D, grade {{bomb.betteroffice.grade:.2f}}).
- Its speed is not measured by the trial: timing it needs the cloud machines, which this release did not use (Report E, "Not measured").

## OnlyOffice (CryptPad build)

This is the OnlyOffice document editor as CryptPad builds it: the editor's JavaScript draws on a canvas, and OnlyOffice's converter runs in the browser as WebAssembly, so no document server is needed. OnlyOffice is developed by Ascensio System SIA; the browser-only build is the CryptPad project's. The license is AGPL-3.0. The sources are github.com/cryptpad/onlyoffice-editor and github.com/cryptpad/onlyoffice-x2t-wasm.

This benchmark is not affiliated with, sponsored by, or endorsed by OnlyOffice or CryptPad. The build is run unmodified from CryptPad's release archives, and what is measured is that build, not OnlyOffice's own Document Server.

The trial runs this build since v0.11.0, and it has no round-trip result: its converter did not return from the test document.

### What the benchmark runs

`build/run_all.sh` runs `harness/onlyoffice`: CryptPad's `onlyoffice-x2t-wasm` {{ver.release.onlyoffice_x2t.tag}}, the converter alone, in Node. It did not return from the test document within {{rt.onlyoffice.outcome_limit_s}} s, in both runs, so there is no output to score and no row in the scored tables. Report C runs the editor with that converter in Chromium. The sister sites run `cryptpad/onlyoffice-editor` v9.3.2+3 with `cryptpad/onlyoffice-x2t-wasm` v9.3.2+3, read out of their release archives and shown as the vendor's whole application in a frame.

### Trivia

The editor is distributed as one archive of 608 MB. One header icon is missing from that archive and answers 404.

### Pros

- It lays the 500-page sample out on 500 pages, as Word does (editors site, 2 of 3 runs; the third was cut by the site, not the editor).
- In the redline sample it shows deletions struck and insertions underlined in each author's colour, with its own review and comment panels (editors site, redline sample, seen 2026-11-18).
- It reads and writes `.docx` itself, and it passed all ten checks and every hard case of the editors site's formatting probe (editors site README, probes of 2026-11-20).
- It runs wholly in the browser, with no document server to operate (editors site README, "The editors").
- On eight of the ten hostile files it wrote a file without the weapon in it (Report D, grade {{bomb.onlyoffice.grade:.2f}}).

### Cons

- The license is AGPL-3.0, which the editors site's README calls "a real constraint for a closed product" (editors site README, "Licenses").
- It is heavy on a short file: 3.06 s and 50 MB of JavaScript memory to open the 3-page rich sample, and an 18 MB download (editors site, 3 of 3 runs; viewers site, redline sample).
- It says a long document is ready before it has finished counting pages: on the 500-page sample the count went on rising to 500 after "ready" (editors site README, "Figures to distrust", watched by hand on 2026-11-20).
- It cannot draw pages on a server in this build: the converter is compiled without its renderer (viewers site README, "No server route, and why").
- It did not open the trial's test document. Its converter did not return while the embedded document (`w:altChunk`) was in the file; with that removed the editor reported an error at the SmartArt; with both removed it showed 6 pages (Report C §2.18; main report).

## Nutrient

Nutrient Web SDK is a commercial, closed-source document SDK. It is a viewer here, not an editor: in the browser a .NET engine compiled to WebAssembly turns the `.docx` into a PDF, and the SDK shows that PDF. It has no editing and no DOCX export on the sister sites. It runs there without a key, in trial mode, which draws a "For Evaluation Purposes Only" watermark.

**Who makes it.** Nutrient, formerly PSPDFKit, sells document SDKs to software developers. Its site says "PSPDFKit is now Nutrient" ([nutrient.io](https://www.nutrient.io/), read 2026-11-21).

**No affiliation.** This benchmark is independent. It is not affiliated with, sponsored by, or endorsed by Nutrient, or by any other vendor it measures. Nutrient Web SDK was run from Nutrient's own CDN in its trial mode; the watermark that mode draws is left in what is shown, not removed. Nutrient and PSPDFKit are trademarks of their owner.

Nutrient is in the trial's rendering report (Report C) since v0.11.0, and in no other: it is a viewer, so there is no saved file to round-trip.

### What the benchmark runs

Report C captures `nutrient-viewer` 1.25.0 from Nutrient's CDN in Chromium, with no key (`harness/ui/nutrient`). The sister sites run the same version, view-only.

### Trivia

The SDK's error messages and its CDN host still carry the former name, PSPDFKit.

### Pros

- It opens a file in the browser, with no server and no key for evaluation (editors site README, "Proprietary viewers").
- It rendered every run of the redline and 500-page samples on the viewers site: 7.12 s and 20.7 s (viewers site, 3 of 3 runs each).
- It converts the file to a PDF inside the browser and shows that PDF, so the reader sees fixed pages (editors site README, "Proprietary viewers").

### Cons

- It is view-only: no editing, and no export of the document as `.docx` (editors site README, "Proprietary viewers").
- It shows a redline as the accepted text, with no marks for insertions, deletions or comments (editors site, redline sample).
- It substitutes fonts: in the rich sample inline code is not monospace and the title wraps (editors site README, "Proprietary viewers").
- It is a very large download and slow to start: 105 MB loaded, of which one file is 68 MB, and 15 to 28 s on desktop Chrome (editors site README, measured 2026-11-09); 20.8 s for the 500-page sample (editors site, 2 of 3 runs).
- It lays the test document out on 7 pages where Word has 6, and draws the chart without its axis and category labels and the Hebrew line without its Hebrew letters (Report C §2.19).
