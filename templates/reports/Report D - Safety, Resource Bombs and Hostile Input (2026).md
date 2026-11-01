# Report D — Safety, Resource Bombs and Hostile Input (2026)

## TL;DR

No editor is safe on every package. Safe here means the weapon is not in a finished document and the process did not hang or run out of stack. A named ceiling is stronger than a bare refusal. A bare refusal is stronger than a hang. Keeping the weapon is not safe. Word was not opened in the seatbelt matrix. A separate Word run is in `Report D2 - What Word Protects Against (2026).md`, final since 2026-10-31; its interim snapshot is copied at the end of this report.

Packages: B1 decompression, B2 entry flood, B3 attributes, B4 deep nesting, B5 entities, B6 zip-slip, B7 external relationships, B8 active content, B9 layout bomb, B10 corrupt parts.

- **Plate.** Ceilings on B1, B2, and B4. Cleaned B3 and B7. Refused B5, B6, B8, and B10 with no named ceiling. Kept B9.
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
- **Docxodus.** Cleaned B3. Ran out of stack on B4. Refused B5 and B10 with no named rule. Kept B1, B2, B6, B7, B8, and B9.
- **Google Docs.** Not in the seatbelt matrix. Saved exports of B2, B6, B7, B8, and B10 contain only the body sentence. B1, B3, B4, B5, and B9 produced no file. Those five imports fully failed, and no ceiling was named. Grade 0.70.

Jubarte is not in this list. Its grade on the same scale is 0.65, from jubarte 0.14.0 in `Report D1 - Jubarte on the Hostile Packages (2026).md`. Report D2 is the Word run, final since 2026-10-31; its interim snapshot is copied at the end of this report. Its jubarte column is 0.16.0, not 0.14.0.

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
| Plate | {{bomb.plate.grade:.2f}} | Keeps the layout bomb. |
| Google Docs | 0.70 | Five imports produced no file and named no ceiling. No saved file keeps a weapon. |
| docs.plus | {{bomb.docsplus.grade:.2f}} | Stack on the deep nest. Keeps the layout bomb. |
| LibreOffice | {{bomb.lo_baseline.grade:.2f}} | Hangs on the attributes. Keeps the deep nest. |
| wordcraft | {{bomb.wordcraft.grade:.2f}} | Keeps the decompression bomb, the script, and the layout bomb. |
| eigenpal store | {{bomb.eigenpal.grade:.2f}} | Keeps external relationships, the script, and the layout bomb. |
| eigenpal editor | {{bomb.eigenpal-editor.grade:.2f}} | Same three kept. The entity, zip-slip, and corrupt refusals name no ceiling. |
| Folio model | {{bomb.folio.grade:.2f}} | Keeps external relationships, the script, and the layout bomb. |
| Folio editor | {{bomb.folio-editor.grade:.2f}} | Same as the model. |
| canvas-editor | {{bomb.canvas.grade:.2f}} | Hangs on the decompression bomb, the attributes, and the layout bomb. Keeps the deep nest. |
| SuperDoc | {{bomb.superdoc.grade:.2f}} | No ceiling. Keeps the deep nest, zip-slip, external relationships, the script, and the layout bomb. |
| GenOffice | {{bomb.genoffice.grade:.2f}} | Ceiling on the entry flood only. Keeps the other resource bombs. |
| Docxodus | {{bomb.docxodus.grade:.2f}} | Cleans the attributes. Stack on the deep nest. Keeps six packages. |
| Docen | {{bomb.docen.grade:.2f}} | Cleans the attributes. Stack on the deep nest and the layout bomb. |
| office-open | {{bomb.officeopen.grade:.2f}} | Cleans the attributes. Stack on the deep nest. Keeps seven packages. |
| jubarte 0.14.0 | 0.65 | Jubarte report. Entities stay in the view. Zip-slip, external relationships, and corrupt parts are not refusals. |

Fidus Writer ranks above Plate because seven cleaned packages outweigh three ceilings under these weights. Plate is the stronger ceiling set. Google Docs also scores 0.70. That tie is the weights. Plate has three ceilings and keeps the layout bomb. Google Docs has five cleaned exports and five refusals with no named ceiling, and no saved file keeps a weapon. If a named ceiling were the only non-zero weight, Plate, eigenpal, and Folio would rank above Fidus Writer, and above Google Docs. The weights are a summary, not a second measurement. The Google Docs files are in the section after the kept payloads.

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

Of the {{bomb.cells}} measured cells, fourteen editors and LibreOffice across the ten packages, the primary labels are sanitation {{bomb.count.sanitation}}, preserved {{bomb.count.preserved}}, erroring {{bomb.count.erroring}}, bounded-refusal {{bomb.count.bounded-refusal}}, stack-exhaustion {{bomb.count.stack-exhaustion}}, hang {{bomb.count.hang}}, and failed-load-exit-zero {{bomb.count.failed-load-exit-zero}}.

## Measured scorecard

