# Report D — Safety, Resource Bombs and Hostile Input (2026)

## TL;DR

No editor is safe on every package. Safe here means the weapon is not in a finished document and the process did not hang or run out of stack. A named ceiling is stronger than a bare refusal. A bare refusal is stronger than a hang. Keeping the weapon is not safe. Word was not opened in the seatbelt matrix. A separate Word run is in `Report D2 - What Word Protects Against (2026).md`, final since 2026-10-31; its results are copied at the end of this report.

Packages: B1 decompression, B2 entry flood, B3 attributes, B4 deep nesting, B5 entities, B6 zip-slip, B7 external relationships, B8 active content, B9 layout bomb, B10 corrupt parts.

- **Plate.** Ceilings on B1, B2, and B4. Cleaned B7. Did not finish B3 inside the sandbox's 30-second CPU budget. Refused B5, B6, B8, and B10 with no named ceiling. Kept B9.
- **eigenpal store.** Ceilings on B1, B2, and B4. Cleaned B3. Refused B5 (document type), B6 (bad name), and B10. Kept B7, B8, and B9.
- **eigenpal editor.** Ceilings on B1 (compression ratio), B2, and B4. Cleaned B3. Refused B5, B6, and B10 without naming a ceiling or the inner cause. Kept B7, B8, and B9.
- **Folio model and Folio editor.** Same row. Ceilings on B1, B2, and B4. Cleaned B3. Refused B5, B6 (unsafe entry path), and B10. Kept B7, B8, and B9.
- **wordcraft.** Ceilings on B2, B3 (attributes), and B4. Refused B5. Cleaned B6, B7, and B10. Kept B1. Kept B8 because the script marker is still in the package. Kept B9 because the fields and the bibliography remain. The written grid span is 63.
- **Fidus Writer.** Ceiling on B4 (nested tags). Cleaned B2, B3, B6, B7, B8, B9, and B10. Refused B5. Kept B1.
- **GenOffice.** Ceiling on B2 only. Cleaned B3. Refused B10. Kept B1, B4, B5, B6, B7, B8, and B9. The B5 package it wrote is still the unexpanded entity declaration.
- **SuperDoc.** No ceiling. Refused B1, B2, B3, B5, and B10 with no named cap. Kept B4, B6, B7, B8, and B9.
- **docs.plus.** Cleaned B1, B2, B3, B6, B7, and B8. Refused B5 and B10. Ran out of stack on B4. Kept B9.
- **canvas-editor.** Cleaned B2, B5, B6, B7, B8, and B10. Hung on B1, B3, and B9. Kept B4.
- **LibreOffice.** Cleaned B1, B2, B6, B7, B8, B9, and B10. Hung on B3. Kept B4 (the leaf is still there). On B5 it wrote nothing and exited 0. That is a failed load, not a cleaned file.
- **office-open.** Cleaned B3. Refused B5. Ran out of stack on B4. Kept B1, B2, B6, B7, B8, B9, and B10.
- **Docen.** Cleaned B3. Refused B5. Ran out of stack on B4 and B9. Kept B1, B2, B6, B7, B8, and B10.
- **Docxodus.** Ceilings on B1 (compression ratio) and B4 (128 levels of depth). Cleaned B3. Refused B5 (document type declaration). Kept B2, B6, B7, B8, B9, and B10.
- **Apryse WebViewer.** No ceiling. Cleaned B1, B2, B3, and B6. Hung on B4, B5, and B9: each ran past the sandbox's 40-second wall clock, in both passes. Kept B7, B8, and B10.
- **Google Docs.** Not in the seatbelt matrix. Saved exports of B2, B6, B7, B8, and B10 contain only the body sentence. B1, B3, B4, B5, and B9 produced no file. Those five imports fully failed, and no ceiling was named. Grade 0.70.

Jubarte is not in this list. Its grade on the same scale is 0.65, from jubarte 0.14.0 in `Report D1 - Jubarte on the Hostile Packages (2026).md`. Report D2 is the Word run, final since 2026-10-31; its results are copied at the end of this report.

## Grades

The grade is a float from 0 to 1. 1 is a named ceiling that refuses the package. 0 is an unsafe result: the weapon is still in the output, the run does not finish, or the call stack runs out. The grade of an editor is the mean of its ten packages. It is not the catch bit. LibreOffice on the entity package scores 0.4, not 1, because nothing was written and the process exited 0.

