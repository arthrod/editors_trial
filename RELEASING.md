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
| [ ] | Apryse trial-stamp labels (never edits the output) | `python3 -I build/apryse_stamp.py` | main, extras |
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
- [ ] **A new participant joins every lane:** `run_all.sh`, `run_second_pass.sh`, `score_all.py`, `score_extra.py`, `word_verdicts.py`, `ns_map.py`, `word_render_all.py`, `word_pages.py`, `render_compare_word.py`, `ui_figures.py`, `capture_ui.sh`, `update_editors.sh`, `run_broken.sh`, `defect_survival.py`, `run_bomb_sandbox.py`, `label_protection.py`, `preserved_matrix.py`, `facts.py` (`TOOLS`, `NPM`, `SDKS`/`CLOSED`), `test_report_claims.py`, `vendors.md`, `extras/<slug>.md`, and every audit that reads `out/<tool>/complex.docx` (`lo_pages.py`, `lo_render_compare.py`, `render_compare.py`, `render_pages.py`, `render_inventory.py`, `ct_coherence.py`, `orphan_audit.py`, `rel_forward.py`, `malformation_audit.py`, `validate_all_outputs.py`, `scan_word_hostile.py`, `part_map.py`, `verify_findings.py`, `measure_alternate_content.py`). `build/test_every_lane.py` fails on any script that reads SuperDoc's output and not the newest participant's.
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

## 6. Gate (AGENTS.md §6)

- [ ] Every `build/test_*.py` passes: `python3 -m unittest discover -s build -p "test_*.py"`.
- [ ] `build/verify_publication.sh --with-word` passes **twice**, with no `WRONG-DOCUMENT` or `ORACLE-NOT-CLEAN` lines.
- [ ] Every published `.docx` is Word valid: it opens in Word with no warning and no offer to repair.
- [ ] `git status`: no stray caches (`harness/ui/genoffice/.vite-cache`: restore it), no `.env`, no design-system zip.

## 7. Publishing (AGENTS.md §7)

- [ ] `CHANGELOG.md` section: Updated (pins), Measured (what changed, reproduced), Not re-measured, Added, Fixed.
- [ ] PR to `main`; gate any review comments individually; merge.
- [ ] Tag `vX.Y.Z` on the merge commit; GitHub release with the changelog section as notes.
- [ ] Site (`benchmarks-law`, on an up-to-date `main`): `pnpm sync:content`, `pnpm sync:vendors`, `pnpm sync:assets`, `pnpm sync:demos` (if any demo was rebuilt), then `pnpm run deploy`.
- [ ] Verify the live pages in a real browser (Chrome extension; Brave if it fails): home, `/editors-trial/`, vendors, every report, every demo.
- [ ] Commit the site, PR, merge, tag it with the same version.
- [ ] Close the issues, update the tracking issue, and note any leftovers (open PRs, unsent emails awaiting approval).
