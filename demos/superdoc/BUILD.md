# SuperDoc: live demo build

Built from https://github.com/superdoc/docx-editor at commit `f52c959` (AGPL-3.0), the commit the editors trial measured.
The files here are the demo's own host page and build configuration, placed at `examples/bench-demo` inside
that checkout (paths below are relative to it).

```sh
cd examples/bench-demo && pnpm install && pnpm build    # vite build → dist/
```

The output folder is published by benchmarks.law's `pnpm sync:demos` at /demo-apps/superdoc/, with
the sanitized fixture from `build/make_demo_docs.py` as `document.docx`.
