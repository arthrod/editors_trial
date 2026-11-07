# Full browser criteria, laboratory dedicated lanes, WASM C24, and LibreOffice pixels

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans`. Each task uses red-then-green tests and records commands in `perf/out/full_browser_2026_11_07/summary.json`.

**Goal:** On this Linux Cloud Agent VM (~16 GiB RAM), run every catalog criterion once at `ci_broad` or `dedicated_publish` (laboratory host), eliminate final `adapter-not-implemented` outcomes for browser lanes, split C02 vs C03 on harness UIs, probe Docxodus WASM for C24, produce a LibreOffice-baseline pixel diff layer, and add small/gigantic/rapid load-unload fixtures measured with Playwright or Puppeteer only.

**Base branch:** `cursor/low-resource-execution-tiers-5109` (PR #78 perf harness). **Output root:** `perf/out/full_browser_2026_11_07/` (attempts under `attempts/`, suite summaries at `summary.json`, pixels under `pixels/`, C20 full soak under `c20_full_soak/`).

**Honest limits (do not pretend):** Microsoft Word is absent. Apryse has no `APRYSE_LICENSE_KEY` / `PDFTRON_LICENSE_KEY` / `TRIAL_KEY` in the environment — browser and WASM cells for Apryse stay `not_run` or `unverified` with that reason after a real probe attempt. Superdoc browser version is whatever `harness/ui/superdoc/package.json` pins (currently `superdoc@2.29.0-next.3`), recorded in every trial `environment.editor_version` via `perf/runner/harness_ui_versions.py`, not `@superdoc/sdk@2.26.0-next.16` from the design table.

**Global constraints**

- Do not modify anything under `repos/`. Harness changes only under `harness/` (not `repos/`).
- Do not commit `node_modules/`, fabricated `PERF model_ready_ms=` lines, or synthetic C24 RNG loops (`test_benchmark_honesty.C24NoSyntheticWasmLoop` must stay green).
- `publishable` remains `false` for all trials on `host_class` `ci_coarse` or `laboratory` until the amended spec explicitly allows laboratory headline publication (default in this plan: **no** laboratory publication; raw trials are regression artifacts only).
- Set `environment.cache_state: os_cache_cold` only when `page_cache_dropped: true` and the drop command actually ran (see Task 2).
- One editor dev server at a time (`AGENTS.md` quiet machine). Check `uptime` and `ps -Ao pcpu,comm -r | head` before long soaks.

## Coverage ids owned here

C01–C24 (browser-visible completion for harness UIs), I05, I08, I11, plus pixel regression artifacts (not a catalog criterion).

Link this plan in `docs/superpowers/specs/2026-11-05-editor-performance-coverage.json` `plans` arrays for C01–C24 in Task 0.

---

## Task 0: Spec amendment — laboratory host class

**Files:**
- Modify: `docs/superpowers/specs/2026-11-05-editor-performance-benchmark-design.md` (sections *Cache states*, *Execution profiles and low-resource hosts*, scheduler bullets, publication policy)
- Modify: `docs/superpowers/specs/2026-11-05-editor-performance-coverage.json` (append plan path to each criterion’s `plans` list)
- Test: `python3 build/test_perf_plan_coverage.py` (must pass after JSON edit)

**Spec text to add (normative):**

1. **`host_class: laboratory`** — A single-tenant measurement VM (including this Cloud Agent pod) that is not a disposable bare-metal dedicated bench but is operator-approved for invasive cache tests. Records real `ram_bytes`, may run Xvfb, and may execute `drop_caches` when the implementer documents the command in the trial record.
2. **`dedicated_publish` on `laboratory`** — Allowed. Sample budgets stay 30 fresh / 500 in-process. Publication policy: laboratory runs are **not** headline-publishable unless a later spec revision says otherwise; they produce the same immutable JSON as dedicated runs.
3. **`os_cache_cold` on `laboratory`** — Allowed when `page_cache_dropped: true` is recorded and the runner executed the documented drop (below). Still forbidden on plain `ci_coarse` without upgrading `host_class` to `laboratory` in the trial env.
4. **C20 on laboratory** — Enqueues when `execution_profile` is `dedicated_publish`. A **preview soak** of 600 seconds may complete in the main conductor session; the **full** 3600-second soak must be **started** (tmux) and write attempts under `perf/out/full_browser_2026_11_07/c20_full_soak/` even if the conductor exits before it finishes.
5. Keep existing **`dedicated`** host meaning unchanged (disposable host, full publication path when other gates pass).

**Red (before code):** `PYTHONPATH=. python3 -c "from perf.schema import validate_environment; validate_environment({...})"` with `host_class: laboratory` and `execution_profile: dedicated_publish` — expect `ValueError` today.

**Green (after `perf/schema.py` + `perf/runner/schedule.py` updates):**

- Accept `host_class` in `("dedicated", "ci_coarse", "laboratory")`.
- `dedicated_publish` requires `host_class in ("dedicated", "laboratory")`.
- `os_cache_cold` allowed when `host_class in ("dedicated", "laboratory")` and `page_cache_dropped is True`.
- `ci_coarse` + `os_cache_cold` still raises.

Update `perf/tests/test_schema.py` and `perf/tests/test_scenarios.py` only where they assert the old two-value `host_class` set.

**Commit:** `spec: allow laboratory host for dedicated_publish and os_cache_cold`

---

## Task 1: Runner entrypoint and output layout

**Files:**
- Create: `perf/runner/benchmark_full_browser.py` (orchestrates warm_cold + browser criteria + wasm + dedicated lanes; CLI flags below)
- Create: `perf/tests/test_full_browser_runner.py` (dry-run writes summary skeleton; no browser launch in unit test)
- Modify: `perf/runner/benchmark_warm_cold.py` (`--out-root` passthrough; stop hard-coding `adapter-not-implemented` for C07–C10, C22–C23 once probes exist)

**CLI (document in summary.json `commands` list):**

```bash
# 0) Dependencies (once per VM)
cd /agent/repos/editors_trial/harness/ui && pnpm install
cd /agent/repos/editors_trial/harness/ui/docxodus && pnpm install
cd /agent/repos/editors_trial/harness/ui/plate && pnpm install
cd /agent/repos/editors_trial/harness/ui/canvas && pnpm install
cd /agent/repos/editors_trial/harness/ui/genoffice && npm install
cd /agent/repos/editors_trial/harness/ui/superdoc && npm install

