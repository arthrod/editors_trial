# Plate: live demo build

Built from https://github.com/udecode/plate at commit `08b1571` (MIT), the commit the editors trial measured.
The files here are the demo's own host page and build configuration. Put them in a folder named `app` next to
the checkout, which is cloned into `src`; the commands run from that shared parent folder.

```sh
git clone https://github.com/udecode/plate src && git -C src checkout 08b1571
(cd src && pnpm install && pnpm build)   # the workspace packages publish from dist/
cd app && pnpm install && pnpm build      # writes ../dist
```

The output folder is published by benchmarks.law's `pnpm sync:demos` at /demo-apps/plate/, with
the sanitized fixture from `build/make_demo_docs.py` as `document.docx`.
