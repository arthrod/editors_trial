#!/usr/bin/env bash
# Report C, the UI layer: host each editor's own application on its pinned
# commit, load fixture/complex.docx into it, and photograph what it draws.
#
# The recipes are the ones in Report C's "The per-editor recipes"; the
# viewports and scroll targets are the ones the 2026-10-30 captures logged.
# Nothing under repos/ is modified (installing dependencies is allowed).
#
# usage: build/capture_ui.sh [editor ...]     # default: every editor
#        OUT=/tmp/ui-new build/capture_ui.sh  # write somewhere else (default out/ui)
#        TRIAL_ROOT=<checkout> build/capture_ui.sh   # run from another checkout (a worktree)
set -uo pipefail
BASE="${TRIAL_ROOT:-/Users/arthrod/temp/T/editors_trial}"
OUT="${OUT:-$BASE/out/ui}"
FIX="$BASE/fixture/complex.docx"
UI="$BASE/harness/ui"
P1="Chapter 1"                   # Word's page 1 heading: the document has loaded
P3="A sentence with a comment"   # first body line of Word's page 3
P4="Text box content"            # first body line of Word's page 4
P2="inserted text"               # the tracked insertion on Word's page 2
P5="Landscape section content"   # the only body line of Word's page 5 (landscape)
mkdir -p "$OUT"

shot() { ( cd "$UI" && node shot.mjs --outdir "$OUT" "$@" ) 2>&1 | tail -2; }

SERVER_PID=""
serve() {  # serve <port> <dir> <command...>: start a dev server, wait for its port
  local port="$1" dir="$2"; shift 2
  ( cd "$dir" && exec "$@" ) >"/tmp/capture_ui_$port.log" 2>&1 &
  SERVER_PID=$!
  for _ in $(seq 1 120); do
    curl -s -o /dev/null "http://127.0.0.1:$port/" && return 0
    curl -s -o /dev/null "http://localhost:$port/" && return 0
    sleep 1
  done
  echo "server on :$port did not come up, see /tmp/capture_ui_$port.log" >&2
  return 1
}
stop() {
  [ -n "$SERVER_PID" ] && pkill -P "$SERVER_PID" 2>/dev/null; kill "$SERVER_PID" 2>/dev/null
  SERVER_PID=""; sleep 1
}

# A dev server compiles on the first request; load the page once before the
# first capture so a cold start is not photographed as the editor's rendering.
warm() { ( cd "$UI" && node shot.mjs --name _warm --outdir /tmp/capture_ui_warm --url "$1" --wait 15000 ) >/dev/null 2>&1; }

cap_superdoc() {
  serve 5199 "$BASE/repos/superdoc/examples/vanilla" npx vite --port 5199 --host 127.0.0.1 --strictPort || return 1
  warm http://127.0.0.1:5199/
  shot --name superdoc --url http://127.0.0.1:5199/ --serve-as /sample.docx --file "$FIX" --viewport 1440x900 --wait-for "$P1" --wait 4000
  shot --name superdoc_p3 --url http://127.0.0.1:5199/ --serve-as /sample.docx --file "$FIX" --viewport 1440x1400 --wait-for "$P1" --wait 4000 --scroll-text "$P3"
  stop
}

cap_folio() {
  serve 5207 "$BASE/repos/folio/packages/playground" npx vite --port 5207 --host 127.0.0.1 --strictPort || return 1
  local u="http://127.0.0.1:5207/?file=complex.docx"
  warm "$u"
  shot --name folio --url "$u" --serve-as /fixtures/complex.docx --file "$FIX" --viewport 1440x1400 --wait-for "$P1" --wait 4000
  shot --name folio_p3 --url "$u" --serve-as /fixtures/complex.docx --file "$FIX" --viewport 1440x1500 --wait-for "$P1" --wait 4000 --scroll-text "$P3"
  shot --name folio_p4 --url "$u" --serve-as /fixtures/complex.docx --file "$FIX" --viewport 1440x1500 --wait-for "$P1" --wait 4000 --scroll-text "$P4"
  stop
}

