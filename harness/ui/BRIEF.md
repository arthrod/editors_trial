# Rendering study — shared brief (READ FIRST)

You are capturing **how one DOCX editor renders a document in its own running UI**.

The mandated method, in this exact order:

- **(a) get the files** — the input document is
  `/Users/arthrod/temp/T/editors_trial/fixture/complex.docx` (a 35-part
  adversarial DOCX). Use that exact file. Do not use any editor's exported
  DOCX — we are measuring what the editor *displays*, not what it writes.
- **(b) host the tool locally** — run the editor's own dev server / demo app
  from `repos/<repo>` on the port assigned to you. Never modify anything
  under `repos/` (read-only). Installing dependencies into `node_modules`
  is fine.
- **(c) load the file with the tool** — open `complex.docx` in that running
  app.
- **(d) see how it renders** — wait for the layout to settle.
- **(e) screenshot the document being rendered in the tool** — a PNG of the
  app showing the rendered document.
- **(f) compare with how Word renders** — Word's own rendering of the same
  file is at
  `/Users/arthrod/temp/T/editors_trial/out/render/png_word/corpus-1.png` …
  `corpus-6.png` (110 dpi PNGs of Word's own PDF export).
  Look at them and describe, concretely, what the editor's UI shows
  differently.

## The driver

`/Users/arthrod/temp/T/editors_trial/harness/ui/shot.mjs` — a Playwright
script. Playwright is installed in `harness/ui/` (run it from that
directory so `import { chromium } from 'playwright'` resolves).

```
cd /Users/arthrod/temp/T/editors_trial/harness/ui
node shot.mjs --name <slug> --url <url> \
     [--serve-as <path> --file <docx> | --file <docx> --file-selector <css>] \
     [--wait <ms>] [--wait-for <text>] [--click <css>]... \
     [--viewport WxH] [--full-page] [--outdir <dir>]
```

Two ways to get the file in:

1. `--serve-as <path> --file <docx>` — **preferred**. The app requests a
   document from a URL; Playwright intercepts that request and returns the
   corpus bytes instead. Nothing in `repos/` is touched. Example: SuperDoc's
   example app requests `/sample.docx`, so
   `--serve-as /sample.docx --file ../../fixture/complex.docx`.
2. `--file <docx> [--file-selector <css>]` — the app has a file input;
   Playwright sets it. Default selector `input[type=file]`.

Outputs: `<outdir>/<slug>.png` and `<outdir>/<slug>.json` (console log,
page errors, failed requests).

**Write your screenshots to `/Users/arthrod/temp/T/editors_trial/out/ui/`.**
Use the slug assigned to you below.

## Rules

- **Do not modify anything under `repos/`.** If a build step would write
  into the repo (`dist/`, `node_modules/`), that is acceptable only for
  `node_modules/` and build output; never edit source files, never change
  `package.json` scripts, never add files to a repo.
  If you truly need a different entry point, create a host app under
  `/Users/arthrod/temp/T/editors_trial/harness/ui/<slug>/` that imports the
  editor's package from the repo and point the driver at that.
- Keep the server running until the screenshot is taken; kill it afterwards
  (`pkill -f <unique port>` or kill the recorded PID). Do not leave stray
  servers.
- Use the port assigned to you. Do not use 5199, 9094, 9096.
- If the editor simply cannot be hosted (documented blocker), say so
  plainly with the exact error — do not fake a screenshot.
- Prefer a **tall** screenshot that shows the whole first page of the
  document (viewport `1440x1400` or taller) so the reader can compare it
  against Word's page images.

## Reporting back

Report, in plain text:

1. **How it was hosted** — the exact command, the URL, and the exact
   `shot.mjs` invocation you used.
2. **The screenshot path** and whether the document actually rendered
   (paste the JSON's `title`, any `pageErrors`, and the last ~10 console
   lines).
3. **What the editor's UI shows** — be concrete and specific: which of
   these appear in the editor's rendering, and which do not:
   - the blue "fixture image" picture
   - the chart (bar chart, blue bars, legend, axis labels)
   - the SmartArt / diagram band (Word draws nothing there — a blank band)
   - the `mc:AlternateContent` text box (Word shows "Text box content")
   - the OLE object (blue rectangle)
   - the OMML equation (Word draws it as a vector outline)
   - the `w14:textOutline` run (Word draws it as a vector outline)
   - the footnote / endnote / comment markers
   - tracked changes (insert/delete) markup
   - the table
4. **How it differs from Word's rendering of the same file** — concrete
   differences, not adjectives.
5. **Any blocker**, with the exact error text.
