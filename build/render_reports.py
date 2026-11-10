#!/usr/bin/env python3
"""
Render every report from its template and the current facts.

    python3 build/render_reports.py               # render templates/ -> reports, rebuild changed DOCX twins
    python3 build/render_reports.py --no-docx     # Markdown only
    python3 build/render_reports.py --check       # exit 1 if a report differs from its rendering
    python3 build/render_reports.py --templatize  # bind remaining literals (new report: make its template)

The template for ``<path>.md`` is ``templates/<path>.md``. ``--templatize``
refuses to write a template that does not render back to its report byte for
byte, and it records every figure it left literal in
out/templatize_unbound.json, so the figures a person still owns are listed.

``--stale OLD_FACTS`` lists literal figures, in sentences or rows about one
editor, that equal one of that editor's old facts which has since changed:
the numbers an update would otherwise leave behind.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "build"))
sys.path.insert(0, str(ROOT))
import reportgen  # noqa: E402
from perf.analysis.anti_ranking import assert_markdown_no_editor_speed_ranking  # noqa: E402

TEMPLATES = ROOT / "templates"
FACTS = ROOT / "out" / "facts.json"
MAIN = "Open-Source DOCX Editors Re-verified Against Code and Measured Round-Trip (2026).md"
# Reports published with a DOCX twin, built by build/make_report.sh.
TWINS = {MAIN} | {
    f"reports/{n}.md" for n in (
        "Report A - Serialization by Namespace (2026)",
        "Report A2 - Pass-Through (2026)",
        "Report B - Malformed Parts, Causes and Repair (2026)",
        "Report C - Rendering Versus Word (2026)",
        "Report D - Safety, Resource Bombs and Hostile Input (2026)",
        "Report D1 - Jubarte on the Hostile Packages (2026)",
        "Report D2 - What Word Protects Against (2026)",
        "Report E - Speed, Opening and Saving a Document (2026)",
        "Report E2 - Speed in the Browser (2026)",
    )
}


def reports() -> list[str]:
    rels = [MAIN]
    rels += sorted(str(p.relative_to(ROOT)) for p in (ROOT / "reports").glob("*.md"))
    rels += sorted(str(p.relative_to(ROOT)) for p in (ROOT / "reports" / "extras").glob("*.md"))
    return rels


def load_facts(path: Path = FACTS) -> dict:
    return json.loads(path.read_text())


def templatize(facts: dict) -> int:
    log, total_bound = {}, 0
    for rel in reports():
        text = (ROOT / rel).read_text()
        dest = TEMPLATES / rel
        # Incremental: an existing template keeps its placeholders (and any
        # binding made by hand); only its remaining literals are considered.
        source = dest.read_text() if dest.exists() else text
        if reportgen.render(source, facts) != text:
            print(f"REFUSED {rel}: the report differs from its template; render or reconcile first", file=sys.stderr)
            return 1
        tpl, unbound = reportgen.templatize(source, facts)
        if reportgen.render(tpl, facts) != text:
            print(f"REFUSED {rel}: the template does not render back to the report", file=sys.stderr)
            return 1
        bound = tpl.count("{{")
        total_bound += bound
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(tpl)
        log[rel] = unbound
        print(f"{bound:4d} bound  {len(unbound):4d} literal  {rel}")
    (ROOT / "out" / "templatize_unbound.json").write_text(json.dumps(log, indent=1, ensure_ascii=False) + "\n")
    print(f"templates: {len(log)} reports, {total_bound} placeholders")
    return 0


def render_all(facts: dict, check: bool, docx: bool, all_twins: bool = False) -> int:
    changed, missing = [], []
    for anti in sorted(TEMPLATES.rglob("*.md")):
        try:
            assert_markdown_no_editor_speed_ranking(anti.read_text())
        except ValueError as exc:
            print(f"ANTI-RANKING {anti.relative_to(TEMPLATES)}: {exc}", file=sys.stderr)
            missing.append(f"{anti}: anti-ranking guard")
    for tpl in sorted(TEMPLATES.rglob("*.md")):
        rel = str(tpl.relative_to(TEMPLATES))
        try:
            text = reportgen.render(tpl.read_text(), facts)
        except KeyError as e:
            missing.append(f"{rel}: no fact {e}")
            continue
        dest = ROOT / rel
        if dest.exists() and dest.read_text() == text:
            continue
        changed.append(rel)
        if not check:
            dest.write_text(text)
    for m in missing:
        print("MISSING", m, file=sys.stderr)
    for rel in changed:
        print(("DIFFERS " if check else "rendered ") + rel)
    if check:
        return 1 if changed or missing else 0
    if docx:
        # A twin also depends on figures and on the build itself, so a release rebuilds every one.
        for rel in (sorted(TWINS) if all_twins else changed):
            if rel in TWINS:
                subprocess.run(["bash", str(ROOT / "build" / "make_report.sh"), str(ROOT / rel)], check=True)
    return 1 if missing else 0


def stale(old: dict, new: dict) -> int:
    """Literal figures that read as an old fact whose value has changed."""
    hits = 0
    for tpl in sorted(TEMPLATES.rglob("*.md")):
        rel = str(tpl.relative_to(TEMPLATES))
        for h in reportgen.stale(tpl.read_text(), old, new):
            hits += 1
            print(f"STALE {rel}:{h['line']} {h['literal']} was {h['key']}, now {h['now']} :: {h['context']}")
    print(f"stale literals: {hits}")
    return 1 if hits else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--facts", default=str(FACTS))
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--no-docx", action="store_true")
    ap.add_argument("--all-twins", action="store_true", help="rebuild every DOCX twin, changed or not (a release does)")
    ap.add_argument("--templatize", action="store_true")
    ap.add_argument("--stale", metavar="OLD_FACTS")
    a = ap.parse_args()
    facts = load_facts(Path(a.facts))
    if a.templatize:
        return templatize(facts)
    if a.stale:
        return stale(load_facts(Path(a.stale)), facts)
    return render_all(facts, a.check, not a.no_docx, a.all_twins)


if __name__ == "__main__":
    sys.exit(main())
