#!/usr/bin/env python3
"""Run the round-trip checker over every editor output and emit a summary table."""
import json
import os
import subprocess
import sys

BASE = "/Users/arthrod/temp/T/editors_trial"
IN = os.path.join(BASE, "fixture", "complex.docx")
CHECKER = os.path.join(BASE, "build", "check_roundtrip.py")

# display name, output dir, is-a-baseline?
TARGETS = [
    ("Plate.js", "plate", False),
    ("Docxodus", "docxodus", False),
    ("SuperDoc", "superdoc", False),
    ("Folio", "folio", False),
    ("GenOffice", "genoffice", False),
    ("eigenpal", "eigenpal", False),
    ("office-open", "officeopen", False),
    ("Docen", "docen", False),
    ("WordCraft", "wordcraft", False),
    ("Fidus Writer", "fidus", False),
    ("canvas-editor + plugin", "canvas", False),
    ("docs.plus", "docsplus", False),
    ("Apryse WebViewer", "apryse", False),
    ("LibreOffice (baseline)", "lo_baseline", True),
]

rows = []
for name, d, baseline in TARGETS:
    out = os.path.join(BASE, "out", d, "complex.docx")
    if not os.path.exists(out):
        print(f"SKIP {name}: no output", file=sys.stderr)
        continue
    js = os.path.join(BASE, "out", d, "score.json")
    r = subprocess.run([sys.executable, CHECKER, IN, out, "--json", js],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(f"CHECKER FAILED for {name}:\n{r.stderr[-500:]}", file=sys.stderr)
        continue
    with open(js) as f:
        res = json.load(f)
    s = res["score"]
    rows.append({
        "name": name, "dir": d, "baseline": baseline,
        "weighted": s["weighted"], "critical": s["critical_pct"],
        "text": res["text_retention_pct"],
        "passed": s["features_passed"], "total": s["features_total"],
        "failed": [c["label"] for c in res["checks"] if not c["pass"]],
        "critical_failed": [c["label"] for c in res["checks"]
                            if not c["pass"] and c["weight"] == 3],
    })

print("\n=== SUMMARY (markdown) ===")
print("| Editor | Weighted | Critical | Text | Passed |")
print("|---|---|---|---|---|")
out = []
for r in rows:
    js = os.path.join(BASE, "out", r["dir"], "score.json")
    with open(js) as f:
        res = json.load(f)
    s = res["score"]
    out.append((r["name"], s["weighted"], s["critical_pct"], s["critical_passed"],
                s["critical_total"], res["text_retention_pct"],
                s["features_passed"], s["features_total"], r["failed"], r["dir"]))
for name, w, cp, cpa, cpt, txt, fp, ft, failed, d in out:
    print("| %s | %s%% | %s%% (%d/%d) | %s%% | %d/%d |" % (name, w, cp, cpa, cpt, txt, fp, ft))

with open(os.path.join(BASE, "out", "summary.json"), "w") as f:
    json.dump(out, f, indent=2)

print("\n\n=== FAILED CHECKS PER EDITOR ===")
for name, w, cp, cpa, cpt, txt, fp, ft, failed, d in out:
    print("\n--- %s (%s%%) ---" % (name, w))
    for lab in failed:
        print("   FAIL %s" % lab)
