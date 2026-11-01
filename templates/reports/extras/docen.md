# Docen

## What the driver runs

`build/score_all.py` measures Docen from `out/docen`. `build/run_all.sh` runs `harness/docen/roundtrip.mts`. This note does not publish a new round-trip percentage for that output.

## What it is

Docen is a browser Office editor. The README says the document model is TipTap and ProseMirror, the painter is LeaferJS, and `@docen/docx` is powered by `@office-open/docx`. Headless Markdown and DOCX conversion goes through one Tiptap JSON model.

## Trivia

The license is MIT, copyright 2025 Demo Macro, the same group as office-open. The README warns that the project is not yet stable and advises against production use. It claims a pagination engine that follows Word's stacking rules: document grid, repeating table headers, and wrap around floats. The live demo is docen.office-open.com.
