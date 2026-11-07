# Cross-editor performance benchmark design

Date: 2026-11-05. Status: design and implementation plans only. This change does not measure an editor and does not add a harness.

The repository is [arthrod/editors_trial](https://github.com/arthrod/editors_trial). It already measures open-source DOCX fidelity and hostile-package behavior. `README.md` names the participants. `build/part_map.py` lists the round-trip lanes. `out/facts.json` holds the pins from the 2026-11-01 release facts. There is no performance harness, no `perf/` tree, and no `docs/superpowers/` history before this design. `repos/` is not present in the workspace used to write this document, so line numbers in the fidelity report are trial-recorded against those pins and were not re-checked in a checkout on 2026-11-05.

The normative coverage matrix is [`2026-11-05-editor-performance-coverage.json`](2026-11-05-editor-performance-coverage.json). `build/test_perf_plan_coverage.py` fails if a criterion, an interpretation condition, an editor id, or a plan link is missing. Human-readable copies of the criterion fields follow the design choices below.

## Decision

Build one scenario and result schema, one adapter per editor lane, and four measurement layers. Store raw trials as immutable artifacts. Publish wall-clock interactive latency only from a dedicated host. Use ordinary CI for the schema, fixtures, statistics, and adapter contracts.

Do not publish a sentence of the form "editor A is N times faster than editor B" unless that sentence names the workload, the feature profile, the cache state, the percentile, the hardware and operating system, and the timing boundary. The fidelity reports stay on their own pipeline. This design does not add a figure to them.

## Why this shape

An editor is a pipeline. Bytes are parsed into a model. The model feeds layout. Input passes through the editor and any plugins. A renderer presents pixels. Save and background work share the CPU, the memory, and the disk. A single startup number or a single large-file open time collapses those stages.

Three rejected alternatives:

- **Editor-specific suites only.** microide, Jet, VS Code, and LVCE each measure their own product with a clock that fits that product. microide's README says its harness does not produce numbers that can be compared with other editors. VS Code's startup marks do not exist on WordCraft. Copying those suites would leave the DOCX trial without a common row. The useful part of each suite is borrowed as a method, and the result stays labeled as a project-owned reference.
- **One end-to-end harness only.** A screen observer can see the pixel and still cannot say whether the time went to the model, the garbage collector, or the WASM boundary. Typometer is that kind of observer for a class of text editors. It cannot see Docxodus's instantiate step, and it cannot see a headless `parseDocument` call. End-to-end observation is one layer, not the whole suite.
- **Internal timers only.** Constructor return, model-ready, and a `requestAnimationFrame` callback all stop before a user has seen a frame. The Event Timing specification defines duration through the next rendering update, and the Paint Timing specification separates paint from earlier callbacks. Internal timers remain in the model layer.

The chosen shape is a common schema plus adapters, with layers kept separate. An adapter may refuse a scenario. The refusal is an outcome. It is not a zero.

## Candidates

Pins below are the values in `out/facts.json` at the time of writing. A later release moves pins only through `build/update_editors.sh`. Performance code must read the pin that the release recorded. It must not float to an unpinned main branch and then compare the result with a pinned neighbor.

| Id | Pin recorded in `out/facts.json` | What the trial drives | Performance quirk that changes a scenario |
|---|---|---|---|
| `plate` | `udecode/plate` `60c7f5530` (2026-11-01), branch `next` | Headless DOCX import and export in `harness/plate` | Slate plus a plugin schema. DOCX goes through HTML. Report C: one continuous scroll, no page model. Yjs collaboration is an optional plugin documented at platejs.org, not the fidelity harness. Slate chunking is off unless the host sets `getChunkSize`. The DOCX import needs a DOM realm and the harness restores Node's streams after happy-dom. |
| `docxodus` | git `583a11c7f`; npm `docxodus@15.0.0` | `harness/ui/docxodus` | One .NET engine, a WASM browser build, `DocxEditor`, and `DocxSession`. WASM initialize is its own phase. README claims bounded undo and per-block re-render; those are project claims. The harness comment that says v14.2.0 is older than the npm pin. |
| `apryse` | npm `@pdftron/webviewer@12.2.1` | `harness/apryse`, `enableOfficeEditing`, `getFileData({ downloadType: 'office' })` | Closed source. Trial key. Startup posts the key, a language code, and the version to `pws-collect.pdftron.com`. Saved files carry a `trn_d_stamp` watermark. The office engine is WebAssembly inside Chromium. On 2026-11-05 the office-edit guide URL redirected to the documentation home and did not return a guide body. |
| `superdoc` | git `0ee03fd3c`; SDK `@superdoc/sdk@2.26.0-next.16`; engine `0.28.0-next.3` | Headless SDK open and save | V2 model is OOXML-backed. The trial report says the V1 ProseMirror editor is not the V2 surface. Current docs, read 2026-11-05, default a paginated window of five pages and one overscan page, and a 30 second worker startup timeout. Headless save is not first paint. |
| `folio` | `stella/folio` `958c582cb` | `parseDocx` to `repackDocx`, DOM-free | ProseMirror over a typed OOXML core. `preloadFonts: false` is required for the headless lane. The browser editor is a different lane. First save normalizes revision and paragraph ids, so it is not a no-op. |
| `genoffice` | `genspark-ai/genoffice` `36a509e8f` | Tiptap editor path, not the CLI docx-to-docx route | The CLI refuses docx-to-docx. The editor is paged Tiptap. An AI panel and an MCP server are feature-profile items, not the core load path. The CLI module pulls a React barrel and does not load under plain Node. |
| `eigenpal` | `eigenpal/docx-editor` `3425d4d7a` | Store lane and `createServer` | Store and server lanes are DOM-free. `editor-api` is EigenPal Pro. Current main, not the pin, materializes visible pages plus caret and selection pages. Browser UI hit testing was not read on the pin. |
| `office-open` | `DemoMacro/office-open` `567addfd4` | `parseDocument` and `generateDocument` | No editor UI. Report C: one continuous flow per section, no page boxes. Interactive caret, scroll, and hit-test scenarios are not applicable. Parse and generate are. |
| `docen` | `DemoMacro/docen` `1890b15aa` | `parseDOCX` and `generateDOCX` over office-open | README: TipTap, ProseMirror, LeaferJS, and a pagination claim. The project says it is not stable. Report C shows six pages for the fidelity corpus. Leafer is not a DOM text surface, so Event Timing is not automatically the paint clock. |
| `wordcraft` | `storytold/wordcraft` `a88e00525` | `wordcraft_docx` read and write, without layout, in the fidelity harness | Rust. Native egui and a wasm32 browser app. README architecture table places hit testing in `wordcraft-layout` and lists IME, clipboard, undo, and find. The 1.4 millisecond relayout sentence is a project claim. No collaboration crate is listed in that architecture table. License text in the README is MIT OR Apache-2.0; the fidelity report also records a conflicting AGPL reading elsewhere. This design does not resolve the license. |
| `fidus` | `fiduswriter` `e14cc456a` and `fiduswriter-document-ts` `dc0981db4` | `@fiduswriter/document` import and template export | The trial does not measure the full Fidus Writer application. Report C: the editor is a continuous scroll. Import has no table handler. Using the input file as the export template is not a model round trip. Collaboration on the document package is not applicable; the full application was not probed. |
| `canvas` | `Hufe921/canvas-editor` `1865c9b06` and plugin `0e8a1b36c` | Plugin `importDocx` / `exportDocx` | Canvas or SVG, not contenteditable. The editor owns hit testing. Workers cover word count and catalog. Pagination is a product feature. On the fidelity corpus the UI showed a header and footer and then threw on a vertical-merge cell. CRDT collaboration is `feature/CRDT`, not the pinned commit. |
| `docsplus` | `docs-plus/docs.plus` `a9b0c69e8` | HTML bridge import and export | TipTap on Next.js. Runtime is Bun. Collaboration uses Hocuspocus and Yjs and, for the full app, PostgreSQL and Redis. The domain conversion functions do not need that stack. Report C: continuous scroll. ProseMirror commits composition updates before `compositionend`. |
| `libreoffice` | system `soffice`, not a git pin | `soffice --headless --norestore --convert-to docx` | The measured lane is headless conversion. It is not an interactive typing surface. A GUI lane would be a new adapter and is unverified. |

Out of scope: Jubarte, which reads hostile packages to a markdown view, and Microsoft Word, which is the fidelity oracle. This design does not open Word and does not upload hostile packages anywhere. Google Docs is not a participant.

## Layers

| Layer | What it may claim | What it must not claim |
|---|---|---|
| `native` | CPU time or wall time inside a native or Rust function, with the harness boundary stated | A browser frame, a WASM call, or a user-visible edit |
| `model` | Time to build or mutate the document model | First paint, first usable, or input-to-pixel |
| `browser_visible` | Time to a paint entry, a presented frame, or an external pixel that shows the edit | A `requestAnimationFrame` callback by itself |
| `wasm_boundary` | Compile, instantiate, call, copy, and `memory.grow` across the host boundary | The whole editor's typing latency |

A comparison across layers is a diagnostic. It is not a ranking.

## Cache states

| State | Definition |
|---|---|
| `process_cold_fs_warm` | New process and new profile. The operating-system page cache is left as it is. |
| `os_cache_cold` | New process and new profile, after `sync` and a clean page-cache drop on a disposable dedicated host or on an operator-approved `laboratory` host with `page_cache_dropped: true` recorded. Linux documents `drop_caches` as a testing and debugging interface that can cost substantial I/O and CPU. It is not used on a shared `ci_coarse` machine and it is not mixed into a warm distribution. |
| `warm_steady` | The same process or a declared preconditioning script has already exercised the fixture. The script is part of the trial record. |

Criterion.rs warms a microbenchmark before measuring it. That warmup is an in-process microbenchmark phase. It is not `warm_steady` for a GUI, and it is not a reason to discard a cold process start.

## Outcomes

`measured`, `unsupported`, `not_applicable`, `unverified`, `failed`, and `not_run` are distinct. Only `measured` carries a latency sample list. The others store null. A report renderer that prints null as `0 ms` is a bug. A harness crash before the editor starts is `not_run`, which matches the fidelity trial's rule that a seatbelt or loader failure is not the editor's result.

`unverified` means the documents read on 2026-11-05 do not establish the feature and no probe has run. It is not a claim that the feature is absent. `unsupported` waits for a positive product statement or a probe that the command does not exist. `not_applicable` is for a lane whose architecture has no such surface, such as hit testing on office-open.

## Statistics and runs

A publishable summary has the sample count, median, p90, p95, p99, median absolute deviation, a 95 percent confidence interval, the minimum, and the maximum. Outliers stay. The repetition unit is `fresh_process` for interactive latency and may be `in_process_iteration` for a Criterion-style microbenchmark. Those two units are never pooled.

A timing run records clocks and cheap resource samples. A diagnostic run may take a Chrome trace, `perf`, or an allocation profile. Playwright documents `trace: 'on'` as performance heavy. That mode is diagnostic. Action duration reported by Playwright is the driver's interval, not the editor's paint interval.

Interactive latency gates run on a dedicated host after the quiet-machine check in `AGENTS.md`. CI runs the unit tests in these plans, fixture checksums, and schema checks. CI does not publish a GUI latency.

Raw trial JSON is written once. Summaries are derived. A later change of the summary function re-reads the raw files.

## Execution profiles and low-resource hosts

Every trial names an `execution_profile` in addition to `host_class`. The profile controls sample budgets, workload byte caps, and which cache-state variants the scheduler enqueues. It never removes a criterion from the catalog. A scenario the profile cannot run is stored as `not_run` with `failure_reason: execution_profile`, not as a zero.

| Profile | Typical `host_class` | RAM guidance | Display | Purpose |
|---|---|---|---|---|
| `ci_contract` | `ci_coarse` | 512 MiB cgroup or container | No compositor: Node headless DOM, native in-process, or `soffice --headless` only | Maximize editor coverage on the smallest machine: every model, native, and `wasm_boundary` scenario that does not require pixels |
| `ci_broad` | `ci_coarse` | 2–4 GiB | Xvfb plus Mesa software GL (SwiftShader or llvmpipe), one browser at a time | Run every criterion at least once with reduced samples and capped workloads; still not publishable for visible latency |
| `dedicated_publish` | `dedicated` or `laboratory` | Host record in `ram_bytes` | Real display or verified Xvfb at recorded refresh | Full sample budgets, `os_cache_cold` when recorded, multi-gigabyte host workloads, and the one-hour soak |

Sample budgets are fixed per profile and repetition unit. They shrink repetition; they do not drop outliers from a run that did execute.

| Profile | `fresh_process` attempts per scenario variant | `in_process_iteration` samples (C24) |
|---|---|---|
| `ci_contract` | 1 | 20 |
| `ci_broad` | 5 | 100 |
| `dedicated_publish` | 30 | 500 |

Workload caps select the largest ladder id the profile may pass to an editor. Host-only generation above the cap stays on the dedicated host; CI never materializes those bytes.

| Profile | Maximum `workload_id` from the ladder |
|---|---|
| `ci_contract` | `micro-paragraphs` and `micro-search` only |
| `ci_broad` | `short-paragraphs`, `mixed-utf8`, and `search-dense` with the generator's built-in paragraph limits (no host-only multi-gigabyte profiles) |
| `dedicated_publish` | Full ladder including `long-paragraphs`, `one-paragraph`, `paginated-equivalent`, and host-generated large files |

### `host_class: laboratory`

A single-tenant measurement VM (including an approved Cloud Agent pod) that is not a disposable bare-metal dedicated bench but is operator-approved for invasive cache tests. Records real `ram_bytes`, may run Xvfb, and may execute `drop_caches` when the implementer documents the command in the trial record. Laboratory trials use the same immutable JSON schema as dedicated runs. **`publishable` stays `false` for laboratory headline publication** unless a later spec revision says otherwise; raw trials are regression artifacts only.

Scheduler rules keep low-resource runs honest:

- `os_cache_cold` runs enqueue only when `execution_profile` is `dedicated_publish` and `host_class` is `dedicated` or `laboratory`, with `page_cache_dropped: true` on `laboratory`. `ci_coarse` never records `os_cache_cold`. Other profiles keep `process_cold_fs_warm` and `warm_steady` variants.
- C20 long-session stability enqueues on `dedicated_publish` for `dedicated` and `laboratory`. A preview soak may complete in the conductor session; the full one-hour soak must be **started** (for example in tmux) even if the conductor exits first. `ci_contract` and `ci_broad` record `not_run` for C20 without starting a truncated soak.
- C18 allocation profiling may run on `ci_broad` once per editor as `run_kind: diagnostic` with `publishable: false`; it is not required on `ci_contract`.
- Browser-visible scenarios on `ci_contract` are `not_run` when the lane has no headless substitute; model-layer timings for the same editor still run (for example Folio parse, Plate headless DOCX, office-open generate).
- Only one editor process group runs at a time on `ci_coarse`, matching the quiet-machine rule in `AGENTS.md`.
- Optional cgroup memory limits (LVCE-style sweeps) are diagnostic metadata on `dedicated_publish` only. They do not replace the primary C17 sample at the profile's workload cap.

Publication policy is unchanged: `ci_coarse` and `laboratory` never publish browser-visible or native-present latency as headline numbers regardless of profile (laboratory runs remain regression artifacts with `publishable: false` unless a later spec revision opens publication). Contract and broad CI runs still produce immutable raw trials, capability matrices, fixture checksums, and model or WASM summaries for regression tracking.

## Correctness before speed

Interactive scenarios that claim text editing carry a correctness check where the product claims the behavior:

- Unicode: a combining sequence and a non-BMP scalar stay intact.
- Emoji: a family sequence with a skin tone and ZWJ is one grapheme for caret and backspace when a caret is claimed.
- Bidirectional text: logical order is checked, and the hit result is recorded separately from visual order.
- IME: composition updates and the committed string are different samples. ProseMirror's documented behavior is to commit composition updates into editor state immediately. Plate's contenteditable host, canvas-editor's own pipeline, WordCraft's claimed IME, and Docxodus's editor each need their own probe.

A failed check yields `failed` with reason `correctness`. The latency samples may be retained in the raw artifact and must have `publishable: false`.

Feature profiles:

| Profile | Contents |
|---|---|
| `P0` | Optional plugins off, language tools off, AI panel off, collaboration off |
| `P1` | The product's ordinary theme and syntax or style display, still without a language server or AI |
| `P2` | A named realistic set for that product: spelling, or a language tool, or Git, listed explicitly |
| `P3` | `P2` plus one named busy extension or panel whose only job is to prove the harness can see interference |

Large-file mode that turns any of those off is recorded on the trial. The comparison uses the recorded profile, not the profile that was requested and then silently dropped.

## Workloads

Generators live under the future `perf/fixtures/` tree and write a checksum. The fidelity file `fixture/complex.docx` remains the correctness smoke fixture. It is not a large-document workload. The size ladder adds `micro-paragraphs` and `micro-search` for `ci_contract`, then short paragraphs, long paragraphs, one enormous paragraph, mixed UTF-8, a bidirectional paragraph, an emoji paragraph, and a search fixture with a declared match count. Multi-gigabyte files are generated on the host and are not committed. Hostile packages in the safety study are not performance fixtures.

## Repository layout this design asks for

```text
perf/
  schema.py
  outcomes.py
  fixtures/
  analysis/summarize.py
  runner/
  adapters/
  layers/
  scenarios/
  tests/
docs/superpowers/specs/
docs/superpowers/plans/
```

`repos/` stays unmodified. Python that reads an untrusted package uses `python3 -I`. The performance fixtures are generated by the harness, so the generator tests use ordinary CPython. The runner refuses a path inside the hostile-package corpus unless a future plan says otherwise. This plan does not.

## Sub-projects

Each plan produces software that its own tests can judge without the other plans' editors.

| Plan | Independent result |
|---|---|
| [Schema and outcomes](../plans/2026-11-05-perf-schema-and-outcomes.md) | A trial record that rejects forbidden clocks and forbids a zero for a non-measurement |
| [Fixtures and parity](../plans/2026-11-05-perf-fixtures-and-parity.md) | Checksummed workloads and feature profiles |
| [Statistics](../plans/2026-11-05-perf-statistics.md) | Summaries with uncertainty, unmixed cache states, and retained outliers |
| [Runner and artifacts](../plans/2026-11-05-perf-runner-and-artifacts.md) | Immutable raw trials, host class, execution-profile scheduling, and timing versus diagnostic |
| [Adapters and quirks](../plans/2026-11-05-perf-adapters-and-quirks.md) | A capability record for every candidate lane |
| [Measurement layers](../plans/2026-11-05-perf-measurement-layers.md) | Layer checks and a WASM boundary contract |
| [Scenarios and coverage](../plans/2026-11-05-perf-scenarios-and-coverage.md) | One scenario file per criterion and a test that the matrix is complete |

## Sources

Access date for every source in this section is 2026-11-05 unless a sentence says the fact comes from `out/facts.json` or from a file in this repository. "Verified" here means the page was fetched and the statement is on that page. It does not mean the benchmark was executed.

### Trial documents in this repository

- `README.md`, `AGENTS.md`, `build/update_editors.sh`, `build/part_map.py`, `out/facts.json`.
- `templates/Open-Source DOCX Editors Re-verified Against Code and Measured Round-Trip (2026).md` for pipelines and harness quirks. Line citations in that file are trial-recorded.
- `templates/reports/Report C - Rendering Versus Word (2026).md` for which UIs paginate. That report is a pixel study at the trial's dpi, not a latency study.
- `templates/reports/vendors.md` and `harness/ui/docxodus/src/main.ts`.

### Candidate primary pages

- Plate collaboration: <https://platejs.org/docs/yjs>
- Slate performance: <https://docs.slatejs.org/walkthroughs/09-performance>
- Slate huge-document example: <https://github.com/ianstormtaylor/slate/blob/main/site/examples/js/huge-document.jsx>
- SuperDoc large documents: <https://docs.superdoc.dev/editor/performance-and-large-documents/>
- SuperDoc issue 2879, closed as a duplicate on 2026-04-22. The `superdoc-dev/superdoc` URL redirects to <https://github.com/superdoc/docx-editor/issues/2879>. The issue text describes a ProseMirror tree. Do not apply it to the pinned V2 model.
- eigenpal viewport comments on main, not on the pin: <https://github.com/eigenpal/docx-editor/blob/main/packages/core/src/layout/viewport.ts>
- Docxodus README: <https://github.com/JSv4/Docxodus/blob/main/README.md>
- WordCraft README: <https://github.com/storytold/wordcraft/blob/main/README.md>
- canvas-editor README: <https://github.com/Hufe921/canvas-editor/blob/main/README.md>
- docs.plus README: <https://github.com/docs-plus/docs.plus>
- Apryse office-edit URL. On this date it redirected to <https://docs.apryse.com/> and did not return a DOCX-editor guide body: <https://docs.apryse.com/documentation/web/guides/office/edit>
- ProseMirror composition behavior, a framework note for the TipTap and ProseMirror lanes: <https://discuss.prosemirror.net/t/programmatically-start-compositionevent-with-prosemirror/4454>
- Yjs and ProseMirror composition sync, a framework issue, not a docs.plus measurement: <https://github.com/yjs/y-prosemirror/issues/81>

### Reference instruments and methods

These are not candidates.

- CodeMirror huge document: <https://codemirror.net/examples/million/>. Parsing is limited and stops when the editor is idle. No pinned editor in this trial uses CodeMirror.
- Typometer: <https://github.com/pavelfatin/typometer> and <https://pavelfatin.com/typometer/>. OS input and a single-pixel read. Synchronous and asynchronous modes. Prefers a stacking window manager. FreshPorts lists 1.0.1. Applicability to canvas, egui, and Wayland is unproven.
- VS Code performance tools: <https://github.com/microsoft/vscode/wiki/%5BDEV%5D-Perf-Tools-for-VS-Code-Development>. Startup Performance view and `--prof-startup`.
- vscode-perf README: <https://github.com/microsoft/vscode-perf>. The README describes a Node CLI and does not define a metric.
- LVCE memory benchmark README: <https://github.com/levivilet/lvce-memory-benchmark>. PSS, USS, RSS, cgroup current and peak, failed runs kept, edit/save probe explicitly not typing-to-paint. Subjects are other desktop editors and a 2600-byte text file.
- JOE editor-perf: <https://github.com/jhallen/joes-sandbox/blob/master/editor-perf/readme.md>. Manual, one laptop, CPU time, indirect launches handled differently. Not a modern ranking.
- microide README: <https://github.com/pablojimenezmateo/microide>. Isolated XDG directories, fixed seed, and an explicit statement that the numbers are not cross-editor comparisons.
- Jet README: <https://github.com/jet-editor/jet/blob/main/README.md>. The `blob/master` URL redirects there. Project-authored startup, RSS, search, and headless latency commands. Not independently run here. Not a DOCX editor. The README leaves the 2 GB Linux search cell unspecified.
- wasm-bindgen benchmarks: <https://wasm-bindgen.github.io/wasm-bindgen/benchmarks/> and <https://github.com/wasm-bindgen/wasm-bindgen/blob/main/benchmarks/README.md>. Boundary microbenchmarks, not an editor suite.
- wasm-bindgen reference types: <https://wasm-bindgen.github.io/wasm-bindgen/reference/reference-types.html>
- Criterion.rs analysis and command-line output: <https://criterion-rs.github.io/book/analysis.html> and <https://criterion-rs.github.io/book/user_guide/command_line_output.html>
- `std::hint::black_box`: <https://doc.rust-lang.org/std/hint/fn.black_box.html>. Best-effort benchmark barrier, not a correctness tool.
- Event Timing: <https://www.w3.org/TR/event-timing/>. Duration runs to the next rendering update, with 8 millisecond granularity. `wheel` and the other continuous events are excluded.
- Interaction to Next Paint: <https://web.dev/articles/inp>
- Paint Timing: <https://www.w3.org/TR/paint-timing/>
- Why a `requestAnimationFrame` callback is earlier than paint: <https://microsoftedge.github.io/MSEdgeExplainers/PerformanceMarkPaintTime/explainer.html>
- Measure Memory API: <https://wicg.github.io/performance-measure-memory/> and <https://web.dev/articles/monitor-total-page-memory-usage>
- Linux `drop_caches`: <https://www.kernel.org/doc/html/latest/admin-guide/sysctl/vm.html>
- Playwright trace modes, including the statement that `trace: 'on'` is performance heavy: <https://playwright.dev/docs/trace-viewer>
- Process memory terms used by the LVCE README: Linux proc and cgroup v2 documents linked from that README, <https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html>

### Not verified in this pass

- Divan, Tinybench, and iai-callgrind are named in the research brief. Their crate or package pages were not fetched. No plan in this set depends on their APIs. Tinybench, if a later plan adds it, is only for isolated synchronous JavaScript or model microbenchmarks and for controlled boundary calls. It is never a browser UI or Interaction to Next Paint clock. That later plan must pin the runner and keep an observable result checksum before it is introduced.
- Kalibera and Jones, and Georges, Buytaert, and Eeckhout, are the methodological background cited by the research brief. The papers were not re-fetched. The plans still require repeated trials, separate cold and warm distributions, and confidence intervals because those requirements are stated here as design rules.
- Apryse's current office-editor performance hooks. The guide URL did not yield a body.
- WordCraft collaboration. Absence from the architecture table is not a proof that no command exists. The adapter records `unverified` until a command-catalog probe runs.
- Whether Docen exposes a Leafer frame callback. Not found in the pages read. The visible clock for Docen is proposed as pixel or presented-frame evidence.

## Coverage matrix

The following sections copy the normative JSON fields. A drift between this text and the JSON fails `build/test_perf_plan_coverage.py`.

<!-- CRITERIA-BEGIN -->

### C01. cold/warm startup

**Measurement method:** Report three separate distributions: process-cold with a warm OS page cache, OS-cache-cold, and warm/steady after a fixed preconditioning script. Each distribution records process spawn, first contentful or first presented frame, input-ready, and quiescent. Do not publish one startup number.

**Tools:** fresh process and disposable profile; GNU time -v as a resource companion; OS page-cache drop only on a disposable dedicated host; editor-specific startup marks where a probe verifies them.

**Existing implementations:** No startup benchmark exists in this repository. Verified external references, not run here: microide cold_startup scenarios (explicitly not cross-editor); Jet cargo bench cold_start and jet --headless --quit (project-authored); VS Code --prof-startup and the Startup Performance view (VS Code only); vscode-perf is a Node CLI whose README does not define a metric.

**Comparability limitations:** Browser and Electron startups include runtime, GPU, and utility processes. Headless LibreOffice conversion is not an editor frame. Apryse startup performs a license request. SuperDoc's default worker startup timeout is 30 seconds and must be recorded. A container does not standardize GUI startup.

**Status:** proposed_harness. Plans: [`2026-11-05-perf-schema-and-outcomes.md`](../plans/2026-11-05-perf-schema-and-outcomes.md), [`2026-11-05-perf-statistics.md`](../plans/2026-11-05-perf-statistics.md), [`2026-11-05-perf-runner-and-artifacts.md`](../plans/2026-11-05-perf-runner-and-artifacts.md), [`2026-11-05-perf-scenarios-and-coverage.md`](../plans/2026-11-05-perf-scenarios-and-coverage.md), [`2026-11-07-full-browser-pixels-and-dedicated.md`](../plans/2026-11-07-full-browser-pixels-and-dedicated.md).

### C02. document loading/model construction

**Measurement method:** Time the editor's own load entry from the load call, or from the open command, until the in-memory model reports ready. Keep that interval on the model layer. It is not first paint and it is not usable.

**Tools:** adapter phase marks; Node perf_hooks or Rust Instant around the documented entry point; checksummed fixture bytes.

**Existing implementations:** This repository's round-trip drivers call import and export but do not publish load latency. JOE editor-perf recorded CPU time to load a file, jump, and exit; that is a different boundary and a 2016-era manual procedure.

**Comparability limitations:** Plate, docs.plus, and Fidus construct an HTML or schema model, not an OOXML tree. SuperDoc's headless SDK and its browser host are different loaders. Folio requires preloadFonts false for a DOM-free parse. office-open and the eigenpal store lane have no view.

**Status:** proposed_harness. Plans: [`2026-11-05-perf-schema-and-outcomes.md`](../plans/2026-11-05-perf-schema-and-outcomes.md), [`2026-11-05-perf-fixtures-and-parity.md`](../plans/2026-11-05-perf-fixtures-and-parity.md), [`2026-11-05-perf-adapters-and-quirks.md`](../plans/2026-11-05-perf-adapters-and-quirks.md), [`2026-11-05-perf-scenarios-and-coverage.md`](../plans/2026-11-05-perf-scenarios-and-coverage.md), [`2026-11-07-full-browser-pixels-and-dedicated.md`](../plans/2026-11-07-full-browser-pixels-and-dedicated.md).

### C03. first visible content/first usable state

**Measurement method:** Record first visible document text only when a document-specific paint target or an external pixel check shows text from the fixture. First-contentful-paint alone is not that evidence, because it marks the first contentful DOM element, which may be toolbar or shell text. Record first usable only when a scripted edit or caret move is accepted and becomes visible. Constructor return, model ready, and a requestAnimationFrame callback are separate marks and cannot satisfy either claim.

**Tools:** a document-specific paint target or pixel check that shows fixture text; Element Timing only when the observed element is fixture text; external pixel observation on a dedicated display; Playwright only to drive the scenario, not as the latency clock.

**Existing implementations:** No first-usable benchmark exists in this repository. Report C waited for each UI's own ready signal and then took a screenshot; that is a fidelity capture, not a latency distribution. Typometer observes a pixel after a keystroke, which is a related but different interval. microide documents large_file_open_first_paint as advisory, not a gated cross-editor number.

**Comparability limitations:** Canvas, Leafer, egui, and WebGL surfaces do not emit DOM first-contentful-paint for document text. A blank shell can paint before document text. Virtualized editors can show a window before the rest of the model exists.

**Status:** proposed_harness. Plans: [`2026-11-05-perf-schema-and-outcomes.md`](../plans/2026-11-05-perf-schema-and-outcomes.md), [`2026-11-05-perf-measurement-layers.md`](../plans/2026-11-05-perf-measurement-layers.md), [`2026-11-05-perf-scenarios-and-coverage.md`](../plans/2026-11-05-perf-scenarios-and-coverage.md), [`2026-11-07-full-browser-pixels-and-dedicated.md`](../plans/2026-11-07-full-browser-pixels-and-dedicated.md).

### C04. deferred work

**Measurement method:** After first usable, sample CPU, process-tree memory, and editor-specific quiescence until a predeclared idle condition holds or a timeout fires. Publish the tail separately from first usable. A timeout is a failed or unfinished outcome, not a quiet editor.

**Tools:** process-tree CPU and memory sampler; main-thread long tasks in Chromium; editor progress or worker-ready probes when the adapter has verified them.

**Existing implementations:** No deferred-work sampler exists in this repository. CodeMirror's huge-document example and Marijn Haverbeke's forum replies document a parser that stops when idle and catches up later; none of the pinned editors uses CodeMirror. SuperDoc's current large-document guide describes a page window and a worker, which is a product control, not a measurement.

**Comparability limitations:** Editors that index, proof, or paginate in the background look faster at first usable and more expensive in the tail. Disabling that work without recording it changes the feature profile.

**Status:** proposed_harness. Plans: [`2026-11-05-perf-runner-and-artifacts.md`](../plans/2026-11-05-perf-runner-and-artifacts.md), [`2026-11-05-perf-scenarios-and-coverage.md`](../plans/2026-11-05-perf-scenarios-and-coverage.md), [`2026-11-07-full-browser-pixels-and-dedicated.md`](../plans/2026-11-07-full-browser-pixels-and-dedicated.md).

### C05. single-edit responsiveness

**Measurement method:** For one committed insertion at a named document position, publish input-to-visible-update only when paint is proved by a presented frame, a screenshot or pixel check of that edit, or a requestAnimationFrame callback followed by a later frame or paint entry in the same trace. A requestAnimationFrame callback alone is not paint. Event Timing is a censored companion: install the observer before input, and a requested durationThreshold below 16 milliseconds is raised to 16 milliseconds. Duration is rounded to 8 milliseconds. buffered true does not recover entries already dropped under the default 104 millisecond buffer. A trusted input with no entry is censored, kept in the sample, and never written as 0. Page-lifetime INP groups events that share a nonzero interactionId. keydown, input, and keyup are not separate interactions. Handler duration and model-mutation duration stay on the model layer. An unrelated paint or a deferred editor render does not complete the edit.

**Tools:** Event Timing observer installed before input, with durationThreshold not below 16 milliseconds, as a censored companion; presented frame, screenshot, or pixel check that the edit is visible; requestAnimationFrame only when the same trace shows a later frame or paint; adapter model marks.

**Existing implementations:** No single-edit latency harness exists in this repository. Typometer's synchronous mode measures keystroke to a pixel change for a period character. Slate's performance guide discusses Interaction to Next Paint while typing; that is guidance for Slate hosts, and Plate's measured DOCX harness does not enable Slate chunking. LVCE's memory benchmark explicitly says its edit probe is not typing-to-paint latency.

**Comparability limitations:** Event Timing duration is rounded to 8 milliseconds. The minimum durationThreshold is 16 milliseconds, and the default buffer keeps only durations of at least 104 milliseconds, so a fast edit can be censored. Canvas and egui input targets can emit Event Timing entries, and those entries do not prove the canvas or egui pixels changed. An IME composition is not a committed insert.

**Status:** proposed_harness. Plans: [`2026-11-05-perf-measurement-layers.md`](../plans/2026-11-05-perf-measurement-layers.md), [`2026-11-05-perf-scenarios-and-coverage.md`](../plans/2026-11-05-perf-scenarios-and-coverage.md), [`2026-11-07-full-browser-pixels-and-dedicated.md`](../plans/2026-11-07-full-browser-pixels-and-dedicated.md).

### C06. sustained typing/bursts

**Measurement method:** Drive a fixed character sequence at a declared rate and, separately, a burst with no per-key wait. Record the per-edit visible latency distribution, the worst one-second window, and dropped or late frames. Each published edit needs the same paint proof as a single edit. Aggregate Interaction to Next Paint by grouping events that share a nonzero interactionId, and keep that page-lifetime value separate from the per-edit distribution. Censored Event Timing entries stay in the sample and are not zeros. Do not summarize the run as average frames per second.

**Tools:** Typometer asynchronous mode where a glyph pixel is a valid probe; Event Timing samples for DOM editors; frame timestamps from the compositor or the native renderer.

**Existing implementations:** Typometer documents an asynchronous mode for rapid typing when drawing lags by multiple characters. microide has typing_small_file and typing_large_file for its own regression gates. Jet documents --bench-latency as a headless keystroke simulation. None of these was run on a trial editor.

**Comparability limitations:** Typometer's single-pixel probe assumes a stable glyph advance and a framebuffer it can read. Burst input overruns editors that coalesce input, so the scenario must say whether coalescing counts as one paint or as lost keystrokes. AutoCorrect and proofing change the work.

**Status:** proposed_harness. Plans: [`2026-11-05-perf-fixtures-and-parity.md`](../plans/2026-11-05-perf-fixtures-and-parity.md), [`2026-11-05-perf-scenarios-and-coverage.md`](../plans/2026-11-05-perf-scenarios-and-coverage.md), [`2026-11-07-full-browser-pixels-and-dedicated.md`](../plans/2026-11-07-full-browser-pixels-and-dedicated.md).

### C07. cursor/selection/hit testing

**Measurement method:** Time a pointer or keyboard selection at the start, middle, and end of the fixture until the caret or selection is both in the model and visibly updated. Check the resolved document position against the fixture coordinate. A hit that returns the wrong position fails correctness and is not a publishable latency.

**Tools:** Playwright mouse and keyboard for DOM and canvas hosts; WordCraft layout hit testing through its command channel when that command is probed; model selection readback.

**Existing implementations:** No hit-test benchmark exists in this repository. WordCraft's README architecture table lists hit testing in wordcraft-layout. eigenpal's current main branch has a viewport materializer that pins caret and selection pages; that file was read on main, not on the trial pin.

**Comparability limitations:** contenteditable, ProseMirror, canvas, and egui resolve hits in different coordinate spaces. office-open has no editor UI, so this scenario is not applicable on that lane. A DOM-free server lane can report model selection and must not claim a visible caret.

**Status:** proposed_harness. Plans: [`2026-11-05-perf-adapters-and-quirks.md`](../plans/2026-11-05-perf-adapters-and-quirks.md), [`2026-11-05-perf-scenarios-and-coverage.md`](../plans/2026-11-05-perf-scenarios-and-coverage.md), [`2026-11-07-full-browser-pixels-and-dedicated.md`](../plans/2026-11-07-full-browser-pixels-and-dedicated.md).

### C08. clipboard/bulk editing

**Measurement method:** Time paste and delete of declared payloads (plain text, and styled text where the editor supports it) at the start, middle, and end. Record model completion and visible completion separately, plus the resulting document size and memory delta.

**Tools:** synthetic clipboard where the platform allows it; adapter paste command; whole-process memory sampler.

**Existing implementations:** No clipboard benchmark exists in this repository. WordCraft's README lists clipboard with formatting. Docxodus documents DocxSession mutations and a browser editor. Those are feature claims, not timings.

**Comparability limitations:** Operating-system clipboards, browser clipboard permissions, and headless lanes do not share a clock. A model-only paste is not a visible paste. Editors that flatten styled paste must record that feature loss.

**Status:** proposed_harness. Plans: [`2026-11-05-perf-fixtures-and-parity.md`](../plans/2026-11-05-perf-fixtures-and-parity.md), [`2026-11-05-perf-scenarios-and-coverage.md`](../plans/2026-11-05-perf-scenarios-and-coverage.md), [`2026-11-07-full-browser-pixels-and-dedicated.md`](../plans/2026-11-07-full-browser-pixels-and-dedicated.md).

### C09. undo/redo

**Measurement method:** After a declared history of N edits, time undo and redo until the document text and the visible viewport match the expected snapshot. Repeat at more than one history depth. Record history memory separately from command latency.

**Tools:** editor undo command; text and viewport oracle; process-tree memory.

**Existing implementations:** No undo benchmark exists in this repository. Docxodus's README describes bounded undo and redo on DocxSession. ProseMirror-history is the usual mechanism for TipTap and ProseMirror editors; this pass did not read each editor's history plugin configuration.

**Comparability limitations:** Bounded histories drop old entries. An undo that restores text but not the caret fails the visible check. Headless lanes can time model undo only.

**Status:** proposed_harness. Plans: [`2026-11-05-perf-scenarios-and-coverage.md`](../plans/2026-11-05-perf-scenarios-and-coverage.md), [`2026-11-05-perf-adapters-and-quirks.md`](../plans/2026-11-05-perf-adapters-and-quirks.md), [`2026-11-07-full-browser-pixels-and-dedicated.md`](../plans/2026-11-07-full-browser-pixels-and-dedicated.md).

### C10. scrolling/viewport

**Measurement method:** Scroll by keyboard, wheel, and a jump to a named offset. Record frame-time distribution and the count of frames later than the display period. First result of a jump is time to the correct visible content, not time to the scroll event handler.

**Tools:** frame timestamps; external capture on a dedicated display; Playwright as the input driver.

**Existing implementations:** No scroll benchmark exists in this repository. Event Timing excludes wheel, touchmove, and pointermove, so it is not the scroll clock. SuperDoc documents a default five-page window with one overscan page. Slate documents content-visibility and experimental chunking for off-screen DOM.

**Comparability limitations:** Average frames per second hides stalls. Software rendering and GPU rendering are different experiments. Canvas virtualization and DOM virtualization mount different amounts of work. office-open has no viewport.

**Status:** proposed_harness. Plans: [`2026-11-05-perf-measurement-layers.md`](../plans/2026-11-05-perf-measurement-layers.md), [`2026-11-05-perf-scenarios-and-coverage.md`](../plans/2026-11-05-perf-scenarios-and-coverage.md), [`2026-11-07-full-browser-pixels-and-dedicated.md`](../plans/2026-11-07-full-browser-pixels-and-dedicated.md).

### C11. initial layout/pagination

**Measurement method:** For editors with a page model, time open until the first page's text is visible and, separately, until the reported page count is stable. Record the page count. For editors whose product is a continuous flow, mark page-count latency not applicable and still time first-page-equivalent visible text if a flow exists.

**Tools:** page-count readback; paint or pixel evidence of first-page text; WordCraft wordcraft-cli info only as a layout-count probe, not as the interactive UI.

**Existing implementations:** Report C records page counts for the fidelity corpus. It is not a timing study. The trial text says nothing in that fidelity pass measured page geometry as a performance result. WordCraft's README claims on-demand page render and a 1.4 millisecond relayout figure; that figure is a project claim and was not reproduced here.

**Comparability limitations:** Plate, docs.plus, and Fidus Writer are continuous flows in Report C. office-open has no page model. canvas-editor claims pagination, but on the fidelity corpus the UI showed a header and footer and then threw. A missing page count after a crash is a failure, not zero milliseconds and not zero pages.

**Status:** proposed_harness. Plans: [`2026-11-05-perf-adapters-and-quirks.md`](../plans/2026-11-05-perf-adapters-and-quirks.md), [`2026-11-05-perf-scenarios-and-coverage.md`](../plans/2026-11-05-perf-scenarios-and-coverage.md), [`2026-11-07-full-browser-pixels-and-dedicated.md`](../plans/2026-11-07-full-browser-pixels-and-dedicated.md).

### C12. incremental reflow

**Measurement method:** Insert or delete a small span at the start, middle, and end, and time until layout marks that are dirty because of that edit have been resolved and the viewport is visibly updated. Record how many blocks or pages the editor reports as invalidated.

**Tools:** model dirty-region readback where an adapter probe finds it; visible viewport oracle; separate model and paint marks.

**Existing implementations:** No reflow benchmark exists in this repository. SuperDoc issue 2879 is closed as a duplicate. Its April 2026 text describes a ProseMirror tree and a synchronous first layout. The fidelity report says the pinned V2 surface is not that ProseMirror editor, so the issue is an upstream report about an earlier architecture, not a measurement of the pinned V2 model. Docxodus's README claims only the changed block re-renders and gives a millisecond range; that is a project claim.

**Comparability limitations:** Editors that always reflow the whole document can still update one screen quickly. Invalidation counts are comparable only when the unit (block, paragraph, page) is declared. A flow editor and a page editor do not share that unit.

**Status:** proposed_harness. Plans: [`2026-11-05-perf-scenarios-and-coverage.md`](../plans/2026-11-05-perf-scenarios-and-coverage.md), [`2026-11-05-perf-measurement-layers.md`](../plans/2026-11-05-perf-measurement-layers.md), [`2026-11-07-full-browser-pixels-and-dedicated.md`](../plans/2026-11-07-full-browser-pixels-and-dedicated.md).

### C13. global invalidation

**Measurement method:** Apply one edit that must change later layout or style state, such as a style change at the start or a paragraph inserted before a table of contents, and time until the far end of the document is consistent. Record both the viewport update and whole-document completion.

**Tools:** fixture with a sentinel at the end; model consistency check; paint check of the sentinel if the scenario scrolls there.

**Existing implementations:** JOE's editor-perf rehighlight procedure changes the start of an XML file and observes work at the end. It is a manual code-editor procedure, not a DOCX measurement. No global-invalidation benchmark exists in this repository.

**Comparability limitations:** An editor that does not update off-screen state until scroll will look faster if only the viewport is timed. The scenario must name which of the two clocks is the published one, and it must record the other.

**Status:** proposed_harness. Plans: [`2026-11-05-perf-fixtures-and-parity.md`](../plans/2026-11-05-perf-fixtures-and-parity.md), [`2026-11-05-perf-scenarios-and-coverage.md`](../plans/2026-11-05-perf-scenarios-and-coverage.md), [`2026-11-07-full-browser-pixels-and-dedicated.md`](../plans/2026-11-07-full-browser-pixels-and-dedicated.md).

### C14. large-document scaling

**Measurement method:** Repeat open, jump, edit, and scroll across a size ladder whose shapes are declared: many short paragraphs, long paragraphs, one enormous paragraph, mixed Unicode, and a paginated equivalent. Report each shape separately. Record large-file modes that disable features.

**Tools:** generated fixtures with checksums; the same scenario runner as the small-document runs; memory sampler.

**Existing implementations:** No large-document performance ladder exists in this repository. The fidelity corpus is one small adversarial DOCX, not a size ladder. Jet documents lazy mmap and a visible window for multi-gigabyte text files; those results are project-authored and are not DOCX results. CodeMirror's huge-document demo shows viewport rendering with deferred parsing and is not a candidate.

**Comparability limitations:** A 100 megabyte file of short paragraphs and a 100 megabyte file of one paragraph are different workloads. Virtualization can keep memory flat while a jump or an edit is still global. Feature fallback must be visible in the row.

**Status:** proposed_harness. Plans: [`2026-11-05-perf-fixtures-and-parity.md`](../plans/2026-11-05-perf-fixtures-and-parity.md), [`2026-11-05-perf-scenarios-and-coverage.md`](../plans/2026-11-05-perf-scenarios-and-coverage.md), [`2026-11-07-full-browser-pixels-and-dedicated.md`](../plans/2026-11-07-full-browser-pixels-and-dedicated.md).

### C15. search/replace/indexing

**Measurement method:** Time literal and regular-expression search to the first match and to completion, then time replace-all, on fixtures with a declared match count. If an index is built in the background, time index quiescence separately from the query.

**Tools:** editor find command; match-count oracle; CPU and allocation samples on the diagnostic run.

**Existing implementations:** No search benchmark exists in this repository. microide gates its own search and file-finder scenarios and says they are not cross-editor numbers. Jet documents SIMD literal search and a --search flag; the README leaves a 2 gigabyte Linux cell unspecified and the numbers are project-authored. Docxodus documents OpenXmlRegex as a library API.

**Comparability limitations:** Interactive find, a library scan, and a background index are different products. Pathological regular expressions need a fuel or time budget so one editor cannot pin the host. A search that misses a known match fails correctness.

**Status:** proposed_harness. Plans: [`2026-11-05-perf-fixtures-and-parity.md`](../plans/2026-11-05-perf-fixtures-and-parity.md), [`2026-11-05-perf-scenarios-and-coverage.md`](../plans/2026-11-05-perf-scenarios-and-coverage.md), [`2026-11-07-full-browser-pixels-and-dedicated.md`](../plans/2026-11-07-full-browser-pixels-and-dedicated.md).

### C16. serialization/save/export

**Measurement method:** Time the save or export command until the editor is interactive again, and separately until the replacement bytes are re-readable. Label that second clock durable only when both the replacement data and its directory entry have been synced. If the save path cannot expose that guarantee, label the clock re-readable. A reopened checksum and filesystem timestamps are supporting evidence, not durability by themselves. Record byte count, checksum, and whether the write is a full regeneration or a selective save.

**Tools:** editor save entry point already used by the fidelity harness; file-data sync and directory sync when the platform exposes both; re-open checksum as a re-readable check, not as durability by itself.

**Existing implementations:** The fidelity harness writes an output DOCX and scores it. It does not publish save latency. GenOffice's CLI refuses docx-to-docx; its editor save path is the one the trial called. Apryse saves through getFileData and a trial key stamps a watermark picture.

**Comparability limitations:** Selective save, HTML regeneration, and WASM serialization do not do the same work. A watermark or a template adds bytes. Interactive-again, re-readable, and durable (data and directory synced) are different clocks and each must be labeled.

**Status:** proposed_harness. Plans: [`2026-11-05-perf-adapters-and-quirks.md`](../plans/2026-11-05-perf-adapters-and-quirks.md), [`2026-11-05-perf-scenarios-and-coverage.md`](../plans/2026-11-05-perf-scenarios-and-coverage.md), [`2026-11-07-full-browser-pixels-and-dedicated.md`](../plans/2026-11-07-full-browser-pixels-and-dedicated.md).

### C17. memory footprint

**Measurement method:** Sample the whole process tree. On Linux record summed RSS, PSS, and USS from smaps_rollup, plus cgroup memory.current and memory.peak when the editor was launched inside a cgroup. Sample idle, after open, after edit, at peak, and after close. One PID is not the result. Browser attribution is a separate record and is not added to RSS. performance.measureUserAgentSpecificMemory is that page estimate only when the page is cross-origin isolated. performance.memory.usedJSHeapSize is diagnostic only. CDP Memory.getDOMCounters reports documents, nodes, and listeners, not detached-node counts. A HeapProfiler snapshot is the detached-node check. Each exposed WASM memory.buffer contributes its byteLength as capacity, refreshed after growth.

**Tools:** Linux /proc/<pid>/smaps_rollup; cgroup v2 memory.current and memory.peak; a process-tree walk; performance.measureUserAgentSpecificMemory only when cross-origin isolated; performance.memory.usedJSHeapSize on a diagnostic run only; CDP Memory.getDOMCounters for documents, nodes, and listeners; CDP HeapProfiler for detached nodes; WASM memory.buffer byteLength as capacity.

**Existing implementations:** No memory harness exists in this repository. LVCE's memory benchmark, README read on 2026-11-05, records PSS, USS, RSS, cgroup current and peak, rejects incomplete process-group snapshots, and does not turn a failed run into zero memory. It measures other desktop editors on a 2600-byte text file under Xvfb, not these DOCX editors. menzew/memoryfootprint is another process-tree tool and was not integrated.

**Comparability limitations:** RSS double-counts shared pages. Cgroup memory includes file cache charged to the group. usedJSHeapSize is not whole-page memory. measureUserAgentSpecificMemory can wait for garbage collection and is not a cheap timing sample. memory.buffer byteLength is capacity, not live allocations, and an inaccessible proprietary or worker memory stays unverified rather than zero. These figures are not added together. GPU memory is outside RSS unless the platform exposes it.

**Status:** proposed_harness. Plans: [`2026-11-05-perf-runner-and-artifacts.md`](../plans/2026-11-05-perf-runner-and-artifacts.md), [`2026-11-05-perf-scenarios-and-coverage.md`](../plans/2026-11-05-perf-scenarios-and-coverage.md), [`2026-11-07-full-browser-pixels-and-dedicated.md`](../plans/2026-11-07-full-browser-pixels-and-dedicated.md).

### C18. allocation/GC

**Measurement method:** On a diagnostic run, record allocation volume and garbage-collection or allocator pause samples correlated with the interaction timestamps. Do not add this instrumentation to the low-overhead timing run. Publish pause count, total pause, p95, p99, and maximum.

**Tools:** Chromium trace GC events on a diagnostic run; Node perf_hooks only if the lane is Node; .NET and Rust allocator statistics where a probe exists; Linux perf or heap profilers on diagnostic runs.

**Existing implementations:** No GC benchmark exists in this repository. Chrome's trace format and the Measure Memory API were read as platform documents. They were not captured against a trial editor.

**Comparability limitations:** Rust editors do not have a JavaScript garbage collector; report allocator behavior instead of inventing a GC pause. Forcing a collection changes the timing run, so it stays on the diagnostic lane. Browser traces add overhead, which Playwright documents for trace: 'on'.

**Status:** proposed_harness. Plans: [`2026-11-05-perf-runner-and-artifacts.md`](../plans/2026-11-05-perf-runner-and-artifacts.md), [`2026-11-05-perf-measurement-layers.md`](../plans/2026-11-05-perf-measurement-layers.md), [`2026-11-05-perf-scenarios-and-coverage.md`](../plans/2026-11-05-perf-scenarios-and-coverage.md), [`2026-11-07-full-browser-pixels-and-dedicated.md`](../plans/2026-11-07-full-browser-pixels-and-dedicated.md).

### C19. disposal/reopen

**Measurement method:** Close the document, wait a declared interval, and record retained process-tree memory and whether the UI accepts a new open. Then reopen the same fixture and time first usable again. A process that exits can be recorded as reclaimed; a hang is a failure. On a diagnostic run, a HeapProfiler check looks for detached nodes after dispose. A deliberately retained detached subtree is the red case. Released references and zero detached nodes from that fixture are the green case. That check is not part of the timing run.

**Tools:** process-tree sampler at 1, 5, and 30 seconds after close; a second open scenario; editor dispose or session.close where that API exists; CDP HeapProfiler detached-node check on a diagnostic run.

**Existing implementations:** Docxodus's harness calls session.close after save. That call is a fidelity step, not a retention series. LVCE stops the measured service in cleanup and does not report a 30-second retention curve for DOCX editors.

**Comparability limitations:** Browser tabs retain JIT code and caches after a document close. WASM linear memory may not shrink after dispose. A headless process that exits has a different residual than a long-lived UI.

**Status:** proposed_harness. Plans: [`2026-11-05-perf-scenarios-and-coverage.md`](../plans/2026-11-05-perf-scenarios-and-coverage.md), [`2026-11-05-perf-runner-and-artifacts.md`](../plans/2026-11-05-perf-runner-and-artifacts.md), [`2026-11-07-full-browser-pixels-and-dedicated.md`](../plans/2026-11-07-full-browser-pixels-and-dedicated.md).

### C20. long-session stability

**Measurement method:** Run a scripted edit, scroll, save, and idle cycle for a declared duration of at least one hour on a dedicated host. Compare visible latency and process-tree memory at the start and end of the session. Keep every sample. A crash or an unbounded growth rule declared in the scenario is a failure.

**Tools:** the scenario runner in a loop; process-tree sampler; a watchdog that does not kill a slow-but-live editor before the declared timeout.

**Existing implementations:** microide lists long_soak_8h and idle_soak_30s for its own app. Those gates were not run here and are not comparable. This repository has no soak test.

**Comparability limitations:** A one-hour soak is not comparable to a 30-second idle assertion. Host sleep, thermal throttling, and automatic updates invalidate the run and must be recorded as not_run with a host reason. This scenario is dedicated-host only.

**Status:** proposed_harness. Plans: [`2026-11-05-perf-runner-and-artifacts.md`](../plans/2026-11-05-perf-runner-and-artifacts.md), [`2026-11-05-perf-scenarios-and-coverage.md`](../plans/2026-11-05-perf-scenarios-and-coverage.md), [`2026-11-07-full-browser-pixels-and-dedicated.md`](../plans/2026-11-07-full-browser-pixels-and-dedicated.md).

### C21. CPU/background interference

**Measurement method:** During idle, typing, and scrolling, sample CPU time for the whole process tree and, on a diagnostic run, attribute it to editor threads versus known helpers. A separate controlled interference run adds one declared CPU-bound process and reports the delta. The quiet dedicated-host run remains the primary result.

**Tools:** process-tree CPU seconds; Linux perf stat on diagnostic runs; a declared interference fixture.

**Existing implementations:** The fidelity sandbox records that hostile-package runs have CPU budgets. That is a safety limit, not an interactive CPU profile. VS Code's performance documents separate extension-host cost from editor cost; those documents apply to VS Code, not to these products, except as a method analogy.

**Comparability limitations:** Pinning a multithreaded GUI to one core changes the product. perf stat counters depend on kernel permissions. A noisy CI runner cannot publish this delta. Background proofing and AI panels must be named in the feature profile.

**Status:** proposed_harness. Plans: [`2026-11-05-perf-runner-and-artifacts.md`](../plans/2026-11-05-perf-runner-and-artifacts.md), [`2026-11-05-perf-fixtures-and-parity.md`](../plans/2026-11-05-perf-fixtures-and-parity.md), [`2026-11-05-perf-scenarios-and-coverage.md`](../plans/2026-11-05-perf-scenarios-and-coverage.md), [`2026-11-07-full-browser-pixels-and-dedicated.md`](../plans/2026-11-07-full-browser-pixels-and-dedicated.md).

### C22. feature/extension overhead

**Measurement method:** Run the same scenario at feature profiles P0, P1, P2, and P3. Publish absolute and relative deltas for startup, typing, scrolling, save, idle CPU, and memory. P3 includes one intentionally busy extension or panel so the harness can attribute interference.

**Tools:** declared feature profiles; the same clocks as the baseline scenario; per-helper CPU and RSS when the helper is a separate process.

**Existing implementations:** No profile matrix exists in this repository. The fidelity harness uses each project's suggested import configuration, which is a correctness configuration, not P0. VS Code documents extension bisect and startup profiling for its own host. microide redirects XDG directories so user configuration cannot leak in; that isolation pattern is applicable, the numbers are not.

**Comparability limitations:** Products do not have the same plugins. P2 means a realistic set for that product, listed by name, not a pretence that every editor loads the same code. A built-in proofing pass is a feature even when it is not an extension.

**Status:** proposed_harness. Plans: [`2026-11-05-perf-fixtures-and-parity.md`](../plans/2026-11-05-perf-fixtures-and-parity.md), [`2026-11-05-perf-adapters-and-quirks.md`](../plans/2026-11-05-perf-adapters-and-quirks.md), [`2026-11-05-perf-scenarios-and-coverage.md`](../plans/2026-11-05-perf-scenarios-and-coverage.md), [`2026-11-07-full-browser-pixels-and-dedicated.md`](../plans/2026-11-07-full-browser-pixels-and-dedicated.md).

### C23. collaboration

**Measurement method:** With two local clients and a local relay, time a remote insert until it is visible on the second client, and time a concurrent overlapping edit until both clients converge. Record relay CPU and whether intermediate IME text is broadcast. Editors without a verified collaboration surface produce unverified or not_applicable, never zero milliseconds.

**Tools:** a local Yjs or Hocuspocus fixture for editors that document that stack; two browser contexts; convergence oracle on plain text.

**Existing implementations:** No collaboration benchmark exists in this repository. docs.plus documents Hocuspocus and Yjs. Plate documents a Yjs plugin. canvas-editor documents an experimental feature/CRDT branch that is not the pinned main commit. SuperDoc's current performance guide says to measure collaboration; the trial report found no V2 ProseMirror editor. WordCraft's README architecture table read on 2026-11-05 does not list a collaboration crate.

**Comparability limitations:** A full docs.plus deployment needs PostgreSQL, Redis, and Bun; the model conversion path does not. Those are different scenarios. ProseMirror commits composition updates before compositionend, so an IME collaboration result must say whether intermediates were included. A WAN test is a different experiment from localhost.

**Status:** proposed_harness. Plans: [`2026-11-05-perf-adapters-and-quirks.md`](../plans/2026-11-05-perf-adapters-and-quirks.md), [`2026-11-05-perf-scenarios-and-coverage.md`](../plans/2026-11-05-perf-scenarios-and-coverage.md), [`2026-11-07-full-browser-pixels-and-dedicated.md`](../plans/2026-11-07-full-browser-pixels-and-dedicated.md).

### C24. Rust/TS/WASM overhead

**Measurement method:** Keep four layers separate: native Rust, TypeScript or JavaScript, the host/WASM boundary, and the full editor scenario. The boundary menu is compile and instantiate, an empty call, a scalar call, a string conversion, a typed-array transfer, a batched call, and memory.grow. Each operation has its own capability flag. A closed or proprietary lane such as Apryse stores null and unverified for an operation it cannot call, and that null does not reject a host-visible initialization sample. A wasm-bindgen reference fixture may enable every flag. An SDK call that also edits the document is not a boundary sample. Compare a batch with the same work only when both sides share the capability.

**Tools:** Criterion.rs for native Rust microbenchmarks, with std::hint::black_box; wasm-bindgen's own boundary benchmarks as a method reference; browser Performance.now around instantiate and call; the editor scenario clocks from the other criteria.

**Existing implementations:** No WASM boundary suite exists in this repository. wasm-bindgen publishes JS, raw Wasm, and wasm-bindgen microbenchmarks and states they are not a general WebAssembly performance suite. WordCraft is Rust with a native egui UI and a wasm32 browser target. Docxodus and Apryse ship WebAssembly office engines. Plate, the ProseMirror editors, and canvas-editor are TypeScript.

**Comparability limitations:** A native Criterion time is not a browser frame time. wasm-bindgen reference types change the glue and must be recorded, and Docxodus .NET glue is not that reference fixture. Apryse at npm 12.2.1 is closed source, so empty, scalar, string, typed-array, batched, and memory.grow calls stay null unless a probe can actually invoke them. Docxodus WASM initialization is not document load. black_box is a best-effort optimization barrier, not a correctness tool.

**Status:** proposed_harness. Plans: [`2026-11-05-perf-measurement-layers.md`](../plans/2026-11-05-perf-measurement-layers.md), [`2026-11-05-perf-scenarios-and-coverage.md`](../plans/2026-11-05-perf-scenarios-and-coverage.md), [`2026-11-07-full-browser-pixels-and-dedicated.md`](../plans/2026-11-07-full-browser-pixels-and-dedicated.md).

<!-- CRITERIA-END -->

## Interpretation conditions

<!-- CONDITIONS-BEGIN -->

### I01. Unicode correctness prerequisite

Where the editor claims text editing, a scenario that publishes latency must also check a declared Unicode fixture. A wrong result is a correctness failure and is not publishable as responsiveness. An editor that does not claim the operation records unsupported or not_applicable.

Plans: [`2026-11-05-perf-fixtures-and-parity.md`](../plans/2026-11-05-perf-fixtures-and-parity.md), [`2026-11-05-perf-scenarios-and-coverage.md`](../plans/2026-11-05-perf-scenarios-and-coverage.md).

### I02. emoji and grapheme-cluster correctness prerequisite

Caret movement and backspace across the family sequence U+1F468 U+200D U+1F469 U+200D U+1F467 U+200D U+1F466 must move by one grapheme. That sequence is 11 UTF-16 code units and one grapheme. A skin-tone thumbs-up is a separate one-grapheme check. A readback that moves by one UTF-16 unit fails correctness and is not publishable. Do not score a failed caret as zero milliseconds.

Plans: [`2026-11-05-perf-fixtures-and-parity.md`](../plans/2026-11-05-perf-fixtures-and-parity.md), [`2026-11-05-perf-scenarios-and-coverage.md`](../plans/2026-11-05-perf-scenarios-and-coverage.md).

### I03. bidirectional text correctness prerequisite

A mixed Arabic and Latin paragraph is checked for stored order and for a hit or caret that the editor claims. Visual order and logical order are both recorded. Failure blocks publication of that scenario's latency.

Plans: [`2026-11-05-perf-fixtures-and-parity.md`](../plans/2026-11-05-perf-fixtures-and-parity.md), [`2026-11-05-perf-scenarios-and-coverage.md`](../plans/2026-11-05-perf-scenarios-and-coverage.md).

### I04. IME composition correctness prerequisite

Where an editor accepts composition, record compositionstart, compositionupdate, and compositionend or cancel separately from the committed string. The committed fixture is 地. Intermediate di is not a committed insert. Playwright insertText, fill, and a dispatched CompositionEvent are synthetic contract tests, not OS IME coverage. OS IME coverage is a Chromium CDP IME route or a dedicated-host native IME probe. A wrong readback blocks publication. Editors with no composition path record unverified or unsupported after a probe, not zero.

Plans: [`2026-11-05-perf-fixtures-and-parity.md`](../plans/2026-11-05-perf-fixtures-and-parity.md), [`2026-11-05-perf-adapters-and-quirks.md`](../plans/2026-11-05-perf-adapters-and-quirks.md), [`2026-11-05-perf-scenarios-and-coverage.md`](../plans/2026-11-05-perf-scenarios-and-coverage.md).

### I05. explicit workload profile

Every trial names a workload profile id, fixture checksum, byte size, paragraph shape, Unicode class, and match count where search is involved. Results from different profiles are not merged.

Plans: [`2026-11-05-perf-fixtures-and-parity.md`](../plans/2026-11-05-perf-fixtures-and-parity.md), [`2026-11-05-perf-runner-and-artifacts.md`](../plans/2026-11-05-perf-runner-and-artifacts.md).

### I06. feature parity and large-file mode

Every trial names a feature profile. If the editor disables highlighting, proofing, pagination, collaboration, or another named feature for a large file, the trial records that fallback. The row is not compared as if the feature had remained on.

Plans: [`2026-11-05-perf-fixtures-and-parity.md`](../plans/2026-11-05-perf-fixtures-and-parity.md), [`2026-11-05-perf-adapters-and-quirks.md`](../plans/2026-11-05-perf-adapters-and-quirks.md).

### I07. unsupported versus zero

unsupported, not_applicable, unverified, failed, and not_run store null latency. A measured zero is allowed only for a real empty interval that the clock observed, and the sample list is still present. Null is never rendered as 0 ms.

Plans: [`2026-11-05-perf-schema-and-outcomes.md`](../plans/2026-11-05-perf-schema-and-outcomes.md), [`2026-11-05-perf-adapters-and-quirks.md`](../plans/2026-11-05-perf-adapters-and-quirks.md).

### I08. timing boundaries

A requestAnimationFrame callback must not claim visible paint. Constructor completion must not claim usability. Internal model time must not claim user-visible latency. Each published latency names exactly one boundary.

Plans: [`2026-11-05-perf-schema-and-outcomes.md`](../plans/2026-11-05-perf-schema-and-outcomes.md), [`2026-11-05-perf-measurement-layers.md`](../plans/2026-11-05-perf-measurement-layers.md).

### I09. cold and warm definitions

process_cold_fs_warm, os_cache_cold, and warm_steady are different cache states. A summary that mixes them is rejected. OS-cache-cold is legal only on a dedicated disposable host that has recorded a page-cache drop.

Plans: [`2026-11-05-perf-statistics.md`](../plans/2026-11-05-perf-statistics.md), [`2026-11-05-perf-runner-and-artifacts.md`](../plans/2026-11-05-perf-runner-and-artifacts.md).

### I10. distributions, uncertainty, and independent repetitions

A publishable summary includes sample count, median, p90, p95, p99, median absolute deviation, a 95 percent confidence interval, minimum, and maximum. Outliers stay in the sample. The repetition unit is fresh_process or in_process_iteration, and GUI scenarios that publish latency use fresh_process.

Plans: [`2026-11-05-perf-statistics.md`](../plans/2026-11-05-perf-statistics.md).

### I11. low-overhead timing versus diagnostic profiling

A timing run records clocks and cheap resource samples. A diagnostic run may attach traces, perf, or allocation profilers and cannot be published as the timing distribution. Playwright trace mode on is diagnostic because the project documents it as performance heavy.

Plans: [`2026-11-05-perf-runner-and-artifacts.md`](../plans/2026-11-05-perf-runner-and-artifacts.md), [`2026-11-05-perf-measurement-layers.md`](../plans/2026-11-05-perf-measurement-layers.md).

### I12. failures remain outcomes

Timeout, crash, out of memory, correctness miss, and feature fallback remain rows with reasons. They are not dropped, not imputed, and not written as zero. A harness failure before the editor starts is not_run, matching the fidelity trial's harness- reason rule.

Plans: [`2026-11-05-perf-schema-and-outcomes.md`](../plans/2026-11-05-perf-schema-and-outcomes.md), [`2026-11-05-perf-scenarios-and-coverage.md`](../plans/2026-11-05-perf-scenarios-and-coverage.md).

<!-- CONDITIONS-END -->

## What this design refuses to pretend

- There is no verified cross-editor DOCX performance implementation in this repository or in the reference tools above. The reference tools are real, and they measure other programs or a single project.
- Page counts in Report C are rendering observations. They are not timings.
- Project README millisecond claims for WordCraft, Docxodus, Jet, and Slate's example table are not results of this trial.
- `requestAnimationFrame`, constructor return, and model-ready stay in the artifact as diagnostic marks. They do not fill the visible or usable columns.
