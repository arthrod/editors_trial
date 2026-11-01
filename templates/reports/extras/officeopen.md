# office-open

## What the driver runs

`build/score_all.py` measures office-open from `out/officeopen`. `build/run_all.sh` runs `harness/officeopen/roundtrip.mts`. This note does not publish a new round-trip percentage for that output.

## What it is

office-open is a TypeScript library for Office documents: generate, parse, and patch Word, Excel, PowerPoint, RTF, and OpenDocument from JSON or typed APIs. The README says Microsoft Office is not required to produce the files.

## Trivia

The license is MIT, copyright 2026 Demo Macro. The README's own coverage sentence says all 2,273 elements and 1,969 attributes across the 21 OOXML Transitional schemas are implemented for generation and parsing. That is the project's claim, not a figure from this benchmark. json-to-office uses the library through `@office-open/docx`. The playground is docx.json-to-office.com.
