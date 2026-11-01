# Changelog

Every release of the editors trial is a measurement: the editor commits it
pins, the fixture it feeds them, the scorer that reads their output, and the
reports written from that output. A release never changes a figure without
re-running the measurement behind it. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/) with the trial still pre-1.0.

## [0.9.0] - 2026-11-01

The first tagged release: the edition published on benchmarks.law on
2026-11-01, after the correction of that day.

### Measured

- Thirteen participants on `fixture/complex.docx` (35 package parts, 31
  critical exception cases): Plate.js, Docxodus, SuperDoc, Folio (model and
  editor lanes), GenOffice, eigenpal (store and editor lanes), office-open,
  Docen, WordCraft, Fidus Writer, canvas-editor and docs.plus, with LibreOffice
  as the baseline.
- Each editor driven through its own import and export entry point, at the
  commits pinned in the main report (`08b1571f2` Plate, `f52c959b2` SuperDoc
  with `@superdoc/sdk` 2.25.0-next.14, `docxodus` 14.2.0, and so on).
- A 99-check scorer; a second pass that feeds each editor its own output; a
  LibreOffice re-open; Microsoft Word 16.115 opening every output.
- Ten hostile packages run in a sandbox against every editor (Report D), the
  same packages read by Jubarte 0.14.0 (Report D1) and by Word (Report D2).

### Results

- SuperDoc, Docxodus and eigenpal tie for first; Folio is fifth at 97.5%;
  Plate.js is last at 20.6%.

### Corrected (2026-11-01)

- The scorer no longer fails equivalent rewrites that Word itself makes
  (`text.exact` and two field and part checks); eigenpal was rescored
  (#24).
- Every report counts 99 checks, not 97, and quotes the rescored figures
  (Folio 97.5%, Plate.js 20.6%, WordCraft 84.9%).
- Report C: 83 differing pixels are 0.005% of the corpus's ink, not 0.0006%.
- The "only" claims and stale statuses that the reports' own tables
  contradicted were corrected; Report E became Reports D1 and D2.

### Added

- `build/make_demo_docs.py`: one sanitized copy of the fixture per editor
  for the live demos on benchmarks.law (#19, #23), and the demo build
  recipes under `demos/` (#20).
- The release gate `build/verify_publication.sh`: repository claims, DOCX
  twin parity, the findings ledger, the number gate, ECMA-376 schema
  validation, the claim-evidence matrix and, with `--with-word`, Word.
- The per-tool notes filed as issues on each project's repository
  (`outreach/`).

[0.9.0]: https://github.com/arthrod/editors_trial/releases/tag/v0.9.0