cap_eigenpal() {
  serve 5206 "$BASE/repos/eigenpal-docx-editor/examples/vite" npx vite --port 5206 --host 127.0.0.1 --strictPort || return 1
  local u="http://127.0.0.1:5206/"
  warm "$u"
  shot --name eigenpal --url "$u" --file "$FIX" --file-accept docx --viewport 1440x1400 --wait-for "$P1" --wait 4000
  shot --name eigenpal_p3 --url "$u" --file "$FIX" --file-accept docx --viewport 1440x1500 --wait-for "$P1" --wait 4000 --scroll-text "$P3"
  stop
}

cap_plate() {
  serve 5208 "$UI/plate" npx vite --port 5208 --strictPort --host 127.0.0.1 || return 1
  local u="http://127.0.0.1:5208/"
  warm "$u"
  shot --name plate --url "$u" --serve-as /corpus.docx --file "$FIX" --viewport 1440x1500 --wait-for "$P1" --wait 4000
  shot --name plate_p3 --url "$u" --serve-as /corpus.docx --file "$FIX" --viewport 1440x1400 --wait-for "$P1" --wait 4000 --scroll-text "$P3"
  stop
}

cap_officeopen() {
  ( cd "$UI/officeopen" && node build.mjs ) >/tmp/capture_ui_officeopen_build.log 2>&1
  serve 5203 "$UI/officeopen" node server.mjs || return 1
  local u="http://localhost:5203/"
  shot --name officeopen --url "$u" --serve-as /sample.docx --file "$FIX" --viewport 1440x1500 --wait-for "$P1" --wait 3000
  shot --name officeopen_p3 --url "$u" --serve-as /sample.docx --file "$FIX" --viewport 1440x1500 --wait-for "$P1" --wait 3000 --scroll-text "$P3"
  stop
}

cap_canvas() {
  serve 5204 "$UI/canvas" npx vite --config vite.config.mjs --port 5204 --host 127.0.0.1 --strictPort || return 1
  local u="http://127.0.0.1:5204/"
  warm "$u"
  shot --name canvas --url "$u" --viewport 1440x1400 --wait 12000 --probe canvas/probe-dom.mjs
  stop
}

cap_genoffice() {
  serve 5201 "$UI/genoffice" npx vite --config vite.config.mjs --port 5201 --strictPort || return 1
  local u="http://localhost:5201/"
  warm "$u"
  shot --name genoffice --url "$u" --serve-as /sample.docx --file "$FIX" --viewport 1440x1400 --probe genoffice/probe.mjs
  shot --name genoffice_p3 --url "$u" --serve-as /sample.docx --file "$FIX" --viewport 1440x1500 --probe genoffice/probe.mjs --scroll-text "$P3"
  stop
}

cap_docen() {
  serve 5202 "$BASE/repos/docen/packages/editor" npx vp dev --port 5202 --strictPort || return 1
  local u="http://localhost:5202/document.html"
  warm "$u"
  DOCEN_MARKS=off shot --name docen --url "$u" --viewport 1440x1400 --probe docen/probe-load.mjs
  DOCEN_MARKS=off DOCEN_PAGE=3 shot --name docen_p3 --url "$u" --viewport 1440x1500 --probe docen/probe-load.mjs
  stop
}

cap_docsplus() {
  # The REST stub on :4000 calls the repo's own importDocx; the webapp reads the
  # repo's own .env.example (local-development values, no secrets).
  ( exec bun "$UI/docsplus/restapi.ts" ) >/tmp/capture_ui_4000.log 2>&1 &
  local stub=$!
  serve 5205 "$BASE/repos/docs-plus/apps/webapp" npx dotenv -e ../../.env.example -- npx next dev --turbopack -p 5205 || { kill $stub; return 1; }
  local u="http://127.0.0.1:5205/editor"
  warm "$u"
  DOCSPLUS_SCROLL_TOP=1 shot --name docsplus --url "$u" --viewport 1440x1400 --probe docsplus/probe_import.mjs
  DOCSPLUS_SCROLL_TEXT="$P3" shot --name docsplus_p3 --url "$u" --viewport 1440x1400 --probe docsplus/probe_import.mjs
  stop; kill $stub 2>/dev/null
}

