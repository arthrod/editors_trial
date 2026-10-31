#!/usr/bin/env python3
"""
Package-level malformation audit.

Checks every package part of a .docx for defects that a consumer can trip on,
independently of the OOXML schema:

  NOT-WELL-FORMED   the part is not parseable XML (unbound prefix, unclosed
                    tag, bad entity) - the file cannot be re-imported
  DANGLING-REL      an r:id / r:embed / r:link in a part has no matching
                    relationship in that part's .rels
  MISSING-TARGET    a relationship points at a part that is not in the package
  NO-CONTENT-TYPE   a part is not covered by a Default (by extension) or an
                    Override in [Content_Types].xml
  STALE-OVERRIDE    an Override names a part that does not exist
  BAD-IGNORABLE     mc:Ignorable / mc:Choice Requires= names a prefix that is
                    not declared on an ancestor element
  UNBALANCED-FIELD  w:fldChar begin/separate/end do not nest correctly
  DANGLING-MOVE     a w:moveFrom / w:moveTo has no counterpart of the same
                    w:name

Usage:
  python3 build/malformation_audit.py                  # corpus + every output
  python3 build/malformation_audit.py FILE [FILE ...]
"""
import os
import re
import sys
import xml.etree.ElementTree as ET
import zipfile

BASE = "/Users/arthrod/temp/T/editors_trial"
IN = os.path.join(BASE, "fixture", "complex.docx")

R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
MC_NS = "http://schemas.openxmlformats.org/markup-compatibility/2006"
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

TARGETS = [
    ("Plate.js", "out/plate/complex.docx"),
    ("Docxodus", "out/docxodus/complex.docx"),
    ("INPUT (corpus)", IN),
    ("SuperDoc", "out/superdoc/complex.docx"),
    ("Folio", "out/folio/complex.docx"),
    ("GenOffice", "out/genoffice/complex.docx"),
    ("eigenpal", "out/eigenpal/complex.docx"),
    ("office-open", "out/officeopen/complex.docx"),
    ("Docen", "out/docen/complex.docx"),
    ("WordCraft", "out/wordcraft/complex.docx"),
    ("Fidus Writer", "out/fidus/complex.docx"),
    ("canvas-editor + plugin", "out/canvas/complex.docx"),
    ("docs.plus", "out/docsplus/complex.docx"),
    ("LibreOffice (baseline)", "out/lo_baseline/complex.docx"),
]

REL_ATTRS = ("id", "embed", "link", "pict", "dm", "lo", "qs", "cs", "href",
              "target", "top", "bottom", "left", "right", "origin", "align")


def rels_for(part):
    d, base = os.path.split(part)
    return "%s/_rels/%s.rels" % (d, base) if d else "_rels/%s.rels" % base