```
sandbox: libreoffice in docker, network none, memory 2g, read-only root. editors under seatbelt. External network is denied. Localhost and unix sockets inside the work directory are allowed, because the editors' own tooling binds them. Writes stay in the work directory, plus the canvas vitest config cache. The editors are macOS binaries and were not run inside the Linux container.
taxonomy: preserving a hostile payload is not the same single result as a crash.
reference Word fidelity: not-run safety: not-run Word was not opened. LibreOffice is the comparison.
B7 note: NTLM credential leak was not measured. No hash collector was started. External network and UNC were denied. Localhost was allowed so a tool loopback stub and the 127.0.0.1 probe are not blocked by the seatbelt.
B5 note: the entity bomb expands one million times, not to a gigabyte. This Mac cannot cap address space.
B1 note: one deflate member tops out near one thousand to one. A single member at two thousand five hundred to one is not a real deflate stream.
config: each editor used that project's documented import and export. Plate used BaseEditorKit, retainSource, and the default reject policy, and a refused import wrote no second permissive file. Canvas did not replace a thrown import with the blank starter document. docs.plus stopped at its own importDocx and exportDocx. docen, officeopen and fidus were started with their own tsx.
comparison libreoffice B1 fidelity: dropped safety: ok catch: yes
comparison libreoffice B2 fidelity: dropped safety: ok catch: yes
comparison libreoffice B3 fidelity: refused safety: hang catch: no
comparison libreoffice B4 fidelity: preserved safety: ok catch: no
comparison libreoffice B5 fidelity: refused safety: ok catch: yes
comparison libreoffice B6 fidelity: dropped safety: ok catch: yes
comparison libreoffice B7 fidelity: dropped safety: ok catch: yes
comparison libreoffice B8 fidelity: dropped safety: ok catch: yes
comparison libreoffice B9 fidelity: dropped safety: ok catch: yes
comparison libreoffice B10 fidelity: dropped safety: ok catch: yes
tool plate B1 fidelity: refused safety: bounded-reject catch: yes
tool eigenpal B1 fidelity: refused safety: bounded-reject catch: yes
tool eigenpal-editor B1 fidelity: refused safety: bounded-reject catch: yes
tool folio B1 fidelity: refused safety: bounded-reject catch: yes
tool folio-editor B1 fidelity: refused safety: bounded-reject catch: yes
tool genoffice B1 fidelity: preserved safety: ok catch: no
tool superdoc B1 fidelity: refused safety: bounded-reject catch: yes
tool officeopen B1 fidelity: preserved safety: ok catch: no
tool docen B1 fidelity: preserved safety: ok catch: no
tool fidus B1 fidelity: preserved safety: ok catch: no
tool wordcraft B1 fidelity: preserved safety: ok catch: no
tool canvas B1 fidelity: refused safety: hang catch: no
tool docsplus B1 fidelity: dropped safety: ok catch: yes
tool docxodus B1 fidelity: preserved safety: ok catch: no
tool plate B2 fidelity: refused safety: bounded-reject catch: yes
tool eigenpal B2 fidelity: refused safety: bounded-reject catch: yes
tool eigenpal-editor B2 fidelity: refused safety: bounded-reject catch: yes
tool folio B2 fidelity: refused safety: bounded-reject catch: yes
tool folio-editor B2 fidelity: refused safety: bounded-reject catch: yes
tool genoffice B2 fidelity: refused safety: bounded-reject catch: yes
tool superdoc B2 fidelity: refused safety: bounded-reject catch: yes
tool officeopen B2 fidelity: preserved safety: ok catch: no
tool docen B2 fidelity: preserved safety: ok catch: no
tool fidus B2 fidelity: dropped safety: ok catch: yes
tool wordcraft B2 fidelity: refused safety: bounded-reject catch: yes
tool canvas B2 fidelity: dropped safety: ok catch: yes
tool docsplus B2 fidelity: dropped safety: ok catch: yes
tool docxodus B2 fidelity: preserved safety: ok catch: no
tool plate B3 fidelity: dropped safety: ok catch: yes
tool eigenpal B3 fidelity: dropped safety: ok catch: yes
tool eigenpal-editor B3 fidelity: dropped safety: ok catch: yes
tool folio B3 fidelity: dropped safety: ok catch: yes
tool folio-editor B3 fidelity: dropped safety: ok catch: yes
tool genoffice B3 fidelity: dropped safety: ok catch: yes
tool superdoc B3 fidelity: refused safety: bounded-reject catch: yes
tool officeopen B3 fidelity: dropped safety: ok catch: yes
tool docen B3 fidelity: dropped safety: ok catch: yes
tool fidus B3 fidelity: dropped safety: ok catch: yes
tool wordcraft B3 fidelity: refused safety: bounded-reject catch: yes
tool canvas B3 fidelity: refused safety: hang catch: no
tool docsplus B3 fidelity: dropped safety: ok catch: yes
tool docxodus B3 fidelity: dropped safety: ok catch: yes
tool plate B4 fidelity: refused safety: bounded-reject catch: yes
tool eigenpal B4 fidelity: refused safety: bounded-reject catch: yes
tool eigenpal-editor B4 fidelity: refused safety: bounded-reject catch: yes
tool folio B4 fidelity: refused safety: bounded-reject catch: yes
tool folio-editor B4 fidelity: refused safety: bounded-reject catch: yes
tool genoffice B4 fidelity: preserved safety: ok catch: no
tool superdoc B4 fidelity: preserved safety: ok catch: no
tool officeopen B4 fidelity: refused safety: bounded-reject catch: yes
tool docen B4 fidelity: refused safety: bounded-reject catch: yes
tool fidus B4 fidelity: refused safety: bounded-reject catch: yes
tool wordcraft B4 fidelity: refused safety: bounded-reject catch: yes
tool canvas B4 fidelity: preserved safety: ok catch: no
tool docsplus B4 fidelity: refused safety: bounded-reject catch: yes
tool docxodus B4 fidelity: refused safety: bounded-reject catch: yes
tool plate B5 fidelity: refused safety: bounded-reject catch: yes
tool eigenpal B5 fidelity: refused safety: bounded-reject catch: yes
tool eigenpal-editor B5 fidelity: refused safety: bounded-reject catch: yes
tool folio B5 fidelity: refused safety: bounded-reject catch: yes
tool folio-editor B5 fidelity: refused safety: bounded-reject catch: yes
tool genoffice B5 fidelity: preserved safety: ok catch: no
tool superdoc B5 fidelity: refused safety: bounded-reject catch: yes
tool officeopen B5 fidelity: refused safety: bounded-reject catch: yes
tool docen B5 fidelity: refused safety: bounded-reject catch: yes
tool fidus B5 fidelity: refused safety: bounded-reject catch: yes
tool wordcraft B5 fidelity: refused safety: bounded-reject catch: yes
tool canvas B5 fidelity: dropped safety: ok catch: yes
tool docsplus B5 fidelity: refused safety: bounded-reject catch: yes
tool docxodus B5 fidelity: refused safety: bounded-reject catch: yes
tool plate B6 fidelity: refused safety: bounded-reject catch: yes
tool eigenpal B6 fidelity: refused safety: bounded-reject catch: yes
tool eigenpal-editor B6 fidelity: refused safety: bounded-reject catch: yes
tool folio B6 fidelity: refused safety: bounded-reject catch: yes
tool folio-editor B6 fidelity: refused safety: bounded-reject catch: yes
tool genoffice B6 fidelity: preserved safety: ok catch: no
tool superdoc B6 fidelity: preserved safety: ok catch: no
tool officeopen B6 fidelity: preserved safety: ok catch: no
tool docen B6 fidelity: preserved safety: ok catch: no
tool fidus B6 fidelity: dropped safety: ok catch: yes
tool wordcraft B6 fidelity: dropped safety: ok catch: yes
tool canvas B6 fidelity: dropped safety: ok catch: yes
tool docsplus B6 fidelity: dropped safety: ok catch: yes
tool docxodus B6 fidelity: preserved safety: ok catch: no
tool plate B7 fidelity: dropped safety: ok catch: yes
tool eigenpal B7 fidelity: preserved safety: ok catch: no
tool eigenpal-editor B7 fidelity: preserved safety: ok catch: no
tool folio B7 fidelity: preserved safety: ok catch: no
tool folio-editor B7 fidelity: preserved safety: ok catch: no
tool genoffice B7 fidelity: preserved safety: ok catch: no
tool superdoc B7 fidelity: preserved safety: ok catch: no
tool officeopen B7 fidelity: preserved safety: ok catch: no
tool docen B7 fidelity: preserved safety: ok catch: no
tool fidus B7 fidelity: dropped safety: ok catch: yes
tool wordcraft B7 fidelity: dropped safety: ok catch: yes
tool canvas B7 fidelity: dropped safety: ok catch: yes
tool docsplus B7 fidelity: dropped safety: ok catch: yes
tool docxodus B7 fidelity: preserved safety: ok catch: no
tool plate B8 fidelity: refused safety: bounded-reject catch: yes
tool eigenpal B8 fidelity: preserved safety: ok catch: no
tool eigenpal-editor B8 fidelity: preserved safety: ok catch: no
tool folio B8 fidelity: preserved safety: ok catch: no
tool folio-editor B8 fidelity: preserved safety: ok catch: no
tool genoffice B8 fidelity: preserved safety: ok catch: no
tool superdoc B8 fidelity: preserved safety: ok catch: no
tool officeopen B8 fidelity: preserved safety: ok catch: no
tool docen B8 fidelity: preserved safety: ok catch: no
tool fidus B8 fidelity: dropped safety: ok catch: yes
tool wordcraft B8 fidelity: preserved safety: ok catch: no
tool canvas B8 fidelity: dropped safety: ok catch: yes
tool docsplus B8 fidelity: dropped safety: ok catch: yes
tool docxodus B8 fidelity: preserved safety: ok catch: no
tool plate B9 fidelity: preserved safety: ok catch: no
tool eigenpal B9 fidelity: preserved safety: ok catch: no
tool eigenpal-editor B9 fidelity: preserved safety: ok catch: no
tool folio B9 fidelity: preserved safety: ok catch: no
tool folio-editor B9 fidelity: preserved safety: ok catch: no
tool genoffice B9 fidelity: preserved safety: ok catch: no
tool superdoc B9 fidelity: preserved safety: ok catch: no
tool officeopen B9 fidelity: preserved safety: ok catch: no
tool docen B9 fidelity: refused safety: bounded-reject catch: yes
tool fidus B9 fidelity: dropped safety: ok catch: yes
tool wordcraft B9 fidelity: preserved safety: ok catch: no
tool canvas B9 fidelity: refused safety: hang catch: no
tool docsplus B9 fidelity: preserved safety: ok catch: no
tool docxodus B9 fidelity: preserved safety: ok catch: no
tool plate B10 fidelity: refused safety: bounded-reject catch: yes
tool eigenpal B10 fidelity: refused safety: bounded-reject catch: yes
tool eigenpal-editor B10 fidelity: refused safety: bounded-reject catch: yes
tool folio B10 fidelity: refused safety: bounded-reject catch: yes
tool folio-editor B10 fidelity: refused safety: bounded-reject catch: yes
tool genoffice B10 fidelity: refused safety: bounded-reject catch: yes
tool superdoc B10 fidelity: refused safety: bounded-reject catch: yes
tool officeopen B10 fidelity: preserved safety: ok catch: no
tool docen B10 fidelity: preserved safety: ok catch: no
tool fidus B10 fidelity: dropped safety: ok catch: yes
tool wordcraft B10 fidelity: dropped safety: ok catch: yes
tool canvas B10 fidelity: dropped safety: ok catch: yes
tool docsplus B10 fidelity: refused safety: bounded-reject catch: yes
tool docxodus B10 fidelity: refused safety: bounded-reject catch: yes
```

