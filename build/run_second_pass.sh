#!/bin/bash
# Second pass: feed every editor its OWN first-pass output and re-score it.
#
# The first pass answers "does the editor keep the corpus?". The second pass
# answers the stricter question: "is the editor's own output still a valid
# document, and does re-importing it reach a fixed point?".
#
# Each harness is the same command build/run_all.sh uses, with the editor's
# own output as the input. The scorer is then run with the FIRST PASS as the
# reference, so the number reported is "how much of what this editor wrote
# survived this editor".
#
# usage: build/run_second_pass.sh
set -u
BASE="/Users/arthrod/temp/T/editors_trial"
OUTROOT="$BASE/out"

run() {
  name="$1"; shift
  in="$1"; shift
  dst="$OUTROOT/$name/second"
  rm -f "$dst/complex.docx"
  mkdir -p "$dst"
  ( "$@" ) >/tmp/sp_$name.log 2>&1
  if [ -s "$dst/complex.docx" ]; then
    echo "OK   $name ($(wc -c < "$dst/complex.docx" | tr -d ' ') bytes)"
  else
    echo "FAIL $name :: $(tail -4 /tmp/sp_$name.log | tr '\n' ' ' | cut -c1-200)"
  fi
}

second() {
  name="$1"; shift
  in="$OUTROOT/$name/complex.docx"
  [ -s "$in" ] || { echo "SKIP $name :: no first-pass output"; return; }
  # The command is a template. __IN__ and __OUT__ are substituted here, inside
  # the function, so that each editor is fed its OWN first-pass output.
  cmd="${1//__IN__/$in}"
  cmd="${cmd//__OUT__/$OUTROOT/$name/second/complex.docx}"
  cmd="${cmd//__OUTDIR__/$OUTROOT/$name/second}"
  run "$name" "$in" bash -c "$cmd"
}

# --- baseline: LibreOffice ---
in="$OUTROOT/lo_baseline/complex.docx"
if [ -s "$in" ]; then
  dst="$OUTROOT/lo_baseline/second"; rm -rf "$dst"; mkdir -p "$dst"
  timeout 200 soffice --headless --norestore --convert-to docx --outdir "$dst" "$in" >/tmp/sp_lo.log 2>&1
  if [ -s "$dst/complex.docx" ]; then
    echo "OK   lo_baseline ($(wc -c < "$dst/complex.docx" | tr -d ' ') bytes)"
  else
    echo "FAIL lo_baseline :: $(tail -3 /tmp/sp_lo.log | tr '\n' ' ' | cut -c1-200)"
  fi
else
  echo "SKIP lo_baseline :: no first-pass output"
fi

second plate \
  "cd $BASE/harness/plate && bun --preload ./aliases.ts roundtrip.ts '__IN__' '__OUT__'"
second eigenpal \
  "cd $BASE/repos/eigenpal-docx-editor && bun $BASE/harness/eigenpal.ts '__IN__' '__OUT__' store"
second folio \
  "cd $BASE/repos/folio && bun $BASE/harness/folio.ts '__IN__' '__OUT__' model"
second genoffice \
  "cd $BASE/repos/genoffice && node --import $BASE/harness/css-stub.mjs --import $BASE/repos/genoffice/node_modules/tsx/dist/loader.mjs $BASE/harness/genoffice.cts '__IN__' '__OUT__'"
second superdoc \
  "cd $BASE && node $BASE/harness/superdoc.mjs '__IN__' '__OUT__'"
second officeopen \
  "cd $BASE/repos/office-open && ./node_modules/.bin/tsx --tsconfig $BASE/repos/office-open/packages/docx/tsconfig.json $BASE/harness/officeopen/roundtrip.mts '__IN__' '__OUT__'"
second docen \
  "cd $BASE/repos/docen && ./node_modules/.bin/tsx $BASE/harness/docen/roundtrip.mts '__IN__' '__OUT__'"
second fidus \
  "cd $BASE/repos/fiduswriter-document-ts && IN_DOCX='__IN__' OUT_DOCX='__OUT__' TEMPLATE=generated ./node_modules/.bin/tsx --no-cache $BASE/harness/fidus/roundtrip.mts"
second wordcraft \
  "cd $BASE/harness/wordcraft && cargo run --release -- '__IN__' '__OUT__'"
second canvas \
  "cd $BASE/repos/canvas-editor && IN_DOCX='__IN__' OUT_DIR='__OUTDIR__' ./node_modules/.bin/vitest run --root $BASE/harness/canvas"
second docsplus \
  "mkdir -p $BASE/out/docsplus/second/evidence && cd $BASE/harness/docsplus/repo-copy && EVIDENCE_DIR=$BASE/out/docsplus/second/evidence bun $BASE/harness/docsplus/roundtrip.ts '__IN__' '__OUT__'"
second docxodus \
  "cd $BASE/harness/ui/docxodus && node roundtrip.mjs '__IN__' '__OUT__'"

pkill -f "superdoc host" 2>/dev/null
echo "=== SECOND PASS DONE ==="
