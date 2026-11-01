#!/usr/bin/env python3
"""
Check that every published .docx is the faithful twin of its .md source.

The DOCX files in this repository are generated from their Markdown source by
build/make_report.sh. A twin that has drifted from its source is a
publication defect that no schema validator sees: the document opens in Word,
every table is laid out correctly, and the file is simply not the report.

Comparing a Markdown file with its twin by reading the prose out of both is
a mistake this gate used to make, and it produced 205 false positives: the
two sides are not comparable as raw text, because pandoc consumes the
markdown syntax. Emphasis markers, code ticks, link targets and list markers
are present in one side and absent in the other, and markdown nests - a bold
run can contain an italic run, and an emphasis span can straddle a line
break. Re-implementing that grammar in Python reproduces it wrong.

So the comparison uses the pipeline itself as the common renderer, and runs
four independent axes:

  A. percentage and byte-size tokens - the numbers the report is about.
     Compared as sets, after the markdown markers are removed from both
     sides, so "**8,010** bytes" in the source matches "8,010 bytes" in the
     twin. A token on one side only is a real drift.
  B. table count - one markdown table per w:tbl in the twin.
  C. heading count - one markdown heading per Heading* paragraph in the twin.
  D. reproducible build - the source is rebuilt with build/make_report.sh
     into a temporary file and the twin's paragraph sequence is compared
     against the rebuild, run by run. This is the axis that cannot be
     fooled by a reader: if the source moved and the twin did not, the two
     paragraph sequences differ.

Axis D is the strongest of the four and the others are cheap, so all four
run. A report with no twin is reported separately, because a note is not a
publication twin.

usage: python3 build/verify_twin_parity.py [report.md ...]

With no arguments, every publication report in the repository root and in
reports/ is checked.
"""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAKE_REPORT = ROOT / "build" / "make_report.sh"

# The same token grammar the consistency gate uses, so the two gates agree.
PCT = re.compile(r"\d[\d,]*(?:\.\d+)?\s*%")
BYTE = re.compile(r"\d[\d,]*\s+bytes\b", re.I)

MD_SEPARATOR = re.compile(r"^\s*\|[\s:|-]+\|\s*$")
MD_HEADING = re.compile(r"^(#{1,6})\s")
MD_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")

# Documents that are notes, not publication reports: they have no DOCX twin
# and are not expected to have one.
NOTES = {
    "README.md",
    "reports/vendors.md",
    "reports/rendering-openability.md",
}

ENTITIES = {
    "&amp;": "&",
    "&lt;": "<",
    "&gt;": ">",
    "&quot;": '"',
    "&#39;": "'",
    "&apos;": "'",
    "&nbsp;": " ",
}


def docx_paragraphs(path: Path) -> list[str]:
    """Return the nonempty paragraph text of a DOCX, with entities resolved.

    Args:
        path: DOCX path.

    Returns:
        A list of stripped paragraph strings.

    Raises:
        OSError: If the file cannot be read.
        zipfile.BadZipFile: If the file is not a valid ZIP.
        KeyError: If the document part is missing.
    """
    with zipfile.ZipFile(path) as zf:
        xml = zf.read("word/document.xml").decode("utf-8", "replace")
    plain = re.sub(r"</w:p>", "\n", xml)
    plain = re.sub(r"<[^>]+>", "", plain)
    for entity, char in ENTITIES.items():
        plain = plain.replace(entity, char)
    return [line.strip() for line in plain.splitlines() if line.strip()]


def docx_counts(path: Path) -> tuple[int, int]:
    """Return the twin's table and heading counts.

    Args:
        path: DOCX path.

    Returns:
        ``(tables, headings)``.
    """
    with zipfile.ZipFile(path) as zf:
        xml = zf.read("word/document.xml").decode("utf-8", "replace")
    tables = len(re.findall(r"<w:tbl>", xml))
    headings = len(re.findall(r'<w:pStyle w:val="Heading[1-6]"', xml))
    return tables, headings


def strip_markers(text: str) -> str:
    """Remove the markdown markers that pandoc consumes.

    Only the emphasis and code markers are removed. Underscores are left
    alone, because they occur inside identifiers such as `CT_PPr` and inside
    file names such as `score_all.py`.

    Args:
        text: Markdown text.

    Returns:
        The text without emphasis or code markers.
    """
    return text.replace("*", "").replace("`", "")


def tokens(text: str, pattern: re.Pattern[str]) -> set[str]:
    """Return the set of pattern matches in a text, whitespace-normalised.

    Args:
        text: Text to scan.
        pattern: Token pattern.

    Returns:
        A set of normalised token strings.
    """
    return {" ".join(m.group(0).split()) for m in pattern.finditer(text)}


