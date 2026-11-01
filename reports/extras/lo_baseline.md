# LibreOffice

## What the driver runs

`build/score_all.py` measures LibreOffice as the baseline, from `out/lo_baseline`. `build/run_all.sh` converts the fixture with `soffice --headless --norestore --convert-to docx`. LibreOffice is not one of the vendored editor trees. This note does not publish a new round-trip percentage for that output.

## What it is

The baseline is a headless conversion through the installed LibreOffice binary. It is here so the editor lanes have a full word processor next to them.

## Trivia

The binary the driver invokes is named `soffice`. That name is the StarOffice binary name, kept by OpenOffice and then by LibreOffice. The history of the name is not a score.
