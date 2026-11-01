#!/usr/bin/env python3
"""Measure the mc:AlternateContent block in word/document.xml.

The length is the UTF-8 byte length of the element, from the opening
``<mc:AlternateContent`` through the matching ``</mc:AlternateContent>``.
Report A quotes these lengths. The printer is what the lane log records.
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
START = b"<mc:AlternateContent"
END = b"</mc:AlternateContent>"

# Slugs whose round-trip output Report A compares to the corpus block.
PACKAGES = (
    ("corpus", ROOT / "fixture" / "complex.docx"),
    ("genoffice", ROOT / "out" / "genoffice" / "complex.docx"),
    ("superdoc", ROOT / "out" / "superdoc" / "complex.docx"),
    ("folio", ROOT / "out" / "folio" / "complex.docx"),
    ("eigenpal", ROOT / "out" / "eigenpal" / "complex.docx"),
    ("officeopen", ROOT / "out" / "officeopen" / "complex.docx"),
    ("docen", ROOT / "out" / "docen" / "complex.docx"),
    ("docxodus", ROOT / "out" / "docxodus" / "complex.docx"),
    ("apryse", ROOT / "out" / "apryse" / "complex.docx"),
)


def alternate_content_lengths(path: Path) -> list[int]:
    """Measure literal mc:AlternateContent blocks in document.xml.

    Args:
        path: DOCX ZIP path.

    Returns:
        Byte lengths from each opening marker through its closing marker. An
        unmatched opening marker ends the scan and is omitted.

    Raises:
        OSError: If the file cannot be opened or read.
        zipfile.BadZipFile: If the file is not a valid ZIP.
        KeyError: If word/document.xml is missing.
    """
    with zipfile.ZipFile(path) as zf:
        raw = zf.read("word/document.xml")
    lengths: list[int] = []
    cursor = 0
    while True:
        start = raw.find(START, cursor)
        if start < 0:
            break
        stop = raw.find(END, start)
        if stop < 0:
            break
        stop += len(END)
        lengths.append(stop - start)
        cursor = stop
    return lengths


def format_token(n: int) -> str:
    """Thousands-separated byte size, the form Report A prints."""
    return f"{n:,} bytes"


def main() -> int:
    """Print one block length per package and report unexpected counts.

    Returns:
        0 if each package has one block, otherwise 1.
    """
    failed = False
    for label, path in PACKAGES:
        lengths = alternate_content_lengths(path)
        if len(lengths) != 1:
            print(
                f"{label} expected one mc:AlternateContent block, found {len(lengths)} in {path}",
                file=sys.stderr,
            )
            failed = True
            continue
        print(f"{label} {path.relative_to(ROOT)} {format_token(lengths[0])}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