| Level | Weight |
| --- | --- |
| bounded-refusal | 1.0 |
| sanitation | 0.8 |
| erroring | 0.6 |
| bounded-delivery | 0.5 |
| failed-load-exit-zero | 0.4 |
| unexpanded-kept | 0.3 |
| not-in-view | 0.3 |
| stack-exhaustion, hang, crash, leak, preserved | 0.0 |

Sanitation is safe output without a declared ceiling, so it is not 1. A bare refusal is safer than keeping the weapon and weaker than a ceiling, so it is 0.6. A mean hides a bad package. The unsafe packages are named beside the grade.

| Editor | Grade | Still unsafe |
| --- | --- | --- |
| Fidus Writer | {{bomb.fidus.grade:.2f}} | Keeps the decompression bomb. |
| Google Docs | 0.70 | Five imports produced no file and named no ceiling. No saved file keeps a weapon. |
| Plate | {{bomb.plate.grade:.2f}} | Does not finish the attributes. Keeps the layout bomb. |
| docs.plus | {{bomb.docsplus.grade:.2f}} | Stack on the deep nest. Keeps the layout bomb. |
| LibreOffice | {{bomb.lo_baseline.grade:.2f}} | Hangs on the attributes. Keeps the deep nest. |
| wordcraft | {{bomb.wordcraft.grade:.2f}} | Keeps the decompression bomb, the script, and the layout bomb. |
| eigenpal store | {{bomb.eigenpal.grade:.2f}} | Keeps external relationships, the script, and the layout bomb. |
| eigenpal editor | {{bomb.eigenpal-editor.grade:.2f}} | Same three kept. The entity, zip-slip, and corrupt refusals name no ceiling. |
| Folio model | {{bomb.folio.grade:.2f}} | Keeps external relationships, the script, and the layout bomb. |
| Folio editor | {{bomb.folio-editor.grade:.2f}} | Same as the model. |
| canvas-editor | {{bomb.canvas.grade:.2f}} | Hangs on the decompression bomb, the attributes, and the layout bomb. Keeps the deep nest. |
| Docxodus | {{bomb.docxodus.grade:.2f}} | Ceilings on the decompression bomb and the deep nest. Keeps six packages. |
| Apryse WebViewer | {{bomb.apryse.grade:.2f}} | No ceiling. Hangs on the deep nest, the entities, and the layout bomb. Keeps external relationships, the script, and the corrupt parts. |
| SuperDoc | {{bomb.superdoc.grade:.2f}} | No ceiling. Keeps the deep nest, zip-slip, external relationships, the script, and the layout bomb. |
| GenOffice | {{bomb.genoffice.grade:.2f}} | Ceiling on the entry flood only. Keeps the other resource bombs. |
| Docen | {{bomb.docen.grade:.2f}} | Cleans the attributes. Stack on the deep nest and the layout bomb. |
| office-open | {{bomb.officeopen.grade:.2f}} | Cleans the attributes. Stack on the deep nest. Keeps seven packages. |
| jubarte 0.14.0 | 0.65 | Jubarte report. Entities stay in the view. Zip-slip, external relationships, and corrupt parts are not refusals. |

Fidus Writer ranks above Plate because seven cleaned packages outweigh three ceilings under these weights. Plate is the stronger ceiling set. Google Docs ranks above Plate, 0.70 to {{bomb.plate.grade:.2f}}, and that order is the weights too. Plate has three ceilings, keeps the layout bomb, and did not finish the attribute package inside the CPU budget. Google Docs has five cleaned exports and five refusals with no named ceiling, and no saved file keeps a weapon. If a named ceiling were the only non-zero weight, Plate, eigenpal, and Folio would rank above Fidus Writer, and above Google Docs. The weights are a summary, not a second measurement. The Google Docs files are in the section after the kept payloads.

## Unsandboxed refusal

The fenced log below is what `build/run_bombs.py` prints when it is started with no sandbox flag. That command does not build a package and does not open one. It is the unsandboxed entry. Sentences inside the fence that say the suite was not executed describe that entry. They do not describe the sandboxed matrix later in this report.

Fidelity and safety are separate fields. Preserving a hostile payload is not the same single result as a crash. Word was not opened by that command. An NTLM credential leak cannot be measured on macOS.

