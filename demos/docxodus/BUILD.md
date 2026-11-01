# Docxodus: live demo build

Built from https://github.com/JSv4/Docxodus (MIT) at the commit the editors trial measured. That commit is not typed here: it is written to
`dist/SOURCE.txt` from git by `build/rebuild_demo.sh docxodus`, which checks it out from the trial's `repos/` checkout.
The files here are the demo's own host page and build configuration. Put them in a folder named `host` next to
the checkout, which is cloned into `src` (the licence is read from `../src/LICENSE`); `pnpm build` runs in `host`.

```sh
pnpm install          # docxodus at the version the trial's harness pins (harness/ui/docxodus), recorded in SOURCE.txt
pnpm build            # writes ../dist; vite.config.ts copies the package's own wasm runtime next to it
```

The output folder is published by benchmarks.law's `pnpm sync:demos` at /demo-apps/docxodus/, with
the sanitized fixture from `build/make_demo_docs.py` as `document.docx`.
`sync:demos` writes that `document.docx` into the published folder itself; set `DEMO_DOCX` to a sanitized copy
(`out/demo/<editor>.docx`) only to preview the build on its own.
