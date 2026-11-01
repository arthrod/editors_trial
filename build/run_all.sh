#!/bin/bash
# Re-run every editor's import->export round trip against the current fixture.
# Each harness uses that project's OWN code path (see harness/<name>/ and harness/<name>.ts).
BASE=/Users/arthrod/temp/T/editors_trial
IN=$BASE/fixture/complex.docx

run() {
  name="$1"; shift
  rm -f "$BASE/out/$name/complex.docx"
  ( "$@" ) >/tmp/rr_$name.log 2>&1 \
    && echo "OK   $name  ($(wc -c < "$BASE/out/$name/complex.docx" 2>/dev/null | tr -d ' ') bytes)" \
    || echo "FAIL $name :: $(tail -4 /tmp/rr_$name.log | tr '\n' ' ' | cut -c1-200)"
}

# --- baseline: LibreOffice ---
rm -rf "$BASE/out/lo_baseline"; mkdir -p "$BASE/out/lo_baseline"
timeout 200 soffice --headless --norestore --convert-to docx --outdir "$BASE/out/lo_baseline" "$IN" >/tmp/rr_lo.log 2>&1 \
  && echo "OK   libreoffice ($(wc -c < "$BASE/out/lo_baseline/complex.docx" | tr -d ' ') bytes)" \
  || echo "FAIL libreoffice :: $(tail -3 /tmp/rr_lo.log | tr '\n' ' ')"

run plate    bash -c "cd $BASE/harness/plate && bun --preload ./aliases.ts roundtrip.ts $IN $BASE/out/plate/complex.docx"
run eigenpal bash -c "cd $BASE/repos/eigenpal-docx-editor && bun $BASE/harness/eigenpal.ts $IN $BASE/out/eigenpal/complex.docx store"
run eigenpal-editor bash -c "cd $BASE/repos/eigenpal-docx-editor && bun $BASE/harness/eigenpal.ts $IN $BASE/out/eigenpal-editor/complex.docx editor"
run folio    bash -c "cd $BASE/repos/folio && bun $BASE/harness/folio.ts $IN $BASE/out/folio/complex.docx model"
run folio-editor bash -c "cd $BASE/repos/folio && bun $BASE/harness/folio.ts $IN $BASE/out/folio-editor/complex.docx editor"
run genoffice bash -c "cd $BASE/repos/genoffice && node --import $BASE/harness/css-stub.mjs --import $BASE/repos/genoffice/node_modules/tsx/dist/loader.mjs $BASE/harness/genoffice.cts $IN $BASE/out/genoffice/complex.docx"
run superdoc bash -c "cd $BASE && node $BASE/harness/superdoc.mjs $IN $BASE/out/superdoc/complex.docx"
run officeopen bash -c "cd $BASE/repos/office-open && ./node_modules/.bin/tsx --tsconfig $BASE/repos/office-open/packages/docx/tsconfig.json $BASE/harness/officeopen/roundtrip.mts $IN $BASE/out/officeopen/complex.docx"
run docen   bash -c "cd $BASE/repos/docen && ./node_modules/.bin/tsx $BASE/harness/docen/roundtrip.mts $IN $BASE/out/docen/complex.docx"
run fidus   bash -c "cd $BASE/repos/fiduswriter-document-ts && IN_DOCX=$IN OUT_DOCX=$BASE/out/fidus/complex.docx TEMPLATE=generated ./node_modules/.bin/tsx --no-cache $BASE/harness/fidus/roundtrip.mts"
run wordcraft bash -c "cd $BASE/harness/wordcraft && cargo run --release -- $IN $BASE/out/wordcraft/complex.docx"
run canvas  bash -c "cd $BASE/repos/canvas-editor && ./node_modules/.bin/vitest run --root $BASE/harness/canvas"
run docsplus bash -c "cd $BASE/harness/docsplus/repo-copy && bun $BASE/harness/docsplus/roundtrip.ts $IN $BASE/out/docsplus/complex.docx"
run docxodus bash -c "cd $BASE/harness/ui/docxodus && node roundtrip.mjs $IN $BASE/out/docxodus/complex.docx"

pkill -f "superdoc host" 2>/dev/null
echo "=== ALL ROUND TRIPS DONE ==="