```
platform: macOS-27.0.1-arm64-arm-64bit-Mach-O
not-run: resource.setrlimit(RLIMIT_AS) raised ValueError: current limit exceeds maximum limit. platform=macOS-27.0.1-arm64-arm-64bit-Mach-O RLIMIT_AS soft=9223372036854775807 hard=9223372036854775807. The hostile suite was not executed.
scheduled: run later, sandboxed. This session did not build or open a hostile package.
taxonomy: preserving a hostile payload is not the same single result as a crash. This run recorded neither, because no vector was executed.
defect_survival.py classifies structural defects in outputs of fixture/complex_broken.docx. It is not this suite, and it did not run B1-B10.
reference Word fidelity: not-run safety: not-run Word was not opened on a hostile package. not-run: resource.setrlimit(RLIMIT_AS) raised ValueError: current limit exceeds maximum limit. platform=macOS-27.0.1-arm64-arm-64bit-Mach-O RLIMIT_AS soft=9223372036854775807 hard=9223372036854775807. The hostile suite was not executed.
reference LibreOffice fidelity: not-run safety: not-run LibreOffice was not opened on a hostile package. not-run: resource.setrlimit(RLIMIT_AS) raised ValueError: current limit exceeds maximum limit. platform=macOS-27.0.1-arm64-arm-64bit-Mach-O RLIMIT_AS soft=9223372036854775807 hard=9223372036854775807. The hostile suite was not executed.
B1 SKIP not-run: Zip decompression bomb (ratio / total size). fidelity: not-run safety: not-run not-run: resource.setrlimit(RLIMIT_AS) raised ValueError: current limit exceeds maximum limit. platform=macOS-27.0.1-arm64-arm-64bit-Mach-O RLIMIT_AS soft=9223372036854775807 hard=9223372036854775807. The hostile suite was not executed.
B2 SKIP not-run: Zip entry flood. fidelity: not-run safety: not-run not-run: resource.setrlimit(RLIMIT_AS) raised ValueError: current limit exceeds maximum limit. platform=macOS-27.0.1-arm64-arm-64bit-Mach-O RLIMIT_AS soft=9223372036854775807 hard=9223372036854775807. The hostile suite was not executed.
B3 SKIP not-run: XML attribute compression bomb. fidelity: not-run safety: not-run not-run: resource.setrlimit(RLIMIT_AS) raised ValueError: current limit exceeds maximum limit. platform=macOS-27.0.1-arm64-arm-64bit-Mach-O RLIMIT_AS soft=9223372036854775807 hard=9223372036854775807. The hostile suite was not executed.
B4 SKIP not-run: Deep nesting of w:sdt and w:tbl. fidelity: not-run safety: not-run not-run: resource.setrlimit(RLIMIT_AS) raised ValueError: current limit exceeds maximum limit. platform=macOS-27.0.1-arm64-arm-64bit-Mach-O RLIMIT_AS soft=9223372036854775807 hard=9223372036854775807. The hostile suite was not executed.
B5 SKIP not-run: Billion Laughs and XXE. fidelity: not-run safety: not-run not-run: resource.setrlimit(RLIMIT_AS) raised ValueError: current limit exceeds maximum limit. platform=macOS-27.0.1-arm64-arm-64bit-Mach-O RLIMIT_AS soft=9223372036854775807 hard=9223372036854775807. The hostile suite was not executed.
B6 SKIP not-run: Zip-Slip path traversal. fidelity: not-run safety: not-run not-run: resource.setrlimit(RLIMIT_AS) raised ValueError: current limit exceeds maximum limit. platform=macOS-27.0.1-arm64-arm-64bit-Mach-O RLIMIT_AS soft=9223372036854775807 hard=9223372036854775807. The hostile suite was not executed.
B7 SKIP not-run: SSRF / NTLM credential leak via external relationships. NTLM credential leak cannot be measured on macOS. fidelity: not-run safety: not-run not-run: resource.setrlimit(RLIMIT_AS) raised ValueError: current limit exceeds maximum limit. platform=macOS-27.0.1-arm64-arm-64bit-Mach-O RLIMIT_AS soft=9223372036854775807 hard=9223372036854775807. The hostile suite was not executed.
B8 SKIP not-run: XSS / active content. fidelity: not-run safety: not-run not-run: resource.setrlimit(RLIMIT_AS) raised ValueError: current limit exceeds maximum limit. platform=macOS-27.0.1-arm64-arm-64bit-Mach-O RLIMIT_AS soft=9223372036854775807 hard=9223372036854775807. The hostile suite was not executed.
B9 SKIP not-run: Layout and combinatorial bombs (gridSpan, fields, bibliography). fidelity: not-run safety: not-run not-run: resource.setrlimit(RLIMIT_AS) raised ValueError: current limit exceeds maximum limit. platform=macOS-27.0.1-arm64-arm-64bit-Mach-O RLIMIT_AS soft=9223372036854775807 hard=9223372036854775807. The hostile suite was not executed.
B10 SKIP not-run: Corrupt secondary parts and bad PNG magic. fidelity: not-run safety: not-run not-run: resource.setrlimit(RLIMIT_AS) raised ValueError: current limit exceeds maximum limit. platform=macOS-27.0.1-arm64-arm-64bit-Mach-O RLIMIT_AS soft=9223372036854775807 hard=9223372036854775807. The hostile suite was not executed.
```

