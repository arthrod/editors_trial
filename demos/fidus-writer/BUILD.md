# Fidus Writer: live demo build

Built from https://git.fiduswriter.org/fiduswriter/fiduswriter-document-ts (AGPL-3.0) at the commit the editors trial measured. That commit is not typed here: it is written to
`dist/SOURCE.txt` from git by `build/rebuild_demo.sh fidus-writer`, which checks it out from the trial's `repos/` checkout.
The files here are the demo's own host page and build configuration, placed at `.` inside
that checkout (paths below are relative to it).

```sh
git clone https://git.fiduswriter.org/fiduswriter/fiduswriter-document-ts src && git -C src checkout <Commit from SOURCE.txt>
cp -R demo scripts src/     # the files in this folder: demo/docx/ and scripts/build-docx-demo.mjs
cd src && pnpm install && pnpm add -D esbuild && pnpm run build
node scripts/build-docx-demo.mjs ../dist path/to/document.docx
```

The output folder is published by benchmarks.law's `pnpm sync:demos` at /demo-apps/fidus-writer/, with
the sanitized fixture from `build/make_demo_docs.py` as `document.docx`.
