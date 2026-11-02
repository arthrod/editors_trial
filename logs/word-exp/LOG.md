# Word vs bomb packages: what Word protects against, and what it does not

Started 2026-10-31 by Claude for Arthur. This is an experiment journal: append entries; don't rewrite earlier ones.

## Question

For each hostile package in `docs/bomb_prevention.md`, plus the gaps found while reviewing it (element flood,
depth between 256 and 600, DOCTYPE handling, network beacons), what does Microsoft Word do with it when opened
and exported to PDF? Where Word refuses or neutralises a shape, jubarte can copy Word. Where Word itself is
hurt by it (hangs, huge memory, fetches), Word gives no protection, and jubarte must bring its own.

## Setup

- Machine: macOS (Darwin 27.0.0), 24 GiB RAM. The grok, empryo and pi agents were building in other worktrees
  during the runs, so timings carry CPU noise.
- Word: Microsoft Word for Mac, driven only through `neurotic_docx_bench/scripts/word_pdf.py`, one fixture per
  run, alone, with `--timeout 300 --force --log`.
- Watchdog: `scripts/word_watchdog.sh` with `WD_MAX=300` on that run's own log. Before starting, 17 stale
  watchdogs from earlier jobs were killed by PID: they watched dead folders and would have killed a busy Word.
- Screen logger: `scripts/word_screen_log.py` runs for the whole experiment into `screen.log`.
- Word RSS: sampled every second into `runs/ID/rss.tsv`. Guard: Word is killed above 10 GB (`rss_guard.log`).
- Network: `scripts/listen.py` logs every connection to `127.0.0.1:18009` in `net.log`. The doc's own B7 targets
  `127.0.0.1:9` and `\\127.0.0.1\share`. Ports below 1024 need root, so B7 cannot be observed; N1-N4 aim the
  same shapes at 18009.
- Canary: `canary.txt` holds `CANARY_SECRET_7f3a`; B5's external entity points at it. Its atime is recorded,
  but APFS atime is not a reliable read signal; the PDF text is the real check.
- Zip-slip: after each run, a search under the experiment dir, `/tmp` and Word's container for
  `pwned-editors-trial*` newer than the run's start marker.
- jubarte: binary `jubarte-loop/bin/jubarte-rel017` (0.16.0+6bf2efb43), runs in `results_jubarte.tsv`
  under `run_guard.sh` (killed above 6 GB RSS or 300 s).

## Fixtures (`scripts/build.py`, `scripts/build_net.py`)

