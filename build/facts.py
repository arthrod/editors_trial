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
    facts["bomb.tools"] = len([t for t in levels if t != "lo_baseline"])   # editor rows, LibreOffice apart
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


# The release whose pinned commits the [CODE] citations were read at. Its facts
# file is kept (AGENTS.md section 5), so the commits are read from it, not typed.
CODE_READ_RELEASE = "v0.9.0"
SDKS = {"docxodus"}            # an Open XML SDK, not an editor
CLOSED = {"apryse"}            # measured only; there is no source to read
# Second lanes through an editor already counted; LibreOffice is a participant like any other.
LANES = {"eigenpal-editor", "folio-editor"}


def release_facts(path: Path, facts: dict) -> None:
    """The release date and cooldown cutoff, recorded by build/update_editors.sh when it pins."""
    if not path.exists():
        return
    data = json.loads(path.read_text())
    for k in ("date", "cutoff"):
        date.fromisoformat(data[k])  # ValueError on anything that is not YYYY-MM-DD
        facts[f"release.{k}"] = data[k]


def read_facts(old: Path, release: str, facts: dict) -> None:
    """The commits the code was read at: the version facts of the release that read it."""
    if not old.exists():
        return
    facts["read.release"] = release
    for k, v in json.loads(old.read_text()).items():
        if k.startswith("ver.") and k.rsplit(".", 1)[-1] in ("commit", "date"):
            facts["read." + k[4:]] = v


def ns_label_facts(data: dict, facts: dict) -> None:
    """Per participant: in how many namespaces it kept every name, some, or none (out/ns_map.json)."""
    measured = [n for n in data["namespaces"] if n["survival"].get("corpus", {}).get("total")]
    facts["ns.measured"] = len(measured)
    for label in data["labels"]:
        if label == "corpus":
            continue
        groups: dict[str, list[str]] = {"all_kept": [], "partial": [], "none": []}
        for n in measured:
            s = n["survival"].get(label)
            if not s or not s["total"]:
                continue
            g = "all_kept" if s["kept"] == s["total"] else "none" if s["kept"] == 0 else "partial"
            groups[g].append(f"`{n['prefix']}`")
        for g, names in groups.items():
            facts[f"ns.{label}.{g}"] = len(names)
            facts[f"ns.{label}.{g}_list"] = ", ".join(names[:-1]) + (" and " if len(names) > 1 else "") + (names[-1] if names else "")


def word_pixel_facts(path: Path, facts: dict) -> None:
    """Report C section 6.1: each output Word rendered, against Word's rendering of the corpus."""
    if not path.exists():
        return
    data = json.loads(path.read_text())
    inks = {v["corpus_ink"] for v in data.values()}
    if len(inks) == 1:
        facts["wpx.corpus_ink"] = inks.pop()
    for label, v in data.items():
        for k, name in (("pages", "pages"), ("diff_px", "diff_px"), ("pct_of_ink", "pct"), ("verdict", "verdict")):
            facts[f"wpx.{label}.{name}"] = v[k]


def lo_pixel_facts(path: Path, facts: dict) -> None:
    """Report C section 6.2: each output LibreOffice rendered, against LibreOffice's
    rendering of the corpus (build/lo_render_compare.py). A page count unlike the
    corpus's has no page-for-page comparison, shown as a dash."""
    if not path.exists():
        return
    for label, v in json.loads(path.read_text()).items():
        key = label.replace("-", "").replace(".", "")
        facts[f"lpx.{key}.pages"] = v["pages"]
        facts[f"lpx.{key}.diff_px"] = "—" if v["diff"] is None else f"{v['diff']:,}"
        facts[f"lpx.{key}.pct"] = "—" if v["pct"] is None else f"{v['pct']:.2f}%"
        facts[f"lpx.{key}.verdict"] = v["verdict"]


