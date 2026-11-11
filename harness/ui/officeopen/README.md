# office-open — browser perf host

`@office-open/docx` is a headless OOXML library: it parses, generates and
patches DOCX and ships **no editor UI and no layout engine**. This host (built
on the rendering-study app that already lived here) parses the corpus with the
pinned repo's `parseDocument()` and lays the parsed model out in the browser, so
the perf suite has a page to load and a document to look at.

## Start

```sh
cd harness/ui/officeopen
node server.mjs                     # PORT=5212 by default, 127.0.0.1 only
# -> http://127.0.0.1:5212/  loads /corpus.docx
```

`/corpus.docx` is `corpus.docx` in this directory, generated from the warm_cold
fixture (`micro-paragraphs` + the Unicode correctness fixture):

```sh
PYTHONPATH=. /opt/homebrew/bin/python3.13 make_corpus.py
```

The perf driver intercepts the same route, so measurements use the runner's
own fixture bytes; the file only keeps the host usable by hand.

Rebuild the bundle after editing `app.js` / `index.html`:

```sh
node build.mjs        # esbuild from repos/office-open/node_modules, reads packages/*/dist
```

The bundle reads the repo's own build output, which must exist first:

```sh
cd ../../../repos/office-open && pnpm --filter "@office-open/docx..." run build
```

`build.mjs` aliases `node:zlib` to `node-zlib-stub.js`: the library probes that
module and falls back to its JavaScript deflate/inflate, and the stub keeps
Chromium from logging a failed `node:` module load on every page load.

## Perf contract

| key | value | why |
|---|---|---|
| corpus route | `/corpus.docx` | served here and intercepted by the driver |
| ready | `#status.status-ok` **and** `window.__OFFICEOPEN_READY__ === true` | both set only after the rendered model has been in the DOM through two animation frames |
| edit | `#input-probe` | host `contenteditable` strip in the bar under the app bar; it exists so a typing smoke can run, **not** as an editor input pipeline |
| skip edit | `true` | `typing`/`visible_paint` are `not_applicable` on the `office-open/library` lane (`perf/adapters/capabilities.py`); C05/C06 would measure the browser, not office-open |
| scroll container | root element (`html { overflow-y: auto }`) | the C10 probe's predicate finds it; office-open itself has no viewport, so C10 stays not applicable |

C03 (`first_usable`, `browser_visible`) is the one warm/cold criterion this host
can feed: navigation → `parseDocument()` → parsed model rendered and the ready
marker visible. Read it as the host app's first usable render of the library's
output, not as an editor UI becoming usable.

## Smoke

```sh
node smoke.mjs        # starts the server itself, one page load, one keystroke
```

Writes `/tmp/perf-run-logs/officeopen-smoke.json`, `officeopen-console.log`,
`officeopen-server.log`, `officeopen-after-typing.png`,
`officeopen-fullpage.png`.
