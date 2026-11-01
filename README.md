# Editors trial

This repo measures open-source DOCX editors on one adversarial fixture, then, separately, on a sandboxed set of hostile packages. Fidelity and safety are different results. A tool that keeps a hostile payload is not the same result as a tool that crashes.

The measured write-up is [Open-Source DOCX Editors Re-verified Against Code and Measured Round-Trip (2026).md](Open-Source%20DOCX%20Editors%20Re-verified%20Against%20Code%20and%20Measured%20Round-Trip%20(2026).md). The per-tool notes are in `reports/extras/`. The vendor notes are `reports/vendors.md`.

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

Jubarte is not in that matrix. The same packages, read by the release binary of `../jubarte-redlines` at version 0.14.0, are `logs/jubarte-bombs` and [Report E](reports/Report%20E%20-%20Jubarte%20on%20the%20Hostile%20Packages%20(2026).md). The skill copy of the binary was not used. `jubarte read` writes a markdown view, not a second package.

Word is not opened. No NTLM hash is collected. A slip onto the host temp directory is denied by the seatbelt, so the only slip that can be observed is one that lands inside the work directory, or file contents that come back in the saved package.

## Logs

`logs/bombs/trace.log` keeps the full stdout and stderr of every cell. Nothing in that trace is truncated. `logs/bombs/scorecard.txt` is written when the run finishes. `logs/bombs/tool/<editor>/<bomb>/` and `logs/bombs/comparison/libreoffice/<bomb>/` hold the same streams per cell.

`logs/bombs-before-suggested-config` is the earlier matrix. Several of its columns died in the seatbelt before the editor ran. Do not read those cells as the editor's result. `logs/bombs-suggested-smoke` is the one-package check that the corrected harness actually reaches Plate, canvas-editor, docs.plus, Docen, office-open, and Fidus Writer.

`BOMB_RESUME=1` continues a run. A run without it deletes `logs/bombs` first. Move that directory aside if the previous trace should be kept.
