# Docen: live demo build

Built from https://github.com/DemoMacro/docen (MIT) at the commit the editors trial measured. That commit is not typed here: it is written to
`dist/SOURCE.txt` from git by `build/rebuild_demo.sh docen`, which checks it out from the trial's `repos/` checkout.
The files here are the demo's own host page and build configuration, placed at `packages/editor` inside
that checkout (paths below are relative to it).

```sh
cd packages/editor && pnpm exec vite build --config benchmark.vite.config.ts    # → ../../../dist/ (outDir in the config)
```

The output folder is published by benchmarks.law's `pnpm sync:demos` at /demo-apps/docen/, with
the sanitized fixture from `build/make_demo_docs.py` as `document.docx`.
