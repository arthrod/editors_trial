# Editors trial

This repo measures open-source DOCX editors on one adversarial fixture, then, separately, on a sandboxed set of hostile packages. Fidelity and safety are different results. A tool that keeps a hostile payload is not the same result as a tool that crashes. A third tree, `perf/`, measures performance under explicit layers and cache states; see [Performance](#performance).

The measured write-up is [Open-Source DOCX Editors Re-verified Against Code and Measured Round-Trip (2026).md](Open-Source%20DOCX%20Editors%20Re-verified%20Against%20Code%20and%20Measured%20Round-Trip%20(2026).md). The per-tool notes are in `reports/extras/`. The vendor notes are `reports/vendors.md`.

Each per-tool note has also been filed as an issue on that project's own repository, so that a maintainer can correct the measurement where they already work. The list of those issues is in [`outreach/`](outreach/).

## Fidelity

`fixture/complex.docx` is the corpus. `build/make_fixture.py` writes it as raw OOXML with hand-checked element order, choosing every construct because at least one surveyed editor is documented to lose it: tracked changes and moves, tables with `vMerge`/`gridSpan`, fields, content controls, charts, SmartArt, OLE, comments, headers/footers, multi-section layout, bidi/RTL, math, alternate content and `altChunk`, bookmarks, footnotes/endnotes, permissions, and the namespace prefixes Word itself declares (`wp14`, `w16du`, ...).

The editors are Plate, eigenpal (store and editor), Folio (model and editor), GenOffice, SuperDoc, office-open, Docen, Fidus Writer, WordCraft, canvas-editor, docs.plus, Docxodus, and Apryse WebViewer (closed source, run in a real browser with a trial key from `.env`, which is never committed). Headless lanes are not the browser. LibreOffice is the baseline and counts as a participant.

### Pipeline

`build/run_trial.sh` runs the whole fidelity measurement and then generates the reports from it:

1. `build/run_all.sh` — first pass: each editor's own import and export (`harness/`), plus LibreOffice headless as the baseline. Outputs land in `out/<lane>/complex.docx`.
2. `build/run_second_pass.sh` — second pass: each editor is fed its own first-pass output, and the scorer judges how much of what the editor wrote survives a second cycle (a fixed-point check).
3. `build/score_all.py` and `build/score_extra.py` — `build/check_roundtrip.py` scores every output: ZIP/CRC package integrity, `word/document.xml` well-formedness, the visible text stream, and weighted feature checks (critical/major/minor). The result is a weighted percentage, a critical-feature percentage, a text-retention percentage, and per-check JSON in `out/<lane>/score.json`.
4. `build/apryse_stamp.py` labels what Apryse's trial stamp added (it never edits the output); `build/ns_json.py` builds Report A's namespace tables.
5. `build/facts.py` reads the score artifacts into `out/facts.json`; `build/render_reports.py` renders every report from `templates/` and rebuilds the DOCX twin of each report it renders (`build/make_report.sh`, pandoc).

One file by hand: `python3 build/check_roundtrip.py IN OUT`.

### What you need

- The `repos/` checkouts with their dependencies installed (gitignored; installing dependencies is allowed, modifying them is not) and the same toolchains as the headless perf lanes: `bun`, `node`, each repo's `tsx`/`vitest` binaries, `cargo` for `harness/wordcraft`, `soffice` for LibreOffice, and a `timeout` command (GNU coreutils) for the LibreOffice lanes.
- A trial key in `.env` for the Apryse lane (never committed).
- `pandoc` for the DOCX report twins.
- Microsoft Word only for the separate Word steps (`build/word_verdicts.py`, Report C's Word renders), never shared with another Word job; `build/run_trial.sh` itself does not open Word.

### Run it

```sh
python3 build/make_fixture.py     # only to (re)build fixture/complex.docx
build/run_trial.sh                # round trips, second pass, scores, facts, reports
```

The scripts hardcode `BASE=/Users/arthrod/temp/T/editors_trial` (`run_trial.sh`, `run_all.sh`, `run_second_pass.sh`, `score_all.py`, `score_extra.py`); adjust it for another checkout.

## Hostile packages

`python3 build/run_bombs.py` records the ten vectors and does not build them. The run that actually opens them is:

```sh
WORDCRAFT_BIN=/path/to/wc-harness BOMB_WORK=/tmp/editors-trial-bombs \
  python3 -u build/run_bomb_sandbox.py
```

`node` has to be on `PATH` before that process starts. This machine uses the current nvm Node. `WORDCRAFT_BIN` is the release `wc-harness`.

LibreOffice is the comparison. It runs in the image `editors-trial-bombs:local`: no network, 2 GB, read-only root, one container per package. The editors are macOS binaries, so they are not run in that Linux container. They run under seatbelt. External network stays denied. Localhost is allowed, because several of these tools bind their own loopback stub, and so is the unix socket `tsx` opens inside the work directory. Writes stay in the work directory, plus the canvas vitest config cache, which Vite will not put anywhere else.

Each editor is driven with that project's own documented import and export (`EDITOR_CONFIG=suggested`). Plate uses `BaseEditorKit`, `retainSource`, and the default reject policy. A refused import writes no second file. canvas-editor does not replace a thrown import with the blank starter document. docs.plus stops at its own `importDocx` and `exportDocx`. The Plate www kit imports `remark-emoji`, `remark-gfm`, and `remark-math` at the versions pinned in `apps/www/package.json`. Those copies live in `harness/plate` because this checkout does not have them installed, and `harness/plate/aliases.ts` points the kit at them.

A seatbelt or loader failure before the editor runs is recorded as `not-run` with a `harness-` reason. It is not a catch. Preserving the payload is not a catch. A crash, a hang, or a leak is not a catch.

The sandboxed matrix is `logs/bombs`. [Report D](reports/Report%20D%20-%20Safety%2C%20Resource%20Bombs%20and%20Hostile%20Input%20(2026).md) keeps the unsandboxed refusal and then the measured scorecard. The safety word `bounded-reject` only means a non-zero exit that was not a crash, a hang, or a leak. The protection level is a separate reading: a named ceiling, a reduced write under a declared cap, sanitation, a parse or name-policy error, stack exhaustion, a kept payload, an unexpanded entity reference, a hang, a crash, a leak, or a load that exits zero and writes nothing.

Jubarte is not in that matrix. The same packages, read by the release binary of `../jubarte-redlines` at version 0.14.0, are `logs/jubarte-bombs` and [Report D1](reports/Report%20D1%20-%20Jubarte%20on%20the%20Hostile%20Packages%20(2026).md). The skill copy of the binary was not used. `jubarte read` writes a markdown view, not a second package.

Word is not opened. No NTLM hash is collected. A slip onto the host temp directory is denied by the seatbelt, so the only slip that can be observed is one that lands inside the work directory, or file contents that come back in the saved package.

## Performance

`perf/` is the performance harness. Its scenario catalog spans four layers — `native`, `model`, `browser_visible`, and `wasm_boundary` — and keeps them separate: a model-ready time is not a first-paint time, and a `requestAnimationFrame` callback is not a presented frame. It is a harness, not a report; no performance figures appear in the published reports. The full reference is [`perf/README.md`](perf/README.md).

- **Scenarios.** `perf/scenarios/catalog.py` defines C01–C24: startup, document load, first usable content, deferred work, edit responsiveness, typing bursts, cursor and hit testing, clipboard, undo, scrolling, layout, reflow, invalidation, large documents, search, save, memory, allocation, disposal, long-session stability, CPU interference, feature overhead, collaboration, and the WASM boundary. `perf/scenarios/coverage.py` checks the catalog against the normative matrix in `docs/superpowers/specs/`.
- **Workloads.** `perf/fixtures/generate.py` builds deterministic DOCX packages from a size ladder (`micro-paragraphs` through `paginated-equivalent`) plus Unicode, emoji, bidi, and IME correctness fixtures. `perf/fixtures/profiles.py` caps which workloads each execution profile may run and refuses hostile packages as fixtures.
- **Execution profiles.** `ci_contract` is headless with one fresh process per scenario and micro workloads; `ci_broad` allows five fresh processes and broader workloads but still cannot publish visible latency; `dedicated_publish` is the full ladder on a dedicated host, including `os_cache_cold` and the one-hour soak. The profile is recorded on every trial.
- **Honesty rules.** `perf/schema.py` validates every trial; only `measured` carries samples. `perf/runner/policy.py` and `perf/analysis/publication_gate.py` decide what may be published: a `ci_coarse` host never publishes a headline distribution, diagnostic runs are not timing publications, and a publishable distribution needs at least two independent samples. The I01–I12 interpretation conditions gate measured trials, and the run summary refuses to mix publishable and blocked medians. `perf/analysis/anti_ranking.py` rejects "N× faster than" prose that does not name the workload, layer, cache state, and host.
- **Statistics.** `perf/analysis/summarize.py` reports n, median, p90/p95/p99, MAD, a bootstrap 95% CI, and min/max. Cache states and repetition units are never pooled.
- **Adapters.** `perf/adapters/capabilities.py` records each editor's lanes and which features — pagination, hit testing, collaboration, WASM, typing, visible paint, IME, save, undo — are supported, not applicable, or unverified, with the pin and evidence note. `perf/adapters/protocol.py` turns a capability state into an explicit refusal outcome rather than a zero.
- **Runners.** `perf/runner/benchmark_ci_contract.py` drives the headless lanes for C02 (model load), C16 (save), and C21 (child CPU), and records the rest as `not_run` or `adapter-not-implemented`. `perf/runner/benchmark_warm_cold.py` drives the `harness/ui` browser hosts for warm-vs-cold C02/C03/C05/C06; its suite summary is diagnostic (`publishable: false`). `perf/runner/adversarial_c10_scroll.py` measures scroll frame time for one editor. Raw trials are immutable JSON under `perf/out/` with a `summary.json` beside them.

### What you need

- Python 3.10+; the harness itself is standard-library only.
- `out/facts.json`, produced by the release pipeline (`build/facts.py`). Every runner reads editor pins from it and stops if it is missing.
- The `repos/` checkouts with their dependencies installed (gitignored; installing dependencies is allowed, modifying them is not). Which toolchains a run needs depends on the lane: `bun` and `node` for most headless lanes, each repo's `tsx`/`vitest` binaries, `cargo build --release` for `harness/wordcraft` (`wc-harness`), and `soffice` for the LibreOffice lane. Apryse WebViewer has no headless round-trip harness here and is recorded `not_run`.
- For the browser lanes: the five `harness/ui` hosts (plate, docxodus, superdoc, genoffice, canvas) with dependencies installed — pnpm for plate/docxodus/canvas, npm for superdoc/genoffice — plus `playwright`/`puppeteer` at `harness/ui`. The runner starts each dev server itself.
- Publishable visible-latency numbers need a dedicated host and the `dedicated_publish` profile. That profile is defined in the schema but no runner accepts it yet; `ci_contract` and `ci_broad` runs are recorded with `publishable: false`.

### Run it

Headless model/save/CPU lanes — `--dry-run` first, it writes scheduler outcomes without invoking an editor (it still resolves pins, so it needs `facts.json`):

```sh
PYTHONPATH=. python3 perf/runner/benchmark_ci_contract.py --dry-run
PYTHONPATH=. python3 perf/runner/benchmark_ci_contract.py --execution-profile ci_contract --workload micro-paragraphs
PYTHONPATH=. python3 perf/runner/benchmark_ci_contract.py --execution-profile ci_broad --workload short-paragraphs
```

Browser warm-vs-cold lanes — starts the `harness/ui` dev servers itself:

```sh
PYTHONPATH=. python3 perf/runner/benchmark_warm_cold.py --pairs 3
PYTHONPATH=. python3 perf/runner/benchmark_warm_cold.py --pairs 3 --editors plate docxodus
```

One-off scroll probe:

```sh
PYTHONPATH=. python3 perf/runner/adversarial_c10_scroll.py --editor plate --out-root perf/out/c10_plate --pairs 3
```

Tests and coverage gate:

```sh
python3 -m unittest discover -s perf/tests -q
python3 -I build/test_perf_plan_coverage.py
```

Artifacts land under `perf/out/` (gitignored): `attempts/*.json` plus a `summary.json` per run.

## Logs

`logs/bombs/trace.log` keeps the full stdout and stderr of every cell. Nothing in that trace is truncated. `logs/bombs/scorecard.txt` is written when the run finishes. `logs/bombs/tool/<editor>/<bomb>/` and `logs/bombs/comparison/libreoffice/<bomb>/` hold the same streams per cell.

`logs/bombs-before-suggested-config` is the earlier matrix. Several of its columns died in the seatbelt before the editor ran. Do not read those cells as the editor's result. `logs/bombs-suggested-smoke` is the one-package check that the corrected harness actually reaches Plate, canvas-editor, docs.plus, Docen, office-open, and Fidus Writer.

`BOMB_RESUME=1` continues a run. A run without it deletes `logs/bombs` first. Move that directory aside if the previous trace should be kept.

## Releasing

A release is a re-measurement. [`AGENTS.md`](AGENTS.md) holds the rules and [`RELEASING.md`](RELEASING.md) the checklist (also the "Release" issue template). The steps are scripted:

```sh
build/update_editors.sh                 # move every pin to its newest version at least 5 days old
build/run_trial.sh                      # round trips, second pass, scores, namespace tables, facts, reports
build/release_broken.sh                 # Report B's broken corpus, twice, cells compared
build/release_word.sh                   # every Word step, twice, passes compared (Terminal tab, Word clean)
python3 build/facts.py && python3 build/render_reports.py --all-twins
build/verify_publication.sh --with-word # the gate, twice
```

Microsoft Word is only ever opened by the neurotic bench's audited driver and its watchdog, vendored unmodified in `build/vendor/` (`build/vendor_word_driver.sh` refreshes them after running their spec). Never open Word by hand or with ad-hoc osascript.

Every figure in a report is a placeholder in `templates/` filled from `out/facts.json`; change a figure by re-measuring, never by editing a rendered report.

## Release gate

The published report set is eight Markdown reports and their DOCX twins. One
command checks every gate that has to pass before they ship:

```
build/verify_publication.sh              # everything except Word
build/verify_publication.sh --with-word  # also drive Word to open each file
```

The gates answer different questions, and none substitutes for another:

| Gate | Question it answers |
|---|---|
| `build/test_report_claims.py` | Do the repository's own claims still hold? |
| `build/verify_twin_parity.py` | Is each published DOCX what its Markdown says, and exactly what the build pipeline produces? |
| `build/verify_findings.py` | Does every figure in the published tables belong to the subject its table row names? |
| `build/check_report_consistency.py` | Does every percentage and byte size in every live report occur in the measurement artifacts? |
| `build/validate_ooxml.py` | Does each DOCX validate against the ECMA-376 schemas? |
| `build/build_claim_evidence.py` | Is the review's claim-evidence matrix complete and well formed? |
| `build/verify_deliverables.py` | Does each deliverable open in Microsoft Word? |

The findings gate is the one that cannot be replaced by a token check. A
token check asks whether "100%" occurs somewhere in the logs; it cannot tell
SuperDoc's 100% from SuperDoc's 84.9%. The findings gate compares each
figure with the measurement for the subject the table row names.

The number gate scans every live report and its twin - thirty-five documents,
468 percentages and byte sizes - against a corpus built from the measurement
artifacts in `out/` and `logs/`. `--diff-only` narrows it to the reports a
branch has touched, which is what a pre-commit run wants.

A DOCX twin is generated output. It must never be patched by matching text
against its source: the source is rendered, so the markdown markers are gone
and the context match fails silently. Rebuild it with `build/make_report.sh`.

## Review

`out/review/` holds the reader's report on the study, prepared with the
Scientific Research Workflows peer-review skill. It is a working draft for a
human to verify and rewrite, not an editorial decision.

| File | What it is |
|---|---|
| `out/review/review_draft.md` | The review: eleven major and twelve minor comments, channels separated |
| `out/review/claim_evidence_matrix.csv` | Every claim mapped to its evidence: 126 claims, 107 machine-verified and 19 needing an author action |
| `out/review/venue_and_reporting_guidance.md` | Venue shortlist by fit, and the reporting instruments to prespecify |
| `out/review/intake.json` | The review's own intake record, as the skill validates it |
| `out/review/findings_ledger.csv` | The findings ledger the claim matrix is generated from |

The bundled reporting-guideline catalogue has no software-benchmark
instrument, so no checklist coverage audit was possible. The venue dossier
names the three instruments to adopt instead, and records that a catalogue's
`VALID` status is a coverage statement, not a statement that reporting is
complete.
