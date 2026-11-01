# eigenpal docx-editor: live demo build

Built from https://github.com/eigenpal/docx-editor at commit `c6f8f0f` (Apache-2.0 (no Pro packages)), the commit the editors trial measured.
The files here are the demo's own host page and build configuration, placed at `app/ beside the checkout (src/)` inside
that checkout (paths below are relative to it).

```sh
cd app && pnpm build    # prepare-public, vite build against ../src/packages/*/dist, finalize-dist → ../dist/
```

The output folder is published by benchmarks.law's `pnpm sync:demos` at /demo-apps/eigenpal/, with
the sanitized fixture from `build/make_demo_docs.py` as `document.docx`.
