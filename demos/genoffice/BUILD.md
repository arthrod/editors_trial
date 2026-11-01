# GenOffice: live demo build

Built from https://github.com/genspark-ai/genoffice at commit `a538d04` (Apache-2.0), the commit the editors trial measured.
The files here are the demo's own host page and build configuration, placed at `apps/docs/demo-web` inside
that checkout (paths below are relative to it).

```sh
git clone https://github.com/genspark-ai/genoffice src && git -C src checkout a538d04
cp -R apps/docs/demo-web src/apps/docs/demo-web   # the files in this folder
cd src && npm install
cd apps/docs/demo-web && ../../../node_modules/.bin/vite build   # writes dist/
```

The output folder is published by benchmarks.law's `pnpm sync:demos` at /demo-apps/genoffice/, with
the sanitized fixture from `build/make_demo_docs.py` as `document.docx`.
