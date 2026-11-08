# perf/ — performance benchmark harness

`perf/` measures the editors_trial participants over time. It is a harness,
not a report: no performance figures appear in the published reports, and a
`ci_coarse` host never publishes a headline distribution.

- Design: [`docs/superpowers/specs/2026-11-05-editor-performance-benchmark-design.md`](../docs/superpowers/specs/2026-11-05-editor-performance-benchmark-design.md)
- Normative matrix: [`docs/superpowers/specs/2026-11-05-editor-performance-coverage.json`](../docs/superpowers/specs/2026-11-05-editor-performance-coverage.json)
- Implementation plans: [`docs/superpowers/plans/`](../docs/superpowers/plans/)

The harness is Python 3.10+ and standard-library only. The editors need their
own toolchains; see [What you need](#what-you-need).

## Concepts

### Layers

Every scenario declares one layer. A measurement may claim only what its
layer can see; a comparison across layers is a diagnostic, not a ranking.

| Layer | May claim | Must not claim |
|---|---|---|
| `native` | CPU or wall time inside a native/Rust function, boundary stated | A browser frame, a WASM call, a user-visible edit |
| `model` | Time to build or mutate the document model | First paint, first usable, input-to-pixel |
| `browser_visible` | Time to a paint entry, presented frame, or external pixel | A `requestAnimationFrame` callback by itself |
| `wasm_boundary` | Compile, instantiate, call, copy, `memory.grow` across the host boundary | The whole editor's typing latency |

`perf/layers/classify.py` maps timing marks to layers and rejects
`raf_callback` as visible-paint evidence. `perf/layers/event_timing.py`
implements the Event Timing rules (16 ms floor, 8 ms rounding, INP
aggregation). `perf/layers/wasm.py` is the C24 operation contract.

### Outcomes

`measured`, `unsupported`, `not_applicable`, `unverified`, `failed`, and
`not_run` are distinct. Only `measured` carries samples; the others store
null. A refusal is an outcome, not a zero. `perf/schema.py` validates every
trial and rejects forbidden claim/boundary pairs (for example
`model_ready` claiming `user_visible`).

### Cache states

| State | Definition |
|---|---|
| `process_cold_fs_warm` | New process and profile; OS page cache left as is |
| `os_cache_cold` | New process after `sync` and a page-cache drop; dedicated disposable host only |
| `warm_steady` | Same process or a declared preconditioning script already exercised the fixture |

Cache states and repetition units (`fresh_process` vs
`in_process_iteration`) are never pooled.

### Execution profiles

The profile is recorded on every trial and controls sample budgets,
workload caps, and which cache-state variants the scheduler enqueues. It
never removes a criterion from the catalog; a scenario the profile cannot
run is stored as `not_run` with `failure_reason: execution_profile`.

| Profile | `fresh_process` | `in_process_iteration` | Workload cap | Purpose |
|---|---|---|---|---|
| `ci_contract` | 1 | 20 | `micro-paragraphs`, `micro-search` | Headless coverage on the smallest machine |
| `ci_broad` | 5 | 100 | adds `short-paragraphs`, `mixed-utf8`, `search-dense` | Every criterion at least once, reduced samples; still not publishable for visible latency |
| `dedicated_publish` | 30 | 500 | full ladder | Full budgets, `os_cache_cold`, host-generated large files, the one-hour soak |

Scheduler rules (`perf/runner/schedule.py`): `os_cache_cold` enqueues only
on `dedicated_publish` with a dedicated host; C20 enqueues only on
`dedicated_publish`; `browser_visible` scenarios are `not_run` on
`ci_contract`. Only one editor process group runs at a time on `ci_coarse`.

`dedicated_publish` is defined in the schema and profiles but no runner
accepts it yet; today's runners implement `ci_contract` and `ci_broad`.

### Statistics

`perf/analysis/summarize.py` reports n, median, p90, p95, p99, median
absolute deviation, a seeded bootstrap 95% CI, minimum, and maximum.
Outliers stay. Interactive-latency criteria require `fresh_process`.

### Publication policy

`perf/runner/policy.py` and `perf/analysis/publication_gate.py` decide what
may be published as a distribution:

- `run_kind` must be `timing`; diagnostic runs are not timing publications.
- A `ci_coarse` host never publishes a headline distribution, and
  `browser_visible` latency additionally requires `fresh_process`.
- `os_cache_cold` is dedicated-host only.
- A publishable distribution needs at least two independent samples.
- `perf/schema.py` requires an explicit `publication_block_reason` whenever
  `publishable` is false.
- `perf/analysis/summary_integrity.py` refuses a run summary that mixes
  publishable and blocked medians for one criterion.
- `perf/analysis/anti_ranking.py` rejects "N× faster than" prose that does
  not name workload, layer, cache state, and host.

The I01–I12 interpretation conditions (`perf/analysis/interpretation.py`,
required in every trial environment by `perf/schema.py`) gate measured
trials on workload metadata, published statistics, run kind, and
scenario-specific correctness (Unicode, emoji, bidi, IME).

## Layout

```text
perf/
  schema.py                  trial record validation and environment rules
  pins.py                    editor version labels from out/facts.json
  adapters/
    capabilities.py          per-editor lanes and feature states
    protocol.py              capability state -> explicit refusal outcome
  analysis/
    summarize.py             distribution statistics
    interpretation.py        I01–I12 checks on measured trials
    publication_gate.py      publishable flags and block reasons
    summary_integrity.py     no mixed publishable/blocked medians
    anti_ranking.py          rejects context-free speed rankings
  fixtures/
    profiles.py              feature profiles P0–P3 and the workload size ladder
    generate.py              deterministic workload bytes and correctness fixtures
    oracles.py               Unicode/grapheme/bidi/IME oracles
  layers/
    classify.py              timing mark -> layer; visible-evidence rules
    event_timing.py          Event Timing threshold, rounding, INP
    wasm.py                  C24 WASM boundary operation contract
  runner/
    benchmark_ci_contract.py headless C02/C16/C21 contract runner
    benchmark_warm_cold.py   browser warm-vs-cold suite (C02/C03/C05/C06)
    adversarial_c10_scroll.py one-off C10 scroll probe
    warm_cold_browser.mjs    Playwright/Puppeteer paired probe
    adversarial_c10_scroll.mjs scroll-frame probe
    artifacts.py             immutable attempt writer (exclusive create)
    schedule.py              execution-profile scheduler
    policy.py                publication policy
    order.py                 seeded editor ordering
    load_timing.py           PERF key=value stdout parser
    memory.py                process-memory sample validator
    browser_memory.py        browser memory evidence validator
    cause_attribution.py     warm/cold delta attribution
    harness_ui_versions.py   served npm versions vs trial pins
    docx_plaintext.py        w:t text extraction for correctness checks
  scenarios/
    catalog.py               C01–C24 scenario records
    coverage.py              catalog vs normative matrix gaps
  tests/                     unittest suite (standard library only)
```

## Running

### What you need

- Python 3.10+; the harness is standard-library only.
- `out/facts.json`, produced by the release pipeline (`build/facts.py`).
  Every runner reads editor pins from it and stops if it is missing.
- The `repos/` checkouts with dependencies installed (gitignored;
  installing dependencies is allowed, modifying them is not). Toolchains by
  lane: `bun` and `node` for most headless lanes, each repo's
  `tsx`/`vitest` binaries, `cargo build --release` in `harness/wordcraft`
  for `wc-harness`, and `soffice` for the LibreOffice lane. Apryse WebViewer
  has no headless round-trip harness here and is recorded `not_run`.
- For the browser lanes: the five `harness/ui` hosts (plate, docxodus,
  superdoc, genoffice, canvas) with dependencies installed — pnpm for
  plate/docxodus/canvas, npm for superdoc/genoffice — plus
  `playwright`/`puppeteer` at `harness/ui`. The runner starts each dev
  server itself.
- Publishable visible-latency numbers need a dedicated host and the
  `dedicated_publish` profile, which no runner accepts yet.

### Contract runner (headless)

```sh
PYTHONPATH=. python3 perf/runner/benchmark_ci_contract.py --dry-run
PYTHONPATH=. python3 perf/runner/benchmark_ci_contract.py \
  --execution-profile ci_contract --workload micro-paragraphs
PYTHONPATH=. python3 perf/runner/benchmark_ci_contract.py \
  --execution-profile ci_broad --workload short-paragraphs
```

`--dry-run` writes scheduler outcomes without invoking an editor; it still
resolves pins, so it needs `facts.json`. The runner measures C02 (model
load, from harness `PERF model_ready_ms=` marks), C16 (save, from
`PERF save_ms=`), and C21 (child CPU from `getrusage(RUSAGE_CHILDREN)`),
and records the remaining criteria as `not_run` or
`adapter-not-implemented`. Every attempt also keeps the subprocess wall
time and child CPU samples beside the metric, canvas may emit marks
through a perf-mark file, and each harness subprocess has a 600 s
timeout. LibreOffice C02 is conversion wall time, not `model_ready`;
LibreOffice C16 is `not_run` (no save-boundary probe); C24 is
`not_run`/`unverified` (no WASM boundary harness).

### Warm/cold browser suite

```sh
PYTHONPATH=. python3 perf/runner/benchmark_warm_cold.py --pairs 3
PYTHONPATH=. python3 perf/runner/benchmark_warm_cold.py --pairs 3 \
  --editors plate docxodus
PYTHONPATH=. python3 perf/runner/benchmark_warm_cold.py --workload micro-search
```

For each `harness/ui` host the runner starts the dev server, runs paired
cold/warm browser probes (Playwright by default; a Puppeteer driver check
runs for plate), writes measured attempts for C02 (browser model-ready,
skipped when the host exposes a single ready signal), C03 (first usable),
C05 (single edit), and C06 (sustained typing burst), and attributes the
cold/warm delta with `cause_attribution.py`. Editors without a configured
host, and criteria without a probe (C07–C10, C22, C23 here), are recorded
`not_run`. The suite summary is diagnostic: `publishable: false`.

### Adversarial C10 scroll probe

```sh
PYTHONPATH=. python3 perf/runner/adversarial_c10_scroll.py \
  --editor plate --out-root perf/out/c10_plate --pairs 3
```

`--editor` must be one of the warm/cold browser targets; `--out-root` is
required. The probe scrolls the largest vertical container to its midpoint
and times until the next painted frame, one fresh browser per pair.

### Tests and coverage gate

```sh
python3 -m unittest discover -s perf/tests -q
python3 -I build/test_perf_plan_coverage.py
```

## Artifacts

Raw trials are immutable JSON: each attempt is written once with exclusive
creation under `perf/out/<profile>_<date>/attempts/` (contract runner) or
`perf/out/warm_cold_<date>/attempts/` (browser suite), with a
`summary.json` beside them. `perf/out/` is gitignored. Summaries are
derived; a later change to the summary function re-reads the raw files.

## Reading results

- A `not_run`, `unverified`, `unsupported`, or `not_applicable` outcome is
  information, not a zero.
- `publishable: false` always carries a `publication_block_reason`.
- Compare only within one layer, cache state, workload, feature profile,
  and host class. Name all of them before saying one editor is faster.
- The warm/cold suite's paired rows are diagnostics; they are not headline
  publications.