## Sandboxed matrix

A later run did open the ten packages. LibreOffice ran in the image `editors-trial-bombs:local`, one container per package, with no network. The editors are macOS binaries, so they ran under seatbelt on this machine, not in that Linux container. External network stayed denied. Localhost and the unix socket inside the work directory were allowed, because several editors bind those themselves. Each editor used that project's own documented import and export. Plate used `BaseEditorKit`, `retainSource`, and the default reject policy, and a refused import wrote no second file. canvas-editor did not replace a thrown import with the blank starter document. docs.plus stopped at its own `importDocx` and `exportDocx`.

The full stdout and stderr of every cell are in `logs/bombs`. This report quotes `logs/bombs/scorecard.txt` and `logs/bombs/protection.txt`. `logs/bombs-before-suggested-config` is an earlier matrix whose seatbelt failures are not these editors' results.

Word is not in that matrix. No hash collector was started. A slip onto the host temp directory is denied by the seatbelt, so the only slip that can be observed is one that lands inside the work directory, or file contents that come back in the saved package. The entity package expands one million times, not to a gigabyte, because this Mac cannot cap address space. One deflate member tops out near one thousand to one.

No cell in this matrix carries a `harness-` reason.

## Protection degrees

The safety word `bounded-reject` is not a resource bound. It means the process exited non-zero and the run was not a crash, a hang, or a leak. Calling that word "bounded" is wrong. The protection level is a separate reading of the exit, the fidelity field, and the tool's own words. `caught()` was not changed. A catch is still fidelity refused or dropped, and safety other than crash, hang, or leak. The catch bit is coarser than the levels below. LibreOffice on the entity package is the cell where that bit overstates the result.

These are the levels, from a real ceiling down to no protection.

1. `bounded-refusal`. The tool named a ceiling and rejected the package. No finished document carries the weapon. The process exited with an error. A ceiling is a part size, an entry count, a compression ratio, an element depth, a nest cap, or an attribute cap that the tool's own message names.
2. `bounded-delivery`. A declared cap was applied and a reduced form was written. The hostile value itself is absent. The process survived. This is not a refusal and it is not sanitation. No editor cell in this matrix has this as its primary label. One jubarte cell does. It is in Report D1. Inside this matrix, wordcraft's layout package still has this shape on the span alone, and the cell stays `preserved` because the other weapons remain. That split is below.
3. `sanitation`. The process exited 0, wrote a document, and the weapon is not in it.
4. `erroring`. The process exited with an error and the log does not name a ceiling. A document-type refusal, an undefined entity, a bad name, an unsafe entry path, and an opaque argument rejection are this level. A name policy is not a size ceiling.
5. `stack-exhaustion`. Recursion ran out of call stack. The process exited with an error. That is not a declared ceiling, and it is not `bounded-refusal`.
6. `unexpanded-kept`. The process exited 0 and wrote the raw entity references. It did not expand them. Keeping the references is not sanitation. No editor cell uses this as its primary label. GenOffice on the entity package is `preserved`, and the package it wrote is still the unexpanded declaration. Jubarte's reading of the same package is `unexpanded-kept`, in Report D1.
7. `preserved`. The weapon is still in the output and the process survived. This is no protection against that payload. An unexpanded passthrough is still `preserved` when the primary label says so.
8. `errored-but-preserved`. The process errored and the weapon is still in the output. No cell in this matrix.
9. `hang`. The run did not finish. Not a catch.
10. `crash`. The process died. No cell in this matrix.
11. `leak`. File contents or a slipped file came out. No cell in this matrix.
12. `failed-load-exit-zero`. No document was written and the process still exited 0. This is not sanitation and it is not `erroring`.
13. `not-in-view`. A text view was written and this weapon is not something that view carries. Editors in this matrix write packages, so none of them has this label. It is a jubarte reading, in Report D1.
14. `not-run`. No measurement. Word, and every row of the unsandboxed fence.

