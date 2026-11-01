# Docxodus: live demo build

Built from https://github.com/JSv4/Docxodus at commit `ceb5cde` (MIT), the commit the editors trial measured.
The files here are the demo's own host page and build configuration, placed at `.` inside
that checkout (paths below are relative to it).

```sh
pnpm install          # docxodus@14.2.0 from npm, the package the trial measured (Report A)
pnpm build            # writes ../dist; vite.config.ts copies the package's own wasm runtime next to it
```

The output folder is published by benchmarks.law's `pnpm sync:demos` at /demo-apps/docxodus/, with
the sanitized fixture from `build/make_demo_docs.py` as `document.docx`.