cap_fidus() {
  # Django's ALLOWED_HOSTS is ["localhost"] only. FIDUS_PY is a venv with the
  # repo's requirements (the frontend must already be transpiled; Report C §2.11).
  local py="${FIDUS_PY:-/tmp/fidusvenv2/bin/python}" shim=/tmp/capture_ui_gnucp
  # The generated postinstall uses GNU `cp --preserve=mode`; bundle_mathlive needs libmagic.
  mkdir -p "$shim" && ln -sf "$(command -v gcp)" "$shim/cp"
  export PATH="$shim:$PATH" DYLD_FALLBACK_LIBRARY_PATH="/opt/homebrew/opt/libmagic/lib"
  ( cd "$BASE/repos/fiduswriter/fiduswriter" && "$py" manage.py transpile --force ) >/tmp/capture_ui_fidus_transpile.log 2>&1
  grep -q "compiled successfully" /tmp/capture_ui_fidus_transpile.log || { echo "fidus transpile failed, see /tmp/capture_ui_fidus_transpile.log" >&2; return 1; }
  serve 5209 "$BASE/repos/fiduswriter/fiduswriter" "$py" manage.py runserver 127.0.0.1:5209 || return 1
  local u="http://localhost:5209/"
  FIDUS_FILE="$FIX" shot --name fidus --url "$u" --viewport 1440x1500 --probe fidus/probe_load.mjs
  FIDUS_FILE="$FIX" FIDUS_SCROLL="$P3" shot --name fidus_p3 --url "$u" --viewport 1440x1500 --probe fidus/probe_load.mjs
  stop
}

cap_apryse() {
  # Apryse WebViewer's DOCX Editor (closed source, @pdftron/webviewer), hosted
  # by harness/apryse; the license key comes from the trial's .env.
  serve 5210 "$BASE/harness/apryse" npx vite --config vite.config.mjs || return 1
  local u="http://127.0.0.1:5210/"
  warm "$u"
  # Its pages are drawn on a canvas, so readiness and the page-3 target are
  # asked of WebViewer (harness/ui/apryse/probe.mjs), not read from the DOM.
  shot --name apryse --url "$u" --serve-as /sample.docx --file "$FIX" --viewport 1440x1400 --wait 2000 --probe apryse/probe.mjs
  APRYSE_SCROLL="$P3" shot --name apryse_p3 --url "$u" --serve-as /sample.docx --file "$FIX" --viewport 1440x1500 --wait 2000 --probe apryse/probe.mjs
  APRYSE_SCROLL="$P4" shot --name apryse_p4 --url "$u" --serve-as /sample.docx --file "$FIX" --viewport 1440x1500 --wait 2000 --probe apryse/probe.mjs
  # the comments panel: whether the corpus's comment reached the editor at all
  APRYSE_SCROLL="$P3" shot --name apryse_comments --url "$u" --serve-as /sample.docx --file "$FIX" --viewport 1440x1500 --wait 2000 --probe apryse/probe_comments.mjs
  stop
}

cap_wordcraft() {
  mkdir -p "$OUT/wordcraft"
  local cli="$BASE/repos/wordcraft/target/release/wordcraft-cli"
  for p in 1 3; do "$cli" render "$FIX" "$OUT/wordcraft/page$p.png" --page "$p"; done
  "$cli" info "$FIX" > "$OUT/wordcraft/info.txt"
}

cap_libreoffice() {
  mkdir -p "$OUT/libreoffice"
  soffice --headless --convert-to pdf --outdir "$OUT/libreoffice" "$FIX" >/dev/null 2>&1
  rm -f "$OUT"/libreoffice/page-*.png
  # the release resolution (build/pixels.py), the same as Word's pages beside it
  local dpi
  dpi=$(python3 -c 'import sys; sys.path.insert(0, sys.argv[1]); import pixels; print(pixels.DPI)' "$BASE/build")
  pdftoppm -r "$dpi" -png "$OUT/libreoffice/complex.pdf" "$OUT/libreoffice/page"
}

