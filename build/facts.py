#!/usr/bin/env python3
"""
Build out/facts.json: every measured figure a report quotes, under one key.

The reports are rendered from templates (templates/, build/render_reports.py),
and every figure in a template is a placeholder such as
``{{rt.superdoc.weighted:.1f}}``. This script is the only place those values
come from, and it reads them only from the measurement artifacts:

  rt.<tool>.*      first pass   out/<tool>/score.json and out/<tool>/complex.docx
  p2.<tool>.*      second pass  out/<tool>/second/score.json and its package
  parts.<tool>.*   part map     the output package classified against the fixture
  ver.<repo>.*     pins         the git checkouts under repos/ (and npm pins)
  stars.<repo>     stars        out/stars.json, a snapshot taken at measurement
  count.*          derived counts across tools

A key that the artifacts cannot supply is absent, never guessed, so a template
that needs it fails to render.

usage: python3 build/facts.py [--out out/facts.json]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
FIXTURE = ROOT / "fixture" / "complex.docx"
sys.path.insert(0, str(ROOT / "build"))
from part_map import classify  # noqa: E402

# Output directory under out/ for every measured participant (lanes included).
TOOLS = [
    "superdoc", "docxodus", "genoffice", "eigenpal", "eigenpal-editor", "folio",
    "folio-editor", "officeopen", "docen", "wordcraft", "canvas", "fidus",
    "docsplus", "plate", "apryse", "lo_baseline",
]
# Checkout under repos/ -> its GitHub slug.
REPOS = {
    "plate": "udecode/plate",
    "eigenpal-docx-editor": "eigenpal/docx-editor",
    "folio": "stella/folio",
    "genoffice": "genspark-ai/genoffice",
    "wordcraft": "storytold/wordcraft",
    "superdoc": "superdoc/docx-editor",
    "canvas-editor": "Hufe921/canvas-editor",
    "canvas-editor-plugin": "Hufe921/canvas-editor-plugin",
    "docen": "DemoMacro/docen",
    "office-open": "DemoMacro/office-open",
    "office-open-upstream": "akademi-ink/office-open",
    "docs-plus": "docs-plus/docs.plus",
    "fiduswriter": "fiduswriter/fiduswriter",
    "fiduswriter-document-ts": "fiduswriter/fiduswriter-document-ts",
    "fiduswriter-cli-ts": "fiduswriter/fiduswriter-cli-ts",
    "fiduswriter-pandoc-plugin-ts": "fiduswriter/fiduswriter-pandoc-plugin-ts",
    "docxodus": "JSv4/Docxodus",
}
# npm packages the harnesses load, and where the installed copy lives.
NPM = {
    "superdoc_sdk": ("@superdoc/sdk", "repos/superdoc/node_modules/.pnpm", "@superdoc+sdk@"),
    "docxodus": ("docxodus", "harness/ui/docxodus/node_modules/docxodus/package.json", None),
    "apryse": ("@pdftron/webviewer", "harness/apryse/node_modules/@pdftron/webviewer/package.json", None),
}


def parts(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as z:
        return {n: z.read(n) for n in z.namelist() if not n.endswith("/")}


def score_facts(prefix: str, score_path: Path, package: Path, facts: dict) -> None:
    res = json.loads(score_path.read_text())
    s = res["score"]
    f = {
        "weighted": s["weighted"],
        "critical_pct": s["critical_pct"],
        "critical_passed": s["critical_passed"],
        "critical_total": s["critical_total"],
        "passed": s["features_passed"],
        "total": s["features_total"],
        "failed": s["features_total"] - s["features_passed"],
        "critical_failed": s["critical_total"] - s["critical_passed"],
        "text_pct": res["text_retention_pct"],
        "text_tokens": res["text_tokens_input"],
        "text_lost": res["text_tokens_lost"],
    }
    if package.exists():
        f["bytes"] = package.stat().st_size
    for k, v in f.items():
        facts[f"{prefix}.{k}"] = v


def part_facts(tool: str, package: Path, fixture: dict, facts: dict) -> None:
    out = parts(package)
    status = classify(fixture, out)
    counts = {k: 0 for k in ("PASSTHROUGH", "REWRITTEN", "CHANGED", "DROPPED", "ADDED")}
    for v in status.values():
        counts[v] = counts.get(v, 0) + 1
    p = f"parts.{tool}"
    facts[f"{p}.total"] = len(fixture)
    facts[f"{p}.kept"] = len(fixture) - counts["DROPPED"]
    facts[f"{p}.out"] = len(out)
    for k, v in counts.items():
        facts[f"{p}.{k.lower()}"] = v
    facts[f"{p}.reserialized"] = counts["CHANGED"] + counts["REWRITTEN"]


# Report D's protection levels and their weights; an editor's grade is the
# mean weight of its ten packages. Any other level weighs 0.
LEVEL_WEIGHT = {
    "bounded-refusal": 1.0, "sanitation": 0.8, "erroring": 0.6, "bounded-delivery": 0.5,
    "failed-load-exit-zero": 0.4, "unexpanded-kept": 0.3, "not-in-view": 0.3,
}


def bomb_facts(path: Path, facts: dict) -> None:
    """bomb.<tool>.grade, bomb.<tool>.<package>.level, bomb.count.<level>, bomb.cells
    from logs/bombs/protection.txt (build/label_protection.py)."""
    levels: dict[str, dict[str, str]] = {}
    for line in path.read_text().splitlines():
        m = re.match(r"protection (\S+) (B\d+) level: (\S+)", line)
        if m:
            tool = "lo_baseline" if m.group(1) == "libreoffice" else m.group(1)
            levels.setdefault(tool, {})[m.group(2)] = m.group(3)
    counts: dict[str, int] = {}
    for tool, by_pkg in levels.items():
        facts[f"bomb.{tool}.grade"] = round(sum(LEVEL_WEIGHT.get(v, 0.0) for v in by_pkg.values()) / len(by_pkg), 2)
        for pkg, level in by_pkg.items():
            facts[f"bomb.{tool}.{pkg}.level"] = level
            counts[level] = counts.get(level, 0) + 1
    facts["bomb.cells"] = sum(counts.values())
    for level, n in counts.items():
        facts[f"bomb.count.{level}"] = n


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                          text=True, check=True).stdout.strip()


def version_facts(facts: dict) -> None:
    for d, slug in REPOS.items():
        repo = ROOT / "repos" / d
        if not (repo / ".git").exists():
            continue
        key = f"ver.{d}"
        facts[f"{key}.commit"] = git(repo, "rev-parse", "--short=9", "HEAD")
        facts[f"{key}.date"] = git(repo, "log", "-1", "--format=%cs")
        facts[f"{key}.slug"] = slug
    pinned = ROOT / "harness/superdoc-sdk/node_modules/@superdoc/sdk/package.json"
    store = ROOT / NPM["superdoc_sdk"][1]
    if pinned.exists():
        facts["ver.npm.superdoc_sdk"] = json.loads(pinned.read_text())["version"]
    elif store.exists():
        pre = NPM["superdoc_sdk"][2]
        hits = sorted(p.name[len(pre):] for p in store.iterdir() if p.name.startswith(pre))
        if hits:
            facts["ver.npm.superdoc_sdk"] = hits[-1]
    pkg = ROOT / NPM["docxodus"][1]
    if pkg.exists():
        facts["ver.npm.docxodus"] = json.loads(pkg.read_text())["version"]
    pkg = ROOT / NPM["apryse"][1]
    if pkg.exists():
        facts["ver.npm.apryse"] = json.loads(pkg.read_text())["version"]
    # The closed DOCX engine SuperDoc's repository depends on (Report A cites it).
    sd = ROOT / "repos/superdoc/packages/superdoc/package.json"
    if sd.exists():
        dep = json.loads(sd.read_text()).get("dependencies", {}).get("@superdoc/docx-engine")
        if dep:
            facts["ver.npm.superdoc_engine"] = dep.lstrip("^~")


def ui_facts(ui: Path, facts: dict) -> None:
    """Report C's capture date, stamped by build/capture_ui.sh when a full run completes."""
    stamp = ui / "captured_at.txt"
    if not stamp.exists():
        return
    day = stamp.read_text().strip()
    date.fromisoformat(day)  # ValueError on anything that is not YYYY-MM-DD
    facts["ui.date"] = day


