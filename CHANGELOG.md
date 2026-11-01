# Changelog

Every release of the editors trial is a measurement: the editor commits it
pins, the fixture it feeds them, the scorer that reads their output, and the
reports written from that output. A release never changes a figure without
re-running the measurement behind it. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/) with the trial still pre-1.0.

## [0.9.1] - 2026-11-01

Every editor moved to its current upstream and the whole trial re-run, with
every report now generated from the measurement.

### Updated

- Checkouts fast-forwarded with `build/update_editors.sh`: Plate.js
  `60c7f5530` (`next`), eigenpal `3425d4d7a`, Folio `958c582cb`, GenOffice
  `36a509e8f`, SuperDoc `0ee03fd3c`, canvas-editor `1865c9b06`, WordCraft
  `a88e00525`, Docxodus `583a11c7f`. Docen, office-open, docs.plus and the
  Fidus Writer repositories had no new commits.
- `@superdoc/sdk` 2.25.0-next.14 → 2.26.0-next.16 (the `next` channel the
  trial has always measured), now pinned in its own `harness/superdoc-sdk/`;
  `docxodus` and `@docxodus/export` 14.2.0 → 15.0.0.
- The main report's pin table gains a "Measured at" column. The `[CODE]`
  file:line citations still refer to the commits the code was read at.

### Measured

- Round trip, second pass, LibreOffice re-open and the eigenpal and Folio
  editor lanes: **no score changed.** Every output keeps the same parts,
  in the same state, as in 0.9.0; only volatile content differs (the
  `core.xml` timestamps, generated media names) and a few byte sizes.
- Microsoft Word 16.115 opens the same outputs and refuses the same five
  (Folio, Folio's editor lane, office-open, Docen, Fidus Writer).
- Hostile packages (Report D), re-run on a quiet machine, every changed
  cell reproduced twice:
  - Docxodus 15.0.0 now names ceilings on the decompression bomb
    (`compression_ratio_limit_exceeded`) and the deep nest
    (`xml_depth_limit_exceeded`, 128 levels), where 14.2.0 kept the bomb and
    ran out of stack. It now keeps the corrupt parts it used to refuse. Its
    grade goes from 0.20 to 0.34, above SuperDoc.
  - Plate does not finish the attribute package inside the 30-second CPU
    budget (0.70 → 0.62, now below Google Docs). This is not attributable to
    Plate's update: the 0.9.0 commit, re-run with the same lockfile on the
    same quiet machine, does not finish either. The cell sits at the edge of
    the budget.
  - Every other cell is unchanged. docs.plus B9 and canvas-editor B4 failed
    only while another 12-worker job saturated the machine, and measured as
    in 0.9.0 when re-run. No other cell's output reached the 64 KB pipe
    limit below, so no other cell lost its message.
- Star counts re-fetched on 2026-11-01.

### Not re-measured

- Report C's screenshots and Word pixel renders (dated 2026-10-30): the
  outputs they render are part-identical, but Docxodus moved a major version
  and its rendering was not re-captured.
- Report A's namespace matrix, and the Google Docs and Jubarte rows.
- The live demos on benchmarks.law are still built at the 0.9.0 commits.

### Added

- Generated reports (#28): every report is rendered from `templates/` and
  `out/facts.json` by `build/render_reports.py`; `build/facts.py` builds the
  facts from the scores, part maps, pins, star snapshot (`build/stars.py`),
  Word verdicts (`build/word_verdicts.py`) and bomb protection levels.
  `--stale OLD_FACTS` lists literal figures an update would leave behind, and
  the release gate gains a "generated" check.
- `build/run_trial.sh` runs the whole measurement end to end;
  `build/score_extra.py` scripts the second-pass and editor-lane scoring that
  0.9.0 did by hand.

### Fixed

- The hostile-package scorer labelled a run stopped by the sandbox's CPU
  limit (SIGXCPU) as a `crash`; it is now a `hang`, like a wall-clock
  timeout. No 0.9.0 cell carried that label.
- The hostile-package sandbox read a child's output through a pipe. Node on
  macOS writes pipes asynchronously and drops what is past the 64 KB buffer
  when it dies, which cut off the message Docxodus prints after a 200 KB
  runtime dump. Output now goes to a file. The labeller also reads
  snake_case ceiling codes (`…_limit_exceeded`) and the .NET DTD refusal.
  Re-running Docxodus 14.2.0 this way confirms the 0.9.0 levels; only their
  wording ("does not name a ceiling") was vague.
- Report D quotes its scorecard and protection labels from the logs, so they
  can no longer drift from the run.
- The DOCX twin-parity gate failed on the v0.9.0 tag because it counted
  `CHANGELOG.md` as a report; it no longer does.

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

[0.9.1]: https://github.com/arthrod/editors_trial/releases/tag/v0.9.1
[0.9.0]: https://github.com/arthrod/editors_trial/releases/tag/v0.9.0
