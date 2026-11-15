#!/usr/bin/env bash
# One-command perf host for docs.plus: the product's own webapp, a DOCX loaded
# into it, and a ready signal that waits for the document to paint.
#
#   ./start.sh
#
# Serves http://127.0.0.1:5215/editor  (front: serve.mjs, injects bridge.js)
#        http://127.0.0.1:5216/editor  (the Next.js dev server, internal)
#        http://127.0.0.1:4210/api     (the import endpoint, internal)
#
# Overrides: DOCSPLUS_PORT, DOCSPLUS_INTERNAL_PORT, DOCSPLUS_STUB_PORT,
#            DOCSPLUS_FIXTURE, DOCSPLUS_REPO, DOCSPLUS_SKIP_PREWARM=1
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${DOCSPLUS_REPO:-$HERE/../../../../repos/docs-plus}"
PORT="${DOCSPLUS_PORT:-5215}"
INTERNAL="${DOCSPLUS_INTERNAL_PORT:-5216}"
STUB_PORT="${DOCSPLUS_STUB_PORT:-4210}"
FIXTURE="${DOCSPLUS_FIXTURE:-$HERE/../../../../fixture/complex.docx}"
REST="http://127.0.0.1:${STUB_PORT}/api"

die() { echo "start.sh: $*" >&2; exit 1; }

# The runner inherits its parent's PATH, which is not guaranteed to carry the
# toolchain dirs; add the usual ones rather than hard-coding a binary path.
for extra in "$HOME/.bun/bin" "$HOME/Library/pnpm/bin" /opt/homebrew/bin /usr/local/bin; do
  case ":$PATH:" in *":$extra:"*) ;; *) if [ -d "$extra" ]; then PATH="$PATH:$extra"; fi ;; esac
done
export PATH

[ -x "$REPO/apps/webapp/node_modules/.bin/next" ] || die \
  "missing $REPO/apps/webapp/node_modules — run: (cd $REPO && bun install --frozen-lockfile --ignore-scripts)"
[ -d "$REPO/extensions/extension-hypermultimedia/dist" ] || die \
  "workspace packages are not built — run: (cd $REPO && bun run --filter './packages/*' build && bun run --filter './extensions/*' build)"
[ -f "$FIXTURE" ] || die "corpus not found: $FIXTURE"

command -v bun >/dev/null || die "bun not found on PATH (looked at $PATH)"
command -v node >/dev/null || die "node not found on PATH (looked at $PATH)"

children=()
cleanup() {
  trap - EXIT INT TERM
  for pid in "${children[@]:-}"; do
    [ -n "${pid:-}" ] && kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "start.sh: import endpoint :${STUB_PORT}"
STUB_PORT="$STUB_PORT" bun "$HERE/restapi.ts" &
children+=("$!")

echo "start.sh: docs.plus webapp :${INTERNAL} (repo $REPO)"
(
  cd "$REPO/apps/webapp"
  exec env \
    NEXT_TELEMETRY_DISABLED=1 \
    NEXT_PUBLIC_RESTAPI_URL="$REST" \
    NEXT_PUBLIC_SUPABASE_URL="http://127.0.0.1:54321" \
    NEXT_PUBLIC_SUPABASE_ANON_KEY="harness-anon-key" \
    NEXT_PUBLIC_PROVIDER_URL="ws://127.0.0.1:4001" \
    "$REPO/apps/webapp/node_modules/.bin/next" dev --turbopack -H 127.0.0.1 -p "$INTERNAL"
) &
children+=("$!")

# Pre-warm the route once. Turbopack compiles /editor on first request; letting
# that land here keeps a one-off bundler compile out of the measured page load.
# Set DOCSPLUS_SKIP_PREWARM=1 to measure the compile along with the editor.
if [ "${DOCSPLUS_SKIP_PREWARM:-0}" != "1" ]; then
  (
    for _ in $(seq 1 180); do
      if curl -fsS --max-time 120 -o /dev/null "http://127.0.0.1:${INTERNAL}/editor"; then
        echo "start.sh: /editor pre-warmed"
        break
      fi
      sleep 1
    done
  ) &
  children+=("$!")
fi

echo "start.sh: front http://127.0.0.1:${PORT}/editor"
# Foreground (not exec) so the trap still stops the two children above.
env \
  PORT="$PORT" \
  UPSTREAM_PORT="$INTERNAL" \
  CORPUS_FILE="$FIXTURE" \
  CORPUS_ROUTE="/corpus.docx" \
  REST_URL="$REST" \
  node "$HERE/serve.mjs"