def smartart_facts(path: Path, facts: dict) -> None:
    """Report C section 5: the SmartArt band, its positive control and its border
    control, as build/smartart_verify.py measured them (out/smartart/verify.json)."""
    if not path.exists():
        return
    from decimal import ROUND_HALF_UP, Decimal
    d = json.loads(path.read_text())
    m, band = d["band_measurement"], d["band"]
    dpi = m["dpi"]

    def box(b):
        return f"({b[0]}, {b[1]}) – ({b[2]}, {b[3]})"

    def inches(px):
        return str((Decimal(px) / Decimal(dpi)).quantize(Decimal("0.01"), ROUND_HALF_UP))

    def total(name):
        return sum(v["diff_px"] for v in d["controls"].get(name, {}).values())

    checker = [v for v in d["controls"]["dgm_pic_checker"].values() if v["diff_px"]]
    facts.update({
        "sa.dpi": dpi, "sa.page": band["page"], "sa.w": band["w"], "sa.h": band["h"],
        "sa.band_px": f"{m['band_px']:,}", "sa.bbox": box(band["bbox"]),
        "sa.w_in": inches(band["w"]), "sa.h_in": inches(band["h"]),
        "sa.corpus_ink": m["corpus_ink_in_band"], "sa.border_ink": f"{m['border_variant_ink_in_band']:,}",
        "sa.checker": f"{total('dgm_pic_checker'):,}",
        "sa.checker_bbox": box(checker[0]["diff_bbox"]) if len(checker) == 1 else "several pages",
        "sa.marker": total("dgm_marker"), "sa.cached": total("dgm_cached"),
        "sa.border_diff": f"{m['diff_px_corpus_vs_border']:,}",
        "sa.outside": m.get("outside_band_diff_px", 0),
        "sa.outside_bbox": box(m["outside_band_bbox"]) if m.get("outside_band_bbox") else "none",
    })


def isolation_facts(path: Path, facts: dict) -> None:
    """Report B section 2: Word on each single-defect corpus (out/word_isolation.json, two passes)."""
    if not path.exists():
        return
    data = json.loads(path.read_text())
    for name in data["passes"][0]:
        opened = [p.get(name) == "OPENED" for p in data["passes"]]
        facts[f"iso.{name}"] = "opened" if all(opened) else "did not open" if not any(opened) else "differed between passes"


def broken_facts(facts: dict) -> None:
    """Report B's defect-survival table: out_broken/ scanned, plus Word's verdict on the same outputs.
    An output Word has not opened in this release reads "not measured", never an old verdict."""
    if not (ROOT / "out_broken").exists():
        return
    import defect_survival
    word = OUT / "word_verdicts_broken.json"
    data = json.loads(word.read_text()) if word.exists() else {"word": facts.get("word.version", "?"), "verdicts": {}}
    rows = defect_survival.survival()
    facts["broken.survival"] = defect_survival.table(rows, data["verdicts"], data["word"])
    facts["broken.fatal"] = defect_survival.fatal_table(rows, data["verdicts"])
    clean = {d: facts[f"word.{d}.opens"] for _, d in defect_survival.EDITORS if f"word.{d}.opens" in facts}
    facts["broken.flip"] = defect_survival.flip_table(rows, clean, data["verdicts"])
    flipped, spared = defect_survival.groups(rows, clean, data["verdicts"])
    facts["broken.flipped"], facts["broken.flipped_list"] = len(flipped), defect_survival.names(flipped)
    facts["broken.spared"], facts["broken.spared_list"] = len(spared), defect_survival.names(spared)
    facts["broken.word_measured"] = word.exists()
    editors = [d for d in rows if d != "lo_baseline"]
    facts["broken.editors"] = len(editors)
    facts["broken.produced"] = sum(1 for d in editors if rows[d] is not None)


def count_facts(facts: dict) -> None:
    """How many took part, counted from the measurements present rather than typed."""
    measured = sorted({k.split(".")[1] for k in facts if k.startswith("rt.") and k.endswith(".weighted")} - LANES)
    editors = [t for t in measured if t not in SDKS]
    open_editors = [t for t in editors if t not in CLOSED]
    facts["count.participants"] = len(measured)
    facts["count.participants_others"] = len(measured) - 1
    facts["count.editors"] = len(editors)
    facts["count.open_editors"] = len(open_editors)
    facts["count.open_editors_others"] = len(open_editors) - 1


