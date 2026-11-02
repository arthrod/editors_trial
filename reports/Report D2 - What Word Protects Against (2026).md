# Report D2 — What Microsoft Word protects against, and what it does not (2026)

**Status: final (2026-10-31).** Every fixture but E6 was opened in Microsoft
Word alone, one fixture per run. Most were opened once; D_tbl60, D_tbl200,
D_tbl300 and X4 were opened twice. A second run of the rest has not been done.

This report records what Word does with each hostile package: whether it opens
it, warns, refuses, hangs or crashes, how much memory it takes, and whether it
reaches the network. It is the reference the editors in Report D are compared
against when we say a refusal "costs no Word-valid input".

Raw evidence, scripts and the run journal are in
[`logs/word-exp/`](../logs/word-exp/) (`LOG.md`, `results_word.tsv`,
`runs/ID/word.log`, `screen.log`, `net.log`). The hostile fixtures are not
published; the five `scripts/build*.py` rebuild all 33.

## Method

- **Word:** only through `neurotic_docx_bench/scripts/word_pdf.py` (open,
  then export to PDF), one fixture per run, alone, `--timeout 300`.
  - The bench watchdog ran on that run's own log, and `word_screen_log.py`
    recorded every dialog.
  - Word's RSS was sampled every second, with a 10 GB kill guard.
  - Verdict: **CLEAN** = PDF written and no dialog. Anything else is a
    refusal, an alert, a hang or a failure.
  - A file that failed twice was not retried (D_tbl60, D_tbl200).
- **Network:** a listener on `127.0.0.1:18009` logs every connection
  (`net.log`). The doc's B7 aims at `127.0.0.1:9` and `\\127.0.0.1\share`.
  Ports below 1024 need root, so B7 cannot be observed directly; N1–N4 aim
  the same shapes at the listener.
- **Canary:** B5's external entity points at a file holding
  `CANARY_SECRET_7f3a`; the PDF text is checked for it.
- **Fixtures:** B1–B10 are the doc's packages, built by
  `editors_trial/build/make_bombs.py` unchanged. The others are described in
  the table.

## Results

| Fixture | Shape | Word | Word peak RSS |
| --- | --- | --- | --- |
| C0 | one paragraph (control) | CLEAN, 1 page | 506 MB |
| B1 | one `w:t` of 66 MiB of spaces (68 KB zipped) | **CLEAN**, 1 page, 7 s | 711 MB |
| B2 | 25,000 `customXml` parts | **CLEAN** | 460 MB |
| B3 | 500,000 attributes on one `w:p` | **refused**: "Word experienced an error trying to open the file." | 615 MB |
| B4 | 5,000-deep `w:sdt` + 250-deep `w:tbl` | **refused**: same error | 511 MB |
| D_sdt200/300/600 | `w:sdt` chains 200 / 300 / 600 deep | **CLEAN**, leaf text present | 559–619 MB |
| D_tbl60 | nested tables 60 deep (948 bytes) | **hung**, twice (AppleEvent timeout at 375 s) | 509 MB |
| D_tbl200/300 | nested tables 200 / 300 deep | **hung** at 376 s; D_tbl300 crashed Word on an earlier run | 515 MB |
| B5 | billion-laughs entities (10^6) + external entities (`/etc/hosts`, canary) | **refused**: same error; canary absent | 470 MB |
| X1 | a bare `<!DOCTYPE w:document>` | **refused**: same error | 1.5 GB |
| X2 | internal entity used in text | **refused**: same error | 470 MB |
| X3 | internal entity whose value holds a `>` | **refused**: same error | 467 MB |
| X4 | the same DOCTYPE in a `customXml` item | **alert**: unreadable content, then refused | 464 MB |
| X4c | X4 without the DOCTYPE (control) | **CLEAN** | 514 MB |
| X5 | the same DOCTYPE in `styles.xml` | **alert**: unreadable content, then refused | 470 MB |
| B6 | zip-slip entry `../escaped/…` + traversal relationships | **alert**: unreadable content; no slipped file anywhere | 440 MB |
| B7 | external template on `127.0.0.1:9` + UNC subDocument | **CLEAN**, 1 page (not observable without root) | 501 MB |
| B8 | `javascript:` hyperlink + altChunk HTML with script | **refused**: same error | 457 MB |
| B9 | `gridSpan` 1,000,000 + 2,000 field begins + 60,000 sources | **CLEAN**, 77 pages | 545 MB |
| B10 | non-UTF-8 styles, truncated comments, fake PNG | **alert**: unreadable content | 473 MB |
| N1 | remote template → listener | **CLEAN, and fetched it**: OPTIONS, HEAD, GET, no prompt | 515 MB |
| N2 | linked picture (`a:blip r:link`) → listener | **CLEAN, and fetched it 8 times**, no prompt | 488 MB |
| N3 | `INCLUDEPICTURE` → listener | **CLEAN**; no fetch | 502 MB |
| N4 | `w:subDoc` → listener | **CLEAN; HEAD probe** ("Microsoft Office Existence Discovery") | 489 MB |
| E1 | 1 MiB element flood | **CLEAN**, 1,187 pages, 15 s | 765 MB |
| E2 | 8 MiB element flood | **CLEAN**, 9,490 pages, 89 s | 2.36 GB |
| E5 | 1,999,817 elements | **CLEAN**, 25,639 pages, 237 s | 3.9 GB |
| E6 | 2,001,017 elements | not run | |
| E3 | 60 MiB element flood (215 KB zipped) | **failed** after 1,641 s | 6.2 GB |
| E4 | 70 MiB element flood | **failed** after 1,610 s | 7.2 GB |

On E4 the canary file's access time changed during Word's 27-minute run.
E4 references no canary, and Word wrote no PDF; the access is unexplained
and is not counted as a leak.

## Conclusions

1. **Word refuses every DTD, in every part.** A bare `<!DOCTYPE>` (X1), the
   entity bomb (B5), and a DOCTYPE in `styles.xml` (X5) or in a `customXml`
   item (X4) are all refused; X4 without it (X4c) is CLEAN. An editor that
   refuses a DOCTYPE loses no document Word opens.
2. **Word refuses attribute floods and extreme depth** (B3, B4). It still opens
   a 600-deep `w:sdt` chain, so a depth cap below 600 refuses documents Word
   renders.
3. **Word is permissive on size and entries.** It opens a 66 MiB run (B1) in
   7 s and 25,000 parts (B2). A cap on either is the editor's own choice; Word
   sets no lower bound to copy.
4. **Word does not protect itself from element floods or nested tables.** A
   60 or 70 MiB flood made it fail after about 27 minutes at 6–7 GB. A
   948-byte nest of 60 tables hung it twice. 1,999,817 elements (E5) took
   4 minutes and 3.9 GB.
5. **Word is a network beacon.** It fetched a remote template (N1) and a
   linked picture (N2, eight times), and probed a subdocument (N4), with no
   prompt. Opening an untrusted document in Word tells its author that it was
   opened, and from where.
6. **Word's warnings are not a sanitizer.** B6 and B10 raise "unreadable
   content" and offer to recover; B8 (a `javascript:` link and a script in an altChunk) is refused
   outright. Recovery is the user's choice, and the dialog does not say what
   would be kept.
