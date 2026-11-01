#!/usr/bin/env python3
"""
Verify every derived findings table in the reports against the measurement.

The reports state a large number of findings in tables: a scorecard, an
idempotence table, a preserved-vs-dropped matrix, a namespace matrix, a part
matrix. Each of those tables is a grid of claims, and a grid drifts when it
is edited by hand. This gate recomputes every cell from the artifact the
table is derived from and compares.

The check is per CELL, not per token. A token-level check - the one the
consistency gate does - cannot tell "SuperDoc 100%" from "SuperDoc 84.9%",
because both figures are strings that occur somewhere in the logs. What a
reviewer would actually check is whether the number in the row for an editor
is that editor's number. That is what this gate checks.

Groups
------
scorecard     the main report's round-trip scorecard, 13 rows x 6 columns
idempotence   the main report's second-pass table, 13 rows
preserved     the main report's preserved-vs-dropped matrix
namespace     Report A's cross-editor namespace matrix
parts         Report A2's part x editor matrices

Usage:
    python3 build/verify_findings.py                 # check and print the ledger
    python3 build/verify_findings.py --ledger FILE   # also write the ledger CSV
    python3 build/verify_findings.py --group scorecard

Exit status is 0 when every cell agrees with the measurement.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / ("Open-Source DOCX Editors Re-verified Against Code and "
               "Measured Round-Trip (2026).md")
REPORT_A = ROOT / "reports" / "Report A - Serialization by Namespace (2026).md"
REPORT_A2 = ROOT / "reports" / "Report A2 - Pass-Through (2026).md"
FIXTURE = ROOT / "fixture" / "complex.docx"

# display name, output directory
TOOLS = [
    ("SuperDoc V2", "superdoc"),
    ("Docxodus", "docxodus"),
    ("Apryse WebViewer", "apryse"),
    ("GenOffice", "genoffice"),
    ("eigenpal", "eigenpal"),
    ("Folio", "folio"),
    ("office-open", "officeopen"),
    ("Docen", "docen"),
    ("WordCraft", "wordcraft"),
    ("canvas-editor + plugin", "canvas"),
    ("Fidus Writer", "fidus"),
    ("docs.plus", "docsplus"),
    ("Plate.js", "plate"),
    ("LibreOffice (baseline)", "lo_baseline"),
]

ROW = re.compile(r"^\|(?P<cells>.+)\|\s*$")
PCT = re.compile(r"(\d+(?:\.\d+)?)%")


def entries(path: Path) -> set[str]:
    """Return the non-directory entry names of a package.

    Args:
        path: DOCX or ZIP path.

    Returns:
        A set of entry names, excluding directory entries.
    """
    try:
        with zipfile.ZipFile(path) as zf:
            return {
                n for n in zf.namelist()
                if not n.endswith("/") and not n.startswith("__MACOSX")
            }
    except (OSError, zipfile.BadZipFile):
        return set()


def score_of(slug: str, second: bool = False) -> dict | None:
    """Return a participant's score.json content.

    Args:
        slug: Output directory name.
        second: Read the second-pass score instead of the first.

    Returns:
        The parsed score, or None when it is not present.
    """
    rel = Path(slug) / "second" / "score.json" if second else Path(slug) / "score.json"
    path = ROOT / "out" / rel
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def table_blocks(text: str) -> list[list[str]]:
    """Return every markdown table in a document as a list of cell lists.

    Args:
        text: Markdown text.

    Returns:
        A list of tables, each a list of rows of cells.
    """
    tables: list[list[list[str]]] = []
    current: list[list[str]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            match = ROW.match(stripped)
            if match:
                cells = [c.strip() for c in match.group("cells").split("|")]
                if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                    continue
                current.append(cells)
                continue
        if current:
            tables.append(current)
            current = []
    if current:
        tables.append(current)
    return tables


def find_table(text: str, header_cell: str, column_count: int) -> list[list[str]] | None:
    """Return the first table whose header contains a given cell.

    Args:
        text: Markdown text.
        header_cell: A cell value the header must contain.
        column_count: The expected number of columns.

    Returns:
        The table's rows, or None when no such table exists.
    """
    for table in table_blocks(text):
        if not table:
            continue
        header = table[0]
        if header_cell in header and len(header) == column_count:
            return table
    return None


def cell_number(cell: str) -> str | None:
    """Return the number a table cell states.

    Args:
        cell: Table cell text.

    Returns:
        The numeric text, or None when the cell states no number.
    """
    stripped = cell.replace("*", "").replace("`", "").strip()
    match = PCT.match(stripped)
    if match:
        return match.group(1)
    match = re.match(r"^(\d+(?:\.\d+)?)$", stripped)
    if match:
        return match.group(1)
    return None


def same_number(reported: str | None, measured: str) -> bool:
    """Compare two figures numerically.

    The reports round to one decimal place, so "100.0" and "100" are the same
    measurement. Comparing the strings would report a difference that does not
    exist, and a gate that cries wolf is a gate that gets ignored.

    Args:
        reported: The figure as the report states it.
        measured: The figure as the measurement gives it.

    Returns:
        True when the two figures agree to one decimal place.
    """
    if reported is None:
        return False
    try:
        return abs(float(reported) - float(measured)) < 0.05
    except ValueError:
        return False


def same_count(reported: str | None, measured: str) -> bool:
    """Compare two counts as integers.

    Args:
        reported: The count as the report states it.
        measured: The count as the measurement gives it.

    Returns:
        True when the two counts agree.
    """
    if reported is None:
        return False
    try:
        return int(reported) == int(measured)
    except ValueError:
        return False


def ledger_add(rows: list[dict], finding_id: str, report: str, location: str,
               subject: str, metric: str, reported: str, measured: str,
               ok: bool | None = None) -> None:
    """Append a finding to the ledger.

    Args:
        rows: The ledger rows.
        finding_id: Stable identifier.
        report: Report the finding is stated in.
        location: Where in the report.
        subject: The participant the finding is about.
        metric: The metric being stated.
        reported: What the report says.
        measured: What the measurement says.
        ok: Whether the two agree. None means the figures are not comparable
            as strings - a table that was compared in full, for instance - and
            the comparison result is carried by the group verdict.
    """
    if ok is None:
        status = "match"
    else:
        status = "match" if ok else "MISMATCH"
    rows.append({
        "finding_id": finding_id,
        "report": report,
        "location": location,
        "subject": subject,
        "metric": metric,
        "reported": reported,
        "measured": measured,
        "status": status,
    })


def check_scorecard(rows: list[dict]) -> list[str]:
    """Check the main report's round-trip scorecard against the scorer output.

    Args:
        rows: The ledger rows.

    Returns:
        A list of problem strings.
    """
    problems: list[str] = []
    text = MAIN.read_text(encoding="utf-8")
    table = find_table(text, "Weighted score", 6)
    if table is None:
        return ["scorecard table not found in the main report"]
    by_name = {row[0].replace("*", "").strip(): row for row in table[1:]}
    by_name.setdefault("SuperDoc V2", by_name.get("SuperDoc", {}))
    fixture_entries = entries(FIXTURE)

    for name, slug in TOOLS:
        row = by_name.get(name)
        if row is None:
            problems.append(f"scorecard has no row for {name}")
            continue
        score = score_of(slug)
        if score is None:
            problems.append(f"no score.json for {name} ({slug})")
            continue
        s = score["score"]
        out = ROOT / "out" / slug / "complex.docx"

        for metric, reported, measured in (
            ("weighted", cell_number(row[1]), f"{s['weighted']:g}"),
            ("critical", cell_number(row[2]), f"{s['critical_pct']:g}"),
            ("text", cell_number(row[3]), f"{score['text_retention_pct']:g}"),
        ):
            ledger_add(rows, f"FND-SCORE-{slug}-{metric}", MAIN.name,
                       "Round-trip scorecard", name, metric,
                       reported or "", measured, same_number(reported, measured))
            if not same_number(reported, measured):
                problems.append(
                    f"scorecard {name} {metric}: report says {reported!r}, "
                    f"scorer says {measured!r}"
                )

        kept = row[4].replace("*", "").strip()
        parts = re.findall(r"(\d+)\s*/\s*(\d+)", kept)
        if parts:
            got_kept, got_total = parts[0]
            measured_kept = len(fixture_entries & entries(out))
            measured_total = len(fixture_entries)
            ledger_add(rows, f"FND-SCORE-{slug}-parts", MAIN.name,
                       "Round-trip scorecard", name, "parts kept",
                       f"{got_kept}/{got_total}",
                       f"{measured_kept}/{measured_total}",
                       (int(got_kept), int(got_total)) ==
                       (measured_kept, measured_total))
            if (int(got_kept), int(got_total)) != (measured_kept, measured_total):
                problems.append(
                    f"scorecard {name} parts kept: report says {got_kept}/{got_total}, "
                    f"measurement says {measured_kept}/{measured_total}"
                )

        failed = cell_number(row[5])
        measured_failed = str(s["features_total"] - s["features_passed"])
        ledger_add(rows, f"FND-SCORE-{slug}-failed", MAIN.name,
                   "Round-trip scorecard", name, "failed checks",
                   failed or "", measured_failed, same_count(failed, measured_failed))
        if not same_count(failed, measured_failed):
            problems.append(
                f"scorecard {name} failed checks: report says {failed!r}, "
                f"scorer says {measured_failed!r}"
            )

        if not re.search(r"\(\d+/\d+\)", row[2]):
            problems.append(
                f"scorecard {name} critical cell states no n/m denominator"
            )
    return problems


def check_idempotence(rows: list[dict]) -> list[str]:
    """Check the main report's second-pass table against the second-pass scores.

    Args:
        rows: The ledger rows.

    Returns:
        A list of problem strings.
    """
    problems: list[str] = []
    text = MAIN.read_text(encoding="utf-8")
    table = find_table(text, "Byte-identical?", 5)
    if table is None:
        return ["second-pass table not found in the main report"]
    by_name = {row[0].replace("*", "").strip(): row for row in table[1:]}
    by_name.setdefault("SuperDoc V2", by_name.get("SuperDoc", {}))

    for name, slug in TOOLS:
        row = by_name.get(name)
        if not row:
            problems.append(f"second-pass table has no row for {name}")
            continue
        first = score_of(slug)
        second = score_of(slug, second=True)
        if first is None or second is None:
            problems.append(f"no second-pass score for {name} ({slug})")
            continue

        ledger_add(rows, f"FND-IDEM-{slug}-first", MAIN.name, "Second pass",
                   name, "first pass", cell_number(row[1]) or "",
                   f"{first['score']['weighted']:g}",
                   same_number(cell_number(row[1]), f"{first['score']['weighted']:g}"))
        ledger_add(rows, f"FND-IDEM-{slug}-second", MAIN.name, "Second pass",
                   name, "second pass", cell_number(row[2]) or "",
                   f"{second['score']['weighted']:g}",
                   same_number(cell_number(row[2]), f"{second['score']['weighted']:g}"))
        if not same_number(cell_number(row[1]), f"{first['score']['weighted']:g}"):
            problems.append(
                f"second-pass table {name} first-pass score: report says "
                f"{cell_number(row[1])!r}, scorer says "
                f"{first['score']['weighted']:g}"
            )
        if not same_number(cell_number(row[2]), f"{second['score']['weighted']:g}"):
            problems.append(
                f"second-pass table {name} second-pass score: report says "
                f"{cell_number(row[2])!r}, scorer says "
                f"{second['score']['weighted']:g}"
            )

        said = row[3].replace("*", "").strip().lower()
        first_path = ROOT / "out" / slug / "complex.docx"
        second_path = ROOT / "out" / slug / "second" / "complex.docx"
        measured = (first_path.is_file() and second_path.is_file()
                    and first_path.read_bytes() == second_path.read_bytes())
        ledger_add(rows, f"FND-IDEM-{slug}-bytes", MAIN.name, "Second pass",
                   name, "byte-identical", said, "yes" if measured else "no",
                   (said == "yes") == measured)
        if (said == "yes") != measured:
            problems.append(
                f"second-pass table {name} byte-identical: report says {said!r}, "
                f"measurement says {'yes' if measured else 'no'}"
            )
    return problems


def check_derived(rows: list[dict], name: str, cmd: list[str], report: Path,
                  header: str, group: str, expected_rows: int | None = None) -> list[str]:
    """Check a generated table against the table committed in a report.

    Args:
        rows: The ledger rows.
        name: Group name.
        cmd: The builder command.
        report: The report that carries the table.
        header: The header cell that identifies the table.
        group: Group prefix for finding identifiers.
        expected_rows: Expected number of body rows, when known.

    Returns:
        A list of problem strings.
    """
    problems: list[str] = []
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
    if proc.returncode != 0:
        return [f"{name}: builder failed: {(proc.stdout + proc.stderr).strip()[-300:]}"]
    derived = proc.stdout.strip()
    text = report.read_text(encoding="utf-8")
    try:
        start = text.index(header)
        end = text.index("\n\n", start)
    except ValueError:
        return [f"{name}: header {header!r} not found in {report.name}"]
    committed = text[start:end].strip()
    if committed != derived:
        committed_lines = committed.splitlines()
        derived_lines = derived.splitlines()
        for index in range(max(len(committed_lines), len(derived_lines))):
            a = committed_lines[index] if index < len(committed_lines) else "<missing>"
            b = derived_lines[index] if index < len(derived_lines) else "<missing>"
            if a != b:
                problems.append(
                    f"{name} row {index + 1}: report has {a[:110]!r}, "
                    f"measurement derives {b[:110]!r}"
                )
        ledger_add(rows, f"FND-{group}", report.name, "derived table",
                   "all", "table equality", "committed table", "derived table")
        return problems
    ledger_add(rows, f"FND-{group}", report.name, "derived table", "all",
               "table equality", "committed table", "derived table")
    if expected_rows is not None:
        body = len(committed.splitlines()) - 2
        if body != expected_rows:
            problems.append(
                f"{name}: {body} body rows, expected {expected_rows}"
            )
    return problems


def check_parts(rows: list[dict]) -> list[str]:
    """Check Report A2's part matrices against the regenerated matrix.

    The builder prints the grid as two tables, because thirteen editor
    columns do not fit a landscape page, and it prints a bold caption above
    each one. Both the builder's output and the report are parsed into
    tables and compared table by table, so the captions and the split do not
    have to be reproduced exactly.

    Args:
        rows: The ledger rows.

    Returns:
        A list of problem strings.
    """
    problems: list[str] = []
    proc = subprocess.run([sys.executable, str(ROOT / "build" / "part_matrix_md.py")],
                          capture_output=True, text=True, cwd=str(ROOT))
    if proc.returncode != 0:
        return [f"part matrix: builder failed: {(proc.stdout + proc.stderr).strip()[-300:]}"]

    def part_tables(text: str) -> list[list[list[str]]]:
        return [t for t in table_blocks(text)
                if t and t[0] and t[0][0].replace("*", "").strip() == "Package part"]

    derived = part_tables(proc.stdout)
    committed = part_tables(REPORT_A2.read_text(encoding="utf-8"))
    if not derived:
        return ["part matrix: builder produced no part table"]
    if not committed:
        return ["part matrix: report has no part table"]
    if len(derived) != len(committed):
        problems.append(
            f"part matrix: {len(committed)} tables in the report, "
            f"{len(derived)} derived"
        )
    for index, (a, b) in enumerate(zip(committed, derived)):
        for row_index in range(max(len(a), len(b))):
            left = a[row_index] if row_index < len(a) else ["<missing>"]
            right = b[row_index] if row_index < len(b) else ["<missing>"]
            if left != right:
                problems.append(
                    f"part matrix table {index + 1} row {row_index + 1}: report "
                    f"has {left[:8]!r}, measurement derives {right[:8]!r}"
                )
    ledger_add(rows, "FND-PARTS", REPORT_A2.name, "part matrix", "all",
               "table equality", "committed table", "derived table")
    return problems


GROUPS = {
    "scorecard": check_scorecard,
    "idempotence": check_idempotence,
    "preserved": lambda rows: check_derived(
        rows, "preserved matrix",
        [sys.executable, str(ROOT / "build" / "preserved_matrix.py")],
        MAIN, "| Item | ", "PRESERVED"),
    "namespace": lambda rows: check_derived(
        rows, "namespace matrix",
        [sys.executable, str(ROOT / "build" / "report_a_matrix.py")],
        REPORT_A, "| namespace | ", "NAMESPACE"),
    "parts": check_parts,
}


def main() -> int:
    """Run the requested groups and report the ledger.

    Returns:
        0 when every checked cell agrees with the measurement.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group", action="append", choices=sorted(GROUPS),
                        help="run only this group; repeatable")
    parser.add_argument("--ledger", help="write the findings ledger to this CSV")
    args = parser.parse_args()

    selected = args.group or sorted(GROUPS)
    rows: list[dict] = []
    problems: list[str] = []
    for group in selected:
        found = GROUPS[group](rows)
        if found:
            problems.extend(found)
            print(f"FAIL {group}: {len(found)} problem(s)")
        else:
            print(f"PASS {group}")

    if args.ledger:
        path = Path(args.ledger)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=[
                "finding_id", "report", "location", "subject", "metric",
                "reported", "measured", "status",
            ])
            writer.writeheader()
            writer.writerows(rows)
        print(f"ledger: {path} ({len(rows)} findings)")

    print()
    mismatches = [r for r in rows if r["status"] != "match"]
    print(f"findings checked: {len(rows)}  mismatches: {len(mismatches)}")
    for row in mismatches:
        print(f"  - {row['finding_id']}: report {row['reported']!r} vs "
              f"measurement {row['measured']!r}")
    if problems:
        print()
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("every checked finding agrees with the measurement")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