## Protection record

```
protection: a named ceiling that refuses the package is bounded-refusal.
protection: a clean exit whose output does not carry the weapon is sanitation.
protection: a non-zero exit with no named ceiling is erroring.
protection: a call stack that ran out is stack-exhaustion, not a ceiling.
protection: a weapon still in the output is preserved.
protection: hang, crash, and leak are separate.
protection: failed-load-exit-zero wrote nothing and still exited zero.
protection: the safety word bounded-reject is not a resource bound.
protection libreoffice B1 level: sanitation detail: the written package does not carry the weapon
protection libreoffice B2 level: sanitation detail: the written package does not carry the weapon
protection libreoffice B3 level: hang detail: the run did not finish
protection libreoffice B4 level: preserved detail: the weapon is still in the written package
protection libreoffice B5 level: failed-load-exit-zero detail: soffice said the source file could not be loaded
protection libreoffice B6 level: sanitation detail: the written package does not carry the weapon
protection libreoffice B7 level: sanitation detail: the written package does not carry the weapon
protection libreoffice B8 level: sanitation detail: the written package does not carry the weapon
protection libreoffice B9 level: sanitation detail: the written package does not carry the weapon
protection libreoffice B10 level: sanitation detail: the written package does not carry the weapon
protection plate B1 level: bounded-refusal detail: named ceiling on the size of one part
protection plate B2 level: bounded-refusal detail: named ceiling on the number of parts
protection plate B3 level: sanitation detail: the written package does not carry the weapon
protection plate B4 level: bounded-refusal detail: named ceiling on element depth
protection plate B5 level: erroring detail: rejected a document type declaration
protection plate B6 level: erroring detail: rejected the package
protection plate B7 level: sanitation detail: a source was unavailable
protection plate B8 level: erroring detail: the editor schema could not decode the package
protection plate B9 level: preserved detail: a source was unavailable
protection plate B10 level: erroring detail: rejected XML that is not UTF-8
protection eigenpal B1 level: bounded-refusal detail: named ceiling: too-large
protection eigenpal B2 level: bounded-refusal detail: named ceiling: too-many-entries
protection eigenpal B3 level: sanitation detail: the written package does not carry the weapon
protection eigenpal B4 level: bounded-refusal detail: named ceiling: too-deep
protection eigenpal B5 level: erroring detail: named rejection: dtd-forbidden
protection eigenpal B6 level: erroring detail: named rejection: bad-name
protection eigenpal B7 level: preserved detail: the weapon is still in the written package
protection eigenpal B8 level: preserved detail: the weapon is still in the written package
protection eigenpal B9 level: preserved detail: the weapon is still in the written package
protection eigenpal B10 level: erroring detail: named rejection: parse-error
protection eigenpal-editor B1 level: bounded-refusal detail: named ceiling: zip.maxRatio
protection eigenpal-editor B2 level: bounded-refusal detail: named ceiling: zip.maxEntries
protection eigenpal-editor B3 level: sanitation detail: the written package does not carry the weapon
protection eigenpal-editor B4 level: bounded-refusal detail: named ceiling: xml.maxDepth
protection eigenpal-editor B5 level: erroring detail: the editor rejected the input and did not name a ceiling
protection eigenpal-editor B6 level: erroring detail: the editor rejected the input and did not name a ceiling
protection eigenpal-editor B7 level: preserved detail: the weapon is still in the written package
protection eigenpal-editor B8 level: preserved detail: the weapon is still in the written package
protection eigenpal-editor B9 level: preserved detail: the weapon is still in the written package
protection eigenpal-editor B10 level: erroring detail: the editor rejected the input and did not name a ceiling
protection folio B1 level: bounded-refusal detail: named ceiling on compression ratio
protection folio B2 level: bounded-refusal detail: named ceiling on the number of parts
protection folio B3 level: sanitation detail: the written package does not carry the weapon
protection folio B4 level: bounded-refusal detail: named ceiling: depth
protection folio B5 level: erroring detail: preflight rejected malformed markup
protection folio B6 level: erroring detail: rejected an unsafe entry path
protection folio B7 level: preserved detail: the weapon is still in the written package
protection folio B8 level: preserved detail: the weapon is still in the written package
protection folio B9 level: preserved detail: the weapon is still in the written package
protection folio B10 level: erroring detail: preflight rejected malformed markup
protection folio-editor B1 level: bounded-refusal detail: named ceiling on compression ratio
protection folio-editor B2 level: bounded-refusal detail: named ceiling on the number of parts
protection folio-editor B3 level: sanitation detail: the written package does not carry the weapon
protection folio-editor B4 level: bounded-refusal detail: named ceiling: depth
protection folio-editor B5 level: erroring detail: preflight rejected malformed markup
protection folio-editor B6 level: erroring detail: rejected an unsafe entry path
protection folio-editor B7 level: preserved detail: the weapon is still in the written package
protection folio-editor B8 level: preserved detail: the weapon is still in the written package
protection folio-editor B9 level: preserved detail: the weapon is still in the written package
protection folio-editor B10 level: erroring detail: preflight rejected malformed markup
protection genoffice B1 level: preserved detail: the weapon is still in the written package
protection genoffice B2 level: bounded-refusal detail: named ceiling on the number of parts
protection genoffice B3 level: sanitation detail: the written package does not carry the weapon
protection genoffice B4 level: preserved detail: the weapon is still in the written package
protection genoffice B5 level: preserved detail: the weapon is still in the written package
protection genoffice B6 level: preserved detail: the weapon is still in the written package
protection genoffice B7 level: preserved detail: the weapon is still in the written package
protection genoffice B8 level: preserved detail: the weapon is still in the written package
protection genoffice B9 level: preserved detail: the weapon is still in the written package
protection genoffice B10 level: erroring detail: a styles part could not be parsed
protection superdoc B1 level: erroring detail: the opener reported unterminated markup
protection superdoc B2 level: erroring detail: the opener said source loading does not apply
protection superdoc B3 level: erroring detail: the opener reported a malformed start tag
protection superdoc B4 level: preserved detail: the weapon is still in the written package
protection superdoc B5 level: erroring detail: the opener reported no document root
protection superdoc B6 level: preserved detail: the weapon is still in the written package
protection superdoc B7 level: preserved detail: the weapon is still in the written package
protection superdoc B8 level: preserved detail: the weapon is still in the written package
protection superdoc B9 level: preserved detail: the weapon is still in the written package
protection superdoc B10 level: erroring detail: the opener said source loading does not apply
protection officeopen B1 level: preserved detail: the weapon is still in the written package
protection officeopen B2 level: preserved detail: the weapon is still in the written package
protection officeopen B3 level: sanitation detail: the written package does not carry the weapon
protection officeopen B4 level: stack-exhaustion detail: the call stack ran out
protection officeopen B5 level: erroring detail: rejected a malformed entity
protection officeopen B6 level: preserved detail: the weapon is still in the written package
protection officeopen B7 level: preserved detail: the weapon is still in the written package
protection officeopen B8 level: preserved detail: the weapon is still in the written package
protection officeopen B9 level: preserved detail: the weapon is still in the written package
protection officeopen B10 level: preserved detail: the weapon is still in the written package
protection docen B1 level: preserved detail: the weapon is still in the written package
protection docen B2 level: preserved detail: the weapon is still in the written package
protection docen B3 level: sanitation detail: the written package does not carry the weapon
protection docen B4 level: stack-exhaustion detail: the call stack ran out
protection docen B5 level: erroring detail: rejected a malformed entity
protection docen B6 level: preserved detail: the weapon is still in the written package
protection docen B7 level: preserved detail: the weapon is still in the written package
protection docen B8 level: preserved detail: the weapon is still in the written package
protection docen B9 level: stack-exhaustion detail: the call stack ran out
protection docen B10 level: preserved detail: the weapon is still in the written package
protection fidus B1 level: preserved detail: the weapon is still in the written package
protection fidus B2 level: sanitation detail: the written package does not carry the weapon
protection fidus B3 level: sanitation detail: the written package does not carry the weapon
protection fidus B4 level: bounded-refusal detail: named ceiling on nested tags
protection fidus B5 level: erroring detail: rejected an external entity
protection fidus B6 level: sanitation detail: the written package does not carry the weapon
protection fidus B7 level: sanitation detail: the written package does not carry the weapon
protection fidus B8 level: sanitation detail: the written package does not carry the weapon
protection fidus B9 level: sanitation detail: the written package does not carry the weapon
protection fidus B10 level: sanitation detail: the written package does not carry the weapon
protection wordcraft B1 level: preserved detail: the weapon is still in the written package
protection wordcraft B2 level: bounded-refusal detail: named ceiling
protection wordcraft B3 level: bounded-refusal detail: named ceiling on attributes of one element
protection wordcraft B4 level: bounded-refusal detail: named ceiling on element depth
protection wordcraft B5 level: erroring detail: an entity is not defined
protection wordcraft B6 level: sanitation detail: the written package does not carry the weapon
protection wordcraft B7 level: sanitation detail: the written package does not carry the weapon
protection wordcraft B8 level: preserved detail: the weapon is still in the written package
protection wordcraft B9 level: preserved detail: the weapon is still in the written package
protection wordcraft B10 level: sanitation detail: the written package does not carry the weapon
protection canvas B1 level: hang detail: the run did not finish
protection canvas B2 level: sanitation detail: the written package does not carry the weapon
protection canvas B3 level: hang detail: the run did not finish
protection canvas B4 level: preserved detail: the weapon is still in the written package
protection canvas B5 level: sanitation detail: the written package does not carry the weapon
protection canvas B6 level: sanitation detail: the written package does not carry the weapon
protection canvas B7 level: sanitation detail: the written package does not carry the weapon
protection canvas B8 level: sanitation detail: the written package does not carry the weapon
protection canvas B9 level: hang detail: the run did not finish
protection canvas B10 level: sanitation detail: the written package does not carry the weapon
protection docsplus B1 level: sanitation detail: the written package does not carry the weapon
protection docsplus B2 level: sanitation detail: the written package does not carry the weapon
protection docsplus B3 level: sanitation detail: the written package does not carry the weapon
protection docsplus B4 level: stack-exhaustion detail: the call stack ran out
protection docsplus B5 level: erroring detail: an entity was not found
protection docsplus B6 level: sanitation detail: the written package does not carry the weapon
protection docsplus B7 level: sanitation detail: the written package does not carry the weapon
protection docsplus B8 level: sanitation detail: the written package does not carry the weapon
protection docsplus B9 level: preserved detail: the weapon is still in the written package
protection docsplus B10 level: erroring detail: the xml parser rejected a tag
protection docxodus B1 level: preserved detail: the weapon is still in the written package
protection docxodus B2 level: preserved detail: the weapon is still in the written package
protection docxodus B3 level: sanitation detail: the written package does not carry the weapon
protection docxodus B4 level: stack-exhaustion detail: the call stack ran out
protection docxodus B5 level: erroring detail: the cell log does not name a ceiling
protection docxodus B6 level: preserved detail: the weapon is still in the written package
protection docxodus B7 level: preserved detail: the weapon is still in the written package
protection docxodus B8 level: preserved detail: the weapon is still in the written package
protection docxodus B9 level: preserved detail: the weapon is still in the written package
protection docxodus B10 level: erroring detail: the cell log does not name a ceiling
```

