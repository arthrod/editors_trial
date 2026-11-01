#!/usr/bin/env python3
"""
Score what build/score_all.py does not: the second pass and the editor lanes.

  second pass   out/<tool>/second/complex.docx against the tool's OWN first
                pass (out/<tool>/complex.docx) -> out/<tool>/second/score.json
  lanes         out/eigenpal-editor and out/folio-editor against the fixture
                -> out/<lane>/score.json

Paths are written relative to the repository, as the published scores have them.

usage: python3 build/score_extra.py
"""
import os
import subprocess
import sys

BASE = "/Users/arthrod/temp/T/editors_trial"
CHECKER = "build/check_roundtrip.py"
SECOND = ["plate", "docxodus", "superdoc", "folio", "genoffice", "eigenpal", "officeopen",
          "docen", "wordcraft", "fidus", "canvas", "docsplus", "lo_baseline"]
LANES = ["eigenpal-editor", "folio-editor"]


def score(ref: str, out: str, js: str) -> bool:
    if not os.path.exists(os.path.join(BASE, out)):
        print(f"SKIP {out}: missing", file=sys.stderr)
        return True
    r = subprocess.run([sys.executable, CHECKER, ref, out, "--json", js], cwd=BASE,
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(f"CHECKER FAILED {out}:\n{r.stderr[-400:]}", file=sys.stderr)
        return False
    print(f"scored {out}")
    return True


ok = True
for t in SECOND:
    ok &= score(f"out/{t}/complex.docx", f"out/{t}/second/complex.docx", f"out/{t}/second/score.json")
for lane in LANES:
    ok &= score("fixture/complex.docx", f"out/{lane}/complex.docx", f"out/{lane}/score.json")
sys.exit(0 if ok else 1)
