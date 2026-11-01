# canvas-editor + docx plugin: live demo build

Built from https://github.com/Hufe921/canvas-editor at commit `8b94772` (MIT), the commit the editors trial measured.
The files here are the demo's own host page and build configuration, placed at `demo` inside
that checkout (paths below are relative to it).

```sh
git clone https://github.com/Hufe921/canvas-editor src && git -C src checkout 8b94772
git clone https://github.com/Hufe921/canvas-editor-plugin plugin && git -C plugin checkout 0e8a1b3
(cd plugin && pnpm install)
pnpm install && pnpm build   # writes dist/
```

The output folder is published by benchmarks.law's `pnpm sync:demos` at /demo-apps/canvas-editor/, with
the sanitized fixture from `build/make_demo_docs.py` as `document.docx`.
