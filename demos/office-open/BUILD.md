# office-open: live demo build

Built from https://github.com/DemoMacro/office-open at commit `567addf` (MIT), the commit the editors trial measured.
The files here are the demo's own host page and build configuration. Put them in a folder named `demo` next to
the checkout, which is cloned into `src`; the commands run from that shared parent folder.

```sh
git clone https://github.com/DemoMacro/office-open src && git -C src checkout 567addf
(cd src && pnpm install)
cd demo && pnpm install && pnpm build   # writes ../dist
```

The output folder is published by benchmarks.law's `pnpm sync:demos` at /demo-apps/office-open/, with
the sanitized fixture from `build/make_demo_docs.py` as `document.docx`.
`sync:demos` writes that `document.docx` into the published folder itself; set `DEMO_DOCX` to a sanitized copy
(`out/demo/<editor>.docx`) only to preview the build on its own.
