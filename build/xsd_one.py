#!/usr/bin/env python3
"""Print the full XSD error for one part of one package (no filtering)."""
import os
import subprocess
import sys
import tempfile
import zipfile

BASE = "/Users/arthrod/temp/T/editors_trial"
XSD = os.path.join(BASE, "repos", "office-open", "ooxml-schemas", "transitional",
                   "wml.xsd")

pkg = os.path.join(BASE, sys.argv[1])
part = sys.argv[2]
z = zipfile.ZipFile(pkg)
tmp = tempfile.mkdtemp()
z.extractall(tmp)
r = subprocess.run(["xmllint", "--noout", "--schema", XSD, os.path.join(tmp, part)],
                   capture_output=True, text=True)
print(r.stderr.strip()[:2200])
