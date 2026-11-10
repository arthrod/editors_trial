# WordCraft browser host (perf harness, port 5219)

Hosts `repos/wordcraft/apps/wordcraft-web` (Trunk + eframe/egui, WebGPU with a WebGL2 fallback) for
`perf/runner/benchmark_warm_cold.py` (`BROWSER_TARGETS["wordcraft"]`) and
`perf/runner/adversarial_c10_scroll.py --editor wordcraft`.

The app renders into one `<canvas id="wordcraft_canvas">`. Everything below exists because that
canvas is the only observable surface: the web runner ignores egui's `ViewportCommand::Title`, has
no accesskit tree on web (`eframe/src/web/app_runner.rs`: `accesskit_update: _ // not currently
implemented`), and posts no "document open" message on its `?host=parent` bridge — `wordcraft:ready`
fires when the runner is up, before any document is loaded.

## Build (once per pin)

```bash
export PATH="$HOME/.cargo/bin:$PATH"
cd repos/wordcraft/apps/wordcraft-web
trunk build --release        # 178 s cold (2 m 51 s cargo + wasm-bindgen + wasm-opt -Oz), output: repos/wordcraft/dist/web
```

`repos/wordcraft/target` is a symlink into the `mbx` build cache
(`~/Library/Caches/mbx/targets/v1/<hash>`). When that cache directory is missing, cargo dies with
`failed to create directory .../target: Not a directory (os error 20)`; `mkdir -p` on the symlink
target fixes it without touching the repo. `dist/` is gitignored.

## Serve

```bash
cd harness/ui/wordcraft-host
node server.mjs              # http://127.0.0.1:5219/  (PORT=, WC_DIST=, CORPUS_DOCX= override)
```

Not `trunk serve`: the shim has to be injected into the app's own `index.html`, and `server.mjs`
does that while serving the Trunk output at `/` (assets keep their `./`-relative hashed names).

## How the document is opened

`/_host/host.js` fetches `/corpus.docx` (the driver intercepts that route, so the measured bytes are
the runner's fixture) and dispatches `dragenter`/`dragover`/`drop` on the canvas with a `DataTransfer`
holding a real `File`. That is the app's own open path — `apps/wordcraft-web/src/web.rs` reads
dropped files into `Inbox`, `wordcraft_ui_egui` drains it into `file.open` — the same path File ›
Open (rfd picker) and a user drop use. The app is not modified.

## Ready signal

- `ready_js`: `window.__WORDCRAFT_READY__ === true`
- `ready_selector`: `#wc-ready[data-state="rendered"]` (status chip, `pointer-events: none`)

The app draws into one canvas and publishes no DOM/JS state about the open document, so readiness
uses the app's own window title: `sync_title_and_frame` (`crates/ui-egui/src/app/frame.rs`) sends
`ViewportCommand::Title(<document> - WordCraft)` at the end of every frame whose title changed, and
eframe's web runner logs what it cannot apply:

```
[eframe::web::app_runner] eframe/src/web/app_runner.rs:353:
Unhandled egui viewport command: Title("corpus - WordCraft") - not implemented in web backend
```

`host.js` taps `console.warn`/`log`/`info` before Trunk's deferred module runs (every line is still
printed), and waits for a title line, issued after the drop, that differs from the pre-open title —
i.e. the app stating that the document is now the session's document, at the end of the frame that
laid it out and painted it. Then two animation frames, so that paint has been presented, and only
then `window.__WORDCRAFT_READY__ = true`. A failed open never produces the title line, so ready
stays false.

Canvas pixel readback is not used: the wgpu WebGL2 surface has no `preserveDrawingBuffer`, so
`drawImage`/`toDataURL` return a fully transparent frame (sampled: `opaque 0.000` at every frame).
Readiness therefore cannot be a pixel test without changing the app's context attributes, which
would alter what is measured.

Measured on this machine: ready at 711-1135 ms in-page (783-1272 ms from `domcontentloaded`), on the
runner's own 1.2 KB `micro-paragraphs` corpus.

## Edit target

`edit_selector: "#wordcraft_canvas"` — the canvas is focusable (`tabindex=0`, set by eframe), so the
driver's click focuses it and `keyboard.type` reaches the app's `keydown` listener; focus ends up in
eframe's hidden text agent (`document.activeElement` = its `<input>`). Confirmed by smoke: a typed
`x` appears in the document.

Caveat: `fixture/complex.docx` carries `w:documentProtection w:edit="readOnly" w:enforcement="1"`
in `word/settings.xml`, and WordCraft honours it — typing there is refused with
`not available: text.insert: only the editable regions of this protected document can change`. The
perf corpus (`perf/fixtures/generate.py::docx_zip_bytes`) has no `settings.xml` and is editable.

## C10 scroll

`adversarial_c10_scroll.mjs` looks for the largest `overflow-y: auto|scroll` element with
`scrollHeight - clientHeight >= 200` and measures the paint after setting `scrollTop`. A canvas app
has no such element, and with none the probe measures two empty rAFs. `#wc-scroll` (invisible,
`pointer-events: none`, 3× viewport tall) is that element: its `scroll` event is forwarded to the
canvas as a `wheel` event of the same pixel delta, at the canvas centre, which is the app's own
scroll path.
