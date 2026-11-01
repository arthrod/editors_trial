#!/usr/bin/env bash
# The whole measurement, then the reports generated from it.
#
#   1. build/run_all.sh          every editor's own import -> export, and LibreOffice
#   2. build/run_second_pass.sh  every editor fed its own output
#   3. build/score_all.py        the first pass against the fixture
#   4. build/score_extra.py      the second pass and the editor lanes
#      build/apryse_stamp.py     labels what Apryse's trial stamp added (never edits it)
#   5. build/ns_json.py          out/ns_map.json, Report A's namespace tables
#   6. build/facts.py            out/facts.json from the artifacts
#   7. build/render_reports.py   every report from its template, and its DOCX twin
#
# Separate, because each needs something this script cannot assume (AGENTS.md
# lists them all); run them before step 6 when a release re-measures them:
#   build/run_bomb_sandbox.py, build/run_jubarte_bombs.py   the sandbox image
#   build/stars.py                                          the network
#   build/capture_ui.sh                                     a quiet machine (Report C, UI)
#   build/word_verdicts.py; build/word_render_all.py, build/word_pages.py,
#   build/render_compare_word.py                            Microsoft Word, unshared
# Report A's section 6 matrix is checked with build/report_a_matrix.py --patch
# on a copy of the rendered report; it must come back unchanged.
#
# usage: build/run_trial.sh
set -uo pipefail
BASE="/Users/arthrod/temp/T/editors_trial"
cd "$BASE"
bash build/run_all.sh
bash build/run_second_pass.sh
python3 build/score_all.py
python3 build/score_extra.py
python3 -I build/apryse_stamp.py
python3 build/ns_json.py
python3 build/facts.py
python3 build/render_reports.py
