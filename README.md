# Editors trial

This repo measures open-source DOCX editors on one adversarial fixture, then, separately, on a sandboxed set of hostile packages. Fidelity and safety are different results. A tool that keeps a hostile payload is not the same result as a tool that crashes.

The measured write-up is [Open-Source DOCX Editors Re-verified Against Code and Measured Round-Trip (2026).md](Open-Source%20DOCX%20Editors%20Re-verified%20Against%20Code%20and%20Measured%20Round-Trip%20(2026).md). The per-tool notes are in `reports/extras/`. The vendor notes are `reports/vendors.md`.

Each per-tool note has also been filed as an issue on that project's own repository, so that a maintainer can correct the measurement where they already work. The list of those issues is in [`outreach/`](outreach/).

## Fidelity

`fixture/complex.docx` is the corpus. `build/run_all.sh` runs each editor's own import and export. `build/score_all.py` scores the files under `out/`. One file is `python3 build/check_roundtrip.py IN OUT`.

The editors are Plate, eigenpal (store and editor), Folio (model and editor), GenOffice, SuperDoc, office-open, Docen, Fidus Writer, WordCraft, canvas-editor, docs.plus, and Docxodus. Headless lanes are not the browser.

## Hostile packages

`python3 build/run_bombs.py` records the ten vectors and does not build them. The run that actually opens them is:

```sh
WORDCRAFT_BIN=/path/to/wc-harness BOMB_WORK=/tmp/editors-trial-bombs \
  python3 -u build/run_bomb_sandbox.py
```

`node` has to be on `PATH` before that process starts. This machine uses the current nvm Node. `WORDCRAFT_BIN` is the release `wc-harness`.

LibreOffice is the comparison. It runs in the image `editors-trial-bombs:local`: no network, 2 GB, read-only root, one container per package. The editors are macOS binaries, so they are not run in that Linux container. They run under seatbelt. External network stays denied. Localhost is allowed, because several of these tools bind their own loopback stub, and so is the unix socket `tsx` opens inside the work directory. Writes stay in the work directory, plus the canvas vitest config cache, which Vite will not put anywhere else.

Each editor is driven with that project's own documented import and export (`EDITOR_CONFIG=suggested`). Plate uses `BaseEditorKit`, `retainSource`, and the default reject policy. A refused import writes no second file. canvas-editor does not replace a thrown import with the blank starter document. docs.plus stops at its own `importDocx` and `exportDocx`. The Plate www kit imports `remark-emoji`, `remark-gfm`, and `remark-math` at the versions pinned in `apps/www/package.json`. Those copies live in `harness/plate` because this checkout does not have them installed, and `harness/plate/aliases.ts` points the kit at them.

A seatbelt or loader failure before the editor runs is recorded as `not-run` with a `harness-` reason. It is not a catch. Preserving the payload is not a catch. A crash, a hang, or a leak is not a catch.

The sandboxed matrix is `logs/bombs`. [Report D](reports/Report%20D%20-%20Safety%2C%20Resource%20Bombs%20and%20Hostile%20Input%20(2026).md) keeps the unsandboxed refusal and then the measured scorecard. The safety word `bounded-reject` only means a non-zero exit that was not a crash, a hang, or a leak. The protection level is a separate reading: a named ceiling, a reduced write under a declared cap, sanitation, a parse or name-policy error, stack exhaustion, a kept payload, an unexpanded entity reference, a hang, a crash, a leak, or a load that exits zero and writes nothing.

Jubarte is not in that matrix. The same packages, read by the release binary of `../jubarte-redlines` at version 0.14.0, are `logs/jubarte-bombs` and [Report D1](reports/Report%20D1%20-%20Jubarte%20on%20the%20Hostile%20Packages%20(2026).md). The skill copy of the binary was not used. `jubarte read` writes a markdown view, not a second package.

Word is not opened. No NTLM hash is collected. A slip onto the host temp directory is denied by the seatbelt, so the only slip that can be observed is one that lands inside the work directory, or file contents that come back in the saved package.

## Logs

`logs/bombs/trace.log` keeps the full stdout and stderr of every cell. Nothing in that trace is truncated. `logs/bombs/scorecard.txt` is written when the run finishes. `logs/bombs/tool/<editor>/<bomb>/` and `logs/bombs/comparison/libreoffice/<bomb>/` hold the same streams per cell.

`logs/bombs-before-suggested-config` is the earlier matrix. Several of its columns died in the seatbelt before the editor ran. Do not read those cells as the editor's result. `logs/bombs-suggested-smoke` is the one-package check that the corrected harness actually reaches Plate, canvas-editor, docs.plus, Docen, office-open, and Fidus Writer.

`BOMB_RESUME=1` continues a run. A run without it deletes `logs/bombs` first. Move that directory aside if the previous trace should be kept.

## Release gate

The published report set is eight Markdown reports and their DOCX twins. One
command checks every gate that has to pass before they ship:

```
build/verify_publication.sh              # everything except Word
build/verify_publication.sh --with-word  # also drive Word to open each file
```

The gates answer different questions, and none substitutes for another:

| Gate | Question it answers |
|---|---|
| `build/test_report_claims.py` | Do the repository's own claims still hold? |
| `build/verify_twin_parity.py` | Is each published DOCX what its Markdown says, and exactly what the build pipeline produces? |
| `build/verify_findings.py` | Does every figure in the published tables belong to the subject its table row names? |
| `build/check_report_consistency.py` | Does every percentage and byte size in every live report occur in the measurement artifacts? |
| `build/validate_ooxml.py` | Does each DOCX validate against the ECMA-376 schemas? |
| `build/build_claim_evidence.py` | Is the review's claim-evidence matrix complete and well formed? |
| `build/verify_deliverables.py` | Does each deliverable open in Microsoft Word? |

The findings gate is the one that cannot be replaced by a token check. A
token check asks whether "100%" occurs somewhere in the logs; it cannot tell
SuperDoc's 100% from SuperDoc's 84.9%. The findings gate compares each
figure with the measurement for the subject the table row names.

The number gate scans every live report and its twin - thirty-five documents,
468 percentages and byte sizes - against a corpus built from the measurement
artifacts in `out/` and `logs/`. `--diff-only` narrows it to the reports a
branch has touched, which is what a pre-commit run wants.

A DOCX twin is generated output. It must never be patched by matching text
against its source: the source is rendered, so the markdown markers are gone
and the context match fails silently. Rebuild it with `build/make_report.sh`.

## Review

`out/review/` holds the reader's report on the study, prepared with the
Scientific Research Workflows peer-review skill. It is a working draft for a
human to verify and rewrite, not an editorial decision.

| File | What it is |
|---|---|
| `out/review/review_draft.md` | The review: eleven major and twelve minor comments, channels separated |
| `out/review/claim_evidence_matrix.csv` | Every claim mapped to its evidence: 126 claims, 107 machine-verified and 19 needing an author action |
| `out/review/venue_and_reporting_guidance.md` | Venue shortlist by fit, and the reporting instruments to prespecify |
| `out/review/intake.json` | The review's own intake record, as the skill validates it |
| `out/review/findings_ledger.csv` | The findings ledger the claim matrix is generated from |

The bundled reporting-guideline catalogue has no software-benchmark
instrument, so no checklist coverage audit was possible. The venue dossier
names the three instruments to adopt instead, and records that a catalogue's
`VALID` status is a coverage statement, not a statement that reporting is
complete.
