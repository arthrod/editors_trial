#!/usr/bin/env python3
"""Build diagnostic variants of Report B to find why Word refuses it."""
import os
import re
import subprocess
import sys

BASE = "/Users/arthrod/temp/T/editors_trial"
SRC = os.path.join(BASE, "reports",
                   "Report B - Malformed Parts, Causes and Repair (2026).md")
OUT = os.path.join(BASE, "out", "variants")
os.makedirs(OUT, exist_ok=True)


def build(name, md, toc=True):
    mdp = os.path.join(OUT, name + ".md")
    with open(mdp, "w") as f:
        f.write(md)
    docx = os.path.join(OUT, name + ".docx")
    cmd = ["pandoc", mdp, "-f", "gfm", "-t", "docx",
           "--reference-doc", os.path.join(BASE, "build", "reference.docx"),
           "-o", docx]
    if toc:
        cmd += ["--toc", "--toc-depth=2"]
    subprocess.run(cmd, check=True)
    subprocess.run([sys.executable, os.path.join(BASE, "build", "fix_dirty.py"), docx],
                   capture_output=True)
    return docx


src = open(SRC).read()

# V1: no TOC at all
build("B1_notoc", src, toc=False)

# V2: without the three new subsections (4.1 / 4.2 / 4.3)
i = src.index("### 4.1 ")
j = src.index("## 5. The causes, in seven shapes")
build("B2_no_new", src[:i] + src[j:])

# V3: only the new 4.1-4.3 sections, nothing else
head = src[:src.index("## TL;DR")]
build("B3_only_new", head + src[i:j])

# V4: the source with every table stripped (keeps all prose)
no_tbl = re.sub(r"(?ms)^\|.*\n(?:\|.*\n)*", "", src)
build("B4_no_tables", no_tbl)

for f in sorted(os.listdir(OUT)):
    if f.endswith(".docx"):
        print(os.path.join(OUT, f), os.path.getsize(os.path.join(OUT, f)))
