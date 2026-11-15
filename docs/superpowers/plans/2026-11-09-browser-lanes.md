# Plan: browser lanes fit to measure (Report E2), runnable in a Linux container

Date: 2026-11-09. Issues: #104, #105, #106, #107, #108, #109, #110, #113, #114.
Base: `perf/e-111-report` (Report E). One plan = one stack, one task = one layer.

## Constraints

- `harness/` is untracked on this stack (commits 9115f65/07b2ce2, pending the
  owner's decision). **No task edits `harness/` or `repos/`.** Build wrappers,
  static servers and fake test hosts live under `perf/`.
- Every runner must work headless in a Linux container (Playwright Chromium,
  software rendering). The run records `headless`, the GPU/renderer string
  (`chrome://gpu` or `WEBGL_debug_renderer_info`) and the container facts that
  `perf/runner/host.py` already reads. A report states the rendering mode; it
  never compares a headless figure with a headed one.
- Tests: `python3 -m unittest`, each task's red tests fail before its code and pass
  after. Browser tests use fake hosts in `perf/tests/fixtures/hosts/` served by
  the task's own static server, with headless Chromium.
- Same rules as Report E's runner (`perf/runner/speed_headless.py`): every sample
  kept on disk with its evidence; a refusal is an outcome, never a zero.

## Task B1: run bookkeeping and production hosts (#110, #107, #114)

Files: new `perf/runner/browser_run.py`, new `perf/runner/browser_hosts.py`,
`perf/runner/benchmark_warm_cold.py` (`_start_server`, `BROWSER_TARGETS`),
`perf/layers/event_timing.py`, the four runner entry points (bookkeeping only).

- `browser_run.py`: one run id per invocation (out dir `<out-root>/<runner>/<run_id>/`,
  refused if it exists); write-once sample files (open with `x`); seeded
  interleaving per repetition (reuse `perf/runner/order.py`), seed recorded;
  fixture file names carry workload id and sha256 prefix; record-don't-abort
  (a failed assertion becomes the sample's `failure_reason`, never an exception
  that ends the run); no duplicate keys in the summary.
- `browser_hosts.py`: for each Vite host, `vite build` through a wrapper config
  under `perf/runner/hosts/` that imports the host's config and overrides
  `build.outDir` and `cacheDir` to `<out-root>/builds/<host>/` (outside `repos/`
  and `harness/`); serve the build with a threaded static server in `perf/`
  (correct MIME for `.wasm`, `.mjs`; the corpus route served from the run's
  fixture). Record the build's tree hash (sha256 over sorted relative paths and
  bytes) in the run. Hosts with no static build (docsplus: Next; fidus: Django
  proxy; wordcraft: already a Trunk release build, keep, but hash it) are run as
  they are and marked `host_build: "dev_server"` or `"app_server"`; a
  `dev_server` host's figures are not publishable (`publishable: false`, reason).
- Before and after every run: `git -C repos/<name> status --porcelain` for every
  checkout; a change fails the run (`repos_modified`).
