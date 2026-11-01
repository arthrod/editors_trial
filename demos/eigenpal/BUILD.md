# eigenpal docx-editor: live demo build

Built from https://github.com/eigenpal/docx-editor (Apache-2.0 (no Pro packages)) at the commit the editors trial measured. That commit is not typed here: it is written to
`dist/SOURCE.txt` from git by `build/rebuild_demo.sh eigenpal`, which checks it out from the trial's `repos/` checkout.
The files here are the demo's own host page and build configuration. Put them in a folder named `app` next to
the checkout, which is cloned into `src`; the commands run from that shared parent folder.

```sh
cd app && pnpm build    # prepare-public, vite build against ../src/packages/*/dist, finalize-dist → ../dist/
```

The output folder is published by benchmarks.law's `pnpm sync:demos` at /demo-apps/eigenpal/, with
the sanitized fixture from `build/make_demo_docs.py` as `document.docx`.
`sync:demos` writes that `document.docx` into the published folder itself; set `DEMO_DOCX` to a sanitized copy
(`out/demo/<editor>.docx`) only to preview the build on its own.
