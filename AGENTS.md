# AGENTS.md — working on the editors trial

The trial is a measurement: every figure in every report comes from running
the editors. These rules keep each release honest and repeatable. They bind
people and agents alike.

## Releases

The step-by-step inventory, with the lessons of earlier releases, is
`RELEASING.md`. A release's tracking issue is opened from the "Release" issue
template (`.github/ISSUE_TEMPLATE/release.md`), which carries the same
checklist; `build/test_release_template.py` keeps the two identical.

### 1. Every release updates the editors

Unless the request for a release says otherwise, **every release moves every
editor to its newest version that is at least 5 days old on the release
date**, and **never to a version older than the one currently pinned**.

- Git checkouts (`repos/<name>`): the newest commit of the upstream default
  branch (Plate measures its `next` branch) committed on or before the cutoff.
- Published packages (`@superdoc/sdk` on the `next` channel; `docxodus` and
  `@docxodus/export` on `latest`): the newest version published on or before
  the cutoff.
- The cutoff is the release date minus 5 days. A version newer than the
  cutoff waits for the next release; this keeps a broken or compromised
  release out of the measurement.
- If the newest version before the cutoff is older than the current pin, the
  current pin stays. A release never measures older code than the last one.

`build/update_editors.sh` applies the rule (it calls `build/pin_versions.py`;
`RELEASE_DATE=YYYY-MM-DD` overrides today). Do not move a pin by hand.

### 2. If anything changed, every report is re-measured

If any pin moved, **re-run every measurement and update every report**, not
only the ones you expect to change. A report that was not re-measured is out
of date even when its numbers happen to match.

The measurements, in order (`build/run_trial.sh` runs the ones it can):

| Step | Command | Feeds |
|---|---|---|
| Round trip, every editor | `build/run_all.sh` | main report, A, A2, B |
| Second pass | `build/run_second_pass.sh` | main report, A2 |
| Scores | `build/score_all.py`, `build/score_extra.py`, then `build/apryse_stamp.py` (labels the trial stamp, never edits the output) | all |
| Broken corpus | `build/run_broken.sh`, `build/defect_survival.py` | B |
| Word opens every output | `build/word_verdicts.py`, `build/word_verdicts.py --set broken` | main report, B, D2 |
| Report A namespace tables | `build/ns_json.py`; check §6 with `build/report_a_matrix.py --patch` on a copy | A |
| Report C: each editor's own UI | `build/capture_ui.sh` (twice; compare with `build/compare_ui.py`) | C |
| Report C: Word's pixels | `build/word_render_all.py`, `build/word_pages.py`, `build/render_compare_word.py` | C |
| Report C: LibreOffice's pixels, SmartArt controls, A/B variants | `build/lo_render_compare.py`, `build/raster_controls.py`, `build/smartart_verify.py`, `build/lo_pages.py`, `build/ab_table.py`, `build/construct_presence.py`, `build/render_inventory.py`, `build/strips.py` | C |
| Report B: XSD and package integrity | `build/validate_all_outputs.py`, `build/malformation_audit.py` | B |
| Hostile packages (sandbox) | `build/run_bomb_sandbox.py`, `build/label_protection.py` | D |
| Jubarte on the hostile packages | `build/run_jubarte_bombs.py` | D1 |
| Star counts | `build/stars.py` | main report |
| Facts and reports | `build/facts.py`, `build/render_reports.py` | all |
| Live demos | `demos/<editor>/BUILD.md`, then `pnpm sync:demos` in the site | benchmarks.law |

**Exception: Google Docs and Microsoft Word are never re-tested on the hostile
packages.** Their rows in Report D and Report D2 stay as measured; a release
does not upload the hostile packages to Google or open them in Word again.
Word is still used for everything that is not hostile: opening every editor
output, and Report C's pixel layer.

Every page image compared pixel by pixel is rasterised at **200 dpi**
(`build/pixels.py`, from v0.9.3); no script sets its own resolution.

Anything else that is not re-run is named in the changelog's "Not
re-measured" section and in the report itself. Never leave it silent.

### 3. Measure on a quiet machine

The hostile-package cells have CPU and wall-clock budgets, and Word is a
single shared application. Before measuring:

- check `uptime` and `ps -Ao pcpu,comm -r | head`; nothing else heavy may run
  (in particular no `neurotic_docx_bench` batch and no other Word job);
- if something is running, wait or ask; never kill another session's job.

### 4. Every change is reproduced twice, and the scripts are suspects

- **A result that differs from the last release is re-run at least twice**
  before it is published. A change that does not reproduce is not a result.
- **Check our own scripts before blaming an editor.** Read the full cell log,
  not the label: a harness that truncates output, mislabels a signal, or
  overwrites evidence produces a "change" no editor made. When a script is
  wrong, fix it with a test, and re-check the previous release with the fix.
- If the old version is still installable, run it under the fixed scripts to
  separate an editor change from an environment change.

### 5. Reports are generated, never hand-edited for figures

- Every report is rendered from `templates/<path>.md` and `out/facts.json`
  (`build/render_reports.py`). Change a figure by changing the measurement
  or the template, never the rendered report.
- After the facts change, run `build/render_reports.py --stale <old facts>`
  and re-read every sentence about an editor whose facts moved: prose such as
  rankings, "ties" and "only" claims is not a placeholder.
- Keep `out/facts-v<previous>.json` so the next release can diff against it.

### 6. The release gate

- `build/verify_publication.sh --with-word` must pass, twice, with no
  `WRONG-DOCUMENT` or `ORACLE-NOT-CLEAN` lines (those mean Word was shared).
- Every unit test in `build/test_*.py` passes.

### 7. Publishing

1. `CHANGELOG.md`: a new section with Updated (pins), Measured (what changed,
   reproduced), Not re-measured, Added, Fixed.
2. PR to `main`, merge, tag `vX.Y.Z` on the merge commit, GitHub release with
   the changelog section as notes.
3. Site (`benchmarks-law`, on `main`, not a stale branch):
   `pnpm sync:content`, `sync:vendors`, `sync:assets`, `sync:demos` when the
   demos were rebuilt, then `pnpm run deploy`. Verify the live pages in a real
   browser. Commit, PR, merge, and tag the site with the same version.

## Cloud agent environment

Harness scripts use the absolute path `/Users/arthrod/temp/T/editors_trial`. The environment links the workspace to that path. Editor checkouts live in gitignored `repos/` at the commits recorded in `out/facts.json` (`ver.<repo>.commit`). Do not move a pin except with `build/update_editors.sh` during a release. Node on `PATH` is 24, which canvas-editor and docs.plus require. Round trip every editor with `build/run_all.sh`. Unit tests: `python3 -m unittest discover -s build -p 'test_*.py'`. Apryse's browser round trip reads `APRYSE_API_KEY` from gitignored `.env`. Microsoft Word does not run on Linux.

## Other standing rules

- Issues first: every piece of work is a GitHub issue (ending with
  `@coderabbitai plan`) before code is written; a tracking issue lists them.
- Nothing under `repos/` is modified. Installing its dependencies is allowed.
- Run Python that reads untrusted input (hostile packages, downloaded
  archives) with `python3 -I`.
- Use pnpm and biome in TypeScript projects; uv in Python projects.
- "Word valid" means Microsoft Word opens the file with no warning and no
  offer to repair it.
