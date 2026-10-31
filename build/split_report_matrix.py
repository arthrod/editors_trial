#!/usr/bin/env python3
"""Replace the part matrix in Report A with four readable, name-shortened tables.

The 13-column matrix does not fit a landscape page: the renderer wraps every
header onto four lines and the part names wrap too.  The matrix is therefore
split into two editor halves x two part groups, and the part names are
compacted by the documented convention in part_matrix_md.short().

Editor names are shortened for the header row only; the classification maps
stay keyed by the original names.
"""
import contextlib
import io
import os
import sys

BASE = "/Users/arthrod/temp/T/editors_trial"
REPORT = os.path.join(BASE, "reports",
                       "Report A - Serialized vs Pass-Through vs Rendered (2026).md")

sys.path.insert(0, os.path.join(BASE, "build"))
import part_map  # noqa: E402
from part_matrix_md import PAYLOAD, collect, table  # noqa: E402

START = "**WordprocessingML and package parts**"
END = "\nThe payload tables are the ones worth dwelling on."

inp, maps = collect()
# order keeps the ORIGINAL editor names, which are the keys of `maps`
order = [n for n, _ in part_map.EDITORS if n in maps]
a, b = order[:6], order[6:]
common = sorted(set(inp) - set(PAYLOAD))

blocks = []
for title, ords, parts in [
        ("WordprocessingML and package parts", a, common),
        ("WordprocessingML and package parts (continued)", b, common),
        ("Binary payload and opaque parts", a, PAYLOAD),
        ("Binary payload and opaque parts (continued)", b, PAYLOAD)]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        table(inp, maps, ords, parts, title)
    blocks.append(buf.getvalue().rstrip())

new = "\n\n".join(blocks)

s = open(REPORT).read()
start = s.index(START)
end = s.index(END)
s = s[:start] + new + s[end:]
open(REPORT, "w").write(s)
print("matrix replaced: %d chars, %d tables" % (len(new), len(blocks)))
