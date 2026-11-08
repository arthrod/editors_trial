# Changelog

Every release of the editors trial is a measurement: the editor commits it
pins, the fixture it feeds them, the scorer that reads their output, and the
reports written from that output. A release never changes a figure without
re-running the measurement behind it. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/) with the trial still pre-1.0.

## [Unreleased]

### Added

- `perf/`: the performance harness (#91). One schema and outcome set for
  every trial (`measured`, `unsupported`, `not_applicable`, `unverified`,
  `failed`, `not_run`), a 24-scenario catalog (C01–C24) across the `native`,
  `model`, `browser_visible`, and `wasm_boundary` layers, deterministic
  workload fixtures with a size ladder and Unicode/emoji/bidi/IME correctness
  fixtures, execution profiles (`ci_contract`, `ci_broad`,
  `dedicated_publish`), per-lane capability records, summary statistics with
  uncertainty, a publication policy that keeps CI from publishing visible
  latency, and immutable raw trials under `perf/out/`. Runners today:
  `benchmark_ci_contract.py` (headless C02 model load, C16 save, C21 child
  CPU), `benchmark_warm_cold.py` (browser C02/C03/C05/C06 warm-vs-cold on the
  `harness/ui` hosts), and `adversarial_c10_scroll.py` (C10 scroll). Design
  and coverage matrix in `docs/superpowers/specs/`; unit tests in
  `perf/tests/`; documentation in `perf/README.md`.
- Documentation (#92): the README Fidelity section now describes the
  round-trip pipeline end to end — fixture, first and second pass, scoring,
  facts, and report rendering — with what a run needs; `perf/README.md`
  gained the runner-level details (PERF marks, wall/CPU companion samples,
  the 600 s harness timeout).

### Changed
- `RELEASING.md` §7: publishing the bundle is one command, `bench publish editors_trial et-vX.Y.Z`
  (bench-ops plan 6, editors_trial#74; first used for et-v0.9.4, #75), and the site picks the
  release up with `bench bump editors_trial`. No figure changes.

## [0.9.4] - 2026-11-01

Tooling only: every TypeScript project in the trial installs with pnpm, and
nothing newer than 5 days enters it. No figure changes.

### Updated

- No editor pin moved (cutoff 2026-10-27, as in 0.9.2 and 0.9.3).
- Twelve projects (six demos, six harnesses) updated with
  `pnpm update --latest` under `minimumReleaseAge: 7200` (5 days, AGENTS.md
  section 1); the editor pins are excluded and move only through
  `build/update_editors.sh`. npm and bun lockfiles removed (#59, #60).
- Live demos rebuilt on the new dependencies: canvas-editor, docxodus, plate,
  superdoc.

### Measured

- Plate, Docxodus and Apryse round trips, run twice: part-for-part identical
  to the published outputs. Their UI captures match `out/ui`.

### Not re-measured

- Every other lane: no pin moved and no harness changed for them.
- **The release gate (`build/verify_publication.sh --with-word`) was not
  run**: Word was busy with another session's job. Published on the owner's
  instruction without it.
- docs-plus and office-open demos have no rebuild recipe; their live builds
  are those of 0.9.3.

### Fixed

- `build/update_editors.sh` installs the docxodus pin with pnpm, not npm.
- `build/rebuild_demo.sh` never copies a demo's local `node_modules` into the
  build tree (`build/test_rebuild_demo.py`).
- superdoc and office-open demos minify with Oxc: Vite 8 no longer ships
  esbuild.

## [0.9.3] - 2026-11-01

Every pixel measurement is taken at 200 dpi; Apryse WebViewer joins every lane
it was missing from; every remaining typed table and pixel figure in Reports
A2, B and C is generated.

### Updated

- No editor pin moved: the release date and cutoff (2026-10-27) are those of
  0.9.2.
- **Pixel resolution: 200 dpi** (110 before), in `build/pixels.py`, the one
  place every pixel script reads it from (`build/test_pixels.py`). The rule
  is in AGENTS.md and RELEASING.md.

### Measured

Each result below was run twice, with identical outputs.

- **Word's pixel layer** at 200 dpi, from the stored Word PDFs: every verdict
  unchanged. Corpus ink is now 5,450,749 px; Apryse 2,119 px (0.04%).
- **LibreOffice's pixel layer**, now generated (`build/lo_render_compare.py`),
  with an Apryse row: Apryse 24,540 px (4.32%, very close); LibreOffice's own
  round trip 888 px (it was 335 at 110 dpi).
- **SmartArt band** (Report C §5) at 200 dpi: the band holds 469,131 px and
  Word draws 0 of them. The checkerboard control lights up 269,641 px, and
  the border control 28,000 px, all of them its own border. The 151
  differing pixels outside the band are one edge that moves by a pixel.
- **A/B variants** (Report C §6.3), now generated (`build/ab_table.py`), in Word
  and in LibreOffice. LibreOffice's corpus and variants are rendered in one
  run.
- **Construct presence** and the **package inventory** with Apryse: every
  construct is visible in Word's render of its output and present in its
  package.
- **Report C UI:** LibreOffice's own pages are rasterised at 200 dpi, and Apryse
  pages 3 and 4 and its comment panel are captured.
- **XSD and package integrity** (Report B), generated: Plate.js 1 real XSD
  violation (published as 0 in 0.9.2), Apryse 4.

### Not re-measured

- **Word was not opened.** Another session's Word job was running, and
  AGENTS.md forbids sharing Word. The Word pixel layer, the SmartArt
  controls and the A/B variants were re-rasterised from the PDFs Word
  exported for 0.9.2. The Word verdicts are 0.9.2's.
- **The publication gate** (`build/verify_publication.sh --with-word`) needs
  Word, for the same reason. It is outstanding.
- Round trips, second passes, the broken corpus and the hostile packages:
  no pin moved, so 0.9.2's results stand.
- Google Docs and Microsoft Word on the hostile packages (AGENTS.md: never
  re-tested).

### Added

- `build/pixels.py`, `build/lo_render_compare.py`, `build/raster_controls.py`,
  `build/ab_table.py`, `build/smartart_band.py`.
- Facts for the remaining typed figures: `lpx.*`, `sa.*`, `ab.*`, `xsd.*`,
  `pkg.*`, `word.<tool>.cell`, `parts.matrix`, `inventory.table` and
  `pixels.dpi`.
- Report C §2.14 (Apryse WebViewer) and Report A2 §6.8 (Apryse).

### Fixed

- **A missed capture failed silently.** `harness/ui/shot.mjs` printed OK when
  a wait or a scroll found nothing; Apryse's "page 3" was page 1. It now
  exits 4 (`build/test_ui_captures.py`).
- **Absolute relationship targets.** `malformation_audit.py` reported 18
  missing parts for Apryse's `/word/...` targets; it now resolves them from
  the package root.
- **Every lane.** Apryse was missing from 15 measurement scripts, among them
  the audits behind six tables, `verify_findings.py` (part of the publication
  gate), `construct_presence.py` and `inventory_table.py`. `build/test_every_lane.py` now checks both path
  patterns and editor lists.
- **Report C §6.3** cited the picture's figures for the chart. It also listed
  page 3 only for `no_chart`, which changes page 4 too.
- **Report C §4.2(a)** called the parts the regenerators *write* the parts
  they *keep*.
- **The SmartArt band locator** took the box around every difference, which
  at 200 dpi swallowed an object below the band. It now takes the control's
  own footprint.
- **Fixed crops.** `strips.py` cropped in 110-dpi pixels; the crops are now in
  inches.
- **Retired instructions.** Report C's recipe used a `/tmp` venv, and Report
  A's patched a rendered report; both now use the PEP 723 scripts and facts.

## [0.9.2] - 2026-11-01

Apryse WebViewer joins as the first closed-source participant; Word is
driven by the audited driver; every remaining typed figure in the reports
is generated; the live demos are rebuilt at the trial's pins.

### Updated

- No editor pin moved: the release date and cutoff (2026-10-27) are those of
  0.9.1, and `build/update_editors.sh` found nothing newer before the cutoff.
- Added `@pdftron/webviewer` 12.2.1 (Apryse WebViewer, trial key), driven
  through its own DOCX editor in a real browser (`harness/apryse/`).
- Microsoft Word is now opened only through the neurotic bench's audited
  driver (`build/vendor/word_pdf.py`, commit 2f2e23db) and its watchdog
  (`build/vendor/word_watchdog.sh`, commit 6fd25e9c), both vendored
  unmodified with their sha256 in `build/vendor/word_pdf.SOURCE`.

### Measured

- **Apryse WebViewer:** 89.9% weighted, 9 failed of 99; the second pass scores the same.
  Its trial stamp adds parts; `build/apryse_stamp.py` labels them and the
  one failure that cannot be separated from the stamp. Word opens its
  output. Three round trips and three second passes give identical parts,
  after the harness was fixed to export only once the comments had loaded.
- **Apryse on the hostile packages** (Report D), two passes, identical:
  grade 0.32. Cleaned B1, B2, B3, B6; kept B7, B8, B10; ran past the
  40-second wall clock on B4, B5 and B9 in both passes.
- **Word verdicts** through the audited driver, twice, identical: the same
  five outputs refused as in 0.9.1, and Apryse's opens.
- **Broken corpus** (Report B), every editor, twice: every defect cell is
  identical across the passes and to 0.9.1. Word on those outputs, twice,
  identical. WordCraft's output now opens (it was recorded as refused in
  0.9.1, on the same file); the change is in how Word was driven, since the
  file did not change.
- **`w:dirty="true"` is no longer fatal on its own.** The single-defect
  corpora, opened twice through the driver: d10 alone and d11 alone do not
  open, d12 alone opens after Word asks whether to update the fields. The
  first report's table, from a hand-written driver that kept no record of
  Word's dialogs, is kept as history. Report B, the main report and
  Reports A/A2 say so.
- **Report C:** the editors' UI captured twice (identical); only GenOffice
  differs from the published captures. Word's pixel layer twice
  (identical); SuperDoc and Docxodus now 0 px, and the corpus ink moved
  from 1,661,202 to 1,661,285 px with every verdict unchanged, an
  environment change.

### Not re-measured

- Google Docs and Microsoft Word on the hostile packages (AGENTS.md: never
  re-tested).
- The `w:dirty` attribute variants (`"1"`, `"false"`, `w:fldLock`) in the
  first report's table; only `w:dirty="true"` was re-opened.
- Report C §5's controls, the §6.2 LibreOffice table and the §6.3 A/B,
  which are not part of the pipeline.
- Jubarte on the hostile packages (Report D1).
- The hostile-package runs were made at load 40–80 while another session's
  batch ran; Apryse's three wall-clock hangs reproduced in both passes but
  were not re-run on a quiet machine.

### Added

- `RELEASING.md` and the "Release" issue template, kept identical by
  `build/test_release_template.py`.
- `build/release_word.sh` (every Word step twice, passes compared) and
  `build/release_broken.sh` (the broken corpus twice, cells compared).
- Generated facts: release dates, code-read commits, participant counts,
  Report B's three tables, Report C's Word pixel table, Report A's
  per-participant namespace counts, `out/word_isolation.json`.
- `build/rebuild_demo.sh`: every live demo rebuilt at the trial's pins,
  with `SOURCE.txt` written from git.
- `render_reports.py --all-twins` rebuilds every DOCX twin.

### Fixed

- `build/run_broken.sh` gave Plate an unset input variable (Report B's
  "no output" came from the script; Plate's own failure, `decode-failed`,
  is now logged in `out_broken/logs/`), gave canvas no input or output
  path, and looked for LibreOffice's output under the wrong name.
- `build/word_verdicts.py` ran a whole Word batch when imported; every
  Word-driving script is now import-safe, with a test.
- LibreOffice is counted as a participant like any other.

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
