#!/usr/bin/env bash
# Build one report into .docx and put it through the fixes Word needs.
#
#   pandoc      -> writes w:dirty="true" on the TOC field, which Word 16.115
#                  refuses outright
#   fix_dirty   -> rewrites that flag to "false"
#   bake_toc    -> fills the TOC field's cached result, so the table of
#                  contents is visible without a manual field update
#   retune      -> pandoc sizes every table for a PORTRAIT page; this document
#                  is LANDSCAPE, so the tables are re-fitted to the real
#                  content width
#
# usage: build/make_report.sh <report.md> [out.docx]
set -euo pipefail
BASE="/Users/arthrod/temp/T/editors_trial"
SRC="$1"
OUT="${2:-${SRC%.md}.docx}"

pandoc "$SRC" -f gfm -t docx \
  --reference-doc="$BASE/build/reference.docx" \
  --resource-path="$BASE:$(dirname "$SRC")" \
  --toc --toc-depth=3 \
  -o "$OUT"

python3 "$BASE/build/fix_dirty.py" "$OUT"
python3 "$BASE/build/bake_toc.py" "$OUT"
python3 "$BASE/build/retune_tables.py" "$OUT"
python3 "$BASE/build/fit_images.py" "$OUT"
echo "built: $OUT"
