# docs.plus: live demo build

Built from https://github.com/docs-plus/docs.plus (MIT) at the commit the editors trial measured. That commit is not typed here: it is written to
`dist/SOURCE.txt` from git by `build/rebuild_demo.sh docs-plus`, which checks it out from the trial's `repos/` checkout.
The files here are the demo's own host page and build configuration. Put them in a folder named `app` next to
the checkout, which is cloned into `src`; the commands run from that shared parent folder.

```sh
git clone https://github.com/docs-plus/docs.plus src && git -C src checkout <Commit from SOURCE.txt>
cd app && pnpm install && pnpm build   # writes ../dist; the converter is imported unchanged from ../src
```

The output folder is published by benchmarks.law's `pnpm sync:demos` at /demo-apps/docs-plus/, with
the sanitized fixture from `build/make_demo_docs.py` as `document.docx`.
`sync:demos` writes that `document.docx` into the published folder itself; set `DEMO_DOCX` to a sanitized copy
(`out/demo/<editor>.docx`) only to preview the build on its own.
