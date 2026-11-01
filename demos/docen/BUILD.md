# Docen: live demo build

Built from https://github.com/DemoMacro/docen at commit `1890b15` (MIT), the commit the editors trial measured.
The files here are the demo's own host page and build configuration, placed at `packages/editor` inside
that checkout (paths below are relative to it).

```sh
cd packages/editor && pnpm exec vite build --config benchmark.vite.config.ts    # → ../../../dist/ (outDir in the config)
```

The output folder is published by benchmarks.law's `pnpm sync:demos` at /demo-apps/docen/, with
the sanitized fixture from `build/make_demo_docs.py` as `document.docx`.