# 1) Contract tests
cd /agent/repos/editors_trial
PYTHONPATH=. python3 -m unittest discover -s perf/tests -q
python3 build/test_perf_plan_coverage.py

# 2) Main browser + ci_broad pass (3 pairs = 9 samples where applicable)
PYTHONPATH=. python3 perf/runner/benchmark_full_browser.py \
  --execution-profile ci_broad \
  --host-class ci_coarse \
  --out-root perf/out/full_browser_2026_11_07/ci_broad \
  --pairs 3 \
  --editors docxodus,superdoc,genoffice,plate,canvas

# 3) Laboratory dedicated_publish (includes os_cache_cold + C20 preview + full soak start)
PYTHONPATH=. python3 perf/runner/benchmark_full_browser.py \
  --execution-profile dedicated_publish \
  --host-class laboratory \
  --out-root perf/out/full_browser_2026_11_07/dedicated_publish \
  --pairs 3 \
  --c20-preview-seconds 600 \
  --start-c20-full-soak \
  --editors docxodus,superdoc,genoffice,plate,canvas

# 4) Re-run ci_contract/broad catalog fill for non-browser editors (no regression)
PYTHONPATH=. python3 perf/runner/benchmark_ci_contract.py \
  --execution-profile ci_broad \
  --out-root perf/out/full_browser_2026_11_07/ci_broad_catalog