## Where the safety word is the wrong name

LibreOffice on the entity package is `failed-load-exit-zero`. soffice said the source file could not be loaded. No cleaned file was written. The process exited 0. The score line says catch yes. That bit overstates the cell. There is no sanitized document.

LibreOffice on the attribute package hung. The leaf of the deep package is still in the written file, so that cell is `preserved`. The other LibreOffice drops are `sanitation`.

`stack-exhaustion`, not a ceiling: office-open on the deep package, Docen on the deep package and on the layout package, docs.plus on the deep package, Docxodus on the deep package. Fidus Writer on the deep package is the other kind of nest failure: its own message is a maximum on nested tags, so that cell is `bounded-refusal`.

`erroring`, and the log names no ceiling:

- Plate rejected the entity package for a document type declaration, rejected the zip-slip package as a package, failed to decode the active-content package, and rejected the corrupt package as XML that is not UTF-8.
- The eigenpal store named `dtd-forbidden`, `bad-name`, and `parse-error`. `bad-name` is a name policy.
- The eigenpal editor, on the entity package, the zip-slip package, and the corrupt package, rejected the argument. The visible error is `InvalidArgument`, the limit field is unset, and the inner cause is not in the cell log. Do not copy the store's `dtd-forbidden`, `bad-name`, or `parse-error` onto that lane.
- Folio and the Folio editor rejected the entity package and the corrupt package because preflight could not scan the markup, and rejected the zip-slip package for an unsafe entry path. The unsafe path is a name policy. An earlier reading of the Folio zip-slip cell called it a size ceiling. That reading was a stack frame quoting a source line, not the error. The level is `erroring`.
- GenOffice could not parse a styles part on the corrupt package.
- SuperDoc reported unterminated markup on the decompression package. That message names no ceiling. On the attribute package it reported a malformed start tag. The attribute bomb broke the tag. That is not an attribute cap. On the entry flood and the corrupt package it said source loading does not apply. On the entity package it reported no document root.
- office-open and Docen rejected a malformed entity. Fidus Writer rejected an external entity. wordcraft said an entity is not defined. docs.plus said an entity was not found, and on the corrupt package the XML parser rejected a tag.
- Docxodus on the entity package and the corrupt package exited non-zero inside the wall. The cell log is a runtime script dump. It does not name a package limit. This is not a hang. No limit is invented for it.

