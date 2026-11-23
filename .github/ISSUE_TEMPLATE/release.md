---
name: Release
about: Tracking issue for a release of the editors trial (checklist from RELEASING.md)
title: "Release vX.Y.Z"
labels: release
---

# Release checklist

Everything a release of the editors trial needs, in order. Open the release's
tracking issue from the "Release" issue template, which carries this checklist,
and tick it there; record what happened in `CHANGELOG.md` (step 7). The rules behind each step are
in `AGENTS.md`; this file is the inventory, plus what earlier releases taught
us the hard way (marked **Lesson**).

Release: `vX.Y.Z` · release date: `YYYY-MM-DD` · cutoff (date − 5 days): `YYYY-MM-DD`

## 0. Before anything

- [ ] A GitHub issue for every piece of work, each ending with `@coderabbitai plan`, listed in one tracking issue (status, branch, PR).
- [ ] Release branch `release/vX.Y.Z` cut from `main`.
- [ ] `out/facts-v<previous>.json` exists (the `--stale` diff and the "Code read at" column both read it).
- [ ] Secrets: `.env` holds `APRYSE_API_KEY` and is git-ignored. Check only its length or prefix; never print it, commit it, or put it in a published bundle.
- [ ] Nothing under `repos/` is modified (installing its dependencies is allowed).

## 1. Pins (AGENTS.md §1)