```

**Red:** `test_full_browser_runner.py` — `benchmark_full_browser.main(["--dry-run", ...])` exits 0 and creates `summary.json` with `suite: full_browser`.

**Green:** implement argparse and wire sub-stages.

**Commit:** `runner: add benchmark_full_browser orchestrator`

---

## Task 2: `os_cache_cold` on this machine

**Files:**
- Create: `perf/runner/page_cache_drop.sh` (documented, called only from runner)
- Modify: `perf/runner/benchmark_full_browser.py` (invoke before `os_cache_cold` attempts)
- Test: `perf/tests/test_page_cache_drop.py` (mocks `subprocess`; asserts runner refuses `os_cache_cold` without `page_cache_dropped`)

**Exact drop command (record verbatim in trial `diagnostic.cache_drop_command`):**

```bash
sync
echo 3 | sudo tee /proc/sys/vm/drop_caches
```

If `sudo` or `/proc/sys/vm/drop_caches` fails, write `not_run` with `failure_reason` containing the captured stderr — do **not** label the attempt `os_cache_cold`.

**C01 startup matrix:** For each browser editor in `BROWSER_TARGETS`, run three cache states where the spec allows: `process_cold_fs_warm`, `os_cache_cold` (laboratory only), `warm_steady` (precondition: one completed load). Store separate attempt files; never mix cache states in one `summary_stats` object.

**Commit:** `runner: laboratory os_cache_cold with recorded drop_caches`

---

## Task 3: C20 long-session stability

**Files:**
- Create: `perf/runner/c20_soak.mjs` (Playwright; warm editor; loop typed edits + scroll every 30s; sample `input_to_next_paint` every 5 min)
- Create: `perf/runner/benchmark_c20_soak.py`
- Modify: `perf/runner/benchmark_full_browser.py` (`--c20-preview-seconds`, `--start-c20-full-soak`)

**Preview soak (conductor completes):** `min_seconds: 600`, tag `diagnostic.soak_kind: preview`, `environment.execution_profile: dedicated_publish`, `host_class: laboratory`, workload `short-paragraphs`, `samples_ms` length ≥ 3.

**Full soak (must start):**

```bash
tmux -f /exec-daemon/tmux.portal.conf new-session -d -s c20-full-soak -c /agent/repos/editors_trial -- \
  env PYTHONPATH=. python3 perf/runner/benchmark_c20_soak.py \
    --seconds 3600 \
    --out-root perf/out/full_browser_2026_11_07/c20_full_soak \
    --editor plate