cap_docxodus() {
  local chrome
  chrome=$(ls -d "$HOME"/Library/Caches/ms-playwright/chromium-*/chrome-mac*/*.app/Contents/MacOS/* 2>/dev/null | grep -v Helper | tail -1)
  local fmt
  for fmt in html pdf; do
    ( cd "$UI/docxodus" && ./node_modules/.bin/docxodus convert "$FIX" --to "$fmt" \
        --review-profile markup --markup-presentation word \
        --comments margin --comment-column-placement balloons \
        --font-directory "$UI/docxodus/fonts" --browser-executable "$chrome" \
        --output "$OUT/docxodus.$fmt" ) 2>&1 | tail -3
  done
  for p in 1 3 4; do
    DX_PAGE=$p shot --name "docxodus_p$p" --url "file://$OUT/docxodus.html" --viewport 1000x1180 --probe docxodus/probe_scroll_page.mjs
  done
  # ui_figures.py reads <slug>.png as page 1.
  cp "$OUT/docxodus_p1.png" "$OUT/docxodus.png"; cp "$OUT/docxodus_p1.json" "$OUT/docxodus.json"
}

# --- hosts added 2026-11-21 (pinned packages or archives under harness/ui/<name>) ---

cap_reactdocx() {
  # react-docx (@extend-ai/react-docx, the /vanilla entry): the package's own
  # quick start. Its review marks are off by default; ?review=1 passes its own
  # showTrackedChanges / showComments options for the two review captures.
  serve 5211 "$UI/react-docx" pnpm exec vite --config vite.config.mjs || return 1
  local u="http://127.0.0.1:5211/"
  warm "$u"
  local common=(--serve-as /sample.docx --file "$FIX" --wait-for "$P1" --wait 4000 --probe react-docx/probe.mjs)
  shot --name reactdocx --url "$u" "${common[@]}" --viewport 1440x1400
  shot --name reactdocx_p2 --url "$u" "${common[@]}" --viewport 1440x1500 --scroll-text "$P2"
  shot --name reactdocx_p3 --url "$u" "${common[@]}" --viewport 1440x1500 --scroll-text "$P3"
  shot --name reactdocx_p4 --url "$u" "${common[@]}" --viewport 1440x1500 --scroll-text "$P4"
  shot --name reactdocx_p5 --url "$u" "${common[@]}" --viewport 1440x1500 --scroll-text "$P5"
  shot --name reactdocx_review_p2 --url "$u?review=1" "${common[@]}" --viewport 1440x1500 --scroll-text "$P2"
  shot --name reactdocx_review_p3 --url "$u?review=1" "${common[@]}" --viewport 1440x1500 --scroll-text "$P3"
  stop
}

cap_betteroffice() {
  # BetterOffice DOCX (@betteroffice/docx-react): <DocxEditor> with its defaults.
  # Its pages are canvases; betteroffice/probe.mjs waits for its own
  # whenLayoutComplete() and goes to the page that holds the target text.
  serve 5214 "$UI/betteroffice" pnpm exec vite --config vite.config.mjs || return 1
  local u="http://127.0.0.1:5214/"
  warm "$u"
  local common=(--url "$u" --serve-as /sample.docx --file "$FIX" --wait 3000 --probe betteroffice/probe.mjs)
  shot --name betteroffice "${common[@]}" --viewport 1440x1400
  BO_SCROLL="$P2" shot --name betteroffice_p2 "${common[@]}" --viewport 1440x1500
  BO_SCROLL="$P3" shot --name betteroffice_p3 "${common[@]}" --viewport 1440x1500
  BO_SCROLL="$P4" shot --name betteroffice_p4 "${common[@]}" --viewport 1440x1500
  BO_SCROLL="$P5" shot --name betteroffice_p5 "${common[@]}" --viewport 1440x1500
  stop
}

cap_opendoc() {
  # OpenDoc (CasualOffice/opendoc): its own editor application, served as it
  # is from the pinned checkout, with the engine the vendor built from that
  # commit (opendoc/fetch_engine.py). The corpus goes in through its own file
  # input; the pages are canvases, so opendoc/probe.mjs navigates by its status bar.
  python3 -I "$UI/opendoc/fetch_engine.py" "$BASE/repos/opendoc" >/tmp/capture_ui_opendoc_engine.log 2>&1 \
    || { echo "opendoc engine missing, see /tmp/capture_ui_opendoc_engine.log" >&2; return 1; }
  serve 5213 "$UI" node static_server.mjs 5213 "$BASE/repos/opendoc/webapp" || return 1
  local u="http://127.0.0.1:5213/editor.html?blank=1"
  local common=(--url "$u" --wait 2000 --probe opendoc/probe.mjs)
  OPENDOC_FILE="$FIX" shot --name opendoc "${common[@]}" --viewport 1440x1400
  local p
  for p in 2 3 4 5; do
    OPENDOC_FILE="$FIX" OPENDOC_PAGE=$p shot --name "opendoc_p$p" "${common[@]}" --viewport 1440x1500
  done
  stop
}

cap_onlyoffice() {
  # OnlyOffice as CryptPad builds it for the browser: the editor and the x2t
  # converter, unpacked unmodified from their pinned release archives
  # (onlyoffice/fetch.py). It does not open the corpus: the converter does not
  # return on the altChunk, and the editor raises an error on the SmartArt. The
  # first two captures record those two stops (each is a MISS, with the reason
  # in its JSON); the rest are of a control with both constructs removed
  # (onlyoffice/make_controls.py), named for what it is.
  python3 -I "$UI/onlyoffice/fetch.py" >/tmp/capture_ui_onlyoffice_fetch.log 2>&1 \
    || { echo "onlyoffice archives missing, see /tmp/capture_ui_onlyoffice_fetch.log" >&2; return 1; }
  local ctl="$OUT/onlyoffice_controls"
  python3 -I "$UI/onlyoffice/make_controls.py" "$FIX" "$ctl" >/dev/null || return 1
  serve 5215 "$UI" node static_server.mjs 5215 "$UI/onlyoffice" || return 1
  local common=(--url "http://127.0.0.1:5215/" --serve-as /sample.docx --wait 1000 --probe onlyoffice/probe.mjs)
  shot --name onlyoffice "${common[@]}" --file "$FIX" --viewport 1440x1400
  shot --name onlyoffice_noaltchunk "${common[@]}" --file "$ctl/no_altchunk.docx" --viewport 1440x1400
  shot --name onlyoffice_noaltchunk_nodgm "${common[@]}" --file "$ctl/no_altchunk_no_dgm.docx" --viewport 1440x1400
  local p
  for p in 2 3 4 5; do
    OO_PAGE=$p shot --name "onlyoffice_noaltchunk_nodgm_p$p" "${common[@]}" --file "$ctl/no_altchunk_no_dgm.docx" --viewport 1440x1500
  done
  stop
}

cap_nutrient() {
  # Nutrient Web SDK (commercial, a viewer): the pinned version from Nutrient's
  # public CDN with no license key (its trial mode, watermarked), as the sister
  # site loads it. It shows the PDF it makes from the .docx inside a shadow root,
  # so nutrient/probe.mjs reads each page's text through the SDK.
  serve 5216 "$UI" node static_server.mjs 5216 "$UI/nutrient" || return 1
  local common=(--url "http://127.0.0.1:5216/" --serve-as /sample.docx --file "$FIX" --wait 2000 --probe nutrient/probe.mjs)
  shot --name nutrient "${common[@]}" --viewport 1440x1400
  NUTRIENT_SCROLL="$P2" shot --name nutrient_p2 "${common[@]}" --viewport 1440x1500
  NUTRIENT_SCROLL="$P3" shot --name nutrient_p3 "${common[@]}" --viewport 1440x1500
  NUTRIENT_SCROLL="$P4" shot --name nutrient_p4 "${common[@]}" --viewport 1440x1500
  NUTRIENT_SCROLL="$P5" shot --name nutrient_p5 "${common[@]}" --viewport 1440x1500
  stop
}

# Univer has no recipe: its open-source packages cannot open a .docx
# (harness/ui/univer/README.md has the evidence), so there is nothing to capture.

ALL=(superdoc folio genoffice eigenpal docen officeopen wordcraft canvas plate docsplus fidus libreoffice docxodus apryse
     reactdocx betteroffice opendoc onlyoffice nutrient)
[ $# -gt 0 ] && ALL=("$@")
for e in "${ALL[@]}"; do
  echo "== $e"
  if declare -F "cap_$e" >/dev/null; then "cap_$e"; else echo "no recipe for $e" >&2; fi
done
# Report C's date (facts.py: ui.date) is the day a run of every editor completed.
[ $# -eq 0 ] && date -u +%F > "$OUT/captured_at.txt"
