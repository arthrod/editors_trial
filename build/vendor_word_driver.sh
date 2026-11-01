#!/usr/bin/env bash
# Copy the audited Word driver from the neurotic bench, and record where it came from.
#
#   build/vendor_word_driver.sh [path/to/neurotic_docx_bench]
#
# scripts/word_pdf.py there is the reviewed Word-for-Mac driver (its own
# docs/WORD_DRIVER_AUDIT.md); the trial runs it unmodified, through
# build/word_batch.py. Its spec (tests/test_word_pdf*.py, with the bench's
# conftest) is run in the source repo before the copy; a driver whose spec
# fails is not vendored.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
SRC=${1:-$ROOT/../neurotic_docx_bench}
[ -z "$(git -C "$SRC" status --porcelain -- scripts/word_pdf.py scripts/test_word_pdf_alerts.py)" ] \
  || { echo "word_pdf.py has uncommitted changes in $SRC; vendor a commit, not a working copy" >&2; exit 1; }
SPEC="tests/test_word_pdf.py tests/test_word_pdf_alerts.py tests/test_word_pdf_focus.py tests/test_word_pdf_manifest.py tests/test_word_pdf_source.py"
# shellcheck disable=SC2086  # SPEC is a fixed list of paths
( cd "$SRC" && .venv/bin/python -m pytest -q -p no:cacheprovider $SPEC ) | grep -E "passed|failed|error" | tail -1
[ "${PIPESTATUS[0]}" = 0 ] || { echo "the driver's spec failed; not vendoring" >&2; exit 1; }
cp "$SRC/scripts/word_pdf.py" "$ROOT/build/vendor/"
{
  echo "Repository: $(git -C "$SRC" remote get-url origin 2>/dev/null || echo "$SRC")"
  echo "Commit: $(git -C "$SRC" log -1 --format=%H -- scripts/word_pdf.py)"
  echo "Date: $(git -C "$SRC" log -1 --format=%cs -- scripts/word_pdf.py)"
  echo "Spec: tests/test_word_pdf*.py passed in the source repo when vendored"
  echo "sha256 word_pdf.py: $(shasum -a 256 "$ROOT/build/vendor/word_pdf.py" | cut -d' ' -f1)"
} > "$ROOT/build/vendor/word_pdf.SOURCE"
cat "$ROOT/build/vendor/word_pdf.SOURCE"