```

Write `perf/out/full_browser_2026_11_07/c20_full_soak/started.json` with ISO timestamp and tmux session name. Conductor may exit while soak continues.

**Red:** `perf/tests/test_c20_soak.py` — scheduler allows C20 when `execution_profile == dedicated_publish` and `host_class == laboratory` (mock env).

**Green:** soak script + attempts.

**Commit:** `runner: C20 preview and background full soak`

---

## Task 4: C24 WASM boundary (Docxodus prebuilt)

**Files:**
- Create: `perf/runner/wasm_docxodus_probe.mjs` (Node 20+; **no RNG**; uses published API)
- Create: `perf/runner/benchmark_wasm_c24.py`
- Modify: `perf/runner/benchmark_ci_contract.py` — `c24_boundary_decision` delegates to probe for `docxodus`; `apryse` stays `unverified` without key; others `not_applicable` or harness-specific probes where listed below

**Prebuilt artifact (do not rebuild WASM):**

- Primary: `harness/ui/docxodus/node_modules/docxodus/dist/wasm/dotnet.native.wasm` (record resolved path in `diagnostic.wasm_artifact`)
- Initialize via the same `initialize(wasmBase)` path as `harness/ui/docxodus/src/main.ts`, or call `getWasmExports()` after init

**Operations (`perf/layers/wasm.py` names), measured per operation as `samples_ms` lists:**

| Operation | Probe |
|---|---|
| `compile_and_instantiate` | Cold `WebAssembly.instantiate` of `dotnet.native.wasm` (or product `initialize` wall time first call) |
| `empty_call` | No-op export if exposed; else smallest documented export |
| `scalar_call` | Integer-returning export used by smoke test |
| `string_conversion` | UTF-8 round trip through WASM marshaling (product API) |
| `typed_array_transfer` | `Uint8Array` slice across boundary |
| `batched_call` | 100× scalar call in one loop (in-process) |
| `memory_grow` | `memory.grow(1)` or product heap growth hook |

Run `repetition_unit: in_process_iteration` with `ci_broad` budget 100 samples for docxodus; `ci_contract` 20. Wordcraft `wasm_ui` may use `harness/wordcraft` wasm32 build only if a prebuilt `.wasm` exists without compiling `repos/` — otherwise `not_run` with reason.

**Red:** extend `test_benchmark_honesty.C24NoSyntheticWasmLoop` — docxodus may become `measured` only when `diagnostic.wasm_artifact` is set and samples come from probe JSON, not inline Python list.

**Green:** probe + integrated runner.

**Commit:** `runner: docxodus C24 wasm boundary probe`

---

## Task 5: C02 vs C03 — model-ready vs first-usable hooks

**Files:**
- Modify: `harness/ui/docxodus/src/main.ts` — set `performance.mark('docxodus-model-ready')` immediately after `await initialize(WASM_BASE)`; keep `state.rendered` / marks for first visible paginated HTML (`docxodus-first-usable`)
- Modify: `harness/ui/superdoc/src/main.ts` (or host entry) — `performance.mark('superdoc-model-ready')` when document model reports ready; separate mark when `.superdoc__document` is visible and accepts focus
- Modify: `harness/ui/genoffice/desktop-stub.js` (or vite entry) — expose `window.__GENOFFICE_PERF__ = { modelReadyMs, firstUsableMs }` via marks
- Modify: `perf/runner/warm_cold_browser.mjs` — read `performance.getEntriesByName` for model mark vs selector-ready; populate **distinct** `model_ready_browser_ms` and `first_usable_ms` (no longer copy the same value)
- Modify: `perf/runner/benchmark_warm_cold.py` — remove blanket C02 `not_run` when both timestamps exist; enforce `assert_no_duplicate_c02_c03_in_dir`
- Test: `perf/tests/test_unblocked_browser_harness.py` — assert docxodus main contains `docxodus-model-ready`; warm_cold runner maps C02 to model mark

**Boundaries:** C02 trials use `boundary: model_ready_browser`, `layer: model`. C03 stays `first_usable`, `layer: browser_visible`.

**Commit:** `harness: split model-ready and first-usable perf marks`

---

## Task 6: Plate browser adapter C07–C09, C22–C23

**Files:**
- Modify: `harness/ui/plate/src/main.tsx` — expose `window.__PLATE_PERF__` with `importDone` mark at end of DOCX import resolver; contenteditable surface selector stable for Playwright
- Create: `perf/runner/browser_interactions.mjs` (shared: C07 caret move, C08 clipboard paste burst, C09 undo chord, C22 toggle `?feature_profile=P1`, C23 collaboration stub = `not_applicable` with capability citation)
- Modify: `BROWSER_TARGETS["plate"]` in `benchmark_warm_cold.py` — add `criteria` keys C07–C09, C22; wire Puppeteer + Playwright (plate already smoke-tested with Puppeteer in `driver_checks`)
- Test: `perf/tests/test_plate_browser_criteria.py` — parses `browser_interactions.mjs` exports list; dry-run mock returns ≥3 samples for C07

**C07:** Click mid-paragraph in `[contenteditable="true"]`, arrow key, measure `nextPaintMs` until selection visible.

**C08:** `navigator.clipboard.writeText` + Ctrl+V (grant `clipboard-read` / `clipboard-write` permissions).

**C09:** Type character, `Control+Z`, wait paint.

**C22:** Load with query param `profile=P1` if host supports; else `not_applicable` with `failure_reason: capability collaboration/profile`.

**C23:** Plate Yjs exists but off in P0 — record `unsupported` or `not_applicable` per `perf/adapters/capabilities.py`, not `adapter-not-implemented`.

**Commit:** `runner: plate C07-C09 and C22 browser probes`

---

## Task 7: Canvas browser C07–C10

**Files:**
- Modify: `harness/ui/canvas/src/main.ts` — set `__CANVAS_PERF__` marks: `model-import-done` at `executeImportDocx` completion (already near `__DOCX_IMPORTED__`), `first-usable` after first layout frame
- Create: `perf/runner/canvas_interactions.mjs` (canvas-aware: click canvas bbox, `executeSearch` for C07; wheel / `scrollToPage` for C10; reuse patterns from `perf/runner/adversarial_c10_scroll.mjs`)
- Modify: `benchmark_warm_cold.py` / `browser_interactions.mjs` — drive C07–C10 for `canvas` editor
- Test: `perf/tests/test_adversarial_c10.py` — extend or duplicate for canvas C10 frame_time samples ≥ 3

**Selectors verified in plan (implementer must screenshot-probe once, save path in `diagnostic.verified_selectors`):**

- Ready: `#editor` + `window.__DOCX_IMPORTED__ === true`
- Edit surface: `#editor canvas` (first canvas in page container)
- Scroll: `?page=2` or editor `executeSearch` path from existing host

**Commit:** `runner: canvas C07-C10 interaction probes`

---

## Task 8: Remaining `ci_broad` browser criteria (no `adapter-not-implemented` finals)

**Files:**
- Extend: `perf/runner/browser_interactions.mjs` + `benchmark_full_browser.py`
- Reuse: `perf/runner/benchmark_ci_contract.py` for model/native C02, C04, C13–C17, C19, C21 on non-browser lanes

**Browser editors in scope:** `docxodus`, `superdoc`, `genoffice`, `plate`, `canvas`.

