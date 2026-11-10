# docen — warm/cold browser host

A one-command Vite host that loads a DOCX into the docen editor
(`<docen-document>` from `repos/docen/packages/editor`) so
`perf/runner/warm_cold_browser.mjs` can measure first_usable (C03),
presented_frame (C05) and input_to_next_paint (C06).

Lives outside `repos/` on purpose: `repos/docen` is never modified. The dev
server serves the editor **from source** — the same aliases the repo's own demo
uses (`repos/docen/packages/editor/vite.config.ts`) — so no build step runs and
no `dist/` is written into the checkout.

## Run it

```bash
cd harness/ui/docen-host
pnpm install --ignore-scripts   # once: vite 8.3.6
pnpm exec vite --port 5214 --strictPort --host 127.0.0.1
```

Then open <http://127.0.0.1:5214/>. The page fetches `/corpus.docx` and opens it;
with no corpus served it shows `fetch /corpus.docx -> HTTP 404` in the console
and stays un-ready (the probe fulfils that route from `--corpus`).

Smoke test (starts its own server on 5214, refuses to run if the port is busy):

```bash
node smoke.mjs
```

It writes `/tmp/perf-run-logs/docen-smoke-{console.log,ready.png,after-typing.png,report.json}`.

## Contract

| Piece | Value | Why |
|---|---|---|
| ready selector | `#host[data-ready="1"]` | set together with the global, only after the DOCX parse returned **and** page 1's canvas has a non-zero bitmap |
| ready JS | `window.__DOCEN_READY__ === true` | same gate; also exposed as `window.__DOCEN__` (the element) and `window.__DOCEN_PAINT__` (`{pageFrames, canvas}`) |
| edit selector | `docen-document .canvas-pages > div:first-child` | page 1's frame, inside the shadow root. The stage's mousedown handler (`edit-bridge.ts` `takeFocus`) parks + focuses the invisible textarea that owns keyboard input; typing then lands through `beforeinput`. Clicking the stage host itself (`.docen-canvas`) is *not* usable — its box is the whole page stack (6368 px tall on `complex.docx`), so its centre is off-screen. |
| scroll proxy | `#scroll-proxy` (light DOM, 2 px, opacity 0, `pointer-events: none`) | C10 (`perf/runner/adversarial_c10_scroll.mjs`) only scans `document.querySelectorAll('*')` for the largest `overflow: auto\|scroll` box, and `docen-document-area` is inside the shadow root. The proxy mirrors the real scroller's `clientHeight`/`scrollHeight`, and `scrollTop` is copied both ways, so the probe's 50 % scroll moves the real scroller by the same pixels. |

`wait_after_ready: 300` covers the caret overlay that follows the first paint.

Editability is the editor's own: `#syncEditable()` = `editable != "false"` ∧
`view != "read"` ∧ no `w:documentProtection` in `settings.xml`. The warm/cold
corpus (`perf/fixtures/generate.py`, micro-paragraphs) is unprotected →
`isEditable === true`, typing inserts. `fixture/complex.docx` carries
`<w:documentProtection w:edit="readOnly" w:enforcement="1">`, so docen opens it
read-only and typing does **not** mutate it — faithful behaviour, and the reason
the smoke uses the suite's own corpus. The host never strips protection.

## Registry entry

`perf/runner/benchmark_warm_cold.py` — appended to `BROWSER_TARGETS` by the
coordinator (this file does not edit it):

```python
    "docen": {
        "cwd": UI / "docen-host",
        "command": ["pnpm", "exec", "vite", "--port", "5214", "--strictPort", "--host", "127.0.0.1"],
        "url": "http://127.0.0.1:5214/",
        "corpus_route": "/corpus.docx",
        "ready_selector": '#host[data-ready="1"]',
        "ready_js": "window.__DOCEN_READY__ === true",
        "wait_after_ready": "300",
        "edit_selector": "docen-document .canvas-pages > div:first-child",
        "driver": "playwright",
        "criteria": {
            "C03": ("first_usable", "browser_visible"),
            "C02b": ("model_ready_browser", "model"),
            "C05": ("presented_frame", "browser_visible"),
            "C06": ("input_to_next_paint", "browser_visible"),
        },
    },
```

C02b is listed for parity with the other hosts; the harness exposes a single
ready signal, so `benchmark_warm_cold.py` itself records C02 as
`not_run` with its "shared ready signal" reason.

## Evidence (final state of this host)

- `node smoke.mjs` → all checks PASS: ready selector visible, `isEditable === true`, page-1 canvas non-zero, 4 cold + 1 warm edit each insert exactly one character and repaint the canvas, and the scroll proxy moves the real scroller 88 → 330 px.
- `perf/runner/warm_cold_browser.mjs --pairs 1` → cold `first_usable_ms` 772,
  `presented_frame_ms` 27.3, `sustained_typing_median_ms` 83; warm reload 970,
  warm edit 114. Indicative only (not a quiet-machine measurement).
- `perf/runner/adversarial_c10_scroll.mjs --pairs 1` → `scroll_frame_ms` [30];
  a 50 % proxy scroll moves `docen-document-area` 0 → 330 px and changes the
  screenshot.

## Known noise

- Console: `Module "node:zlib" has been externalized` (a dep touches `node:zlib`
  in a guarded path; the DOCX parse still completes) and one
  `[tiptap warn]: Invalid content … Unknown node type: undefined` from the
  corpus' `w:sdt` run. Both appear identically on every load; neither blocks
  rendering.
- The host renders the real ribbon/status chrome, like the repo's demo. If a
  later criterion wants a chrome-free page, that is a host change, not a
  measurement change.
