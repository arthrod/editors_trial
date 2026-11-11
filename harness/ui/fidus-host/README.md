# Fidus Writer perf host

The warm/cold browser probe (`perf/runner/warm_cold_browser.mjs`) makes one
`goto(url)`, waits for one selector, then clicks and types. Fidus Writer needs
three things a single page load does not give it (Report C §2.11): a signed-in
session, the corpus handed to its **own** DOCX importer, and the
"Updating document. Please wait…" cover lifted — that cover is never lifted by
the application itself because the adjust-doc-to-template worker throws
(`RangeError: Invalid content for node title`) and its `onerror` only logs.

This folder supplies those three things without touching `repos/`:

| file | role |
|---|---|
| `proxy.mjs` | serves the Django app on **one origin** (`localhost:5219` → `127.0.0.1:5209`), passes WebSocket upgrades through, serves `/corpus.docx` and `/__fidus_host/boot.js`, and appends one `<script>` tag to HTML responses. Starts Django itself if nothing is listening on 5209. |
| `boot.js` | the injected script: log in → import the corpus through the app's own dialog → follow the new document into the editor → lift the cover → mark ready. |
| `smoke.mjs` | one page load of the exact probe calls, plus the check the probe cannot make (the text is still there after a keystroke). |

A proxy, not a separate shim page: Fidus's session cookie and CSRF check are
same-origin, so a shim on another port cannot log in. Behind this proxy every
URL, cookie and POST stays on `localhost:5219`, and Django's
`ALLOWED_HOSTS = ["localhost"]` still matches.

## What is injected, and what that changes

Only `<script src="/__fidus_host/boot.js" defer></script>` is added to HTML
responses; no other byte of any response is rewritten. The script performs two
interventions that **Report C §2.11 already discloses for this editor**, both
applied on every load instead of once:

1. the corpus is imported through the application's own
   "Import document" dialog (`#doc-uploader` + the dialog's Import button) —
   the same path the screenshot probe uses;
2. the never-cleared `#wait` cover is lifted, which is what `deactivateWait()`
   does. Without it the cover sits over the editor and the edit measurement
   cannot click the text.

Everything visible in the editor is Fidus's own output; what is *not* Fidus's
own output is the cover's absence and the login/import driving.

## Ready and edit selectors

- `ready_selector: html[data-fidus-host-ready="1"]` — set by `boot.js` only
  after `#document-editable .ProseMirror` holds the imported text (≥ 80 chars)
  **and** the cover is gone. It is deliberately not `.ProseMirror`: that element
  exists before the document arrives, and `.ProseMirror` also matches the
  footnote editor (two nodes, 865 and 71 chars).
- `edit_selector: #document-editable .ProseMirror` — the body editor only.

## Running it

Precondition: the account `corpus` / `corpus-pass-2026` exists in
`repos/fiduswriter/fiduswriter/fiduswriter.sqlite3` (it does in this checkout;
the previous release's probe used the same account). Without it `boot.js`
retries three times, then sets `data-fidus-host-error`, which the smoke prints.

```bash
# 1. the venv the whole recipe expects (Report C §2.11). Rebuild if missing:
#    uv venv /tmp/fidusvenv2 --python 3.13
#    uv pip install --python /tmp/fidusvenv2/bin/python -r repos/fiduswriter/fiduswriter/requirements.txt
#    (prosemirror-rs is not needed with PROSEMIRROR_BACKEND="python" and needs Rust;
#     the installed set omits it)
# 2. transpile the frontend, with the two build blockers from Report C:
#    mkdir -p /tmp/capture_ui_gnucp && ln -sf "$(command -v gcp)" /tmp/capture_ui_gnucp/cp
#    PATH=/tmp/capture_ui_gnucp:$PATH DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/opt/libmagic/lib \
#      (cd repos/fiduswriter/fiduswriter && /tmp/fidusvenv2/bin/python manage.py transpile --force)
#    -> must print "Rspack compiled successfully"
# 3. the host (starts Django on 5209 if it is not already up):
cd harness/ui && node fidus-host/proxy.mjs --port 5219
# 4. one smoke:
cd harness/ui && node fidus-host/smoke.mjs --url http://localhost:5219/
# 5. the probe itself, one pair:
node perf/runner/warm_cold_browser.mjs --driver playwright \
  --url http://localhost:5219/ --corpus fixture/complex.docx --corpus-route /corpus.docx \
  --ready-selector 'html[data-fidus-host-ready="1"]' \
  --edit-selector '#document-editable .ProseMirror' --pairs 1
```

## The target

```python
"fidus": {
    "cwd": UI / "fidus-host",
    "command": ["node", "proxy.mjs", "--port", "5219"],
    "url": "http://localhost:5219/",
    "corpus_route": "/corpus.docx",
    "ready_selector": 'html[data-fidus-host-ready="1"]',
    "edit_selector": "#document-editable .ProseMirror",
    "driver": "playwright",
    "env": {"FIDUS_PY": "/tmp/fidusvenv2/bin/python"},
    "criteria": {
        "C03": ("first_usable", "browser_visible"),
        "C02b": ("model_ready_browser", "model"),
        "C05": ("presented_frame", "browser_visible"),
        "C06": ("input_to_next_paint", "browser_visible"),
    },
},
```

## Measurement caveat — read this before quoting a number

The cold load of this target is `/` → login (AJAX, in place) →
`/documents/overview/` → import → `/document/<id>`, so
`model_ready_browser_ms` for Fidus includes a login round trip, the overview
page load and the client-side DOCX conversion, where the other browser targets
only fetch and parse the corpus. The warm pass (`page.reload()` on the document
URL) does not: it is a plain document load.

A cold/warm contrast is therefore still meaningful, but Fidus's cold
`first_usable_ms` is not on the same footing as the other editors' and must not
be ranked against them without that sentence. Making the cold load comparable
would need the **proxy** to sign in on the browser's behalf and inject the
session cookie, which this host does not do.

### The port opens before the application does

Django's `runserver` binds `5209` for a **maintenance page** before it runs
`setup` (`migrate` + `pnpm install` + the first rspack transpile), and answers
every path with that page until `setup` returns. On a cold checkout that is
minutes. The proxy therefore no longer treats an open socket as a ready app:
it listens at once, lets navigations wait until `/` answers with something
other than the setup page, and answers everything else `503` until then. The
2026-11-08 warm/cold run failed here — the probe's 120 s `waitForSelector`
expired on the self-reloading maintenance page, so `fidus` was recorded
`not_run` without the editor ever being asked to render.

### The perf harness's own fixture does not import

`perf/fixtures/generate.py:docx_zip_bytes` writes a four-part package —
`[Content_Types].xml`, `_rels/.rels`, `word/_rels/document.xml.rels`,
`word/document.xml` — with no `docProps/core.xml`. Fidus Writer's client-side
importer requires that optional part:

```
TypeError: Cannot read properties of null (reading 'query')
    at DocxConvert.extractAuthors
    at DocxConvert.extractMetadata
    at DocxConvert.convertDocument
    at async doImport
```

`extractAuthors` does `zip.file('docProps/core.xml').query(...)` with no null
guard, the dialog stays open, no document row appears, and the probe's 120 s
`waitForSelector` expires — recorded as `not_run`, with the editor never
reaching a document. Measured on 2026-11-08: the same fixture with one added
`docProps/core.xml` (creator/lastModifiedBy) imports in **2.1 s** and renders
152 characters, so the whole gap is that missing part. The file itself is not
malformed: LibreOffice opens the four-part original as a Writer document
(1-page PDF). `boot.js` now catches the importer's throw and writes it to
`data-fidus-host-error` within ~2 s instead of waiting out the row budget, so
a manual run names the cause; the attempt file the runner writes still carries
its own generic `waitForSelector` timeout.

Consequence for the warm/cold suite: `fidus` C02/C03/C05/C06 are `not_run` for
a workload whose fixture is built by `docx_zip_bytes`. Making it pass would
mean adding the part to the document the probe serves, i.e. measuring a file
the editor cannot open — that belongs in the report as a finding, not in the
host. Ten other editors were measured on the identical bytes (1203 B,
`fixture_sha256` `dcfe72be3279`) where `fidus` was `not_run`, so the fixture is
loadable; Fidus's importer is the one that refuses it.

### The first load after a fresh boot is not a measurement

Observed on this machine: the first page load after `proxy.mjs` had just
started Django measured `ready_ms` **9988 ms**; the next load on the same stack
measured **2455 ms**, and a stack that had already served a page measured
1834–2372 ms. That ~7.5 s is Django's first-request warmup (Python imports and
the static bundle fan-out), not Fidus. `build/capture_ui.sh` warms every host
before capturing for exactly this reason. Warm the host once before a measured
pair:

```bash
node fidus-host/smoke.mjs --url http://localhost:5219/   # warm, discard
```