| Criterion | Driver | Acceptable non-measured outcomes |
|---|---|---|
| C01 | `warm_cold_browser.mjs` + cache states | measured or `failed` with stderr |
| C04 | Poll CPU / `performance.now` quiescence after C03 | `failed` on timeout |
| C05–C06 | Existing warm/cold edit paths | measured |
| C07–C10 | Tasks 6–7 | measured or capability `not_applicable` |
| C11 | Navigation + first paginated paint mark | measured |
| C12 | Insert paragraph, reflow paint | measured or `failed` |
| C14 | Load `perf/fixtures/generated/gigantic-one-paragraph.docx` | measured or OOM `failed` |
| C15 | `micro-search` fixture, search API if present | else model-layer `benchmark_ci_contract` |
| C16 | Browser save/export only if harness exposes download | else `not_run: no browser save hook` after attempt |
| C18 | `run_kind: diagnostic`, Chrome trace optional | `publishable: false` |
| C22–C23 | Profile / collaboration probes | see Task 6 |
| Apryse | Open `harness/apryse` only if env key set | else `not_run: Apryse trial key absent` |

**Stop condition:** Grep `perf/out/full_browser_2026_11_07/**/attempts/*.json` for `adapter-not-implemented` — count must be **zero** for browser editors. CLI-only editors may still have honest `not_applicable`.

**Red:** `perf/tests/test_no_adapter_not_implemented.py` — fails on current `perf/out/unblocked_2026_11_07b/summary.json`.

**Green:** after full run, passes on new out root.

**Commit:** `runner: complete ci_broad browser criterion coverage`

---

## Task 9: Fixtures — small, gigantic, rapid load/unload

**Files:**
- Create: `perf/fixtures/manifest.json` (checksums)
- Create: `perf/fixtures/generated/.gitkeep` and generator invocation in runner (materialize on first run)
- Create: `perf/runner/benchmark_load_unload.mjs`
- Create: `perf/runner/benchmark_load_unload.py`
- Test: `perf/tests/test_load_unload_fixtures.py`

**Fixture files (under `perf/fixtures/generated/`):**

| File | Source workload | Purpose |
|---|---|---|
| `small-micro-paragraphs.docx` | `micro-paragraphs` from `build_workload` | C03/C05 smoke |
| `gigantic-one-paragraph.docx` | `one-paragraph` (8000 chars) | C14 scaling |
| `rapid-cycle-index.json` | metadata only | links corpus sha256 for unload test |

**Metrics (Playwright or Puppeteer only, `pairs` ≥ 3):

- `load_ms` — navigation start → model-ready mark
- `unload_ms` — `page.close()` or `context.close()` until UI process RSS drop sampled via `perf/runner/browser_memory.py` helper (peak RSS in `diagnostic.peak_rss_bytes`)
- Record `summary_stats` per metric; `publishable: false`

**Command:**

```bash
PYTHONPATH=. python3 perf/runner/benchmark_load_unload.py \
  --out-root perf/out/full_browser_2026_11_07/load_unload \
  --pairs 3 \
  --fixture perf/fixtures/generated/gigantic-one-paragraph.docx
```

**Commit:** `fixtures: small/gigantic docx and load-unload probes`

---

## Task 10: Pixel reports (LibreOffice baseline, no Word)

**Files:**
- Create: `perf/runner/benchmark_pixels_lo.py` (wrapper; does not fork DPI)
- Modify: none under `build/pixels.py` (read `DPI` = 200)

**Procedure:**

1. Ensure round-trip outputs exist: run `build/run_all.sh` only if `out/<editor>/complex.docx` missing for participants you compare (expensive; prefer existing `out/` from last trial). Pixel plan minimum: editors with browser harness outputs saved during perf runs (`perf/out/.../saved/*.docx`) plus fidelity corpus `fixture/complex.docx` through LibreOffice headless baseline.
2. Generate LibreOffice reference pages:

```bash
cd /agent/repos/editors_trial
uv run --script build/lo_pages.py
uv run --script build/lo_render_compare.py
```

3. Rasterize editor outputs at 200 dpi using `build/pixels.py` patterns; store under:

`perf/out/full_browser_2026_11_07/pixels/<editor_id>/pages/`  
`perf/out/full_browser_2026_11_07/pixels/diff_vs_lo/<editor_id>/` (PNG diff + `metrics.json` with differing pixel count and bbox)

**Editors to rasterize (minimum):** `plate`, `docxodus`, `superdoc`, `genoffice`, `canvas` saved DOCX from harness export hooks or round-trip `out/` copies. Skip Word. Skip Apryse without key.