def source_counts(md: Path) -> tuple[int, int]:
    """Return the markdown table and heading counts of a source file.

    A markdown table has exactly one separator row, so the separator rows
    count the tables. Code fences are excluded, because a table inside a
    fence is an example, not a table.

    Args:
        md: Markdown path.

    Returns:
        ``(tables, headings)``.
    """
    tables = 0
    headings = 0
    in_fence = False
    for raw in md.read_text(encoding="utf-8").splitlines():
        if raw.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if MD_SEPARATOR.match(raw):
            tables += 1
        elif MD_TABLE_ROW.match(raw):
            continue
        elif MD_HEADING.match(raw):
            headings += 1
    return tables, headings


def rebuild(md: Path, out: Path) -> tuple[bool, str]:
    """Rebuild a Markdown report with the repository pipeline.

    Args:
        md: Markdown source.
        out: Destination DOCX path, in a temporary directory.

    Returns:
        ``(ok, message)``.
    """
    proc = subprocess.run(
        ["bash", str(MAKE_REPORT), str(md), str(out)],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return False, (proc.stderr or proc.stdout or "build failed").strip()[-300:]
    return True, ""


def first_difference(left: list[str], right: list[str]) -> str:
    """Return a readable description of the first difference between two lists.

    Args:
        left: Committed twin's paragraphs.
        right: Rebuilt twin's paragraphs.

    Returns:
        A one-line description.
    """
    for index, (a, b) in enumerate(zip(left, right)):
        if a != b:
            return f"paragraph {index + 1}: twin {a[:90]!r} / rebuild {b[:90]!r}"
    if len(left) != len(right):
        longer = "twin" if len(left) > len(right) else "rebuild"
        return f"{longer} has {abs(len(left) - len(right))} extra paragraph(s)"
    return "no difference"


def check_pair(md: Path) -> tuple[list[str], str]:
    """Compare one Markdown report with its DOCX twin.

    Args:
        md: Markdown path; the twin is the same path with a .docx suffix.

    Returns:
        ``(problems, status)`` where status is PASS, FAIL or NO-TWIN.
    """
    docx = md.with_suffix(".docx")
    rel = md.relative_to(ROOT)
    if not docx.is_file():
        return [], "NO-TWIN"

    problems: list[str] = []
    md_raw = md.read_text(encoding="utf-8")
    md_marked = strip_markers(md_raw)
    dx_paras = docx_paragraphs(docx)
    dx_text = "\n".join(dx_paras)

    for name, pattern in (("percentage", PCT), ("byte size", BYTE)):
        missing = tokens(md_marked, pattern) - tokens(dx_text, pattern)
        extra = tokens(dx_text, pattern) - tokens(md_marked, pattern)
        for value in sorted(missing):
            problems.append(f"{rel}: {name} {value!r} missing from twin")
        for value in sorted(extra):
            problems.append(f"{rel}: {name} {value!r} in twin but not source")

    md_tables, md_headings = source_counts(md)
    dx_tables, dx_headings = docx_counts(docx)
    if md_tables != dx_tables:
        problems.append(f"{rel}: {md_tables} markdown tables, {dx_tables} in twin")
    if md_headings != dx_headings:
        problems.append(
            f"{rel}: {md_headings} markdown headings, {dx_headings} in twin"
        )

    with tempfile.TemporaryDirectory() as tmp:
        rebuilt = Path(tmp) / "rebuild.docx"
        ok, message = rebuild(md, rebuilt)
        if not ok:
            problems.append(f"{rel}: rebuild failed: {message}")
        else:
            new_paras = docx_paragraphs(rebuilt)
            if new_paras != dx_paras:
                problems.append(
                    f"{rel}: twin is not the pipeline's output - "
                    f"{first_difference(dx_paras, new_paras)}"
                )

    return problems, "FAIL" if problems else "PASS"


def targets(argv: list[str]) -> list[Path]:
    """Return the Markdown files to check.

    Args:
        argv: Explicit paths, or empty for the repository default.

    Returns:
        A list of Markdown paths.
    """
    if argv:
        return [Path(a).resolve() for a in argv]
    found: list[Path] = []
    for directory in (ROOT, ROOT / "reports"):
        if not directory.exists():
            continue
        found.extend(sorted(directory.glob("*.md")))
    return found


def main() -> int:
    """Check every requested pair and report the result.

    Returns:
        0 when every publication report agrees with its twin, otherwise 1.
    """
    md_files = targets(sys.argv[1:])
    problems: list[str] = []
    checked = 0
    for md in md_files:
        if md.name.startswith("~$"):
            continue
        rel = str(md.relative_to(ROOT))
        if rel in NOTES:
            print(f"NOTE {rel} (a note, not a publication report)")
            continue
        found, status = check_pair(md)
        checked += 1
        if status == "NO-TWIN":
            print(f"FAIL {rel}: no .docx twin")
            problems.append(f"{rel}: no .docx twin")
            continue
        if found:
            problems.extend(found)
            print(f"FAIL {rel}")
        else:
            print(f"PASS {rel}")

    print()
    if problems:
        print(f"{len(problems)} problem(s) in {checked} report(s):")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print(f"all {checked} publication report(s) agree with their twins")
    return 0


if __name__ == "__main__":
    sys.exit(main())
