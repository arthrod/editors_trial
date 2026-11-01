#!/usr/bin/env bash
# Rebuild one live demo at the commit the trial measured, and record that commit.
#
#   build/rebuild_demo.sh <slug>        # DEMO_APPS=/tmp/demos by default
#
# The commit is never typed: it is read from the trial's own checkout under
# repos/ (moved by build/update_editors.sh), fetched into the demo's src/
# checkout, built with the demo's recipe (demos/<slug>/BUILD.md), and written
# to <slug>/dist/SOURCE.txt from git. benchmarks.law's `pnpm sync:demos` reads
# SOURCE.txt. Nothing under repos/ is modified: the demo builds in its own clone.
set -euo pipefail
ROOT=${TRIAL_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}
[ -d "$ROOT/repos" ] || { echo "no repos/ under $ROOT" >&2; exit 2; }
APPS=${DEMO_APPS:-/tmp/demos}
slug=${1:?usage: rebuild_demo.sh <slug>}
D="$APPS/$slug"
cd "$D"
# A build starts from an empty dist/; the previous one is kept beside it until this one succeeds.
# Only a dist/ that exists replaces dist.prev: a failed run must never delete the last good build.
if [ -d dist ]; then rm -rf dist.prev; mv dist dist.prev; fi

# pin <src-dir> <repos/ name>: move a demo checkout to the trial's commit, keeping untracked demo files.
pin() {
  local src=$1 repo="$ROOT/repos/$2" sha
  sha=$(git -C "$repo" rev-parse HEAD)
  # A partial (promisor) clone under repos/ cannot serve a pack; fetch the same commit from upstream then.
  git -C "$src" fetch -q "$repo" "$sha" 2>/dev/null || git -C "$src" fetch -q origin "$sha"
  git -C "$src" checkout -q --detach "$sha"
  echo "pinned $src -> $(git -C "$src" rev-parse --short=9 HEAD)"
}
# restore <src-dir> <file...>: drop a previous build's patch before moving the checkout.
restore() { local src=$1; shift; git -C "$src" checkout -q -- "$@"; }

