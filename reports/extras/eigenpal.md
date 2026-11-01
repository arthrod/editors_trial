# eigenpal

## What the driver runs

`build/score_all.py` measures the eigenpal store lane from `out/eigenpal`. `build/run_all.sh` also runs an editor lane to `out/eigenpal-editor`.

The store lane calls `readOoxmlPackage` and `writeOoxmlPackage`.

The editor lane calls `DocxEditor.createServer` and then `save()`. `index.ts` does not export a bare `createServer`; the harness imports `DocxEditor` from `packages/editor-api`. That runtime is DOM-free. The browser UI is a separate entry, and this lane did not start it. `editor-api` is under the EigenPal Pro License in the vendored tree. Running the lane does not relicense that package.

## This run

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

## Trivia

The project site is docx-editor.dev. The README describes the Editor API as a supported subset of Word Office.js, with React and Vue adapters over the same engine. The repository is Apache-2.0 except the packages that say otherwise. `@docx-editor.dev/editor-api`, `@docx-editor.dev/pro`, `@docx-editor.dev/docx-to-pdf`, and `@docx-editor.dev/telemetry` use the EigenPal Pro License. `@docx-editor.dev/fonts` ships open-licensed substitutes for Word fonts.
