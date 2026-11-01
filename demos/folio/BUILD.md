# Folio: live demo build

Built from https://github.com/stella/folio at commit `c83cfc4` (Apache-2.0), the commit the editors trial measured.
The files here are the demo's own host page and build configuration, placed at `dist/index.html (host page)` inside
that checkout (paths below are relative to it).

One source change, in `mount-fit-width.patch`: the editor opens at "fit-width" zoom on a viewport narrower than
860 px, so a phone sees the whole page width; wider screens keep 100%.

```sh
git apply mount-fit-width.patch
cd packages/editor-web && bun scripts/build.ts    # the repo's own webview bundle build
# copy its output (editor.js, editor.css, fonts/) to dist/, then add host-index.html as dist/index.html,
# plus NOTICE.md and editor.js.LEGAL.txt
```

The output folder is published by benchmarks.law's `pnpm sync:demos` at /demo-apps/folio/, with
the sanitized fixture from `build/make_demo_docs.py` as `document.docx`.