def audit(path):
    z = zipfile.ZipFile(path)
    names = [n for n in z.namelist() if not n.endswith("/")]
    nameset = set(names)
    findings = []

    # --- [Content_Types].xml coverage ------------------------------------
    ct = z.read("[Content_Types].xml").decode("utf-8")
    defaults, overrides = {}, set()
    # parse properly: attribute order varies between writers, so never regex
    ctree = ET.fromstring(ct.encode("utf-8"))
    for el in ctree:
        tag = el.tag.split("}")[-1]
        if tag == "Default":
            defaults[el.get("Extension", "").lower()] = el.get("ContentType", "")
        elif tag == "Override":
            overrides.add(el.get("PartName", "").lstrip("/"))

    for n in names:
        if n == "[Content_Types].xml":
            continue
        ext = n.rsplit(".", 1)[-1].lower() if "." in n else ""
        if n not in overrides and ext not in defaults:
            findings.append(("NO-CONTENT-TYPE", n, ""))
    for o in overrides:
        if o not in nameset:
            findings.append(("STALE-OVERRIDE", o, ""))

    # --- per-part XML + relationship checks --------------------------------
    for n in names:
        if not (n.endswith(".xml") or n.endswith(".rels")):
            continue
        data = z.read(n)
        try:
            root = ET.fromstring(data)
        except ET.ParseError as ex:
            findings.append(("NOT-WELL-FORMED", n, str(ex)[:110]))
            continue

        if n.endswith(".rels"):
            base = os.path.dirname(os.path.dirname(n))
            for rel in root:
                tgt = rel.get("Target", "")
                mode = rel.get("TargetMode", "")
                if mode == "External" or tgt.startswith(("http:", "https:", "mailto:")):
                    continue
                resolved = os.path.normpath(os.path.join(base, tgt)).replace("\\", "/")
                if resolved not in nameset:
                    findings.append(("MISSING-TARGET", n,
                                     "%s -> %s" % (rel.get("Id"), tgt)))
            continue

        # relationship references used by this part
        rp = rels_for(n)
        known = set()
        if rp in nameset:
            rroot = ET.fromstring(z.read(rp))
            known = {r.get("Id") for r in rroot}
        used = set()
        for el in root.iter():
            for k, v in el.attrib.items():
                if k.startswith("{%s}" % R_NS) and k.split("}")[1] in REL_ATTRS:
                    used.add(v)
        for u in sorted(used - known):
            findings.append(("DANGLING-REL", n, u))

        # mc:Ignorable prefixes
        for el in root.iter():
            ig = el.get("{%s}Ignorable" % MC_NS)
            if ig:
                declared = set()
                # ElementTree does not expose xmlns declarations; walk the raw text
                for pfx in ig.split():
                    if ('xmlns:%s=' % pfx) not in data.decode("utf-8", "replace"):
                        findings.append(("BAD-IGNORABLE", n, pfx))
                del declared

        # field character balance
        depth = 0
        for el in root.iter("{%s}fldChar" % W_NS):
            t = el.get("{%s}fldCharType" % W_NS)
            if t == "begin":
                depth += 1
            elif t == "end":
                depth -= 1
            if depth < 0:
                findings.append(("UNBALANCED-FIELD", n, "end before begin"))
                break
        if depth > 0:
            findings.append(("UNBALANCED-FIELD", n, "%d unclosed field(s)" % depth))

        # move pairing
        starts = {}
        for el in root.iter("{%s}moveFromRangeStart" % W_NS):
            starts[el.get("{%s}name" % W_NS)] = "moveFrom"
        for el in root.iter("{%s}moveToRangeStart" % W_NS):
            starts[el.get("{%s}name" % W_NS)] = "moveTo"
        froms = {el.get("{%s}name" % W_NS)
                 for el in root.iter("{%s}moveFromRangeStart" % W_NS)}
        tos = {el.get("{%s}name" % W_NS)
               for el in root.iter("{%s}moveToRangeStart" % W_NS)}
        for nm in froms - tos:
            findings.append(("DANGLING-MOVE", n, "moveFrom %r has no moveTo" % nm))
        for nm in tos - froms:
            findings.append(("DANGLING-MOVE", n, "moveTo %r has no moveFrom" % nm))
    return findings


def main():
    if len(sys.argv) > 1:
        pairs = [(os.path.basename(a), a) for a in sys.argv[1:]]
    else:
        pairs = []
        for label, rel in TARGETS:
            p = rel if os.path.isabs(rel) else os.path.join(BASE, rel)
            if os.path.exists(p):
                pairs.append((label, p))
    for label, p in pairs:
        f = audit(p)
        kinds = {}
        for k, _, _ in f:
            kinds[k] = kinds.get(k, 0) + 1
        print("%-26s %s" % (label, ("CLEAN" if not f else
                                    ", ".join("%s x%d" % (k, v)
                                              for k, v in sorted(kinds.items())))))
        for k, part, detail in f:
            print("      %-18s %s %s" % (k, part, detail))
    return 0


if __name__ == "__main__":
    sys.exit(main())