| id | shape |
| --- | --- |
| C0_control | one paragraph `BODY_OK`; harness check |
| B1..B10 | the doc's packages, built by `editors_trial/build/make_bombs.py` unchanged (canary = `canary.txt`) |
| E1/E2/E3/E4_flood | valid body of N MiB of one-run paragraphs: 1, 8, 60, 70 MiB inflated (4 KB to 215 KB zipped) |
| D_sdt200/300/600 | `w:sdt` chains 200/300/600 deep, plus `BODY_OK` |
| D_tbl60/200/300 | nested tables 60/200/300 deep (Word's documented table nesting limit is far lower) |
| X1_doctype | `<!DOCTYPE w:document>`, no internal subset |
| X2_entity | internal entity `a` = `EXPANDED`, used as `ENT[&a;]` |
| X3_subset_gt | internal entity whose value holds a `<w:p>…SMUGGLED…</w:p>` (a `>` inside the subset) |
| N1_template | `w:attachedTemplate` → `http://127.0.0.1:18009/N1_template.dotm` |
| N2_linked_image | `a:blip r:link` → `http://127.0.0.1:18009/N2_image.png` |
| N3_includepicture | `INCLUDEPICTURE "http://127.0.0.1:18009/N3_field.png" \d`, cached result `FIELD_CACHE` |
| N4_subdoc | `w:subDoc` → `http://127.0.0.1:18009/N4_sub.docx` |

## Verdict words

- **CLEAN**: PDF written, no Word dialog. Only CLEAN passes (bench rule).
- **ALERT**: Word showed a dialog (repair prompt, unreadable content, error). The text is quoted.
- **CRASH** / **HANG**: Word died, or the watchdog or timeout had to end it.
- Peak RSS and seconds are reported beside each verdict.

## Hypotheses (written before the runs)

- H1: Word refuses B1-B4 (size, entries, attributes, depth), each with a dialog.
- H2: Word refuses any DOCTYPE (X1-X3, B5): its parsers prohibit DTDs.
- H3: Word opens element floods (E*) but slowly, with large memory; E3/E4 may exceed 300 s.
- H4: Word fetches at least one of N1-N4 (remote template, linked picture), so Word is no network shield.
- H5: B6 zip-slip: Word refuses the package or ignores the entry; no file is written outside.

## Runs

(entries are appended below as the runs finish)

### 2026-10-31 20:27: D_tbl60 wedges Word; D_tbl200 voided as a cascade

- D_tbl60 (948 bytes; tables nested 60 deep, one paragraph per level) never finished.
  - word_pdf.py gave up after 378 s (exit 1).
  - Word (pid 79914, started 20:18) stayed at ~100% CPU at a flat 175 MB RSS, not answering Apple events.
- The watchdog waits on a busy Word until WD_MAX (300 s) of log silence, and each run restarts its own
  watchdog, so the wedged Word survived into the next runs.
- D_tbl200 (exit 2 after 106 s) therefore ran against the wedged Word. It is VOID (cascade) and will be rerun
  alone with a fresh Word.
- D_tbl300 had just started against the same Word. Killed Word by PID (kill -9 79914) at 20:27 so D_tbl300
  gets a fresh Word.
- Finding (to confirm on a rerun): a sub-1 KB valid docx with 60-deep nested tables pins Word's CPU
  indefinitely. Word offers no protection against nesting-depth CPU bombs. It is itself the victim.
- Harness fix for the reruns: each run kills any Word left over from the previous run before it starts, so
  one wedge cannot cascade.

### 2026-10-31 20:30: jubarte 0.16.0+6bf2efb43 on all 28 fixtures

- Binary `<jubarte-loop>/bin/jubarte-rel017`, version string `jubarte 0.16.0+6bf2efb43`.
- Driver: `scripts/run_jubarte.sh` for every fixture. Each id ran `read`, `read --no-page-markers`, and `validate`, with the script's 6 GB / 300 s guard.
- `results_jubarte.tsv` held two copies of the six depth fixtures. The exits and the error text matched. The RSS samples differed by a few MB. The file now has one row per command, 84 data rows.
- The listener on `127.0.0.1:18009` was already up. `net.log` stayed empty. No `pwned-editors-trial` file appeared under the experiment directory or `/tmp`.
- `read` refuses B1, B2, B3, and B4. B5, X1, X2, and X3 exit 0. B5's view keeps `&lol6;&xxe;&canary;`. X2's view keeps `ENT[&a;]`. X3's view is `BODY_OK` and does not contain the smuggled paragraph. `validate` also exits 0 on those four.
- `read` of a 200-deep `w:sdt` writes `DEEP_LEAF`. Layout warns that the part nests deeper than 256. `validate` refuses that file with the 256 message. `read` refuses 300-deep and 600-deep `w:sdt`, and 200-deep and 300-deep tables, with "XML nesting too deep". A 60-deep table is read and the leaf is in the view.
- B1 `read` peaked at 698 MB and `read --no-page-markers` peaked at 2 MB. Both print the part cap. E4 `read` peaked at 4419 MB before the same cap. E4 without page markers peaked at 2 MB.
- E3 was not killed. Both reads exited 0. Peaks were 5483 MB and 5604 MB. Both flood markers are in the view.
- B6 `read` writes the body and warns on the unsafe entry name. `validate` refuses that name. B8 and B10 follow the same split: `read` writes the body, `validate` reports the defect. N3's view contains the field instruction and `FIELD_CACHE`. N1, N2, and N4 show the body only.

### 2026-10-31 20:50: results through E2 (each fixture alone, fresh Word since B6)

| id | Word verdict | secs | Word peak RSS | notes |
| --- | --- | --- | --- | --- |
| C0_control | CLEAN, 1 p | 10 | 506 MB | harness ok |
| X1_doctype | REFUSED: "Word experienced an error trying to open the file." | 17 | 1.5 GB | bare DOCTYPE, no subset |
| X2_entity | REFUSED (same) | 16 | 470 MB | |
| X3_subset_gt | REFUSED (same) | 17 | 467 MB | |
| B5 | REFUSED (same) | 15 | 470 MB | entity bomb + XXE; canary not read into any output |
| B1 | CLEAN, 1 p | 7 | 711 MB | 66 MiB `w:t` of spaces |
| B2 | CLEAN, body present | 7 | 460 MB | 25,000 entries |
| B3 | REFUSED (same error) | 23 | 615 MB | 500k attributes |
| B4 | REFUSED (same error) | 16 | 511 MB | 5000 sdt + 250 tbl |
| D_sdt200/300/600 | CLEAN, leaf present | 7-10 | 559-619 MB | |
| D_tbl60 | WEDGED: 100% CPU, flat 175 MB, no Apple events for 9 min | 378 (driver gave up) | | see 20:27 entry |
| D_tbl200, D_tbl300 | VOID (cascade from the wedged Word) | | | rerun alone at the end |
| B6 | ALERT: "Word found unreadable content … Do you want to recover the contents" (driver answers No, so FAIL) | 56 | 440 MB | zip-slip entry; no slipped file found anywhere |
| B7 | CLEAN, 1 p | 9 | 501 MB | port 9 / UNC: not observable without root |
| B8 | REFUSED: "Word experienced an error trying to open the file." | 18 | 457 MB | javascript: link + altChunk HTML |
| B9 | CLEAN, **77 pages** | 7 | 545 MB | gridSpan 1e6 + 2000 field begins + 60k sources |
| B10 | ALERT: "unreadable content … recover" | 10 | 473 MB | corrupt styles/comments/png |
| N1_template | **CLEAN, and Word FETCHED it**: OPTIONS /, HEAD, OPTIONS, GET /N1_template.dotm | 6 | 515 MB | no prompt |
| N2_linked_image | **CLEAN, and Word FETCHED it 8 times** (UAs: "Microsoft Office Word/16.115", "ms-office; MSOffice 16", CFNetwork) | 7 | 488 MB | no prompt: a web beacon |
| N3_includepicture | CLEAN, cached result shown, **no fetch** | 7 | 502 MB | field not updated on open |
| N4_subdoc | **CLEAN; HEAD /N4_sub.docx** ("Microsoft Office Existence Discovery") | 7 | 489 MB | existence probe, no GET |
| E1_flood1 | CLEAN, 1,187 pages | 15 | 765 MB | 4 KB zipped |
| E2_flood8 | CLEAN, **9,490 pages** | 89 | **2.36 GB** | 25 KB zipped |

Readings:
- Word is a **network beacon**: a remote template (N1), a linked picture (N2) and a subdocument (N4) all hit
  the listener on open, silently, with no prompt; the file still counts CLEAN. jubarte has no network code on any
  document path, so this is one place jubarte is strictly safer than Word.
- Word **refuses every DOCTYPE** (X1-X3, B5), attribute floods (B3), and B4. jubarte must refuse a DOCTYPE too
  (#2015).
- Word gives **no element-flood protection**: E2's 25 KB file costs it 89 s and 2.4 GB. E3/E4 are pending.
- A 948-byte 60-deep table nest **wedges Word** (D_tbl60; to confirm on the rerun). jubarte reads the same
  file in 1 s at 4 MB.

### 2026-10-31 21:00: E5/E6 built (cap edges); fixtures rebuilt as a side effect

- `scripts/build_cap.py` adds E5_atcap (666,600 paragraphs: 1,999,817 elements, just inside the 2,000,000 default budget of #2014, 67 KB zipped) and E6_overcap (667,000 paragraphs, just outside it).
- Importing `build.py` ran its `main()`, which rebuilt every fixture from the same code. The content is unchanged, but the zip timestamps changed. The Word run in progress (E3) works on its own copy in `runs/E3_flood60/in`, so it was unaffected.
- Word on E3_flood60 at 20:53: still not finished after 401 s at 2.6 GB RSS. word_pdf.py is in recovery pass 2.

### 2026-10-31 21:15: X4/X5 built, the DOCTYPE scope question

- The security branch refuses a DOCTYPE in every XML part. That breaks `tests/inspect_paragraphs.rs::summary_reads_only_wordprocessingml_parts_for_revisions` (from 2d3f5cd4c). The test holds that a DTD inside a `customXml` data item must not fail the summary.
- Word's own behaviour decides which side is right:
  - X4_dtd_customxml: a valid body, plus `customXml/item1.xml` related from the document, holding `<!DOCTYPE vendor [<!ENTITY v "EXPANDED">]>`.
  - X5_dtd_styles: the same DOCTYPE in `word/styles.xml`.
- Hypothesis H6: Word refuses X5, as it refused X1–X3. For X4 there is no prior; custom XML is a data store that Word may skip.
- These run after the main loop, alone, followed by the D_tbl60/200/300 reruns.

### 2026-10-31 21:45: E3 fails in Word; loop stopped before E4

- E3_flood60 (60 MiB of paragraphs, 184 KB zipped): word_pdf.py gave up after 1,641 s (exit 1), with Word at 6.2 GB peak RSS and recovery passes timing out. Under the bench's 5-minute rule this is a Word FAILURE (hang).
- The main loop was stopped during E4, and the E4 Word (pid 33952) was killed by PID. E4 will run last, alone. The probes that decide code, X4 and X5, go first, then the D_tbl reruns.

### 2026-10-31 21:27: X4, X4c, X5: Word refuses a DTD in any XML part

| id | Word verdict | secs | peak RSS |
| --- | --- | --- | --- |
| X4_dtd_customxml (first run) | VOID: driver preflight could not count open documents (Word just relaunched after the E4 kill) | 38 | |
| X4_dtd_customxml (rerun, alone) | ALERT: "Word found unreadable content … recover?", then, after No, "Word experienced an error trying to open the file." | 10 | 464 MB |
| X4c_customxml_control (X4 without the DOCTYPE) | CLEAN, 1 p, BODY_OK | 7 | 514 MB |
| X5_dtd_styles | ALERT: unreadable content (same) | 11 | 470 MB |

- H6 is confirmed, and extended: Word refuses a DOCTYPE in `customXml/item1.xml`, a data part, as well as in `word/styles.xml`. The control isolates the DOCTYPE as the cause.
- Consequence for jubarte: refusing a DOCTYPE in every XML part is Word-faithful. `tests/inspect_paragraphs.rs::summary_reads_only_wordprocessingml_parts_for_revisions` (2d3f5cd4c), which required jubarte to read past one in customXml, encoded a tolerance Word does not have. It is updated to the refusal and cites this entry.

## 2026-10-31 22:30 — rerun on the fix binary (a91b0e8da), all 33 fixtures

- results_jubarte_after.tsv (cols: id, cmd, exit, peak MB, s, msg). `read`/`validate` refuse B1-B5, X1-X3, X4 (customXml DTD),
  X5 (styles DTD), D_sdt300/600, D_tbl200/300, E3, E4 (part cap), E6 (2,000,000 elements). X4c (no DTD) reads, validates, compares.
  E5 (just under the cap) is admitted: read 2224 MB / 30 s, read --no-page-markers 2917 MB, validate 945 MB.
- `compare` is the gap. B1 (66 MiB of spaces, 4 elements; compare budget 512 MiB/part) passed 6 GB in 4 s. E5 and E6 ran > 300 s at ~6 GB.
  N4 (w:subDoc) panicked: exit 101 at src/comparer/atomize.rs:312. Old binary (results_jubarte_before_compare.tsv): B1 > 300 s at 4.7 GB,
  N4 exit 101, E5 > 6 GB, E6 > 300 s; X1/X4/X5 compared (exit 0), now refused. All pre-existing; none came from the fix.
- cmp_scale/ (one side vs C0): 1 MiB spaces in one w:t 3914 MB / 3.5 s; 1 MiB of words 2082 MB / 2.2 s; 4 MiB spaces 8964 MB / 18 s;
  4 MiB words 6565 MB / 12.6 s. About 2-4 KB per character.
- calib/units_count.py over 6,645 real docs (bench + tests): story characters + story elements, max 925,884 (98bf redline),
  max original 557,534.
- customXml also panics the atomizer in compare (body, header, footnote): tests/m_cli_no_panic.rs.

## 2026-10-31 22:35 — Word queue (b8osdomiy)

- D_tbl60, D_tbl200, D_tbl300: AppleEvent timed out at ~375 s, 500 MB. D_tbl60 wedged Word before too: second failure, skipped.
- E5_atcap: CLEAN, 25,639 pages, 237 s, 3909 MB, FLOOD_START/FLOOD_END both rendered.

### 2026-11-01 23:50: E6 in Word, twice

- Run after another session's Word and bench jobs ended (load 2.3, Word idle at 0% CPU, no driver). `run_word.sh E6_overcap`, twice, one after the other.
- E6_overcap (667,000 paragraphs, 2,001,017 elements, 67 KB zipped; rebuilt with `scripts/build_cap.py`): exit 0 both times, 218 s and 220 s, 25,654 pages, both flood markers, peaks 5,119 MB and 5,563 MB. No dialog; the "crash reporters:" alert line is the empty header (no reports). CLEAN, reproduced.
- `net.log` was missing in the experiment dir during these runs, so the network column (0) was not observed. E6 has no external reference, so nothing was expected there.
- Copies of both run folders are in `runs/E6_overcap_run1` and `run2` (PDF and input left out).

### 2026-11-02: jubarte 0.14.0 (Report D1's binary) on all 33 fixtures, twice (#69)

- `JUBARTE_BIN=/tmp/jubarte-redlines-target/release/jubarte` (`jubarte 0.14.0`), `run_jubarte_bin.sh` per fixture (read, read --no-page-markers, validate, compare vs C0; 6 GB / 300 s guard), fixtures rebuilt with `build.py`, `build_cap.py`, `build_net.py`, `build_x4.py`, `build_x4c.py`.
- `results_jubarte_d1_0140.tsv` and `results_jubarte_d1_0140_run2.tsv`: 132 lines each; every exit code (kills included) identical across the two runs.
- Killed at 6 GB: E3 read and read --no-page-markers; E4 read; compare on B1, E3, E4, E5, E6. N4 compare panics (exit 101). E3 validate exits 0 at 2,216 MB.
- The earlier entries (0.16.0+6bf2efb43 interim, 0.16.0+c995f2d46.dirty "final") are dev builds and are not published. Report D1's table is generated from the first run by `build/wordexp_table.py`.
