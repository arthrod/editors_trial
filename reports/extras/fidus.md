# Fidus Writer

## What the driver runs

`build/score_all.py` measures Fidus Writer from `out/fidus`. `build/run_all.sh` runs `harness/fidus/roundtrip.mts` inside the `@fiduswriter/document` tree, not inside the full Fidus Writer application. This note does not publish a new round-trip percentage for that output.

## What it is

`@fiduswriter/document` is the document schema plus importers and exporters. The harness uses the DOCX importer and the DOCX exporter from that package.

## Trivia

The license is AGPL-3.0. The README lists export targets of JATS, HTML, LaTeX, Pandoc JSON, EPUB, DOCX, and ODT. DOCX and ODT accept an uploaded template; the built-in defaults are named Classic (DOCX) and Free (ODT). A browser demo of the package, including a schema viewer, is at fiduswriter.pages.fiduswriter.org.
