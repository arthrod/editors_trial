#!/bin/bash
# Run every editor's import->export over the DELIBERATELY BROKEN corpus
# (fixture/complex_broken.docx - twelve defect classes re-introduced) to see
# which editors, if any, repair malformed input.
#
# Each editor's own code path, same harnesses as build/run_all.sh.
BASE=/Users/arthrod/temp/T/editors_trial
IN=$BASE/fixture/complex_broken.docx
OUTROOT=${OUTROOT:-$BASE/out_broken}   # a scratch directory for a reproduction run
mkdir -p "$OUTROOT"

run() {
  name="$1"; shift
  d="$OUTROOT/$name"; mkdir -p "$d"
  rm -f "$d/complex.docx"
  ( "$@" ) >/tmp/rb_$name.log 2>&1 \
    && echo "OK   $name  ($(wc -c < "$d/complex.docx" 2>/dev/null | tr -d ' ') bytes)" \
    || echo "FAIL $name :: $(tail -4 /tmp/rb_$name.log | tr '\n' ' ' | cut -c1-200)"
}

mkdir -p "$OUTROOT/lo_baseline"
rm -f "$OUTROOT/lo_baseline/complex.docx"
timeout 200 soffice --headless --norestore --convert-to docx --outdir "$OUTROOT/lo_baseline" "$IN" >/tmp/rb_lo.log 2>&1 \
  && mv "$OUTROOT/lo_baseline/complex_broken.docx" "$OUTROOT/lo_baseline/complex.docx" \
  && echo "OK   libreoffice ($(wc -c < "$OUTROOT/lo_baseline/complex.docx" | tr -d ' ') bytes)" \
  || echo "FAIL libreoffice :: $(tail -3 /tmp/rb_lo.log | tr '\n' ' ')"

run plate    bash -c "cd $BASE/harness/plate && bun --preload ./aliases.ts roundtrip.ts $IN $OUTROOT/plate/complex.docx"
run eigenpal  bash -c "cd $BASE/repos/eigenpal-docx-editor && bun $BASE/harness/eigenpal.ts $IN $OUTROOT/eigenpal/complex.docx store"
run folio     bash -c "cd $BASE/repos/folio && bun $BASE/harness/folio.ts $IN $OUTROOT/folio/complex.docx model"
run genoffice bash -c "cd $BASE/repos/genoffice && node --import $BASE/harness/css-stub.mjs --import $BASE/repos/genoffice/node_modules/tsx/dist/loader.mjs $BASE/harness/genoffice.cts $IN $OUTROOT/genoffice/complex.docx"
run superdoc  bash -c "cd $BASE && node $BASE/harness/superdoc.mjs $IN $OUTROOT/superdoc/complex.docx"
run officeopen bash -c "cd $BASE/repos/office-open && ./node_modules/.bin/tsx --tsconfig $BASE/repos/office-open/packages/docx/tsconfig.json $BASE/harness/officeopen/roundtrip.mts $IN $OUTROOT/officeopen/complex.docx"
run docen     bash -c "cd $BASE/repos/docen && ./node_modules/.bin/tsx $BASE/harness/docen/roundtrip.mts $IN $OUTROOT/docen/complex.docx"
run fidus     bash -c "cd $BASE/repos/fiduswriter-document-ts && IN_DOCX=$IN OUT_DOCX=$OUTROOT/fidus/complex.docx TEMPLATE=generated ./node_modules/.bin/tsx --no-cache $BASE/harness/fidus/roundtrip.mts"
run wordcraft bash -c "cd $BASE/harness/wordcraft && cargo run --release -- $IN $OUTROOT/wordcraft/complex.docx"
run canvas    bash -c "cd $BASE/repos/canvas-editor && IN_DOCX=$IN OUT_DIR=$OUTROOT/canvas ./node_modules/.bin/vitest run --root $BASE/harness/canvas"
run docsplus  bash -c "cd $BASE/harness/docsplus/repo-copy && EVIDENCE_DIR=$OUTROOT/docsplus/evidence bun $BASE/harness/docsplus/roundtrip.ts $IN $OUTROOT/docsplus/complex.docx"
run docxodus  bash -c "cd $BASE/harness/ui/docxodus && node roundtrip.mjs $IN $OUTROOT/docxodus/complex.docx"
run apryse    bash -c "cd $BASE/harness/apryse && node roundtrip.mjs $IN $OUTROOT/apryse/complex.docx"

pkill -f "superdoc host" 2>/dev/null
echo "=== BROKEN-CORPUS ROUND TRIPS DONE ==="