`bounded-refusal`, because the tool named the ceiling:

- Plate: part size, entry count, element depth.
- eigenpal store: too-large, too-many-entries, too-deep.
- eigenpal editor: `zip.maxRatio`, `zip.maxEntries`, `xml.maxDepth`.
- Folio and the Folio editor: compression ratio, part count, and a declared depth cap. The depth message is that the part is nested deeper than the cap.
- GenOffice: part count, on the entry flood only.
- Fidus Writer: nested tags, on the deep package.
- wordcraft: entry count, attributes of one element, and element depth. The entry-count line in the protection record says only "named ceiling". The cell log says the limit that was exceeded is the zip entry count. The password retry is wordcraft's own read path, not a second permissive pass.

Plate on the attribute package is `sanitation`, not an attribute cap. wordcraft on that package is the cap. The two are not the same degree.

## Kept payloads

`preserved` means the weapon is still in the written package. GenOffice keeps the original package on the decompression bomb, the deep package, the entity package, zip-slip, the external relationships, the active content, and the layout bomb. On the entity package the written zip still holds the entity declaration and the unexpanded references. The expanded token appears in that declaration. It is not a repeated payload, and it is not a cleaned document. The primary label stays `preserved`.

wordcraft on the active-content package is `preserved` because the script marker is still in the zip. The javascript URL is not in that zip. A partial strip that leaves the script is not sanitation.

