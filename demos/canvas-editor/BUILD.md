# canvas-editor + docx plugin: live demo build

Built from https://github.com/Hufe921/canvas-editor (MIT) at the commit the editors trial measured. That commit is not typed here: it is written to
`dist/SOURCE.txt` from git by `build/rebuild_demo.sh canvas-editor`, which checks it out from the trial's `repos/` checkout.
The files here are the demo's own host page and build configuration, placed at `demo` inside
that checkout (paths below are relative to it).

```sh
git clone https://github.com/Hufe921/canvas-editor src && git -C src checkout <Commit from SOURCE.txt>
git clone https://github.com/Hufe921/canvas-editor-plugin plugin && git -C plugin checkout <Commit from SOURCE.txt>
(cd plugin && pnpm install)
pnpm install && pnpm build   # writes dist/
```

The output folder is published by benchmarks.law's `pnpm sync:demos` at /demo-apps/canvas-editor/, with
the sanitized fixture from `build/make_demo_docs.py` as `document.docx`.
