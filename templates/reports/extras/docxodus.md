# Docxodus

## What the driver runs

`build/score_all.py` measures Docxodus from `out/docxodus`. `build/run_all.sh` runs `harness/ui/docxodus`. This note does not publish a new round-trip percentage for that output.

## What it is

Docxodus is one OOXML engine with several faces: a .NET library, a WebAssembly module in the browser, an npm package, a Python client, and command-line tools. The README describes HTML render, markdown projection, tracked-changes redline, and an in-browser editor as views over that engine.

## Trivia

The README tagline is "Free your .docx files." The license is MIT, copyright Microsoft Corporation and 2025–2026 John Scrudato IV. The Python distribution name on PyPI is `docx-scalpel`. NuGet and npm use the Docxodus name.
