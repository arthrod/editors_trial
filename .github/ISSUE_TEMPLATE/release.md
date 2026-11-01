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
| [ ] | Apryse trial-stamp labels (never edits the output) | `python3 -I build/apryse_stamp.py` | main, extras |
| [ ] | Broken corpus (×2) | `build/run_broken.sh`, `build/defect_survival.py` | B |
| [ ] | Word opens every output (×2, identical) | `build/word_verdicts.py` | main, B, D2 |
| [ ] | Report A namespace tables | `build/ns_json.py`; check §6 with `build/report_a_matrix.py --patch` on a copy | A |
| [ ] | Report C: each editor's own UI (×2) | `OUT=/tmp/ui-runN build/capture_ui.sh`, then `build/compare_ui.py run1 run2` and `compare_ui.py out/ui run2` | C |
| [ ] | Report C: copy the accepted run to `out/ui` (with `captured_at.txt`), rebuild figures | `build/ui_figures.py` | C |
| [ ] | Report C: Word's pixels (×2) | `build/word_render_all.py`, `build/word_pages.py`, `build/render_compare_word.py` | C |
| [ ] | Hostile packages, sandbox (×2, quiet CPU; not Google Docs or Word) | `build/run_bomb_sandbox.py` (resume mode), `build/label_protection.py` | D |
| [ ] | Jubarte on the hostile packages | `build/run_jubarte_bombs.py` | D1 |
| [ ] | Star counts | `build/stars.py` | main |
| [ ] | Facts | `build/facts.py` | all |

- [ ] **A new participant joins every lane:** `run_all.sh`, `run_second_pass.sh`, `score_all.py`, `score_extra.py`, `word_verdicts.py`, `ns_map.py`, `word_render_all.py`, `word_pages.py`, `render_compare_word.py`, `ui_figures.py`, `capture_ui.sh`, `update_editors.sh`, `run_broken.sh`, `defect_survival.py`, `run_bomb_sandbox.py`, `label_protection.py`, `preserved_matrix.py`, `facts.py` (`TOOLS`, `NPM`, `SDKS`/`CLOSED`), `test_report_claims.py`, `vendors.md`, `extras/<slug>.md`.
- [ ] **Lesson (scripts are suspects, §4):** read the full cell log before believing a label. The sandbox once scored a Chromium launch crash as "refused/bounded-reject"; it is now `harness-browser-launch`.
- [ ] **Lesson:** a run that differs from its twin is not a result. Apryse's two round trips once differed in bytes (comment model vs. kept part) at the same score. That points at the harness exporting before the document finished loading; make the driver wait for real readiness before export.
- [ ] **Lesson:** never edit a shell script while bash is running it. Bash reads the file as it goes, and an edit garbles the rest of the run. Freeze a copy to run, and edit the original.
- [ ] **Lesson:** `run_bomb_sandbox.py` without resume deletes `logs/bombs`, and `TOOL_ONLY` / `BOMB_SKIP_LO` drop the other rows from the scorecard. Use resume and seed the existing lines.
- [ ] Anything not re-run is named, with the reason, in the changelog's "Not re-measured" and in the report itself.

## 4. Reports (AGENTS.md §5)

- [ ] Figures change only through measurements or templates (`templates/<path>.md`), never the rendered report.
- [ ] **Nothing typed by hand.** Before rendering, grep the templates for literal figures:
  - [ ] dates: titles use `{{release.date}}`, Report C uses `{{ui.date}}`, code-read commits use `{{read.<repo>.commit}}` / `{{read.<repo>.date}}`. Edition notes and "added on" lines are history and stay literal;
  - [ ] counts: `{{count.participants:w}}`, `count.editors`, `count.open_editors`, `count.word_refused`, `count.word_outputs`, `count.p2_identical` (`:w` = word, `:W` = capitalised, `:ord` = ordinal). Ordinals that record who joined when ("the thirteenth participant") are history;
  - [ ] tables: generated tables come in as facts (`{{matrix.preserved}}`, `{{ns.matrix.N}}`, `{{bomb.scorecard}}`). A table with typed measured cells needs a generator; list each one that is still typed in the tracking issue;
  - [ ] versions: `{{ver.npm.*}}`, `{{ver.<repo>.commit}}`.
- [ ] `python3 build/facts.py`, then `python3 build/render_reports.py --stale out/facts-v<previous>.json`. Re-read **every sentence** about an editor whose facts moved: rankings, "ties", "only", "every", "none of", and lists of names next to a count.
- [ ] `python3 build/render_reports.py`, then `--check`.
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