wordcraft on the layout package is `preserved` because the field markers and the bibliography sources are still there. The written grid span is 63, not the span in the bomb. That is a cap on the span alone. The cell is not labeled `bounded-delivery`, because the fields and the bibliography survived. No cell in this matrix has `bounded-delivery` as its primary label.

Plate on the external-relationship package is `sanitation`: a source was unavailable and the probe URL is not in the export. Plate on the layout package is `preserved`: the same source-unavailable note did not remove the layout bomb.

Fidus Writer's drops, including the layout package, are `sanitation`. canvas-editor's finished drops are `sanitation`. Its decompression, attribute, and layout cells hung at the wall clock. A hang is not a catch.

Docxodus, office-open, Docen, and the eigenpal lanes preserve the decompression bomb, the entry flood, zip-slip, the external relationships, and, except where a row above says otherwise, the active content and the layout bomb. Preserving those is no protection.

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

This section is the interim note in `reports/Report D2 - What Word Protects Against (2026).md`, copied here on 2026-10-31 before that report was finalised. The final report supersedes it: there every fixture but E6 was opened in Word, and two jubarte binaries were run on all 33 fixtures. It is not the seatbelt matrix. The fenced log above still says Word was not opened. That fence is the entry that refuses to run. This run did open Word.

The grade 0.65 is jubarte 0.14.0, in Report D1. The jubarte column in the table below is binary 0.16.0+6bf2efb43. Those are not the same run.