- `event_timing.py` (#114): a raw duration under 16 ms is `censored`
  (`below_16_ms: true`, `duration_ms: null`), never rounded to 0 or 16; a
  censored entry never enters `samples_ms`. Rounding to 8 ms applies only to
  uncensored entries.

Acceptance criteria and measurers:
1. Two invocations on the same day give two run ids and two directories; the
   first's files are byte-identical after the second (measurer: run the
   fake-host smoke twice, `sha256sum -c` on the first run's manifest).
2. A saturated or failing sample is recorded with `failure_reason`; the run
   ends with exit 0 and a summary (measurer: fake host that fails its ready
   check on one rep).
3. A Vite fake host is served from a production build whose tree hash is in
   the run summary; `git status --porcelain` of `repos/` is empty after a run
   (measurer: `git -C repos/<x> status --porcelain | wc -l` = 0).
4. `event_timing`: raw 12 ms gives censored, not 16; raw 0 gives censored, not
   0; a censored entry contributes nothing to `samples_ms` (unit tests).

## Task B2: first usable and input-to-paint (#104, #105)

Files: `perf/runner/warm_cold_browser.mjs`, `perf/runner/benchmark_warm_cold.py`.

- #104: the C03 clock stops at the ready signal; the settle sleep happens after
  the clock and is recorded as `settle_ms`. Cold pair 1 (server-cold) is
  stored separately from later pairs and never pooled.
- #105: C05/C06 are timed in the page: a real key event through CDP
  `Input.dispatchKeyEvent` (no `delay`), Event Timing entry for that event
  (`durationThreshold: 16`, censor from B1), and a compositor-frame witness
  (CDP screencast frame acked after the input whose content differs from the
  pre-input frame), in one clock domain (the page's `performance.timeOrigin`
  + `performance.now()`, screencast metadata converted through
  `Runtime.evaluate` of `performance.timeOrigin`). No fixed delay inside a
  sample. `assert_visible_evidence` (`perf/layers/classify.py`) runs before a
  `browser_visible` trial is written; a bare rAF is refused.

Acceptance:
1. Fake host with a 1000 ms settle: `first_usable_ms` < 1000 and `settle_ms`
   ≈ 1000 in the attempt JSON.
2. Fake host that paints 50 ms after the key event: C05 ≥ 50 ms; fake host with
   no delay: C05 < 33 ms (or censored). Measurer: the two fake hosts.
3. `validate_trial` rejects a C05 trial whose mechanism is `raf_callback`.

## Task B3: document paint and frame witness (#108, #109)

Files: `perf/runner/document_probe.mjs`, `perf/runner/benchmark_document.py`.

- #108: C11 is the first presented frame at or after the first document text
  is in the DOM (canvas hosts: the disclosed usability signal below); if FCP
  precedes any document surface, FCP is never the C11 sample.
- #109: one clock domain; observe usability in a rAF, take the next acked
  screencast frame; window ≥ 500 ms with a forced-repaint fallback (a 1 px
  outline toggle outside the document, recorded); a refused attempt keeps
  `usable_ms`, `frames_total`, `frames_after_usable`. Canvas/shadow hosts use a
  per-host disclosed usability signal (`ready_js` that checks the document is
  drawn: canvas pixel non-blank, open shadow root text), recorded as
  `usable_signal`. C12's window excludes the probe's own forced layout.

Acceptance:
1. Fake host whose shell paints 30 ms and document text at 400 ms: C11 ≥ 400 ms.
2. Fake static host (no damage after load): C14 measures (forced repaint),
   not "no compositor frame".
3. A refused C14 attempt JSON contains `usable_ms`, `frames_total`,
   `frames_after_usable`.

## Task B4: input criteria prove the edit (#113)

Files: `perf/runner/criteria_input.mjs`, `perf/runner/criteria_input_io.py`,
`perf/runner/benchmark_input.py`.

- C04: the sample ends at a stated event, not "last activity"; an idle page
  is `not_applicable` (no deferred work), not ~1 ms.
- C07–C09: before a latency is kept, the exact expected text is at the exact
  position in the fixture body (model text or DOM text of the document node,
  per host adapter); else `failed: correctness`.
- Witnesses below one frame interval (measured `1000/refresh` from rAF deltas,
  recorded) are refused; caret check never skipped; the repetition unit is
  recorded truthfully (three clicks in one page = `in_process_iteration`).
- Uses B1's Event Timing censor.

Acceptance:
1. Fake host inserting the wrong character → C07 `failed: correctness`; at the
   wrong position → `failed: correctness`; paste truncated to 90 % → C08
   `failed: correctness`.
2. No stored C07 sample below the recorded frame interval (unit test on the
   writer + fake host).

## Task B5: scroll (#106)

Files: `perf/runner/adversarial_c10_scroll.mjs`, `perf/runner/adversarial_c10_scroll.py`.

- No scroll container (including open shadow roots) or `scrollTop` unchanged
  → `not_applicable` / `failed` with the reason, never `measured`.
- Runs on prose-50kw (#100 ladder). Each measured sample records the container
  selector and the `scrollTop` delta; frame witness as B3.

Acceptance:
1. Fake host whose document fits the viewport → C10 not `measured`.
2. Fake host with prose-50kw → every measured sample has a container and
   `scrollTop` delta > 0.

## Task B6: the container

Files: new `perf/container/Dockerfile`, `perf/container/run.sh`, `perf/container/README.md`.

- Base `mcr.microsoft.com/playwright` (pinned digest) + Node (the version the
  harness pins), pnpm, Rust (for wordcraft), uv, Python 3.12. The repo is
  mounted, not copied; `repos/` read-only mount.
- `run.sh`: host check (`perf/runner/host.py`), then the four browser runners
  with `--profile dedicated_publish`, two runs (primary, reproduction) with
  different seeds, as Report E.

Acceptance:
1. `docker build` succeeds; `run.sh --smoke` runs one fake host through all four
   runners inside the container and writes a run with a run id and a recorded
   renderer string (measurer: the smoke's summary.json).

## Order

B1 first (everything uses it). Then B2, B3, B4, B5 in parallel worktrees (file-
disjoint). B6 after B1. Stack order for merging: B1, B2, B3, B4, B5, B6.
Reviews: each layer by an other-corpus reviewer (codex or grok), who runs the
measurers. CI waited on only at B6.

## Amendment 1 (after pi glm-5.3's plan review, 2026-11-09; all 16 findings accepted)

Task split. B1 becomes three layers; B2–B5 import B1's modules, never each other.

### B1a: bookkeeping, flags, Event Timing (in progress: codex)
Adds to Task B1 above:
- `--execution-profile` and `--seed` on all four browser runners, threaded into
  `_env_for`/`_host_base` (today `EXECUTION_PROFILE = "ci_broad"` is hardcoded,
  `benchmark_warm_cold.py:53`). (review 13)
- Record-don't-abort names its sites: `assert_warm_cold_distinct(...)` called
  directly at `benchmark_warm_cold.py:901`; `benchmark_input.py` rewriting
  `summary.json` per editor; the dated out-dir pools in `benchmark_warm_cold.py`
  (`:532-533`), `benchmark_input.py`, `benchmark_document.py`; the duplicate
  `"file"` key at `benchmark_document.py:1513/1521`. A test per site. (review 11)
- `aggregate_inp` filters censored entries; unit test. (review 8)
- The browser delivers no Event Timing entry below `durationThreshold`, and
  delivers durations in 8 ms steps. The censor is therefore applied where the
  runner sees "no entry ≥ threshold for this interaction in the window": that
  is an explicit recorded outcome `censored_below_16_ms`, never an absent
  field. Published Event Timing durations are stated as 8 ms-stepped. (review 7)
- A1 is relabelled: it tests the write-once guard, not determinism. (review 4)

### B1b: production hosts, one adapter per host (new)
`perf/runner/browser_hosts.py` gets a per-host build adapter. A host whose build
fails is `failed: host_build` for that run; there is never a silent dev-server
fallback. Per host (review 2, 9, 12):
- plate: the config hardcodes `/Users/arthrod/temp/T/editors_trial`; the adapter
  recomputes the aliases from the repo root it is given.
- docxodus: copy `node_modules/docxodus/dist` (raw dist and the .NET `wasm/`
  tree served today by `configureServer` middleware) into the build output.
- genoffice: emit `desktop-stub.js` into the output; build with `GENOFFICE_REPO`.
- apryse: build only when the key is present (record presence, never the key);
  the static server sends COOP/COEP for it.
- superdoc, canvas, docen-host: plain wrapper build; unproven until built.
- eigenpal, folio: outDir and cacheDir outside `repos/`; folio's
  `?file=corpus.docx` must resolve in the built app.
- docsplus (Next), fidus (Django): `app_server`, not publishable, with the reason;
  #107's `next build`/`next start` for docsplus is descoped in #128, said so.
- wordcraft: already a release build; hashed.
Acceptance: each of the nine Vite hosts builds, and its built page reaches its
`ready_js` in headless Chromium (locally); a deliberately broken build gives
`failed: host_build`, not a dev server; `repos/` porcelain empty after.

### B1c: shared witness module (new)
`perf/runner/witness.mjs` (+ Python reader): the frame witness (observe in rAF,
next acked screencast frame, window ≥ 500 ms), the clock-skew probe (force one
frame at a known `performance.now()`, convert its screencast timestamp, record
the skew; samples are refused when |skew| exceeds 2 ms or a stated bound),
the frame comparator (decode and pixel-diff with a stated threshold; caret
masked or `caret-color: transparent` injected and recorded), the frame-interval
estimate (median rAF delta), and the renderer string (fallback chain: `chrome://gpu`
text, WebGL renderer with the unmask flag, launch args + Chromium version).
The server/target interface (`_start_server`, `_stop_server`, `BROWSER_TARGETS`)
moves to `perf/runner/browser_hosts.py` with a frozen signature. (review 5, 6, 15)
Acceptance: skew recorded per run; a fake caret-blink-only host does not stop
the witness clock; renderer string non-empty or the run records why.

### Changes to B2–B6
- B2: fix `waitForReady` once; `settle_ms` recorded for all three callers (pair
  mode, criteria session, `coldOnlyFreshContext`). Acceptance 2 becomes: the
  no-delay fake host's C05 names its mechanism and is `< 33 ms` or the explicit
  outcome `censored_below_16_ms`; the 50 ms host is ≥ 50 ms *and* names a
  page-side mechanism. Acceptance 3 becomes: the C05 writer calls
  `assert_visible_evidence`, which raises on a `raf_callback` trial (test). (review 4, 16)
- B3: forced-repaint samples are `mechanism: forced_repaint`, excluded from
  publishable C14 (outcome `unverified`, witness facts kept). C15 is in scope:
  event-driven completion instead of the 2 s cap, a minimum n, and
  `not_applicable` with the reason for hosts without a find widget. (review 3, 10)
- B4: acceptance adds a support matrix (per criterion: hosts measured, refused,
  `failed: correctness`); canvas-surface hosts declare their adapter (model API
  or pixel probe) or its absence before the run. (review 14)
- B5: the trial env records a profile that admits prose-50kw. (review 13)
- B6: the image installs dependencies itself (Linux): `pnpm install` for every
  `harness/ui` host and the editor installs AGENTS.md allows under `repos/`, in
  the image's writable copy, never the host checkout; `PLAYWRIGHT_BROWSERS_PATH`
  and the playwright package pinned to the image's Chromium. Acceptance: one
  *real* Vite host builds and reaches `ready_js` inside the container, beside
  the fake-host smoke. (review 1)

## Amendment 2 (2026-11-10): the publication machine, and throttling (#129)

The owner chose Hugging Face `cpu-upgrade` for Report E2's runs: an 8-CPU cgroup quota on a shared EC2
r6a.16xlarge (probe: stolen time 0.0027 %; a 16-worker burst was throttled 7 times, 5.18 s in total;
other tenants kept the machine about 32 % busy). Layer B1d (#129) reads `cpu.stat` and `/proc/stat`
steal around every sample and refuses a sample during which the cgroup was throttled
(`failed: cpu_throttled`). The report states stolen time, throttled samples refused (N of M), that
other tenants shared the machine, and that every printed figure reproduced in a second run.
The twelve free `cpu-basic` Spaces `arthrod/e2-<host>` are for Linux builds and smokes only.