**Commit:** `runner: LO-baseline pixel diffs under perf/out`

---

## Task 11: Final integration run and summary

**Files:**
- Write: `perf/out/full_browser_2026_11_07/summary.json` aggregating sub-suites
- Write: `perf/out/full_browser_2026_11_07/SUPERDOC_INSTALLED_VERSION.txt` — copy from `npm ls superdoc --prefix harness/ui/superdoc`

**Summary fields (conductor checklist):**

- `suite`, `execution_profile`, `host_class`, `fixture_sha256`, `publishable: false`
- `editors[]`: each `criterion_id`, `editor_id`, `outcome`, `failure_reason`, `attempt_file`, `median_ms` when measured
- `commands[]`: exact shell history
- `not_run_honest`: list Apryse/Word rows with keys absent
- `c20_full_soak_started`: boolean

**Verification commands (must all exit 0 before PR merge):**

```bash
cd /agent/repos/editors_trial
PYTHONPATH=. python3 -m unittest discover -s perf/tests -q
python3 build/test_perf_plan_coverage.py
PYTHONPATH=. python3 perf/runner/benchmark_full_browser.py --check-out perf/out/full_browser_2026_11_07
```

Implement `--check-out` to validate every attempt JSON with `perf.schema.load_trial`, grep for forbidden patterns, and assert catalog coverage.

**Commit:** `perf: full browser run 2026-11-07 artifacts`

---

## Second-conductor verification (failure conditions)

| Check | Pass | Fail |
|---|---|---|
| `validate_trial` on every `attempts/*.json` | no exception | schema error |
| Duplicate C02+C03 both `measured` same editor/cache | `assert_no_duplicate_c02_c03_in_dir` | two measured rows |
| C02 `samples_ms` equals C03 exactly for same pair | only if diagnostic says intentional mirror | duplicate timestamps without distinction |
| `failure_reason` contains `adapter-not-implemented` | zero in final out root | any match |
| C24 `measured` | `diagnostic.wasm_artifact` path exists on disk | synthetic Python-only samples |
| `os_cache_cold` | `page_cache_dropped: true` + drop command in diagnostic | cache_state set without drop |
| LibreOffice C16 | `not_run` with save reason (existing honesty test) | `measured` from wall time |
| `git diff repos/` | empty | any edit |
| Apryse browser | `not_run` or `unverified`, reason mentions key | `measured` without key |
| Word | absent from attempts | any trial |
| `publishable: true` on `ci_coarse`/`laboratory` browser_visible | none | any |

**JSON fields to spot-check on measured browser trials:** `outcome`, `boundary`, `layer`, `samples_ms` (non-empty list), `summary_stats.n` ≥ 3 for `ci_broad` fresh_process runs with `--pairs 3`, `environment.execution_profile`, `environment.cache_state`, `environment.editor_version` (superdoc contains `2.29.0-next.3`), `publishable: false`, `publication_block_reason` non-empty when `publishable` false.

---

## Acceptance criteria

- Spec allows `laboratory` host; tests updated and green.
- `perf/out/full_browser_2026_11_07/` contains real attempts for all browser criteria C01–C23 on all five harness UIs, C24 measured for docxodus (and honest cells for Apryse/others).
- C20 preview completes; full soak started in tmux with `started.json`.
- No final `adapter-not-implemented` in that out root for browser editors.
- C02 and C03 both measured with distinct marks for docxodus, superdoc, genoffice where hooks added.
- Pixel diff tree exists under `perf/out/full_browser_2026_11_07/pixels/`.
- Load/unload suite reports `load_ms`, `unload_ms`, peak RSS with n ≥ 3.

## Execution order (15 steps)

1. Task 0 spec + schema `laboratory` host class.  
2. Task 1 orchestrator + output directories.  
3. Task 5 C02/C03 harness marks (unblocks warm_cold honesty).  
4. Task 6 Plate interaction adapter.  
5. Task 7 Canvas interaction adapter.  
6. Task 8 remaining browser criteria + Apryse honest skip.  
7. Task 4 C24 Docxodus WASM probe.  
8. Task 9 load/unload fixtures.  
9. Task 2 `os_cache_cold` on laboratory.  
10. Task 3 C20 preview soak.  
11. Start C20 full 3600s tmux soak.  
12. Run `benchmark_ci_contract` catalog pass into same out root.  
13. Task 10 LibreOffice pixel diffs.  
14. Task 11 aggregate summary + version file.  
15. Second-conductor verification table + push branch.
