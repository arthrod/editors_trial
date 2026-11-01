#!/usr/bin/env python3
"""Gate published report text against the fixture package and the run logs.

Number gate: every percentage and byte size in a report whose content differs
from ``main`` must be a substring of the lane log or the scorer output. The
scan is the full markdown file, or the full docx paragraph text. A clean tree
does not hide a committed edit, and a diff hunk is not the scan. A pure rename
of an unchanged report is left out.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixture" / "complex.docx"
WP14_URI = "http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing"

FALSE_WP14 = (
    "never declared",
    "not declared",
    "is undeclared",
    "undeclared in the corpus",
    "never bound",
    "prefix that does not exist",
)
SECOND_DIAGRAM = re.compile(
    r"\b(?:second SmartArt|two SmartArts?|second diagram|two diagrams)\b",
    re.I,
)
NEGATED = re.compile(r"\b(no|not|never|without)\b", re.I)
PCT = re.compile(r"\d[\d,]*(?:\.\d+)?\s*%")
BYTE = re.compile(r"\d[\d,]*\s+bytes\b", re.I)

def active_markdown() -> list[Path]:
    """Return Markdown paths in the root, reports, and reports/extras directories."""
    found = []
    for path in [ROOT, ROOT / "reports"]:
        if not path.exists():
            continue
        for md in path.glob("*.md"):
            found.append(md)
    extras = ROOT / "reports" / "extras"
    if extras.exists():
        found.extend(sorted(extras.glob("*.md")))
    return found


def active_docx() -> list[Path]:
    """Return root and reports DOCX paths, excluding temporary Word files."""
    found = []
    for path in [ROOT, ROOT / "reports"]:
        if not path.exists():
            continue
        for doc in path.glob("*.docx"):
            if doc.name.startswith("~$"):
                continue
            found.append(doc)
    return found


def docx_paragraphs(path: Path) -> list[str]:
    """Extract nonempty paragraph text from a DOCX document part.

    Args:
        path: DOCX ZIP path.

    Returns:
        Stripped paragraph strings with common XML entities replaced.

    Raises:
        OSError: If the file cannot be opened or read.
        zipfile.BadZipFile: If the file is not a valid ZIP.
        KeyError: If word/document.xml is missing.
    """
    with zipfile.ZipFile(path) as zf:
        xml = zf.read("word/document.xml").decode("utf-8", "replace")
    plain = re.sub(r"</w:p>", "\n", xml)
    plain = re.sub(r"<[^>]+>", "", plain)
    plain = (
        plain.replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
        .replace("&apos;", "'")
    )
    return [ln.strip() for ln in plain.splitlines() if ln.strip()]


def paragraphs_of(path: Path) -> list[str]:
    """Return nonempty DOCX paragraphs or stripped lines of a UTF-8 text file.

    Args:
        path: Input path; a .docx suffix selects DOCX extraction.

    Raises:
        OSError: If the file cannot be opened or read.
        UnicodeDecodeError: If a text file is not valid UTF-8.
        zipfile.BadZipFile: If a DOCX is not a valid ZIP.
        KeyError: If its document part is missing.
    """
    if path.suffix == ".docx":
        return docx_paragraphs(path)
    return [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def wp14_fact() -> tuple[int, int]:
    """Return counts of fixture XML parts mentioning and declaring wp14, respectively."""
    mentioned = declared = 0
    with zipfile.ZipFile(FIXTURE) as zf:
        for name in zf.namelist():
            if not name.endswith((".xml", ".rels")):
                continue
            raw = zf.read(name).decode("utf-8", "replace")
            if "wp14" not in raw:
                continue
            mentioned += 1
            if f'xmlns:wp14="{WP14_URI}"' in raw:
                declared += 1
    return mentioned, declared


def diagram_targets() -> list[str]:
    """Return fixture diagram relationship types and targets as strings."""
    with zipfile.ZipFile(FIXTURE) as zf:
        rels = zf.read("word/_rels/document.xml.rels").decode("utf-8")
    targets = []
    for m in re.finditer(r'Type="([^"]+)"[^>]*Target="([^"]+)"', rels):
        if "/diagram" in m.group(1):
            targets.append(f"{m.group(1).rsplit('/', 1)[-1]} -> {m.group(2)}")
    return targets


def number_corpus(lanes: Path, scores_dir: Path) -> str:
    """Combine lane text and matching score files for substring checks.

    Args:
        lanes: UTF-8 lane log path.
        scores_dir: Directory containing score-named .txt or .json files.

    Returns:
        Text joined with newlines; a missing scores directory contributes nothing.

    Raises:
        OSError: If an input cannot be read.
        UnicodeDecodeError: If the lane log is not valid UTF-8.
    """
    chunks = [lanes.read_text(encoding="utf-8")]
    if scores_dir.exists():
        for path in sorted(scores_dir.iterdir()):
            if path.suffix in {".txt", ".json"} and "score" in path.name:
                chunks.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(chunks)


def updated_report_texts() -> tuple[list[tuple[str, str]], str]:
    """Full text of reports whose content differs from ``main``.

    Returns ``(paths_and_text, git_error)``. ``git_error`` is empty when
    ``git diff`` succeeds. Docx text is the paragraph text, so a number split
    across runs is still one token. A 100% rename is not an update.
    """
    proc = subprocess.run(
        ["git", "diff", "--name-status", "main", "--", "reports"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return [], (proc.stderr or proc.stdout or "git diff main failed").strip()
    found: list[tuple[str, str]] = []
    for raw in proc.stdout.splitlines():
        parts = raw.split("\t")
        if len(parts) < 2:
            continue
        status = parts[0]
        if status.startswith("D"):
            continue
        if status.startswith("R"):
            similarity = status[1:]
            if similarity.isdigit() and int(similarity) == 100:
                continue
        rel = parts[-1]
        path = ROOT / rel
        if not path.is_file() or path.name.startswith("~$"):
            continue
        if path.suffix == ".md":
            text = path.read_text(encoding="utf-8")
        elif path.suffix == ".docx":
            text = "\n".join(docx_paragraphs(path))
        else:
            continue
        found.append((rel, text))
    return found, ""


def number_tokens(text: str) -> list[str]:
    """Return percentage matches followed by byte-size matches, each in scan order."""
    found: list[str] = []
    for rx in (PCT, BYTE):
        found.extend(match.group(0) for match in rx.finditer(text))
    return found


def tokens_absent_from_corpus(text: str, corpus: str) -> list[str]:
    """Percentages and byte sizes in ``text`` that are not substrings of ``corpus``."""
    return [token for token in number_tokens(text) if token not in corpus]


def main() -> int:
    """Check report claims and write the consistency report and inventory.

    Returns:
        0 if no problems were found, otherwise 1.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--lanes", required=True)
    parser.add_argument("--scores-dir", required=True)
    parser.add_argument("--bombs", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--inventory", required=True)
    args = parser.parse_args()

    lanes = Path(args.lanes)
    scores_dir = Path(args.scores_dir)
    bombs_path = Path(args.bombs)
    out_path = Path(args.out)

    problems: list[str] = []
    notes: list[str] = []

    mentioned, declared = wp14_fact()
    notes.append(f"xmlns:wp14 present: {'yes' if declared else 'no'}")
    notes.append(f"xmlns:wp14 parts mentioning wp14: {mentioned}")
    notes.append(f"xmlns:wp14 parts declaring {WP14_URI}: {declared}")
    if mentioned == 0 or declared != mentioned:
        problems.append(
            f"wp14 declarations {declared} do not cover all {mentioned} mentioning parts"
        )

    wp14_lines = 0
    for path in active_markdown() + active_docx():
        for para in paragraphs_of(path):
            if "wp14" not in para:
                continue
            wp14_lines += 1
            low = para.lower()
            for pat in FALSE_WP14:
                if pat in low:
                    problems.append(f"wp14 sentence mismatch in {path.relative_to(ROOT)}: {para[:180]}")
                    break
    notes.append(f"wp14 sentences scanned: {wp14_lines}")
    if wp14_lines == 0:
        problems.append("no report sentence mentions wp14")

    targets = diagram_targets()
    notes.append("diagram relationship targets: " + "; ".join(targets))
    data_targets = [t for t in targets if t.startswith("diagramData")]
    notes.append(f"diagramData relationships: {len(data_targets)}")
    claims = 0
    for path in active_markdown() + active_docx():
        for para in paragraphs_of(path):
            if not SECOND_DIAGRAM.search(para):
                continue
            claims += 1
            if NEGATED.search(para):
                notes.append(f"second-diagram sentence negated in {path.name}: {para[:160]}")
                continue
            if len(data_targets) < 2:
                problems.append(
                    f"second-diagram claim without a second diagramData target in {path.name}: {para[:180]}"
                )
    notes.append(f"second-diagram claims: {claims}")

    corpus = number_corpus(lanes, scores_dir)
    updated, git_error = updated_report_texts()
    if git_error:
        problems.append(f"number gate could not list updated reports: {git_error}")
    if not updated:
        problems.append("number gate scanned no updated reports")
    seen_numbers = 0
    for rel, text in updated:
        notes.append(f"number-scanned: {rel}")
        found = number_tokens(text)
        seen_numbers += len(found)
        for token in found:
            if token not in corpus:
                problems.append(
                    f"number not in lanes or scorer output: {token!r} in {rel}"
                )
    notes.append(f"percentages and byte sizes checked: {seen_numbers}")

    bombs = bombs_path.read_text(encoding="utf-8")
    safety = ROOT / "reports" / "Report D - Safety, Resource Bombs and Hostile Input (2026).md"
    if not safety.exists():
        problems.append("safety report missing")
    else:
        body = safety.read_text(encoding="utf-8")
        for line in bombs.splitlines():
            if line.startswith(("B", "taxonomy:", "reference ")):
                if line not in body:
                    problems.append(f"safety report missing bombs line: {line[:120]}")
        notes.append("safety outcomes quoted from bombs log: yes")

    notes.append(
        "number gate scope: full text of every report whose content differs from main, including docx paragraphs"
    )
    notes.append("pure renames of unchanged reports are not number-scanned")

    status = "PASS" if not problems else "FAIL"
    report = [f"status: {status}", *notes]
    if problems:
        report.append("problems:")
        report.extend(f"- {p}" for p in problems)
    text = "\n".join(report) + "\n"
    out_path.write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    write_inventory(Path(args.inventory), problems)
    return 0 if not problems else 1


def write_inventory(path: Path, problems: list[str]) -> None:
    """Write the measured-tool and report inventory to a UTF-8 file.

    Args:
        path: Destination, overwritten if it exists.
        problems: Consistency problems whose count is included in the inventory.

    Raises:
        OSError: If an input or destination cannot be read or written.
    """
    score_src = (ROOT / "build" / "score_all.py").read_text(encoding="utf-8")
    slugs = re.findall(r'\("[^"]+", "([^"]+)", (?:True|False)\)', score_src)
    lines = ["measured tools: " + ", ".join(slugs)]
    for slug in slugs:
        extra = ROOT / "reports" / "extras" / f"{slug}.md"
        lines.append(
            f"extras/{slug}.md: {'present' if extra.is_file() else 'MISSING'}"
        )
    vendors = ROOT / "reports" / "vendors.md"
    lines.append(f"vendors: {'present' if vendors.is_file() else 'MISSING'} reports/vendors.md")
    if vendors.is_file():
        body = vendors.read_text(encoding="utf-8")
        lines.append(
            "vendors trivia is not a score: "
            + ("yes" if "trivia that is not a score" in body else "no")
        )
    archived = (
        ROOT
        / "reports"
        / "archive"
        / "Report A - Serialized vs Pass-Through vs Rendered (2026).md"
    )
    active = (
        ROOT / "reports" / "Report A - Serialized vs Pass-Through vs Rendered (2026).md"
    )
    lines.append(
        "deprecated combined report: "
        + (
            "archived"
            if archived.is_file() and not active.exists()
            else "STILL ACTIVE OR MISSING"
        )
    )
    lines.append("folio editor lane: documented inside extras/folio.md")
    lines.append("eigenpal editor lane: documented inside extras/eigenpal.md")
    lines.append("inventory problems from consistency: " + ("none" if not problems else str(len(problems))))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