CLEAN in the table means a PDF was written and no dialog appeared. That is not the protection ladder in this report, so this table is not turned into a float grade. Word's B6 through B10, the nested-table probes, the network probes, and the element-count series are still pending. jubarte 0.16.0+6bf2efb43 has been run on all 28 fixtures. The jubarte column below is that run. The source note says 11 of 28 Word fixtures. `results_word.tsv` has 12 finished Word rows, and one of them is the control.

**Status when copied: Word was still interim (2026-10-31); superseded by the final report.** The Word column below is the interim note. jubarte
0.16.0+6bf2efb43 was run the same day on all 28 fixtures. Rows marked *pending* are still open for Word.

Companion to `jubarte-redlines/docs/bomb_prevention.md` (jubarte 0.14.0, `read` only, no Word). This report
opens the same hostile packages, plus the gaps found while reviewing that document, in Microsoft Word for Mac,
and sets Word's behaviour beside jubarte's.

Raw evidence, scripts and the run journal are in [`logs/word-exp/`](../logs/word-exp/) (`LOG.md`,
`results_word.tsv`, `results_jubarte.tsv`, `runs/ID/word.log`, `screen.log`, `net.log`).

### Method

- **Word:** only through `neurotic_docx_bench/scripts/word_pdf.py` (open, then export to PDF), one fixture per
  run, alone, `--timeout 300`.
  - The bench watchdog ran on that run's own log, and `word_screen_log.py` recorded every dialog.
  - Word's RSS was sampled every second, with a 10 GB kill guard.
  - Verdict: **CLEAN** = PDF written and no dialog. Anything else is a refusal, an alert or a hang.
- **Network:** a listener on `127.0.0.1:18009` logs every connection (`net.log`).
  - The doc's B7 aims at `127.0.0.1:9` and `\\127.0.0.1\share`. Ports below 1024 need root, so B7 cannot be
    observed directly; N1–N4 aim the same shapes at the listener.
- **Canary:** B5's external entity points at a file holding `CANARY_SECRET_7f3a`; the PDF text is checked for it.
- **jubarte:** binary 0.16.0+6bf2efb43, `read` (default and `--no-page-markers`) and `validate`, each under a
  6 GB / 300 s guard.
- **Fixtures:**
  - B1–B10 are the doc's packages, built by `editors_trial/build/make_bombs.py` unchanged.
  - The others are described in the table.

### Results

