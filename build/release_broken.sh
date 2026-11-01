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
  OUTROOT="$L/broken$i" bash "$L/run_broken.copy.sh"
  for f in /tmp/rb_*.log; do cp "$f" "$L/broken$i/"; done
done
python3 -I - "$B/build" "$L/broken1" "$L/broken2" "$B/out_broken" <<'PY'
import shutil, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import defect_survival as ds
a, b = ds.survival(sys.argv[2]), ds.survival(sys.argv[3])
for d in a:
    print(f"{d:12s} {'same cells' if a[d] == b[d] else 'cells DIFFER'}")
if a != b:
    print("passes differ: out_broken/ left as it was"); raise SystemExit(1)
out = Path(sys.argv[4])
for d in b:
    src = Path(sys.argv[3]) / d / "complex.docx"
    if src.exists():
        (out / d).mkdir(parents=True, exist_ok=True); shutil.copy(src, out / d / "complex.docx")
(out / "logs").mkdir(exist_ok=True)
for log in (Path(sys.argv[3])).glob("rb_*.log"):
    shutil.copy(log, out / "logs" / log.name)
print("installed pass 2 in out_broken/")
PY
echo "== done ($(date +%T)); next: build/release_word.sh broken"