Of the {{bomb.cells}} measured cells, {{bomb.tools:w}} editors and LibreOffice across the ten packages, the primary labels are sanitation {{bomb.count.sanitation}}, preserved {{bomb.count.preserved}}, erroring {{bomb.count.erroring}}, bounded-refusal {{bomb.count.bounded-refusal}}, stack-exhaustion {{bomb.count.stack-exhaustion}}, hang {{bomb.count.hang}}, and failed-load-exit-zero {{bomb.count.failed-load-exit-zero}}.

## Measured scorecard

```
{{bomb.scorecard}}
```

## Protection record

```
{{bomb.protection}}
```

## Where the safety word is the wrong name

LibreOffice on the entity package is `failed-load-exit-zero`. soffice said the source file could not be loaded. No cleaned file was written. The process exited 0. The score line says catch yes. That bit overstates the cell. There is no sanitized document.

LibreOffice on the attribute package hung. The leaf of the deep package is still in the written file, so that cell is `preserved`. The other LibreOffice drops are `sanitation`.

`stack-exhaustion`, not a ceiling: office-open on the deep package, Docen on the deep package and on the layout package, docs.plus on the deep package. Fidus Writer on the deep package is the other kind of nest failure: its own message is a maximum on nested tags, so that cell is `bounded-refusal`.

`erroring`, and the log names no ceiling:

- Plate rejected the entity package for a document type declaration, rejected the zip-slip package as a package, failed to decode the active-content package, and rejected the corrupt package as XML that is not UTF-8.
- The eigenpal store named `dtd-forbidden`, `bad-name`, and `parse-error`. `bad-name` is a name policy.
- The eigenpal editor, on the entity package, the zip-slip package, and the corrupt package, rejected the argument. The visible error is `InvalidArgument`, the limit field is unset, and the inner cause is not in the cell log. Do not copy the store's `dtd-forbidden`, `bad-name`, or `parse-error` onto that lane.
- Folio and the Folio editor rejected the entity package and the corrupt package because preflight could not scan the markup, and rejected the zip-slip package for an unsafe entry path. The unsafe path is a name policy. An earlier reading of the Folio zip-slip cell called it a size ceiling. That reading was a stack frame quoting a source line, not the error. The level is `erroring`.
- GenOffice could not parse a styles part on the corrupt package.
- SuperDoc reported unterminated markup on the decompression package. That message names no ceiling. On the attribute package it reported a malformed start tag. The attribute bomb broke the tag. That is not an attribute cap. On the entry flood and the corrupt package it said source loading does not apply. On the entity package it reported no document root.
- office-open and Docen rejected a malformed entity. Fidus Writer rejected an external entity. wordcraft said an entity is not defined. docs.plus said an entity was not found, and on the corrupt package the XML parser rejected a tag.
- Docxodus rejected the entity package's document type declaration (`Xml_DtdIsProhibitedEx`).

`bounded-refusal`, because the tool named the ceiling:

- Plate: part size, entry count, element depth.
- eigenpal store: too-large, too-many-entries, too-deep.
- eigenpal editor: `zip.maxRatio`, `zip.maxEntries`, `xml.maxDepth`.
- Folio and the Folio editor: compression ratio, part count, and a declared depth cap. The depth message is that the part is nested deeper than the cap.
- GenOffice: part count, on the entry flood only.
- Fidus Writer: nested tags, on the deep package.
- Docxodus: `compression_ratio_limit_exceeded` on the decompression bomb, and `xml_depth_limit_exceeded` (128 levels) on the deep package. Its message follows a runtime dump of about 200 KB; the sandbox now writes a child's output to a file so the message is kept.
- wordcraft: entry count, attributes of one element, and element depth. The entry-count line in the protection record says only "named ceiling". The cell log says the limit that was exceeded is the zip entry count. The password retry is wordcraft's own read path, not a second permissive pass.

Plate on the attribute package is `hang`: the run used up the sandbox's 30-second CPU budget before it wrote anything. In the 0.9.0 measurement the same package finished and was `sanitation`. Plate's code was not the cause: the 0.9.0 commit, re-run with the same lockfile on the same quiet machine, also did not finish. The cell sits at the edge of the budget. wordcraft on that package is the attribute cap.

## Kept payloads