| Fixture | Shape | Word | Word peak RSS | jubarte `read` (0.16.0) |
| --- | --- | --- | --- | --- |
| C0 | one paragraph (control) | CLEAN, 1 page | 506 MB | ok |
| B1 | one `w:t` of 66 MiB of spaces (68 KB zipped) | **CLEAN**, 1 page, 7 s | 711 MB | refused: `INPUT_LIMIT` (part > 64 MiB) |
| B2 | 25,000 `customXml` parts | **CLEAN**, body text present | 460 MB | refused: `INPUT_LIMIT` (entries > 10,000) |
| B3 | 500,000 attributes on one `w:p` | **refused**: "Word experienced an error trying to open the file." | 615 MB | refused: `INVALID_XML` (> 1024 attributes) |
| B4 | 5,000-deep `w:sdt` + 250-deep `w:tbl` | **refused**: same error | 511 MB | `read` refuses, "XML nesting too deep". `validate` says deeper than 256 |
| D_sdt200/300/600 | `w:sdt` chains 200 / 300 / 600 deep | **CLEAN**, leaf text present | 559–619 MB | 200: `read` writes the leaf, layout warns deeper than 256, `validate` refuses at 256. 300 and 600: `read` refuses, nesting too deep |
| D_tbl60/200/300 | nested tables 60 / 200 / 300 deep | *pending* | | 60: `read` writes the leaf. 200 and 300: `read` refuses, nesting too deep |
| B5 | billion-laughs-style entities (10^6) + external entities (`/etc/hosts`, canary) | **refused**: same error | 470 MB | view written; entity references kept literal, never expanded |
| X1 | a bare `<!DOCTYPE w:document>` (no internal subset) | **refused**: same error | 1.5 GB | `read` and `validate` exit 0. The body stays `BODY_OK` |
| X2 | internal entity used in text | **refused**: same error | 470 MB | `read` and `validate` exit 0. The view keeps `ENT[&a;]`. It does not expand |
| X3 | internal entity whose value holds a `>` (parser-differential probe) | **refused**: same error | 467 MB | `read` and `validate` exit 0. The view is `BODY_OK`. The smuggled paragraph is absent |
| B6 | zip-slip entry `../escaped/…` + traversal relationships | *pending* | | `read` writes the body and warns on the unsafe name. `validate` refuses that name. No slipped file |
| B7 | external template on `127.0.0.1:9` + UNC subDocument | *pending* | | body only. `read` and `validate` exit 0. No connection on the listener |
| B8 | `javascript:` hyperlink + altChunk HTML with script | *pending* | | body only. No javascript target and no script. `validate` exits 2: the hyperlink run is outside a paragraph |
| B9 | `gridSpan` 1,000,000 + 2,000 open field begins + 60,000 bibliography sources | *pending* | | span capped at 64. `read` names 2000 validity errors. `validate` exits 2 with 2000 field errors. Peaks 145 MB and 144 MB |
| B10 | non-UTF-8 styles, truncated comments, fake PNG | *pending* | | `read` writes the body and warns on the comments part. `validate` refuses the unclosed tag |
| N1–N4 | remote template, linked picture (`a:blip r:link`), `INCLUDEPICTURE`, subDocument → listener | *pending* | | N1, N2, N4: body only. N3: the field instruction and `FIELD_CACHE` stay in the view. `net.log` stayed empty |
| E1/E2/E3/E4 | valid element flood: 1 / 8 / 60 / 70 MiB of paragraphs (4 KB–215 KB zipped) | *pending* | | E1 exits 0, peaks 115 MB and 148 MB. E2 exits 0, peaks 783 MB and 985 MB. E3 exits 0 and was not killed, peaks 5483 MB and 5604 MB, both flood markers in the view. E4 is refused by the part cap. `read` peaked at 4419 MB first. `read` without page markers peaked at 2 MB |

### Conclusions so far

1. **Word refuses every DTD.** A bare `<!DOCTYPE>` with no subset (X1) is refused exactly like the entity bomb
   (B5): "Word experienced an error trying to open the file." So entities are never a Word-valid input. On this
   run jubarte `read` and `validate` both exit 0 on X1, X2, X3, and B5. `validate` did not refuse them. The
   view keeps the literal references and does not expand them. A document jubarte reads can be one Word will
   not open. Refusing (or at least warning on) a DOCTYPE in `read` loses no Word-valid input.
2. **Word refuses floods of attributes on one element** (B3), as jubarte does. The depth claim in the first
   draft of this note was wrong. It said jubarte's caps refuse nothing Word opens. Word opens a 600-deep
   `w:sdt`. jubarte `read` refuses a 300-deep one and a 600-deep one. That cap does refuse a document Word opens.
3. **Word opens a 600-deep `w:sdt` chain cleanly; B4 (5,000-deep `w:sdt` plus a 250-deep table) it refuses.**
   Which of B4's two nests Word rejects is still open: the 60-deep table run wedged Word and the journal marks
   the following table runs as a cascade, so they are not a result yet. On jubarte, `read` writes a 200-deep
   `w:sdt` and a 60-deep table. Layout warns that the 200-deep part nests deeper than 256, and `validate`
   refuses it with that 256 message. `read` refuses 300-deep and 600-deep content controls, and 200-deep and
   300-deep tables, with "XML nesting too deep". `validate` on those files says the part nests deeper than 256.
4. **Word is more permissive than jubarte on size and entry count.**
   - B1: a 66 MiB run, CLEAN in 7 s at 711 MB.
   - B2: 25,000 parts, CLEAN.
   - jubarte refuses both. Word's tolerance means it gives jubarte no lower bound to copy here: these caps are
     jubarte's own choice, and they are not Word-faithful.
5. **Word gives no protection against element-count blow-up, and neither does jubarte.** The Word E-series is
   still pending. jubarte's limits are in bytes. On this run the 60 MiB flood was not killed. Both reads exited
   0, with peaks of 5483 MB and 5604 MB, and both flood markers are in the view. The 70 MiB flood is refused by
   the part cap. With page markers on, that refusal came after a peak of 4419 MB. Without page markers the same
   refusal peaked at 2 MB. The same split is on B1: 698 MB with page markers, 2 MB without, and both print the
   part cap.

### What this means for jubarte

- **Word refuses it:** DTD/DOCTYPE, attribute floods, extreme depth. jubarte can refuse the same with no
  Word-validity cost.
- **Word accepts it and jubarte refuses:**
  - A 66 MiB part and 25,000 entries. These are deliberate resource caps, and they are not Word-faithful.
  - 300- to 600-deep content controls: a depth jubarte `read` refuses that Word renders. A 200-deep content
    control is the other way around for `validate` only: `read` writes the leaf, `validate` refuses it at 256.
  - Both trade-offs must be stated in jubarte's docs.
- **Neither defends it yet:** memory blow-up from element count. The 60 MiB flood stayed under the 6 GB guard
  and still exited 0. jubarte needs an element budget of its own. Word's E-series is not finished, so Word
  still offers no measured behaviour to follow on that series.