def stamp_facts(d: Path, facts: dict) -> None:
    """Apryse's trial stamp: what it added, and which failures it could have caused."""
    path = d / "stamp.json"
    if not path.exists():
        return
    data = json.loads(path.read_text())
    facts["stamp.apryse.parts"] = len(data["stamp_parts"])
    facts["stamp.apryse.unseparable"] = len(data.get("unseparable", []))
    facts["stamp.apryse.own"] = len(data.get("own", []))
    labels = data.get("labels", {})
    facts["stamp.apryse.unseparable_labels"] = "; ".join(labels[k] for k in data.get("unseparable", []))


def build() -> dict:
    facts: dict = {}
    fixture = parts(FIXTURE)
    facts["fixture.parts"] = len(fixture)
    for t in TOOLS:
        d = OUT / t
        if (d / "score.json").exists():
            score_facts(f"rt.{t}", d / "score.json", d / "complex.docx", facts)
            if (d / "complex.docx").exists():
                part_facts(t, d / "complex.docx", fixture, facts)
        if (d / "second" / "score.json").exists():
            score_facts(f"p2.{t}", d / "second" / "score.json", d / "second" / "complex.docx", facts)
            first, second = d / "complex.docx", d / "second" / "complex.docx"
            if first.exists() and second.exists():
                facts[f"p2.{t}.identical"] = parts(first) == parts(second)
    totals = {(facts[f"rt.{t}.total"], facts[f"rt.{t}.critical_total"]) for t in TOOLS if f"rt.{t}.total" in facts}
    if len(totals) == 1:
        facts["checks.total"], facts["checks.critical"] = totals.pop()
    word = OUT / "word_verdicts.json"
    if word.exists():
        data = json.loads(word.read_text())
        facts["word.version"] = data["word"]
        for t, verdict in data["verdicts"].items():
            facts[f"word.{t}.opens"] = verdict.startswith("OPENED")
        editors = [t for t in data["verdicts"] if t not in ("lo_baseline", "eigenpal-editor", "folio-editor")]
        facts["count.word_refused"] = sum(1 for t in editors if not facts[f"word.{t}.opens"])
        facts["count.word_outputs"] = len(editors)
    if (ROOT / "logs/bombs/protection.txt").exists():
        bomb_facts(ROOT / "logs/bombs/protection.txt", facts)
    # Report A's namespace tables, generated from out/ns_map.json.
    if (OUT / "ns_map.json").exists():
        import ns_tables
        data = ns_tables.load()
        for i in range(len(ns_tables.GROUPS)):
            facts[f"ns.matrix.{i}"] = ns_tables.report_matrix(data, i)
        facts["ns.partial"] = ns_tables.partial(data)
    # Report D quotes the scorecard and the protection labels whole.
    for name in ("scorecard", "protection"):
        log = ROOT / "logs" / "bombs" / f"{name}.txt"
        if log.exists():
            facts[f"bomb.{name}"] = log.read_text().rstrip("\n")
    version_facts(facts)
    ui_facts(OUT / "ui", facts)
    stamp_facts(OUT / "apryse", facts)
    stars = OUT / "stars.json"
    if stars.exists():
        data = json.loads(stars.read_text())
        facts["stars.date"] = data["date"]
        for slug, n in data["stars"].items():
            facts[f"stars.{slug}"] = n
    editors = [t for t in TOOLS if t != "lo_baseline" and f"p2.{t}.identical" in facts]
    facts["count.p2_identical"] = sum(1 for t in editors if facts[f"p2.{t}.identical"])
    facts["count.zero_failed"] = sum(1 for t in editors if facts[f"rt.{t}.failed"] == 0)
    return dict(sorted(facts.items()))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT / "facts.json"))
    a = ap.parse_args()
    facts = build()
    Path(a.out).write_text(json.dumps(facts, indent=1, ensure_ascii=False) + "\n")
    print(f"facts: {len(facts)} keys -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
