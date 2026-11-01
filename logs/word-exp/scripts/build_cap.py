"""E5/E6: element floods either side of the 2,000,000-element default budget (#2014).
E5 = 666,600 paragraphs (1,999,800 + 6 marker + 11 package elements, under the cap).
E6 = 667,000 paragraphs (past it)."""
import sys
sys.path.insert(0, __file__.rsplit("/", 1)[0])
import build
unit = "<w:p><w:r><w:t>a</w:t></w:r></w:p>"
for name, n in [("E5_atcap", 666_600), ("E6_overcap", 667_000)]:
    build.pack(build.FIX / f"{name}.docx", build.doc("<w:p><w:r><w:t>FLOOD_START</w:t></w:r></w:p>" + unit * n + "<w:p><w:r><w:t>FLOOD_END</w:t></w:r></w:p>"))
    print(name, (build.FIX / f"{name}.docx").stat().st_size)
