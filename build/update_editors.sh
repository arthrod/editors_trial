#!/usr/bin/env bash
# Move every editor the trial measures to its current upstream, and install
# what its harness loads. Run it, then build/run_all.sh, build/run_second_pass.sh,
# build/score_all.py, build/facts.py and build/render_reports.py.
#
# The release rule (AGENTS.md): each editor moves to its newest version that
# is at least 5 days old on the release date, and never to one older than the
# version pinned now. build/pin_versions.py makes that choice.
#
#   checkouts  repos/<name>: the newest commit of the upstream default branch
#              (Plate measures its `next` branch) committed on or before the
#              cutoff, checked out detached; then the project's own package
#              manager installs its lockfile
#   npm pins   @superdoc/sdk on the `next` channel the trial has always
#              measured, docxodus, @docxodus/export, @pdftron/webviewer
#              (Apryse), @extend-ai/react-docx, @betteroffice/docx and
#              @univerjs/presets on `latest`, each the
#              newest version published on or before the cutoff
#   archives   OnlyOffice's converter (harness/onlyoffice/pin.json): fetched and
#              checked against its pinned SHA-512, not moved
#
# RELEASE_DATE=YYYY-MM-DD overrides today's date (the cutoff is 5 days before).
#
# A checkout with local changes is not touched: the script stops.
#
# usage: build/update_editors.sh
set -euo pipefail
BASE="${TRIAL_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$BASE"

pull() {
  local repo="repos/$1" branch="$2"
  if [ -n "$(git -C "$repo" status --porcelain)" ]; then
    echo "STOP $1 has local changes" >&2
    exit 1
  fi
  git -C "$repo" fetch -q origin
  local pin
  pin=$(python3 build/pin_versions.py git "$repo" "origin/$branch" --current HEAD ${RELEASE_DATE:+--date "$RELEASE_DATE"})
  git -C "$repo" checkout -q --detach "$pin"
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
pull opendoc main

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
install docen pnpm install --frozen-lockfile --ignore-scripts

SDK_NOW=$(node -p "require('./harness/superdoc-sdk/node_modules/@superdoc/sdk/package.json').version" 2>/dev/null || true)
SDK=$(python3 build/pin_versions.py npm @superdoc/sdk next ${SDK_NOW:+--current "$SDK_NOW"} ${RELEASE_DATE:+--date "$RELEASE_DATE"})
echo "npm     @superdoc/sdk@$SDK"
( cd harness/superdoc-sdk && pnpm add --save-exact "@superdoc/sdk@$SDK" ) >/tmp/update_superdoc_sdk.log 2>&1

DX_NOW=$(node -p "require('./harness/ui/docxodus/node_modules/docxodus/package.json').version" 2>/dev/null || true)
DX=$(python3 build/pin_versions.py npm docxodus latest ${DX_NOW:+--current "$DX_NOW"} ${RELEASE_DATE:+--date "$RELEASE_DATE"})
echo "npm     docxodus@$DX, @docxodus/export@$DX"
( cd harness/ui/docxodus && pnpm add --save-exact "docxodus@$DX" "@docxodus/export@$DX" ) >/tmp/update_docxodus.log 2>&1

AP_NOW=$(node -p "require('./harness/apryse/node_modules/@pdftron/webviewer/package.json').version" 2>/dev/null || true)
AP=$(python3 build/pin_versions.py npm @pdftron/webviewer latest ${AP_NOW:+--current "$AP_NOW"} ${RELEASE_DATE:+--date "$RELEASE_DATE"})
echo "npm     @pdftron/webviewer@$AP"
( cd harness/apryse && pnpm add --save-exact "@pdftron/webviewer@$AP" ) >/tmp/update_apryse.log 2>&1

RD_NOW=$(node -p "require('./harness/reactdocx/node_modules/@extend-ai/react-docx/package.json').version" 2>/dev/null || true)
RD=$(python3 build/pin_versions.py npm @extend-ai/react-docx latest ${RD_NOW:+--current "$RD_NOW"} ${RELEASE_DATE:+--date "$RELEASE_DATE"})
echo "npm     @extend-ai/react-docx@$RD"
( cd harness/reactdocx && pnpm add --save-exact "@extend-ai/react-docx@$RD" ) >/tmp/update_reactdocx.log 2>&1

BO_NOW=$(node -p "require('./harness/betteroffice/node_modules/@betteroffice/docx/package.json').version" 2>/dev/null || true)
BO=$(python3 build/pin_versions.py npm @betteroffice/docx latest ${BO_NOW:+--current "$BO_NOW"} ${RELEASE_DATE:+--date "$RELEASE_DATE"})
echo "npm     @betteroffice/docx@$BO"
( cd harness/betteroffice && pnpm add --save-exact "@betteroffice/docx@$BO" ) >/tmp/update_betteroffice.log 2>&1

# Univer has no round-trip lane; its pin is what harness/univer/probe.mjs reads.
UV_NOW=$(node -p "require('./harness/univer/node_modules/@univerjs/presets/package.json').version" 2>/dev/null || true)
UV=$(python3 build/pin_versions.py npm @univerjs/presets latest ${UV_NOW:+--current "$UV_NOW"} ${RELEASE_DATE:+--date "$RELEASE_DATE"})
echo "npm     @univerjs/presets@$UV, @univerjs/preset-docs-core@$UV"
( cd harness/univer && pnpm add --save-exact "@univerjs/presets@$UV" "@univerjs/preset-docs-core@$UV" ) >/tmp/update_univer.log 2>&1

# OnlyOffice's converter is a GitHub release archive, pinned by tag and SHA-512 in
# harness/onlyoffice/pin.json. build/pin_versions.py does not choose release tags yet,
# so that file is edited for a release (newest tag published on or before the cutoff, unless the
# current pin is newer: then it stays). This step does not compare versions;
# this only fetches and checks what it names.
echo "fetch   onlyoffice x2t ($(node -p "require('./harness/onlyoffice/pin.json').x2t.tag"))"
( cd harness/onlyoffice && node fetch.mjs ) >/tmp/update_onlyoffice.log 2>&1

echo "build   wordcraft harness"
( cd harness/wordcraft && cargo build --release ) >/tmp/update_wordcraft.log 2>&1

echo "build   opendoc harness"
( cd harness/opendoc && cargo build --release ) >/tmp/update_opendoc.log 2>&1

# The reports cite this date; build/facts.py reads it (release.date, release.cutoff).
python3 build/pin_versions.py release ${RELEASE_DATE:+--date "$RELEASE_DATE"} > out/release.json
echo "release $(cat out/release.json)"

echo "=== EDITORS UPDATED ==="
