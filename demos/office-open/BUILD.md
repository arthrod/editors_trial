# office-open: live demo build

Built from https://github.com/DemoMacro/office-open at commit `567addf` (MIT), the commit the editors trial measured.
The files here are the demo's own host page and build configuration, placed at `demo` inside
that checkout (paths below are relative to it).

```sh
git clone https://github.com/DemoMacro/office-open src && git -C src checkout 567addf
(cd src && pnpm install)
cd demo && pnpm install && pnpm build   # writes ../dist
```

The output folder is published by benchmarks.law's `pnpm sync:demos` at /demo-apps/office-open/, with
the sanitized fixture from `build/make_demo_docs.py` as `document.docx`.