- [ ] `RELEASE_DATE=YYYY-MM-DD build/update_editors.sh`, never a pin moved by hand. It moves:
  - [ ] every git checkout to the newest default-branch commit on or before the cutoff (Plate: `next`);
  - [ ] `@superdoc/sdk` (`next`), `docxodus` + `@docxodus/export` (`latest`), `@pdftron/webviewer` (`latest`, stable only; `12.x.0-YYYYMMDD` builds are nightlies);
  - [ ] never older than the current pin;
  - [ ] writes `out/release.json` (release date and cutoff; the reports' dates come from it).
- [ ] List which pins moved (`git diff out/facts.json` after step 5, or `ver.*` in the facts). If any moved, **every** step below runs.
- [ ] **Lesson:** a pin move can change a harness's inputs (vite config, lockfile, CLI flags). Docxodus 15 dropped `--out`; GenOffice's Vite cache churned. Run each harness once by hand before the batch.

## 2. Quiet machine (AGENTS.md §3)

- [ ] `uptime` and `ps -Ao pcpu,comm -r | head`. Note any other session's jobs (`neurotic_docx_bench`, `release_jubarte.py`, `word_pdf.py`, `word_render_all.py`). Never kill them.
- [ ] Split the work by what it needs, rather than holding everything for a fully quiet machine:
  - **needs neither Word nor a quiet CPU:** round trips, second pass, scores, namespace tables, stamp labelling, broken corpus, UI captures (run twice; the comparison catches load flakiness);
  - **needs Word unshared:** Word verdicts, Report C pixel layer. Check that Word is actually in use (`pgrep -fl "Microsoft Word"`, and what the other jobs' children really are) before waiting on it;
  - **needs a quiet CPU:** hostile packages (their CPU and wall-clock budgets give false timeouts under load).
- [ ] **Lesson:** a waiter that runs `pgrep -f pattern` matches its own command line. Write the pattern as `[r]elease_jubarte.py`.

## 3. Measurements (AGENTS.md §2; every changed result runs twice, §4)

| Done | Step | Command | Feeds |
|---|---|---|---|
| [ ] | Round trip, every editor (×2, compare part contents) | `build/run_all.sh` | main, A, A2, B |
| [ ] | Second pass (×2) | `build/run_second_pass.sh` | main, A2 |
| [ ] | Scores | `build/score_all.py`, `build/score_extra.py` | all |
| [ ] | Apryse trial-stamp labels (never edits the output) | `python3 -I build/apryse_stamp.py` | main, vendors |
| [ ] | Broken corpus (×2, cells compared, pass 2 installed) | `build/release_broken.sh` | B |
| [ ] | Word opens every output, and the broken-corpus outputs (×2, identical) | `build/release_word.sh verdicts broken` | main, B, D2 |
| [ ] | Report A namespace tables | `build/ns_json.py`; check §6 with `build/report_a_matrix.py --patch` on a copy | A |
| [ ] | Report C: each editor's own UI (×2) | `OUT=/tmp/ui-runN build/capture_ui.sh`, then `build/compare_ui.py run1 run2` and `compare_ui.py out/ui run2` | C |
| [ ] | Report C: copy the accepted run to `out/ui` (with `captured_at.txt`), rebuild figures | `build/ui_figures.py` | C |
| [ ] | Report C: Word's pixels (×2) | `build/release_word.sh pixels` | C |
| [ ] | Report C: LibreOffice's pixels (×2, compare the JSONs) | `uv run --script build/lo_render_compare.py` | C |
| [ ] | Report C §5: SmartArt controls rasterised, band measured (×2, compare `verify.json`) | `python3 build/raster_controls.py`, `uv run --script build/smartart_verify.py` | C |
| [ ] | Report C §4.1, §5.6, §6.3: A/B variants in Word and LibreOffice, package inventory, figures (×2, compare `out/ab/ab_compare.json`) | `python3 build/lo_pages.py`, `uv run --script build/ab_table.py`, `uv run --script build/construct_presence.py`, `python3 build/render_inventory.py`, `uv run --script build/strips.py out/render` | C |
| [ ] | Report B: XSD violations and package integrity | `python3 build/validate_all_outputs.py`, `python3 build/malformation_audit.py` | B |
| [ ] | Hostile packages, sandbox (×2, quiet CPU; not Google Docs or Word) | `build/run_bomb_sandbox.py` (resume mode), `build/label_protection.py` | D |
| [ ] | Jubarte on the hostile packages | `build/run_jubarte_bombs.py` | D1 |
| [ ] | Star counts | `build/stars.py` | main |
| [ ] | Facts | `build/facts.py` | all |

- [ ] **One pixel resolution: 200 dpi** (from v0.9.3; 110 before). Every page image that is compared pixel by pixel (Word's, LibreOffice's, the SmartArt controls, LibreOffice's own UI pages) is rasterised at `build/pixels.py`'s `DPI`; no script carries its own `-r`. `build/test_pixels.py` checks it. A change of resolution re-measures both pixel layers and §5, and every pixel figure in the templates is a fact (`{{wpx.*}}`, `{{lpx.*}}`, `{{sa.*}}`, `{{pixels.dpi}}`).
- [ ] **A new participant joins every lane:** `run_all.sh`, `run_second_pass.sh`, `score_all.py`, `score_extra.py`, `word_verdicts.py`, `ns_map.py`, `word_render_all.py`, `word_pages.py`, `render_compare_word.py`, `ui_figures.py`, `capture_ui.sh`, `update_editors.sh`, `run_broken.sh`, `defect_survival.py`, `run_bomb_sandbox.py`, `label_protection.py`, `preserved_matrix.py`, `facts.py` (`TOOLS`, `NPM`, `SDKS`/`CLOSED`), `test_report_claims.py`, `vendors.md` (a full section: what the benchmark runs, trivia, pros and cons), and every audit that reads `out/<tool>/complex.docx` (`lo_pages.py`, `lo_render_compare.py`, `render_compare.py`, `render_pages.py`, `render_inventory.py`, `ct_coherence.py`, `orphan_audit.py`, `rel_forward.py`, `malformation_audit.py`, `validate_all_outputs.py`, `scan_word_hostile.py`, `part_map.py`, `verify_findings.py`, `measure_alternate_content.py`). `build/test_every_lane.py` fails on any script that reads SuperDoc's output and not the newest participant's.
- [ ] **Lesson (scripts are suspects, §4):** read the full cell log before believing a label. The sandbox once scored a Chromium launch crash as "refused/bounded-reject"; it is now `harness-browser-launch`.
- [ ] **Lesson:** a run that differs from its twin is not a result. Apryse's two round trips once differed in bytes (comment model vs. kept part) at the same score. That points at the harness exporting before the document finished loading; make the driver wait for real readiness before export.
- [ ] **Lesson:** never edit a shell script while bash is running it. Bash reads the file as it goes, and an edit garbles the rest of the run. Freeze a copy to run, and edit the original.
- [ ] **Lesson:** `run_bomb_sandbox.py` without resume deletes `logs/bombs`, and `TOOL_ONLY` / `BOMB_SKIP_LO` drop the other rows from the scorecard. Use resume and seed the existing lines.
- [ ] **Lesson:** Word is opened only by the vendored driver with its watchdog (`build/word_batch.py` starts both). A run with no watchdog stalled for minutes on a Word that had died; never start Word by hand or with ad-hoc osascript.
- [ ] **Lesson:** a script that drives Word must not run when imported (`if __name__ == "__main__"`); an import once ran a whole Word batch. `build/test_word_verdicts.py` checks every Word script.
- [ ] **Lesson:** a claim the first report "established" is still a measurement. `w:dirty="true"` read as fatal for two releases; the audited driver showed Word only asks to update the fields. When a verdict moves, re-open the isolation corpora (`build/make_single_defect.py`).
- [ ] **Lesson:** read every runner's input lines. `run_broken.sh` passed Plate an unset variable and canvas no paths for two releases; `build/test_run_scripts.py` now checks them.
- [ ] **Lesson:** a capture that misses its target is not a screenshot. Apryse draws on a canvas, so a text wait found nothing and `shot.mjs` still printed OK over page 1 labelled page 3. A missed wait, scroll or probe now exits 4 (`MISS`), and `build/test_ui_captures.py` checks every `out/ui/*.json`.
- [ ] **Lesson:** a relationship target may be absolute (`/word/header3.xml`, Apryse). An audit that joins it to the source part's folder reports parts missing that are there; resolve absolute targets from the package root (`build/test_malformation_audit.py`).
- [ ] **Lesson:** compare pages from one generation. LibreOffice's corpus rendered on one day and its A/B variants rendered on another differed by the same 4,536 pixels on page 2 in every variant; `ab_table.py` now renders both in one run. When every variant shows the same difference, suspect the reference, not the constructs.
- [ ] **Lesson:** a band located as "the box around every difference" grows with the resolution. At 200 dpi it swallowed an object below the SmartArt; the band is the control's own footprint (`build/smartart_band.py`), and differences outside it are counted apart.
- [ ] Anything not re-run is named, with the reason, in the changelog's "Not re-measured" and in the report itself.

## 3a. Publishing a pending lane (`build/lanes.py`)

A pending lane has a harness, a pin and a line in every runner, and is kept out of a release's scores, facts and tables until this section is done for it. Published in v0.11.0 (2026-11-21): react-docx, OpenDoc, BetterOffice (and its `betteroffice-editor` lane), OnlyOffice (CryptPad build); Univer and Nutrient have no round-trip lane. Nothing is pending now. A development run of any script takes them with `TRIAL_PENDING=1` (or `--pending` on `score_all.py`, `score_extra.py`, `facts.py`, `preserved_matrix.py`); nothing a development run writes is published. Do the steps in order; each names what must be true first.

- [ ] **1. Pins and builds.** Before: §1 done, quiet machine (§2). `harness/reactdocx`, `harness/betteroffice`, `harness/univer`: `pnpm install --frozen-lockfile`. `harness/opendoc`: `repos/opendoc` at the pinned commit, then `cargo build --release` (about 25 minutes cold). `harness/onlyoffice`: `node fetch.mjs` (checks the archive's SHA-512 against `pin.json`). `harness/ui`: `pnpm install --frozen-lockfile`, then Playwright's Chromium installed (react-docx is a browser lane, and its round trip fails without this install); the UI hosts under `harness/ui/<tool>` and `harness/apryse`, `harness/superdoc-sdk` need their own install too. `repos/office-open` must be present: `build/validate_all_outputs.py` reads its schemas. The page-image scripts (`ui_figures.py`, `render_compare_word.py`) need Pillow, and the test suite under pytest needs `pyfakefs`: `uv run --with pillow --with numpy python …`.
- [ ] **2. Move the lanes.** v0.11.0 did this step with one switch and not list by list: `PUBLISHED_IN = "v0.11.0"` in `build/lanes.py` makes `lanes.requested()` true in every run, so every `lanes.join` takes the lanes, and `TRIAL_PENDING=0` reproduces a release from before them. The lists were left as they are, and `defect_survival.EDITORS` took the four by hand (step 5). The next pending lane needs its own list or the switch cleared in its branch. The list-by-list move below is the alternative. Before: step 1. In `build/lanes.py` remove the lane from `PENDING` (and `PENDING_LANES`, `KEYS`); add it to `TARGETS` in `score_all.py`, `SECOND`/`LANES` in `score_extra.py`, `TOOLS` (and `LANES`) in `facts.py`, and to every list `build/test_every_lane.py` then names (each has a `lanes.join` line under it; the list above it is where the entry goes). `perf/pins.py`: drop it from `_PENDING`. `build/test_new_lanes.py` pins the pending state and is rewritten here. Do not move OnlyOffice into the audits that open a package while it writes none: `lanes.join` leaves a no-output lane out, and a hand-written entry would not.
- [ ] **3. Round trip ×2.** Before: step 2; no other run on the machine (`run_all.sh` ends with `pkill -f "superdoc host"`). `build/run_all.sh` from a frozen copy with `TRIAL_ROOT` set, twice; compare part contents. Expect `FAIL onlyoffice` with `out/onlyoffice/no_output.json` (`did-not-return`) both times, and `NONE univer` with `out/univer/probe.json`. If OnlyOffice writes an output, or the probe prints `FOUND`, stop: the lane's description in every report changes.
- [ ] **4. Second pass ×2, then scores.** Before: step 3. `build/run_second_pass.sh`; `python3 build/score_all.py`; `python3 build/score_extra.py`.
- [ ] **5. Broken corpus.** Before: step 3. `build/release_broken.sh` (two passes; installs outputs and no-output records in `out_broken/` only when cells and outcomes agree). Then add the lanes to `EDITORS` in `build/defect_survival.py`: every lane with a committed `out_broken/<slug>/complex.docx` or `no_output.json` is owed a row (`test_every_editor_measured_has_a_row`). Commit `out_broken/<slug>/`.
- [ ] **6. Word.** Before: steps 3 and 5; a Mac with Word and nothing else running. `build/release_word.sh`, `build/release_word.sh broken`, then `build/release_word.sh pixels` (it runs `word_render_all.py`, `word_pages.py` and `render_compare_word.py` twice). Word draws one pixel column on page 4 of the corpus in one of two ways, so two passes can differ by 151 pixels in every row with no output changed: run a third pass, install the one in which the corpus and the outputs fall the same way, and say so in Report C §6.1 (v0.11.0 did).
- [ ] **7. Package audits and Report A, A2, B, C tables.** Before: step 4. `build/ns_map.py` then `build/ns_json.py`; `validate_all_outputs.py`, `ct_coherence.py`, `orphan_audit.py`, `rel_forward.py`, `malformation_audit.py`, `scan_word_hostile.py`, `part_map.py`, `measure_alternate_content.py`, `render_pages.py`, `lo_pages.py`, `lo_render_compare.py`, `render_compare.py`, `render_inventory.py`, `construct_presence.py`, `inventory_table.py`, `preserved_matrix.py`, `verify_findings.py`. `ns_tables.py` needs a display name per lane in `PRETTY`.
- [ ] **8. UI captures (Report C).** Before: the UI hosts of `goal/new-editors-ui` merged. `build/capture_ui.sh` ×2, then `build/ui_figures.py`. Nutrient and the new editors' rendering sections come from here, not from the round trip.
- [ ] **9. Hostile packages (Report D).** Before: steps 1 and 2; the Mac (seatbelt), quiet, twice. `BOMB_WORK=<dir> python3 build/run_bomb_sandbox.py`, then `build/label_protection.py` (it exits 1 on a tool with no rows). The scorecard's header sentence about Apryse's seatbelt profile (`build/run_bomb_sandbox.py:431`) must name react-docx too: both profiles allow Mach port registration. OnlyOffice's own watchdog is set past the sandbox's wall clock there, so a converter that does not return reads `hang`.
- [ ] **10. Speed (Reports E, E2).** Before: step 2; the cloud machines, never the Mac. `perf/runner/speed_headless.py --editors opendoc betteroffice onlyoffice` with the release's profile and seeds, twice. react-docx has no headless entry and joins Apryse in "not measured". E2 lanes are the UI branch's.
- [ ] **11. Facts and vendors page.** Before: every step above. `build/facts.py`. In `reports/vendors.md` and `build/test_report_claims.py`: move each lane's heading from `PENDING_HEADINGS` to the measured ones (`SLUGS`, `VENDOR_HEADINGS`, the anchor maps the test names) and replace "<tool> is not in the trial's reports yet: no published run of the trial includes it." with what was measured. Univer's section keeps "no .docx path" with `probe.univer.*` as its evidence.
- [ ] **12. Sentences the new lanes make false, or put in doubt.** Before: steps 3 to 7, so each is rewritten from a publication measurement. The lines are in `templates/reports/` as of 2026-11-21; the reason given is from development runs and is a lead, not a result.

| Where | Sentence | Why it moves |
|---|---|---|
| `vendors.md:5` | "measures fourteen tools ... Folio and eigenpal each have a second headless lane" | the count; BetterOffice has a second lane too |
| `Report A …:5, 12, 19, 46, 335, 393, 628` and `Report A2 …:504` | "the twelve editors", "the thirteenth participant" | literal counts |
| `Report A …:12` | five kinds of serialization boundary, and a sixth | needs a code read of each new editor's boundary |
| `Report A …:19` | "exactly two have a namespace-level reporting mechanism" | BetterOffice's `repackDocxWithWarnings` returns warnings; read what they cover |
| `Report A …:209` | "WordCraft is the only Rust editor here" | OpenDoc is Rust; BetterOffice's and react-docx's parsers are Rust compiled to WebAssembly |
| `Report A2 …:12, 148, 472` | "Docxodus is the only tool in the study with nothing changed and nothing dropped", "the only all-zero row" | `betteroffice-editor` changed one part (`docProps/core.xml`, a timestamp) and dropped none |
| `Report A2 …:99` | "Docen and WordCraft are the only editors that add parts" | react-docx added 5, BetterOffice 3 |
| `Report B …:11` | "Not one editor repairs anything ... every editor either reproduced the damage or dropped the part" | OpenDoc's output lacked d1, d2, d3, d5, d6 and BetterOffice's d2 to d5 and d12; repair or re-serialisation is a code read |
| `Report B …:13, 43, 271, 289` | Plate "is the only editor that ... refuses"; "has no row at all, and that absence is the finding" | OnlyOffice writes nothing either, on both corpora, and it is a stall, not a refusal: its row says "no output: the converter did not return" |
| `Report B …:41, 171` | "the only non-idempotent ones in the study" | BetterOffice's second pass is never byte-identical (it stamps `dcterms:modified`); say which sense is meant |
| `Report B …:269, 287` | "WordCraft is the only editor that removed the move-source defect and the block-math defect", "removed d10 and d11 and kept d12" | all three new outputs lacked d11 (d10 stayed in all three) |
| `Report B …:272` | "LibreOffice is the only one that repaired the `w:trPr` ordering" | OpenDoc's and BetterOffice's outputs lacked d3 |
| `Report C …:18` | "Eleven editors render the corpus recognisably" | the count, from step 8 |
| `Report C …:703` | WordCraft "the only tool in this study that is not a browser-based editor" | read against OpenDoc's native application |
| `Report E …:88` | "Apryse WebViewer. It has no headless entry point" | react-docx has none either (`harness/reactdocx/headless.mjs` is the evidence) |

Every other "the only", "no editor" and "every editor" in the templates is in doubt until read against the new outputs: `grep -n -E "the only|[Nn]o editor|[Nn]ot one editor|[Ee]very editor|none of the" templates/reports/*.md`. `vendors.md:395` (Apryse "the only commercial, closed-source tool" in the round trip) stays true: Nutrient is view-only and has no round-trip lane.

## 4. Reports (AGENTS.md §5)

- [ ] Figures change only through measurements or templates (`templates/<path>.md`), never the rendered report.
- [ ] **Nothing typed by hand.** Before rendering, grep the templates for literal figures:
  - [ ] dates: titles use `{{release.date}}`, Report C uses `{{ui.date}}`, code-read commits use `{{read.<repo>.commit}}` / `{{read.<repo>.date}}`. Edition notes and "added on" lines are history and stay literal;
  - [ ] counts: `{{count.participants:w}}`, `count.editors`, `count.open_editors`, `count.word_refused`, `count.word_outputs`, `count.p2_identical` (`:w` = word, `:W` = capitalised, `:ord` = ordinal). Ordinals that record who joined when ("the thirteenth participant") are history;
  - [ ] tables: generated tables come in as facts (`{{matrix.preserved}}`, `{{ns.matrix.N}}`, `{{bomb.scorecard}}`, `{{parts.matrix}}`, Report B's `{{xsd.*}}` / `{{pkg.*}}`, Report C's `{{wpx.*}}` / `{{lpx.*}}` / `{{sa.*}}`). v0.9.2 published a typed "0" XSD violations for Plate.js, which has one. A table with typed measured cells needs a generator; list each one that is still typed in the tracking issue;
  - [ ] versions: `{{ver.npm.*}}`, `{{ver.<repo>.commit}}`.
- [ ] `python3 build/facts.py`, then `python3 build/render_reports.py --stale out/facts-v<previous>.json`. Re-read **every sentence** about an editor whose facts moved: rankings, "ties", "only", "every", "none of", and lists of names next to a count.
- [ ] `python3 build/render_reports.py --all-twins` (every DOCX twin rebuilt, not only changed ones), then `--check`.
- [ ] Copy `out/facts.json` to `out/facts-vX.Y.Z.json` for the next release.

## 5. Live demos

- [ ] For every demo whose pin moved: `build/rebuild_demo.sh <slug>`. It checks out the pin from `repos/`, builds, and writes `dist/SOURCE.txt` from git. For an unchanged pin, the same command checks the checkout and re-stamps.
- [ ] `demos/<slug>/BUILD.md` names no commit; SOURCE.txt does.
- [ ] Compare each new `dist/` with `dist.prev/`: files that disappear (beyond content-hashed asset names) need explaining.
- [ ] **Lesson:** a failed build must never delete the last good build (the script now keeps `dist.prev` unless a new `dist` exists). Don't run the script from a copy outside `build/` without `TRIAL_ROOT`.
- [ ] **Lesson:** a partial clone under `repos/` cannot serve a fetch; the script falls back to upstream. A demo folder missing from upstream's lockfile needs `--no-frozen-lockfile`. pnpm 12 blocks build scripts unless `allowBuilds` names them. A demo patch must restore every file it touched before the checkout moves.
- [ ] Check what the demo actually bundles (a workspace link to the checkout, not an npm release that happens to match).
- [ ] A closed-source vendor with a trial key gets no public demo unless Arthur decides otherwise: the key would ship in the bundle.
- [ ] Open each rebuilt demo in a real browser before publishing (document loads, text visible, export works).
- [ ] **Lesson (et-v0.9.5, #225):** five demos were published with only their entry chunks; the lazily imported chunks, fonts and WASM were left behind, and each demo stayed on its loading screen. Copy the whole `dist/`, then run `build/verify_demo.py <slug> out/demos/<slug>` for every demo: it serves the folder as the site does and fails on any missing file or a document that does not appear. A demo that draws on a canvas (canvas-editor, Docen, WordCraft) has no text to find: pass a screenshot path as a third argument and look at the picture. Do it for demos that were not rebuilt too. Once per machine: `uv run --with playwright==1.64.1 playwright install chromium`.

## 6. Gate (AGENTS.md §6)

- [ ] Every `build/test_*.py` passes: `PYTHONPATH=. uv run --no-project --with pytest --with pyfakefs --with pyyaml --with playwright --with pytest-timeout python -m pytest -q build` (pytest collects both the unittest classes and the pytest functions).
- [ ] `build/verify_publication.sh --with-word` passes **twice**, with no `WRONG-DOCUMENT` or `ORACLE-NOT-CLEAN` lines.
- [ ] Every published `.docx` is Word valid: it opens in Word with no warning and no offer to repair.
- [ ] `git status`: no stray caches (`harness/ui/genoffice/.vite-cache`: restore it), no `.env`, no design-system zip.

## 7. Publishing (AGENTS.md §7)

- [ ] `CHANGELOG.md` section: Updated (pins), Measured (what changed, reproduced), Not re-measured, Added, Fixed.
- [ ] PR to `main`; gate any review comments individually; merge.
- [ ] Tag `vX.Y.Z` on the merge commit; GitHub release with the changelog section as notes.
- [ ] Publish the bundle (one command, from any directory with `bench` installed): `bench publish editors_trial et-vX.Y.Z`. It uploads `out/facts.json`, `out/release.json`, `reports/*.md`, `reports/*.docx` and any `reports/figures/` to the private HF dataset `arthrod/editors_trial-artifacts`, verifies every file on the Hub, appends `release/index.jsonl` + `release/et-vX.Y.Z/manifest.json`, and tags `et-vX.Y.Z` locally. Rerunning after a failure resumes. Then run the push it prints (a release branch gets a PR, as for et-v0.9.4, #75).
- [ ] Site: in `benchmarks-law`, `bench bump editors_trial` moves `bench.lock`'s `editors_trial=` line; the build reads `.bench/editors_trial/` (bench-ops plan 5).
- [ ] Site (`benchmarks-law`, on an up-to-date `main`): `pnpm sync:content`, `pnpm sync:vendors`, `pnpm sync:assets`, `pnpm sync:demos` (if any demo was rebuilt), then `pnpm run deploy`.
- [ ] Verify the live pages in a real browser (Chrome extension; Brave if it fails): home, `/editors-trial/`, vendors, every report, every demo.
- [ ] Commit the site, PR, merge, tag it with the same version.
- [ ] Close the issues, update the tracking issue, and note any leftovers (open PRs, unsent emails awaiting approval).