`preserved` means the weapon is still in the written package. GenOffice keeps the original package on the decompression bomb, the deep package, the entity package, zip-slip, the external relationships, the active content, and the layout bomb. On the entity package the written zip still holds the entity declaration and the unexpanded references. The expanded token appears in that declaration. It is not a repeated payload, and it is not a cleaned document. The primary label stays `preserved`.

wordcraft on the active-content package is `preserved` because the script marker is still in the zip. The javascript URL is not in that zip. A partial strip that leaves the script is not sanitation.

wordcraft on the layout package is `preserved` because the field markers and the bibliography sources are still there. The written grid span is 63, not the span in the bomb. That is a cap on the span alone. The cell is not labeled `bounded-delivery`, because the fields and the bibliography survived. No cell in this matrix has `bounded-delivery` as its primary label.

Plate on the external-relationship package is `sanitation`: a source was unavailable and the probe URL is not in the export. Plate on the layout package is `preserved`: the same source-unavailable note did not remove the layout bomb.

Fidus Writer's drops, including the layout package, are `sanitation`. canvas-editor's finished drops are `sanitation`. Its decompression, attribute, and layout cells hung at the wall clock. A hang is not a catch.

Docxodus keeps the entry flood, zip-slip, the external relationships, the active content, the layout bomb, and the corrupt parts. office-open, Docen, and the eigenpal lanes preserve the decompression bomb, the entry flood, zip-slip, the external relationships, and, except where a row above says otherwise, the active content and the layout bomb. Preserving those is no protection.

## Google Docs

Google Docs is not one of the {{bomb.cells}} cells. `Google Docs.app` on this Mac is a Drive launcher. It does not parse a package locally. The imports ran on Google's servers. A file was saved to `~/Downloads` only when the import produced a document. B1, B3, B4, B5, and B9 have no file there. Those five imports fully failed.

The saved files are `~/Downloads/B2.docx`, `B6.docx`, `B7.docx`, `B8.docx`, and `B10.docx`. A second save of the entry flood and of the active-content package has the same part bytes as the first save. The five first saves have the same part bytes as each other. The zip containers differ. Each one is a rewrite: generated styles, settings, numbering, a font table, and a theme. The body is one paragraph, `BOMB_BODY_OK`.

The weapons are absent from those five files.

- B2. No `customXml/p` entries.
- B6. No escaped entry name, no `etc/passwd`, and no `/etc/hosts`.
- B7. No probe URL and no UNC target.
- B8. No `javascript:` target and no script marker. The hyperlink paragraph is gone. The styles part names a hyperlink style. That style is not the weapon.
- B10. No hostile styles prefix, no truncated comments part, and no fake PNG.

That reading is `sanitation`. A finished document, the weapon absent, no named ceiling.

The five failures are fidelity `refused`. No ceiling was written down, because the failure dialog was not copied. The level is `erroring`, not `bounded-refusal`. A missing file does not show whether the server inflated a part or resolved an entity before it failed. It shows that no document was saved.

| Package | What came back | Level | Weight |
| --- | --- | --- | --- |
| B1 decompression | no file, import failed | erroring | 0.6 |
| B2 entry flood | body sentence only | sanitation | 0.8 |
| B3 attributes | no file, import failed | erroring | 0.6 |
| B4 deep nesting | no file, import failed | erroring | 0.6 |
| B5 entities | no file, import failed | erroring | 0.6 |
| B6 zip-slip | body sentence only | sanitation | 0.8 |
| B7 external relationships | body sentence only | sanitation | 0.8 |
| B8 active content | body sentence only | sanitation | 0.8 |
| B9 layout bomb | no file, import failed | erroring | 0.6 |
| B10 corrupt parts | body sentence only | sanitation | 0.8 |

The mean is 7.0 divided by 10, which is 0.70. No local process exit was recorded, so these rows have no harness safety token and no catch bit. Nothing in a saved file is a crash, a hang, or a leak.

## What Microsoft Word protects against

These are the final results of the Word run, from `Report D2 - What Word Protects Against (2026).md` (final since 2026-10-31), which also has the method. They are not the seatbelt matrix: the fenced log above says Word was not opened there, and that is still true of that run. Word was opened separately, one fixture per run, on 33 fixtures: B1–B10 and the controls and probes below. E6 has not been opened in Word.

CLEAN means a PDF was written and no dialog appeared. That is not the protection ladder in this report, so these rows are not turned into a grade.

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

### Conclusions

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
