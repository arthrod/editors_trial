#!/usr/bin/env bash
# Move every editor the trial measures to its current upstream, and install
# what its harness loads. Run it, then build/run_all.sh, build/run_second_pass.sh,
# build/score_all.py, build/facts.py and build/render_reports.py.
#
#   checkouts  repos/<name>: fast-forward to the upstream default branch
#              (Plate measures its `next` branch), then the project's own
#              package manager installs its lockfile
#   npm pins   the harnesses that load a published package get the newest
#              version: @superdoc/sdk on the `next` channel the trial has
#              always measured, docxodus and @docxodus/export on `latest`
#
# A checkout with local changes is not touched: the script stops.
#
# usage: build/update_editors.sh
set -euo pipefail
BASE="/Users/arthrod/temp/T/editors_trial"
cd "$BASE"

pull() {
  local repo="repos/$1" branch="$2"
  if [ -n "$(git -C "$repo" status --porcelain)" ]; then
    echo "STOP $1 has local changes" >&2
    exit 1
  fi
  git -C "$repo" fetch -q origin
  git -C "$repo" checkout -q "$branch"
  git -C "$repo" merge -q --ff-only "origin/$branch"
  echo "pulled  $1 -> $(git -C "$repo" rev-parse --short=9 HEAD) ($(git -C "$repo" log -1 --format=%cs))"
}

pull plate next
pull eigenpal-docx-editor main
pull folio main
pull genoffice main
pull superdoc main
pull canvas-editor main
pull canvas-editor-plugin main
pull wordcraft main
pull docxodus main
pull docen main
pull office-open main
pull office-open-upstream main
pull docs-plus main
pull fiduswriter main
pull fiduswriter-document-ts main
pull fiduswriter-cli-ts main
pull fiduswriter-pandoc-plugin-ts main

install() {
  echo "install $1 ($2)"
  ( cd "repos/$1" && "${@:2}" ) >"/tmp/update_$1.log" 2>&1 || { echo "FAIL install $1, see /tmp/update_$1.log" >&2; exit 1; }
}

install plate pnpm install --no-frozen-lockfile --ignore-scripts
install eigenpal-docx-editor bun install
install folio bun install
install genoffice npm install --no-audit --no-fund
install canvas-editor pnpm install --no-frozen-lockfile
install canvas-editor-plugin pnpm install --no-frozen-lockfile

SDK=$(npm view @superdoc/sdk dist-tags.next)
echo "npm     @superdoc/sdk@$SDK"
( cd harness/superdoc-sdk && pnpm add --save-exact "@superdoc/sdk@$SDK" ) >/tmp/update_superdoc_sdk.log 2>&1

DX=$(npm view docxodus version)
echo "npm     docxodus@$DX, @docxodus/export@$DX"
( cd harness/ui/docxodus && npm install --no-audit --no-fund --save-exact "docxodus@$DX" "@docxodus/export@$DX" ) >/tmp/update_docxodus.log 2>&1

echo "build   wordcraft harness"
( cd harness/wordcraft && cargo build --release ) >/tmp/update_wordcraft.log 2>&1

echo "=== EDITORS UPDATED ==="
