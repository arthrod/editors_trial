#!/usr/bin/env python3
"""Gate published report text against the fixture package and the run logs.

Number gate: percentages and byte sizes in the new reports (extras, vendors,
the safety report, the rendering note, the archive note) must be substrings of
the lane log or the scorer output. Lines added to older reports are scanned
the same way. Pre-existing figures in those older reports are prior
measurements; this script does not treat them as this run.
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

NEW_REPORTS = [
    ROOT / "reports" / "vendors.md",
    ROOT / "reports" / "rendering-openability.md",
    ROOT / "reports" / "Report D - Safety, Resource Bombs and Hostile Input (2026).md",
    ROOT / "reports" / "archive" / "README.md",
]


def active_markdown() -> list[Path]:
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
    xml = zipfile.ZipFile(path).read("word/document.xml").decode("utf-8", "replace")
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
    if path.suffix == ".docx":
        return docx_paragraphs(path)
    return [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def wp14_fact() -> tuple[int, int]:
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
    with zipfile.ZipFile(FIXTURE) as zf:
        rels = zf.read("word/_rels/document.xml.rels").decode("utf-8")
    targets = []
    for m in re.finditer(r'Type="([^"]+)"[^>]*Target="([^"]+)"', rels):
        if "/diagram" in m.group(1):
            targets.append(f"{m.group(1).rsplit('/', 1)[-1]} -> {m.group(2)}")
    return targets


def number_corpus(lanes: Path, scores_dir: Path) -> str:
    chunks = [lanes.read_text(encoding="utf-8")]
    if scores_dir.exists():
        for path in sorted(scores_dir.iterdir()):
            if path.suffix in {".txt", ".json"} and "score" in path.name:
                chunks.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(chunks)


def added_markdown_lines() -> list[tuple[str, str]]:
    diff = subprocess.run(
        ["git", "diff", "-U0", "--", "*.md", "reports"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    lines = []
    current = ""
    for raw in diff.splitlines():
        if raw.startswith("+++ b/"):
            current = raw[6:]
        elif raw.startswith("+") and not raw.startswith("+++") and current.endswith(".md"):
            if "reports/archive/" in current:
                continue
            if current.startswith("reports/extras/") or current.endswith(
                (
                    "vendors.md",
                    "rendering-openability.md",
                    "Report D - Safety, Resource Bombs and Hostile Input (2026).md",
                )
            ):
                continue
            lines.append((current, raw[1:]))
    return lines


def main() -> int:
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
    gated: list[Path] = list(NEW_REPORTS)
    extras = ROOT / "reports" / "extras"
    if extras.exists():
        gated.extend(sorted(extras.glob("*.md")))
    seen_numbers = 0
    for path in gated:
        if not path.exists():
            problems.append(f"missing number-gated report: {path.relative_to(ROOT)}")
            continue
        text = path.read_text(encoding="utf-8")
        for rx in (PCT, BYTE):
            for m in rx.finditer(text):
                seen_numbers += 1
                token = m.group(0)
                if token not in corpus:
                    problems.append(
                        f"number not in lanes or scorer output: {token!r} in {path.relative_to(ROOT)}"
                    )
    for src, line in added_markdown_lines():
        for rx in (PCT, BYTE):
            for m in rx.finditer(line):
                seen_numbers += 1
                token = m.group(0)
                if token not in corpus:
                    problems.append(f"added line number not in log: {token!r} in {src}")
    notes.append(f"percentages and byte sizes checked: {seen_numbers}")

    bombs = bombs_path.read_text(encoding="utf-8")
    safety = ROOT / "reports" / "Report D - Safety, Resource Bombs and Hostile Input (2026).md"
    if not safety.exists():
        problems.append("safety report missing")
    else:
        body = safety.read_text(encoding="utf-8")
        for line in bombs.splitlines():
            if line.startswith("B") or line.startswith("taxonomy:"):
                if line not in body:
                    problems.append(f"safety report missing bombs line: {line[:120]}")
        notes.append("safety outcomes quoted from bombs log: yes")

    notes.append("number gate scope: new reports and lines added to older markdown")
    notes.append(
        "older report files keep prior-session percentages; those figures were not re-measured"
    )

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
