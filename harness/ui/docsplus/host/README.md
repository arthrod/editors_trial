# docs.plus perf host

The product's own webapp, serving `fixture/complex.docx` in its editor, behind a
ready signal the perf probe can wait on.

```
./start.sh                      # http://127.0.0.1:5215/editor
node smoke.mjs --reload true    # one open: wait ready, type one char, screenshot
```

Ports: `5215` front (this host), `5216` the Next.js dev server (internal),
`4210` the import endpoint (internal). Override with `DOCSPLUS_PORT`,
`DOCSPLUS_INTERNAL_PORT`, `DOCSPLUS_STUB_PORT`, `DOCSPLUS_FIXTURE`.

## Why there is a proxy in front

docs.plus has no "open a DOCX from a URL" entry point. A DOCX arrives as an
upload, is converted on the server, and the result replaces the pad
(`ImportExportSection` → `importDocument` → `applyImportedContent`). The app
also has no hook to tell an outside driver "the document is loaded".

So `serve.mjs` reverse-proxies the app's own `/editor` page and appends one
`<script type="module" src="/__perf/bridge.js">` before `</body>`. Nothing else
changes: the page is the product's, the styles are the product's, the editor is
the product's. WebSocket upgrades (HMR) are piped through, and
`accept-encoding` is stripped so the HTML can be edited in place.

## What the bridge does

`bridge.js`, running inside that page:

1. waits for `window._editor` (the playground's own escape hatch,
   `apps/webapp/src/components/pages/editor/EditorPlayground.tsx`);
2. `GET /corpus.docx` — the same route the perf probe intercepts and fulfils;
3. `POST <rest>/documents/harness/import` with the bytes as `documentFile` —
   the product's import endpoint, whose handler here is the repo's own
   `importDocx()` (mammoth + `parseDocumentHtml`), not a re-implementation;
4. `editor.commands.setContent(content)` — the call `applyImportedContent()`
   makes after the user confirms in the import panel;
5. waits for the rendered document, `document.fonts.ready`, every `<img>` to
   decode, then two animation frames.

## Signals

| Signal | Meaning |
|---|---|
| `window.__DOCSPLUS_READY__ === true` | document rendered, fonts and images settled, painted |
| `#perf-status[data-state="ready"]` | the same moment, as a visible element (bottom-right) |
| `window.__DOCSPLUS_INFO__` | `{title, warnings, text_length, images, timings}` |
| `window.__DOCSPLUS_ERROR__` | set instead of `READY` when any step fails |

Ready fires at both signals in the same tick, so the probe can use the global
and a human (or a selector-only consumer) can use the badge. `?perf=0` on the
URL leaves the bridge idle for manual exploration.

`edit_selector` is `.tiptap__editor .ProseMirror`: the ProseMirror
`contenteditable` itself, one element, which is what receives typing.

## Real vs stubbed

Real: the webapp, the editor, the DOCX conversion (`importDocx` from
`apps/hocuspocus.server/.../document-conversion/domain/docxImport.ts`), image
rehosting through the injected `uploadImage` boundary, the apply call.

Stubbed: only the two things the app requires from services that are not
running here — the REST import endpoint (`restapi.ts`, in-memory media store
served back from `/media/<n>`) and the environment variables the app validates
at boot (`NEXT_PUBLIC_SUPABASE_*`, `NEXT_PUBLIC_PROVIDER_URL` are set to
dummy values; the playground runs with `provider: null`, so no collab server is
contacted).

Deliberate deviation: the import *staging panel* is bypassed, so
`commitImportedImageSizes()` does not run. The corpus carries explicit image
extents, so pictures arrive sized; the seven images in `complex.docx` render.

## One-time prerequisites

`repos/docs-plus` needs dependencies and built workspace packages (both are
build output / `node_modules`, no tracked file is touched):

```
cd repos/docs-plus
bun install --frozen-lockfile --ignore-scripts
bun run --filter './packages/*' build
bun run --filter './extensions/*' build
```

`start.sh` refuses to start and prints these commands if either is missing.
Order matters: `packages/*` (floating-popover, floating-tooltip) before
`extensions/*`.

## Notes and limits

- The app runs as a **dev server** (turbopack), like the other browser hosts in
  `harness/ui/`. `start.sh` pre-warms `/editor` once so a one-off bundler
  compile does not land inside the measured load; `DOCSPLUS_SKIP_PREWARM=1`
  turns that off. A production build (`next build` + `next start` with
  `NEXT_PUBLIC_E2E=true`, which is what makes `/editor` routable in prod) would
  remove the remaining compile jitter — not done here.
- `first_usable` includes the server-side conversion (~80 ms for the 25 KB
  corpus) because that is the product's real open path.
- The `#perf-status` badge is deliberately small and `pointer-events: none`; it
  sits in the corner so it cannot intercept a click meant for the editor.
- `window.__DOCSPLUS_INFO__.timings` is diagnostic only, never a measured value.
