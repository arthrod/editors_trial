# WordCraft: live demo build

Built from https://github.com/storytold/wordcraft (MIT OR Apache-2.0) at the commit the editors trial measured. That commit is not typed here: it is written to
`dist/SOURCE.txt` from git by `build/rebuild_demo.sh wordcraft`, which checks it out from the trial's `repos/` checkout. WordCraft is Rust compiled to WebAssembly; the web app is `apps/wordcraft-web`, built with Trunk.

`demo.patch` is everything the demo changes in that checkout:

- `apps/wordcraft-web/src/web.rs`: on start the page fetches `./document.docx` and hands the bytes to the app's
  inbox, where its own `file.open` opens them, as it does a file picked in the browser. `window.wordcraftDemo`
  exposes `downloadDocx()`, which runs the app's own `file.save`, and the open document's text through
  `document.text`, for the checks. On a screen narrower than 860 px the page opens zoomed to the screen's width
  (`view.zoom`).
- `apps/wordcraft-web/index.html`: a 36 px strip above the editor canvas holds the "Download .docx" button.
- `apps/wordcraft-web/Cargo.toml`: eframe paints through WebGL2 (`glow`) rather than WebGPU, which every
  browser has. The root `Cargo.toml` release profile optimises for size (`opt-level = "z"`, fat LTO, one
  codegen unit), keeping the `.wasm` under the 25 MiB per-file limit of the host.
- `apps/wordcraft-web/Trunk.toml`: the output goes to `dist/` next to the checkout.

```sh
git clone https://github.com/storytold/wordcraft src && git -C src checkout <Commit from SOURCE.txt>
git -C src apply ../demo.patch
rustup target add wasm32-unknown-unknown && cargo install trunk --locked
cd src/apps/wordcraft-web && trunk build --release        # → ../../../dist/
# then add LICENSE (the MIT text), LICENSE-APACHE, NOTICE and SOURCE.txt to dist/
```

The output folder is published by benchmarks.law's `pnpm sync:demos` at /demo-apps/wordcraft/, with
the sanitized fixture from `build/make_demo_docs.py` as `document.docx`.
