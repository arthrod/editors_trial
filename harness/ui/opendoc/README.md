# OpenDoc — browser host (Report E2) and screenshot tooling

OpenDoc (CasualOffice/opendoc, pinned commit `ver.opendoc.commit`, 5ac261cea) is
a website, not a package: its editor is `webapp/editor.html` plus an engine
compiled from Rust to WebAssembly into `webapp/pkg/`.

| file | role |
|---|---|
| `fetch_engine.py` | puts the vendor's own Pages build of the engine for the pinned commit into `repos/opendoc/webapp/pkg/`, checked by SHA-256 |
| `host.mjs` | the E2 perf host: serves `repos/opendoc/webapp` as it ships, the document at `/sample.docx`, and the shim below |
| `host.js` | the shim, put inline in `editor.html` before the editor's own scripts: `window.__host` flags |
| `probe.mjs` | the screenshot probe for `shot.mjs` (capture_ui.sh), which opens a file through the editor's own file input |

## Run it

```bash
python3 -I harness/ui/opendoc/fetch_engine.py     # once: the engine, if webapp/pkg/ is empty
cd harness/ui/opendoc
node host.mjs --port 5224                          # CORPUS_DOCX=/abs/file.docx for another document
```

Open <http://127.0.0.1:5224/>. `?doc=/fixture/<name>.docx` opens a file from the
repository's `fixture/` folder instead (the page is redirected to
`/d/fixture/<name>.docx/`, where the same editor's `./sample.docx` is that file).

## How the document goes in

The editor opens `./sample.docx` on boot when its URL names no other document
(`webapp/src/editor_file_open.mjs`, `startupDocument`: "the plain editor ...
open[s] sample.docx"). The host serves the corpus at that path, so the document
goes in through the vendor's documented startup path, with no file input and no
change to the editor. The lanes intercept `/sample.docx` with their own fixture
(`corpus_route`). The embedding contract has no other way in: its own page
(`webapp/embedding.html`, "What it does not ship yet") says "No document I/O
through the contract. There is no open(bytes)" and "No way to hand it your
document."

## Signals (`window.__host`)

| flag | set when | source |
|---|---|---|
| `ready` | `body.doc-loaded` and page 1's raster canvas mounted (`.page-wrap[data-page-number="1"] canvas.page`), then two frames | `editor_file_open.mjs` `openBytes`, `editor_paint.mjs` `paintPageCanvas` |
| `settled` | `body[data-fonts-ready="true"]` | the editor's "painted with its real faces" signal after its background font upgrade |
| `error` | `html.engine-failed`, or the editor withdrew `html.doc-expected` without opening a document | `engine_boot.mjs`, `editor_file_open.mjs` |
| `selection` | every `selection` event of the host contract (`window.opendoc`) | `host_session.mjs` |

`ready` is the editor's first render, on its bundled metric-compatible faces,
with the caret's textarea focused. The font upgrade runs after it and is
network-bound: whenever the engine reports missing script coverage it fetches
fallback faces from `cdn.jsdelivr.net` (on the 500-word prose document, Noto
Color Emoji, 2.4 MB, and Noto Sans CJK SC, 11.5 MB, measured 2026-11-22). The
host contract's own `ready` event is not used: it fires before the first render.

Text is in the engine only (the pages are canvases; `#a11yDocument` is an
off-page screen-reader mirror), so the lanes read it through the host contract,
`window.opendoc.ai.read` (`perf/runner/edit_surface.mjs`, model `opendoc`).
