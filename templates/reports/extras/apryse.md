# Apryse WebViewer

## What the driver runs

`build/score_all.py` measures Apryse WebViewer from `out/apryse`. `build/run_all.sh` runs `harness/apryse`: the published npm package `@pdftron/webviewer@{{ver.npm.apryse}}`, opened with `enableOfficeEditing` (the DOCX Editor) in Chromium, exported with `getFileData({ downloadType: 'office' })`. This note does not publish a new round-trip percentage for that output.

## What it is

Apryse WebViewer is a closed-source JavaScript document SDK. Its DOCX Editor opens a Word file for editing in the browser, with Apryse's own office engine running as WebAssembly, and saves it back as DOCX. It is the only commercial, closed-source editor in the trial's round-trip lanes; it was measured with a trial license key.

**Who makes it.** Apryse Software Inc., formerly PDFTron, sells document SDKs to software developers — WebViewer, and PDF, Office and CAD SDKs — and the Xodo apps to end users. Its company page names Thoma Bravo and Silversmith Capital Partners as investors ([apryse.com/company](https://apryse.com/company), read 2026-11-01).

**No affiliation.** This benchmark is independent. It is not affiliated with, sponsored by, or endorsed by Apryse, or by any other vendor it measures. Apryse WebViewer was measured from the published npm package with a trial license key; the watermark that key stamps into every saved file is labelled in the results, not removed. Apryse, WebViewer, PDFTron and Xodo are trademarks of their owner.

## Trivia

The npm scope is still `@pdftron`, the company's former name, and so is the host the SDK calls when it starts (`pws-collect.pdftron.com`). A file it saves names its writer in `docProps/app.xml` as "Apryse DOCX Editor". With a trial key, every saved file carries a watermark picture named `trn_d_stamp`. The installed package is 179 MB.
