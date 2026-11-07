#!/usr/bin/env bash
set -euo pipefail
cd /agent/repos/editors_trial-fb4268
export PYTHONPATH=.
ROOT=perf/out/full_browser_2026_11_07
while pgrep -f 'benchmark_warm_cold.py.*full_browser_2026_11_07/ci_broad' >/dev/null; do
  sleep 30
done
python3 perf/runner/benchmark_browser_interactions.py \
  --out-root "$ROOT/ci_broad" \
  --pairs 3 \
  --execution-profile ci_broad \
  --host-class ci_coarse \
  --editors docxodus superdoc genoffice plate canvas
python3 perf/runner/benchmark_load_unload.py \
  --out-root "$ROOT/load_unload" \
  --pairs 3 \
  --fixture perf/fixtures/generated/gigantic-one-paragraph.docx
python3 perf/runner/benchmark_full_browser.py \
  --execution-profile dedicated_publish \
  --host-class laboratory \
  --out-root "$ROOT" \
  --pairs 3 \
  --c20-preview-seconds 600 \
  --start-c20-full-soak \
  --editors docxodus superdoc genoffice plate canvas
python3 perf/runner/benchmark_pixels_lo.py --out-root "$ROOT"
python3 perf/runner/benchmark_full_browser.py --skip-run \
  --out-root "$ROOT" \
  --execution-profile ci_broad \
  --host-class ci_coarse \
  --editors docxodus superdoc genoffice plate canvas
echo post_warm_done >> /opt/cursor/artifacts/full_browser_pipeline.log
