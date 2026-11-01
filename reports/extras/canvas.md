# canvas-editor

## What the driver runs

`build/score_all.py` lists this tool as canvas-editor plus its plugin, and scores `out/canvas`. `build/run_all.sh` runs the Vitest harness under `harness/canvas`. That harness imports `@hufe921/canvas-editor` and `@hufe921/canvas-editor-plugin-docx`. This note does not publish a new round-trip percentage for that output.

## What it is

canvas-editor draws the document on Canvas and SVG. The DOCX plugin is what the harness uses to import and export.

## Trivia

The license is MIT, copyright 2021–present hufe. The README says the editor takes over the rendering pipeline, unlike a `contenteditable` editor, so typography is not left to the browser's editing host. The live demo is hufe.club/canvas-editor.