def integrity_facts(xsd: Path, pkg: Path, facts: dict) -> None:
    """Report B's schema and package columns: build/validate_all_outputs.py writes
    out/xsd_real.json, build/malformation_audit.py writes out/package_integrity.json."""
    for t, n in json.loads(xsd.read_text()).items():
        facts[f"xsd.{t}.real"] = n
    for t, kinds in json.loads(pkg.read_text()).items():
        if not kinds:
            facts[f"pkg.{t}"] = "clean"
        elif set(kinds) == {"DANGLING-REL"}:
            facts[f"pkg.{t}"] = f"**{kinds['DANGLING-REL']} dangling relationship ids**"
        else:
            facts[f"pkg.{t}"] = "**" + ", ".join(f"{k.lower()} ×{v}" for k, v in sorted(kinds.items())) + "**"


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
    if (OUT / "xsd_real.json").exists() and (OUT / "package_integrity.json").exists():
        integrity_facts(OUT / "xsd_real.json", OUT / "package_integrity.json", facts)
    word = OUT / "word_verdicts.json"
    if word.exists():
        data = json.loads(word.read_text())
        facts["word.version"] = data["word"]
        for t, verdict in data["verdicts"].items():
            facts[f"word.{t}.opens"] = verdict.startswith("OPENED")
            facts[f"word.{t}.cell"] = "**opened**" if verdict.startswith("OPENED") else "**REFUSED**"
        editors = [t for t in data["verdicts"] if t not in LANES]
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
        ns_label_facts(json.loads((OUT / "ns_map.json").read_text()), facts)
    # Report D quotes the scorecard and the protection labels whole.
    for name in ("scorecard", "protection"):
        log = ROOT / "logs" / "bombs" / f"{name}.txt"
        if log.exists():
            facts[f"bomb.{name}"] = log.read_text().rstrip("\n")
    # Report A2's part matrix, from the same part classification as parts.*
    import part_matrix_md
    facts["parts.matrix"] = part_matrix_md.markdown()
    # The main report's preserved-vs-dropped matrix, derived from the same score.json files.
    import preserved_matrix
    if all((OUT / d / "score.json").exists() for _, d in preserved_matrix.TOOLS):
        facts["matrix.preserved"] = preserved_matrix.build_table()
    version_facts(facts)
    ui_facts(OUT / "ui", facts)
    stamp_facts(OUT / "apryse", facts)
    release_facts(OUT / "release.json", facts)
    read_facts(OUT / f"facts-{CODE_READ_RELEASE}.json", CODE_READ_RELEASE, facts)
    word_pixel_facts(OUT / "render" / "word_render_compare.json", facts)
    lo_pixel_facts(OUT / "render" / "lo_render_compare.json", facts)
    smartart_facts(OUT / "smartart" / "verify.json", facts)
    if (OUT / "ab" / "ab_compare.json").exists():
        import ab_table
        ab_table.facts_into(json.loads((OUT / "ab" / "ab_compare.json").read_text()), facts)
    if (OUT / "render" / "render_inventory.json").exists():
        import inventory_table
        facts["inventory.table"] = inventory_table.table(str(OUT / "render" / "render_inventory.json"))
    import pixels
    facts["pixels.dpi"] = pixels.DPI
    isolation_facts(OUT / "word_isolation.json", facts)
    broken_facts(facts)   # after word.* : 4.2 sets the clean-corpus verdict beside the broken one
    count_facts(facts)
    stars = OUT / "stars.json"
    if stars.exists():
        data = json.loads(stars.read_text())
        facts["stars.date"] = data["date"]
        for slug, n in data["stars"].items():
            facts[f"stars.{slug}"] = n
    editors = [t for t in TOOLS if t not in LANES and f"p2.{t}.identical" in facts]
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
