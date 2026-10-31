#!/usr/bin/env python3
"""Symmetric difference of ZIP part names between a reference and a candidate docx."""
import sys
import zipfile


def parts(p):
    return set(zipfile.ZipFile(p).namelist())


ref, cand = sys.argv[1], sys.argv[2]
a, b = parts(ref), parts(cand)
missing = sorted(a - b)
new = sorted(b - a)
print("INPUT : %s (%d parts)" % (ref, len(a)))
print("OUTPUT: %s (%d parts)" % (cand, len(b)))
print("MISSING from output (%d):" % len(missing))
for n in missing:
    print("   -", n)
print("NEW in output (%d):" % len(new))
for n in new:
    print("   +", n)
print("COMMON (%d)" % len(a & b))
