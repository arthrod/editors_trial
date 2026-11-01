# docs.plus: live demo build

Built from https://github.com/docs-plus/docs.plus at commit `a9b0c69` (MIT), the commit the editors trial measured.
The files here are the demo's own host page and build configuration, placed at `app` inside
that checkout (paths below are relative to it).

```sh
git clone https://github.com/docs-plus/docs.plus src && git -C src checkout a9b0c69
cd app && pnpm install && pnpm build   # writes ../dist; the converter is imported unchanged from ../src
```

The output folder is published by benchmarks.law's `pnpm sync:demos` at /demo-apps/docs-plus/, with
the sanitized fixture from `build/make_demo_docs.py` as `document.docx`.
