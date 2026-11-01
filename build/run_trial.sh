#!/usr/bin/env bash
# The whole measurement, then the reports generated from it.
#
#   1. build/run_all.sh          every editor's own import -> export, and LibreOffice
#   2. build/run_second_pass.sh  every editor fed its own output
#   3. build/score_all.py        the first pass against the fixture
#   4. build/score_extra.py      the second pass and the editor lanes
#   5. build/facts.py            out/facts.json from the artifacts
#   6. build/render_reports.py   every report from its template, and its DOCX twin
#
# The hostile-package run (build/run_bomb_sandbox.py) and the star snapshot
# (build/stars.py) are separate: the first needs the sandbox image, the second
# the network. Run them before step 5 when a release re-measures them.
#
# usage: build/run_trial.sh
set -uo pipefail
BASE="/Users/arthrod/temp/T/editors_trial"
cd "$BASE"
bash build/run_all.sh
bash build/run_second_pass.sh
python3 build/score_all.py
python3 build/score_extra.py
python3 build/facts.py
python3 build/render_reports.py