case "$slug" in
  superdoc)
    pin src superdoc
    rsync -a "$ROOT/demos/superdoc/" src/examples/bench-demo/ --exclude BUILD.md
    ( cd src && pnpm install --no-frozen-lockfile && pnpm --filter superdoc build )   # the demo folder is not in upstream's lockfile
    ( cd src/examples/bench-demo && pnpm install && pnpm build )
    REPO=superdoc; LIC=AGPL-3.0; LICFILE=src/LICENSE ;;
  canvas-editor)
    pin src canvas-editor; pin plugin canvas-editor-plugin
    rsync -a "$ROOT/demos/canvas-editor/" ./ --exclude BUILD.md
    ( cd plugin && pnpm install ) && pnpm install && pnpm build
    REPO=canvas-editor; LIC=MIT; LICFILE=src/LICENSE ;;
  docxodus)
    pin src docxodus
    rsync -a "$ROOT/demos/docxodus/" host/ --exclude BUILD.md
    # The npm package the trial measured (harness/ui/docxodus), not a version typed here.
    v=$(node -p "require('$ROOT/harness/ui/docxodus/node_modules/docxodus/package.json').version")
    ( cd host && pnpm add --save-exact "docxodus@$v" && pnpm build )
    REPO=docxodus; LIC=MIT; LICFILE=src/LICENSE; NPM="docxodus@$v" ;;
  eigenpal)
    pin src eigenpal-docx-editor
    rsync -a "$ROOT/demos/eigenpal/" app/ --exclude BUILD.md
    ( cd src && bun install --frozen-lockfile && bun run build:packages )
    ( cd app && pnpm install && pnpm build )
    REPO=eigenpal-docx-editor; LIC="Apache-2.0 (no Pro packages)"; LICFILE=src/LICENSE ;;
  folio)
    restore src packages/editor-web/src/mount.tsx
    pin src folio
    git -C src apply "$ROOT/demos/folio/mount-fit-width.patch"
    ( cd src && bun install --frozen-lockfile && cd packages/editor-web && bun scripts/build.ts )
    REPO=folio; LIC=Apache-2.0; LICFILE=src/LICENSE ;;
  genoffice)
    pin src genoffice
    rsync -a "$ROOT/demos/genoffice/apps/" src/apps/
    ( cd src && npm ci --no-audit --no-fund )
    ( cd src/apps/docs/demo-web && ../../../node_modules/.bin/vite build )
    REPO=genoffice; LIC=Apache-2.0; LICFILE=src/LICENSE ;;
  plate)
    pin src plate
    rsync -a "$ROOT/demos/plate/" app/ --exclude BUILD.md
    # CI=true: pnpm asks before replacing a node_modules another install left, and with no
    # terminal to answer it silently skips the install (turbo is then missing).
    # PUPPETEER_SKIP_DOWNLOAD: puppeteer is a dev dependency of Plate's own tests; the demo
    # never runs it, and its postinstall would fetch a headless Chrome.
    ( cd src && CI=true PUPPETEER_SKIP_DOWNLOAD=1 pnpm install && CI=true pnpm build )
    # The app links into src/; after src/ is reinstalled, the app's own node_modules is stale
    # while pnpm still reports it "up to date", so it starts clean.
    ( cd app && rm -rf node_modules && CI=true pnpm install && pnpm build )
    REPO=plate; LIC=MIT; LICFILE=src/LICENSE ;;
  wordcraft)
    restore src Cargo.lock Cargo.toml apps/wordcraft-web/Cargo.toml apps/wordcraft-web/Trunk.toml apps/wordcraft-web/index.html apps/wordcraft-web/src/web.rs
    pin src wordcraft
    git -C src apply "$ROOT/demos/wordcraft/demo.patch"
    ( cd src/apps/wordcraft-web && trunk build --release )
    REPO=wordcraft; LIC="MIT OR Apache-2.0"; LICFILE=src/LICENSE-MIT ;;
  # Pins that did not move: the build stands; check it is at the pin and re-record SOURCE.txt.
  docen|docs-plus|fidus-writer|office-open)
    case "$slug" in
      docen) REPO=docen; LIC=MIT ;; docs-plus) REPO=docs-plus; LIC=MIT ;;
      fidus-writer) REPO=fiduswriter-document-ts; LIC=AGPL-3.0 ;; office-open) REPO=office-open; LIC=MIT ;;
    esac
    LICFILE=src/LICENSE
    [ "$(git -C src rev-parse HEAD)" = "$(git -C "$ROOT/repos/$REPO" rev-parse HEAD)" ] \
      || { echo "$slug: src is not at the trial's pin; it needs a recipe here" >&2; mv dist.prev dist; exit 3; }
    mv dist.prev dist ;;
  *) echo "no recipe for $slug" >&2; exit 2 ;;
esac

# genoffice's Vite config writes next to its own root (demo-web/dist); the published bundle is dist/.
if [ "$slug" = genoffice ]; then rm -rf dist; cp -R src/apps/docs/demo-web/dist dist; fi

# folio's bundle is copied into dist by hand in the old recipe; do it here.
if [ "$slug" = folio ]; then
  mkdir -p dist
  cp -R src/packages/editor-web/dist/vscode/. dist/
  cp "$ROOT/demos/folio/host-index.html" dist/index.html
  cp src/NOTICE.md dist/
fi

sha=$(git -C src rev-parse HEAD)
url=$(git -C "$ROOT/repos/$REPO" remote get-url origin); url=${url%.git}
[ -f "$LICFILE" ] && cp "$LICFILE" dist/LICENSE
if [ "$slug" = wordcraft ]; then cp src/LICENSE-APACHE dist/; [ -f src/NOTICE ] && cp src/NOTICE dist/ || cp dist.prev/NOTICE dist/; fi
{
  echo "Live demo for benchmarks.law"
  echo "Repository: $url"
  echo "Commit: $sha"
  [ -n "${NPM:-}" ] && echo "Package: $NPM"
  echo "License: $LIC (see LICENSE)"
  echo "Demo host page and build configuration: https://github.com/arthrod/editors_trial/tree/main/demos/$slug"
  echo "Built: $(date -u +%Y-%m-%d) by build/rebuild_demo.sh"
} > dist/SOURCE.txt
echo "== $slug built at $(git -C src rev-parse --short=9 HEAD)"
