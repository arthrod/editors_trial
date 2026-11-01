#!/usr/bin/env bash
# Every Microsoft Word step of a release, each twice, with the two passes compared.
#
#   1. word_verdicts.py                Word on every editor's output      (main report, D2)
#   2. word_verdicts.py --set broken   Word on the broken-corpus outputs  (Report B)
#   3. Report C's pixel layer          word_render_all.py, word_pages.py, render_compare_word.py
#
# Word is opened only by the audited driver (build/vendor/word_pdf.py, through
# build/word_batch.py); the driver starts, recycles and watches Word itself.
# Run it the way the bench's handoff says: in the foreground of a Terminal tab,
# Word in front with no documents open, nothing else driving Word. Never start
# Word by hand or with ad-hoc osascript.
#
# The second pass of each step is the one installed; a step whose passes
# differ prints DIFFER and is not a result (AGENTS.md §4).
#
# usage: build/release_word.sh [verdicts|broken|pixels ...]   (default: all three)
#        RELEASE_WORK=/tmp/release-x build/release_word.sh
set -uo pipefail
BASE="$(cd "$(dirname "$0")/.." && pwd)"
cd "$BASE"
L=${RELEASE_WORK:-/tmp/release-word}
mkdir -p "$L"
steps=("$@"); [ ${#steps[@]} -eq 0 ] && steps=(verdicts broken pixels)

same_verdicts() {  # same_verdicts <a.json> <b.json>
  python3 -c "import json,sys;a,b=(json.load(open(p))['verdicts'] for p in sys.argv[1:3]);d={k:(a.get(k),b.get(k)) for k in set(a)|set(b) if a.get(k)!=b.get(k)};print('verdicts identical' if not d else 'verdicts DIFFER: %s'%d)" "$1" "$2"
}

for step in "${steps[@]}"; do
  case "$step" in
    verdicts|broken)
      set_name=outputs; json=out/word_verdicts.json
      [ "$step" = broken ] && { set_name=broken; json=out/word_verdicts_broken.json; }
      for i in 1 2; do
        echo "== Word verdicts ($set_name), pass $i ($(date +%T))"
        python3 build/word_verdicts.py --set "$set_name" "$L/$step$i" | tee "$L/$step$i.txt"
        cp "$json" "$L/$step$i.json"
      done
      same_verdicts "$L/${step}1.json" "$L/${step}2.json"
      rm -rf "out/word_verdicts$([ "$step" = broken ] && echo _broken)"
      cp -R "$L/${step}2" "out/word_verdicts$([ "$step" = broken ] && echo _broken)" ;;
    pixels)
      for i in 1 2; do
        D="$L/render$i"; rm -rf "$D"; mkdir -p "$D"
        echo "== Word pixels, pass $i ($(date +%T))"
        python3 build/word_render_all.py "$D/word" | tee "$D/render.log"
        python3 build/word_pages.py "$D" > "$D/pages.log" 2>&1; echo "pages $i exit $?"
        python3 build/render_compare_word.py "$D" > "$D/compare.log" 2>&1; echo "compare $i exit $?"
      done
      if cmp -s "$L/render1/word_render_compare.json" "$L/render2/word_render_compare.json"; then
        echo "pixel layer: identical"
        for p in word png_word; do rm -rf "out/render/$p"; cp -R "$L/render2/$p" "out/render/$p"; done
        cp "$L/render2/word_render_compare.json" out/render/word_render_compare.json
      else
        echo "pixel layer DIFFERS: out/render left as it was"
      fi ;;
    *) echo "unknown step: $step (verdicts, broken, pixels)" >&2; exit 2 ;;
  esac
done
echo "== done ($(date +%T)); next: python3 build/facts.py && python3 build/render_reports.py"
