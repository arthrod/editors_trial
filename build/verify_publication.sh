#!/usr/bin/env bash
# Run every gate that has to pass before the reports are published.
#
# The gates answer different questions, and none of them substitutes for
# another:
#
#   generated      is each report exactly its template rendered against
#                  out/facts.json (build/facts.py), the current measurement?
#   twin parity    does each published DOCX say what its Markdown source says,
#                  and is it exactly what the build pipeline produces?
#   findings       does every figure in the published tables belong to the
#                  subject the table row names? (a token-level check cannot
#                  answer this - "SuperDoc 100%" and "SuperDoc 84.9%" are
#                  both strings that occur somewhere in the logs)
#   numbers        does every percentage and byte size in every live report
#                  occur somewhere in the measurement artifacts?
#   OOXML schema   does every published DOCX validate against the ECMA-376
#                  schemas?
#   claim matrix   does every claim in the review matrix have an evidence
#                  identifier, a support level and, where it is unsupported, a
#                  requested action?
#   Word           does every deliverable actually open in Microsoft Word?
#
# usage: build/verify_publication.sh [--with-word]
#
#   --with-word   also drive Microsoft Word to open every deliverable. It is
#                 off by default because it is slow and it needs the desktop
#                 session; run it before a release.
set -uo pipefail
BASE="/Users/arthrod/temp/T/editors_trial"
cd "$BASE"

WITH_WORD=0
for arg in "$@"; do
  case "$arg" in
    --with-word) WITH_WORD=1 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

FAILED=()
PASSED=()

run() {
  local name="$1"; shift
  printf '\n=== %s ===\n' "$name"
  if "$@"; then
    PASSED+=("$name")
  else
    FAILED+=("$name")
  fi
}

# 1. The repository's own test suite.
run "repo tests" python3 build/test_report_claims.py

# 2. Every report is its template rendered against the current measurement.
run "generated" bash -c 'cd build && python3 -m unittest -q test_reportgen && cd .. && python3 build/facts.py >/dev/null && python3 build/render_reports.py --check'

# 3. Every published DOCX is the faithful twin of its Markdown source.
run "twin parity" python3 build/verify_twin_parity.py

# 4. Every figure in the published tables matches the measurement for its subject.
run "findings" python3 build/verify_findings.py --ledger out/findings_ledger.csv

# 5. Every percentage and byte size in every live report is in the measurement.
run "number gate" python3 build/check_report_consistency.py \
  --lanes out/plate/roundtrip.log \
  --scores-dir out \
  --bombs logs/bombs/scorecard.txt \
  --out out/consistency.txt \
  --inventory out/inventory.txt

# 6. Every published DOCX validates against the ECMA-376 schemas.
schema_gate() {
  local bad=0
  for docx in "Open-Source DOCX Editors Re-verified Against Code and Measured Round-Trip (2026).docx" \
               reports/Report*.docx; do
    case "$docx" in *~\$*) continue ;; esac
    printf '  %-72s ' "$docx"
    if python3 build/validate_ooxml.py "$docx" | tail -1 | grep -q "NO REAL SCHEMA VIOLATIONS"; then
      echo "PASS"
    else
      echo "FAIL"
      bad=1
    fi
  done
  return $bad
}
run "OOXML schema" schema_gate

# 7. The review's claim-evidence matrix is complete and well formed.
run "claim matrix" python3 build/build_claim_evidence.py \
  --ledger out/findings_ledger.csv \
  --out out/review/claim_evidence_matrix.csv

# 8. The deliverables open in Microsoft Word.
if [ "$WITH_WORD" -eq 1 ]; then
  run "Word open" python3 build/verify_deliverables.py
else
  printf '\n=== Word open === skipped (pass --with-word to run it)\n'
fi

printf '\n========================================\n'
printf 'passed: %d  failed: %d\n' "${#PASSED[@]}" "${#FAILED[@]}"
for name in "${PASSED[@]:-}"; do
  [ -n "$name" ] && printf '  PASS %s\n' "$name"
done
for name in "${FAILED[@]:-}"; do
  [ -n "$name" ] && printf '  FAIL %s\n' "$name"
done
printf '========================================\n'

[ "${#FAILED[@]}" -eq 0 ]
