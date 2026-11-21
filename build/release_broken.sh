#!/usr/bin/env bash
# Report B: every editor over the broken corpus, twice into scratch directories, compared
# cell by cell (defect_survival.survival); pass 2 is installed in out_broken/ only when the cells agree.
# Byte differences between passes are expected (core.xml timestamps, regenerated media names).
# usage: build/release_broken.sh   then build/release_word.sh broken
set -uo pipefail
B="$(cd "$(dirname "$0")/.." && pwd)"; L=${RELEASE_WORK:-/tmp/release-broken}; mkdir -p "$L"
cp "$B/build/run_broken.sh" "$L/run_broken.copy.sh"
for i in 1 2; do
  rm -rf "$L/broken$i"; mkdir -p "$L/broken$i"
  echo "== broken corpus, pass $i ($(date +%T))"
  # the copy is outside the checkout, so it is told where the checkout is
  TRIAL_ROOT="$B" OUTROOT="$L/broken$i" bash "$L/run_broken.copy.sh"
  for f in /tmp/rb_*.log; do cp "$f" "$L/broken$i/"; done
done
python3 -I - "$B/build" "$L/broken1" "$L/broken2" "$B/out_broken" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
import defect_survival as ds
# cells and no-output records (no_output.json) must agree between the passes
raise SystemExit(0 if ds.install(sys.argv[2], sys.argv[3], sys.argv[4]) else 1)
PY
echo "== done ($(date +%T)); next: build/release_word.sh broken"
