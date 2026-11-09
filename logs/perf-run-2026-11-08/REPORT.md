# perf/ full run — 2026-11-07/08

Coordinator-run, implementer-executed, inspector-audited full pass over the perf/
harness for every editor that has a harness on this host.

## Commands run (all sequential; uptime logged before each — see `*-uptime.txt`)

| Suite | Command | Output | Result |
|---|---|---|---|
| Unit tests | `python3.13 -m unittest discover -s perf/tests` | 199 tests | 1 pre-existing failure (`test_warm_cold_honesty`: `perf/out/unblocked_2026_11_07b/` absent on this host) |
| Coverage gate | `python3.13 -I build/test_perf_plan_coverage.py` | — | OK |
| Contract (ci_contract, micro-paragraphs) | `perf/runner/benchmark_ci_contract.py` | `perf/out/ci_contract_2026_11_08/summary.json` | 38 measured, 0 failed |
| Contract (ci_broad, short-paragraphs) | same, ci_broad | `perf/out/ci_broad_2026_11_08/summary.json` | 38 measured, 0 failed |
| Warm/cold browser suite, `--pairs 3` | `perf/runner/benchmark_warm_cold.py --editors plate docxodus superdoc canvas genoffice` | `perf/out/warm_cold_2026_11_08c/summary.json` (+ 08, 08b kept) | all 5 editors measured (C03/C05/C06) |
| C10 adversarial scroll, `--pairs 3` each | `perf/runner/adversarial_c10_scroll.py` | `perf/out/c10_{plate,docxodus,superdoc,canvas,genoffice}/summary_c10.json` | all 5 measured |

## Headline (diagnostic only — every cell `publishable=false`, ci_coarse host)

- **ci_contract / ci_broad**: all 13 measurable editors measured on C02/C16/C21.
  Apryse `not_run` by design (no headless round-trip harness); LibreOffice C16
  `not_run` by design (no save probe).
- **Warm/cold (ms, cold median)**: plate C03 299 / C05 136 / C06 100;
  docxodus C03 1960 / C05 82; superdoc C03 3860 / C05 67; canvas C03 864 /
  C05 94 / C06 83; genoffice C03 8430 / C05 101. C02 `not_run` by design
  (single ready signal — recorded reason in the summary).
- **C10 scroll to next painted frame (median, n=3)**: plate 19, docxodus 15,
  superdoc 17, canvas 34, genoffice 34 ms.

## Environment work (all logged here; `fix-*-install.log`)

- `out/facts.json` missing → regenerated with `build/facts.py` (259 keys);
  `@pdftron/webviewer@12.2.1` installed in `harness/apryse` for the pin.
- Default python3 is 3.9 → used `/opt/homebrew/bin/python3.13`.
- Browser lanes: pnpm missing from PATH, Playwright chromium 1248 vs cached
  1254, corrupted genoffice node_modules — fixed; three failed passes
  (`warm_cold_2026_11_07`, `2026_11_08` first attempt) kept as evidence.
- Missing `node_modules` (installed `--ignore-scripts`, allowed by AGENTS.md):
  `repos/{canvas-editor,canvas-editor-plugin,genoffice,docen,office-open,fiduswriter-document-ts}`,
  `harness/{superdoc-sdk,docsplus/repo-copy,apryse}`.
- Harness bug fixed: `harness/canvas/roundtrip.test.ts` mocked the CI-agent
  absolute path `/agent/repos/...`, silently dead on any other host → relative
  literal; regression test `perf/tests/test_no_host_absolute_paths.py`.
  Commit **e57b13a** (lefthook hooks passed).

## Inspector verdict and disposition

Verdict: **BLOCKED — PARTIAL** (core measurement retracted to complete on hard
artifacts; objections and disposition):

1. "uptime recorded before every step" unevidenced → **receipts now in this
   directory** (`*-uptime.txt`, one per step; e.g. step 4 at load 39.81).
2. Harness fix uncommitted, no issue-first evidence → **committed e57b13a**;
   retroactive GitHub issue still open as follow-up (issues-first was not
   satisfied before the code was written).
3. Warm/cold numbers unreproduced (§4 reproduce-twice not applied), taken on a
   noisy host (load 15–77, unrelated rust build, never touched) → **stands as
   disclosed**; they are diagnostic cells, publishable=false by policy; re-run
   on a quiet machine before citing any number.
4. Absolute-path count: 4 candidates, not 3 — `harness/ui/genoffice/{desktop-stub.js,inspect.mjs,vite.config.mjs}`,
   `harness/ui/fidus/probe_load.mjs` (pre-existing diagnostics, one is an
   env-var fallback) → **accepted correction**, left unfixed to avoid touching
   files mid-measurement.

## Known issues / follow-ups

- `perf/runner` `assert_warm_cold_distinct` flakes when integer-ms
  `Date.now()` quantization makes warm/cold medians equal (observed once,
  plate-only retry passed).
- One transient docxodus browser closure in `warm_cold_2026_11_08b` ("Target
  page… has been closed", load ~30); did not reproduce standalone nor in 08c.
- Superdoc first smoke failure (host watchdog timeout) did not reproduce;
  attributed to first-exec Gatekeeper scan of the freshly installed 84 MB
  binary under load — inference, labeled as such.
- `dedicated_publish` profile has no runner yet; nothing on this host class
  can publish a headline distribution (by design).

Raw receipts: this directory (95 files: per-step logs, uptime snapshots,
install logs). Raw trials: `perf/out/**/attempts/` (immutable, exclusive-create).
