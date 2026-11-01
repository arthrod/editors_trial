#!/usr/bin/env python3
"""
Score a DOCX round-trip: input.docx -> editor -> output.docx

Usage: check_roundtrip.py <input.docx> <output.docx> [--json out.json]

Reports, per OOXML exception case, whether the feature survived the round trip.
Two headline numbers:
  * feature score  - weighted survival of the exception-case corpus
  * text retention - share of the input's visible text that survives
"""
import html
import io
import json
import posixpath
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
# Field results that change with pagination: not text a save can be asked to keep.
_PAGE_FIELD = re.compile(r"\s*(PAGE|NUMPAGES|SECTIONPAGES)\b", re.I)
MC = "{http://schemas.openxmlformats.org/markup-compatibility/2006}"
M = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"
W16DU = "{http://schemas.microsoft.com/office/word/2023/wordml/word16du}"
W14 = "{http://schemas.microsoft.com/office/word/2010/wordml}"
C = "{http://schemas.openxmlformats.org/drawingml/2006/chart}"
DGM = "{http://schemas.openxmlformats.org/drawingml/2006/diagram}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
O = "{urn:schemas-microsoft-com:office:office}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
REL_PKG = "{http://schemas.openxmlformats.org/package/2006/relationships}"

# Story parts the corpus names directly. A round trip may renumber the file
# (header2.xml -> header3.xml) and still keep the construct, so these are
# resolved from w:headerReference / w:footerReference when the document has one.
STORY_REFS = {
    "word/header1.xml": ("headerReference", "default"),
    "word/header2.xml": ("headerReference", "first"),
    "word/footer1.xml": ("footerReference", "default"),
    "word/footer2.xml": ("footerReference", "first"),
}

# id, label, weight, category
WEIGHTS = {"critical": 3, "major": 2, "minor": 1}


class Pkg:
    def __init__(self, path=None, data=None):
        """Open a DOCX package and check its ZIP members for CRC errors.

        Args:
            path: ZIP path or file object, used when data is None.
            data: ZIP bytes; takes precedence over path when supplied.

        Raises:
            OSError: If the package cannot be opened or read.
            zipfile.BadZipFile: If the package is not a valid ZIP.
        """
        if data is not None:
            self.path = "<memory>"
            self.z = zipfile.ZipFile(io.BytesIO(data))
        else:
            self.path = path
            self.z = zipfile.ZipFile(path)
        self.names = set(self.z.namelist())
        self.bad = self.z.testzip()
        self._trees = {}
        self._rels = {}

    def tree(self, name):
        if name not in self._trees:
            try:
                self._trees[name] = ET.fromstring(self.z.read(name))
            except Exception:
                self._trees[name] = None
        return self._trees[name]

    def raw(self, name):
        try:
            return self.z.read(name).decode("utf-8", "replace")
        except KeyError:
            return ""

    def has(self, *cands):
        return any(c in self.names for c in cands)

    def doc(self):
        return self.tree("word/document.xml")

    def count(self, local, tree=None, ns=W):
        t = tree if tree is not None else self.doc()
        if t is None:
            return 0
        return sum(1 for e in t.iter() if e.tag == ns + local)

    def attr_count(self, name, value_prefix=None, tree=None, ns=W):
        t = tree if tree is not None else self.doc()
        if t is None:
            return 0
        n = 0
        for e in t.iter():
            for k, v in e.attrib.items():
                if k == ns + name and (value_prefix is None or v.startswith(value_prefix)):
                    n += 1
        return n

    def text(self, include_del=True):
        """Visible text, whitespace-normalised, paragraph-aware.

        Paragraphs are separated so that tokens never merge across a paragraph
        boundary (an artefact of a flat concat would otherwise show up as a
        false "lost text" finding).

        What a reader sees, once (arthrod/editors_trial#24):
        - mc:Fallback is skipped: it restates mc:Choice for older consumers, and a save
          that rewrites it from the choice (as Word does) loses nothing visible;
        - a paragraph's text stops at a nested w:p (a text box), which is its own paragraph;
        - PAGE, NUMPAGES and SECTIONPAGES results are skipped: they change with pagination.
        """
        t = self.doc()
        if t is None:
            return ""
        paras = []
        fields = []  # open complex fields: [instruction, in result]

        def in_page_result():
            return any(res and _PAGE_FIELD.match(instr) for instr, res in fields)

        def walk(el, buf):
            for e in el:
                tag = e.tag
                if tag == MC + "Fallback":
                    continue
                if tag == W + "p":
                    para(e)
                    continue
                if tag == W + "altChunk":
                    # Word shows the chunk's content and imports it on save, so it is text
                    # whether the chunk is kept or imported.
                    paras.extend(self._alt_chunk_paragraphs(e.get(R + "id")))
                    continue
                if tag == W + "fldSimple" and _PAGE_FIELD.match(e.get(W + "instr") or ""):
                    continue
                if tag == W + "fldChar":
                    kind = e.get(W + "fldCharType")
                    if kind == "begin":
                        fields.append(["", False])
                    elif kind == "separate" and fields:
                        fields[-1][1] = True
                    elif kind == "end" and fields:
                        fields.pop()
                elif tag == W + "instrText" and fields and not fields[-1][1]:
                    fields[-1][0] += e.text or ""
                elif not in_page_result():
                    if tag == W + "t":
                        buf.append(e.text or "")
                    elif tag == W + "delText" and include_del:
                        buf.append(e.text or "")
                    elif tag == M + "t":
                        buf.append(e.text or "")
                    elif tag == W + "tab":
                        buf.append("\t")
                    elif tag in (W + "br", W + "cr"):
                        buf.append("\n")
                walk(e, buf)

        def para(p):
            buf = []
            slot = len(paras)
            paras.append("")
            walk(p, buf)
            paras[slot] = "".join(buf)

        walk(t, [])
        # content outside any w:p (e.g. a bare m:oMathPara) still counts; an empty
        # paragraph shows no text
        joined = "\n".join(p for p in paras if p.strip())
        if not joined.strip():
            joined = "".join(e.text or "" for e in t.iter(M + "t"))
        return re.sub(r"[ \t]+", " ", joined).strip()

    def _alt_chunk_paragraphs(self, rid):
        """The paragraphs of an altChunk's HTML part, as text."""
        part = self.resolved_internal("word/document.xml", rid)
        if not part:
            return []
        html_text = self.raw(part)
        found = re.findall(r"<p\b[^>]*>([\s\S]*?)</p>", html_text, re.I)
        return [html.unescape(re.sub(r"<[^>]+>", "", t)).strip() for t in found]

    def tokens(self):
        t = self.text()
        return [w for w in re.split(r"[^\w؀-ۿ]+", t) if len(w) > 2]

    def _rels_name(self, part):
        """Return the relationship part name for a package part."""
        base = posixpath.dirname(part)
        name = posixpath.basename(part)
        rel = "%s.rels" % name
        return posixpath.join(base, "_rels", rel) if base else posixpath.join("_rels", rel)

    def relationships(self, part):
        """Return relationship records for a package part.

        Args:
            part: Source part's ZIP path.

        Returns:
            Records with id, type, target, and mode; an empty list if the
            relationship part is missing or cannot be parsed.
        """
        key = self._rels_name(part)
        if key not in self._rels:
            root = self.tree(key)
            found = []
            if root is not None:
                for el in root.iter(REL_PKG + "Relationship"):
                    found.append({
                        "id": el.get("Id"),
                        "type": el.get("Type") or "",
                        "target": el.get("Target") or "",
                        "mode": (el.get("TargetMode") or "Internal"),
                    })
            self._rels[key] = found
        return self._rels[key]

    def resolve(self, from_part, rid):
        """Internal OPC target for rid, or None if missing, external, or unsafe."""
        if not rid:
            return None
        for rel in self.relationships(from_part):
            if rel["id"] != rid:
                continue
            if rel["mode"].lower() == "external":
                return None
            target = rel["target"]
            if target.startswith("/"):
                path = posixpath.normpath(target.lstrip("/"))
            else:
                path = posixpath.normpath(posixpath.join(posixpath.dirname(from_part), target))
            if path.startswith("..") or path == "." or path.startswith("/"):
                return None
            return path
        return None

    def external_target(self, from_part, rid):
        """Return the external target for a relationship, or None if absent.

        Args:
            from_part: Source part's ZIP path.
            rid: Relationship ID in that part.
        """
        if not rid:
            return None
        for rel in self.relationships(from_part):
            if rel["id"] == rid and rel["mode"].lower() == "external":
                return rel["target"]
        return None

    def resolved_internal(self, from_part, rid):
        """Return an internal target's ZIP path only if the member exists.

        Args:
            from_part: Source part's ZIP path.
            rid: Relationship ID in that part.

        Returns:
            The target path, or None for an unresolved or missing member.
        """
        path = self.resolve(from_part, rid)
        if path and path in self.names:
            return path
        return None

    def story_target(self, local, ref_type):
        """Zip path of a header/footer reference, '' if the reference dangles,
        None if the document has no reference of that type."""
        doc = self.doc()
        if doc is None:
            return None
        found = False
        for el in doc.iter(W + local):
            if el.get(W + "type") != ref_type:
                continue
            found = True
            path = self.resolved_internal("word/document.xml", el.get(R + "id"))
            if path:
                return path
        if not found:
            return None
        return ""

    def declares_uri(self, part, uri):
        """Return whether a part's raw XML declares the given namespace URI.

        Args:
            part: ZIP path of the XML part.
            uri: Namespace URI to match, independent of prefix.
        """
        raw = self.raw(part)
        return re.search(
            r"""xmlns(?::[A-Za-z_][\w.-]*)?\s*=\s*["']%s["']""" % re.escape(uri),
            raw,
        ) is not None


def _uri(clark):
    """Remove the first and last characters if the namespace starts with '{'."""
    return clark[1:-1] if clark.startswith("{") else clark


def _move_from_ok(doc):
    """Return whether a moveFrom exists and none has delText descendants."""
    if doc is None:
        return False
    found = False
    for el in doc.iter(W + "moveFrom"):
        found = True
        for child in el.iter():
            if child is not el and child.tag == W + "delText":
                return False
    return found


def _header_tracked_change(pkg):
    """Return whether a referenced header contains an insertion.

    When there are no header references, inspect the legacy header2.xml path.
    """
    doc = pkg.doc()
    if doc is None:
        return False
    refs = list(doc.iter(W + "headerReference"))
    if not refs:
        tree = pkg.tree("word/header2.xml")
        return tree is not None and any(e.tag == W + "ins" for e in tree.iter())
    for el in refs:
        path = pkg.resolved_internal("word/document.xml", el.get(R + "id"))
        if not path:
            continue
        tree = pkg.tree(path)
        if tree is not None and any(e.tag == W + "ins" for e in tree.iter()):
            return True
    return False


def _blips_resolve(pkg):
    """Return whether embedded image references exist and all resolve to members."""
    doc = pkg.doc()
    if doc is None:
        return False
    embeds = []
    for el in doc.iter(A + "blip"):
        rid = el.get(R + "embed")
        if rid:
            embeds.append(rid)
    if not embeds:
        return False
    return all(pkg.resolved_internal("word/document.xml", rid) for rid in embeds)


def _references_resolve(pkg, tag):
    """Return whether references of this type exist and all resolve to members."""
    doc = pkg.doc()
    if doc is None:
        return False
    nodes = list(doc.iter(tag))
    return bool(nodes) and all(
        pkg.resolved_internal("word/document.xml", el.get(R + "id")) for el in nodes
    )


def _smartart_resolve(pkg):
    """Return whether SmartArt references exist and all four targets resolve."""
    doc = pkg.doc()
    if doc is None:
        return False
    nodes = list(doc.iter(DGM + "relIds"))
    if not nodes:
        return False
    for el in nodes:
        for attr in ("dm", "lo", "qs", "cs"):
            rid = el.get(R + attr)
            if not rid or not pkg.resolved_internal("word/document.xml", rid):
                return False
    return True


def _altchunk_ok(pkg):
    """Return whether all altChunk targets resolve, or imported fixture text remains.

    The text fallback is used only when no altChunk elements are present.
    """
    doc = pkg.doc()
    if doc is None:
        return False
    chunks = list(doc.iter(W + "altChunk"))
    if chunks:
        return all(pkg.resolved_internal("word/document.xml", el.get(R + "id")) for el in chunks)
    return "Imported altChunk paragraph one" in pkg.raw("word/document.xml")


def _note_part(pkg, type_suffix, default):
    """Return the first existing internal note target, or the default path.

    Args:
        pkg: Package containing the document relationships.
        type_suffix: Final relationship type component to match.
        default: Path returned when no matching target resolves.
    """
    for rel in pkg.relationships("word/document.xml"):
        if rel["type"].endswith("/" + type_suffix) and rel["mode"].lower() != "external":
            path = pkg.resolved_internal("word/document.xml", rel["id"])
            if path:
                return path
    return default


def _hyperlink_facts(pkg):
    """Return document hyperlink anchors and targets as prefixed strings.

    Unresolved relationship IDs are recorded with a dangling: prefix.
    """
    doc = pkg.doc()
    facts = set()
    if doc is None:
        return facts
    for el in doc.iter(W + "hyperlink"):
        anchor = el.get(W + "anchor")
        if anchor:
            facts.add("anchor:" + anchor)
        rid = el.get(R + "id")
        if not rid:
            continue
        ext = pkg.external_target("word/document.xml", rid)
        if ext:
            facts.add("ext:" + ext)
            continue
        path = pkg.resolved_internal("word/document.xml", rid)
        if path:
            facts.add("int:" + path)
        else:
            facts.add("dangling:" + rid)
    return facts


def _field_instructions(pkg):
    """Each field's instruction, normalised, whether written as w:fldSimple or as a complex
    field (w:fldChar + w:instrText): the two are the same field (arthrod/editors_trial#24)."""
    doc = pkg.doc()
    found = []
    if doc is None:
        return found
    norm = lambda s: " ".join(s.split())
    for el in doc.iter(W + "fldSimple"):
        found.append(norm(el.get(W + "instr") or ""))
    stack = []  # open complex fields: [instruction, instruction finished]
    for el in doc.iter():
        if el.tag == W + "fldChar":
            kind = el.get(W + "fldCharType")
            if kind == "begin":
                stack.append(["", False])
            elif kind == "separate" and stack and not stack[-1][1]:
                stack[-1][1] = True
                found.append(norm(stack[-1][0]))
            elif kind == "end" and stack:
                instr, done = stack.pop()
                if not done:
                    found.append(norm(instr))
        elif el.tag == W + "instrText" and stack and not stack[-1][1]:
            stack[-1][0] += el.text or ""
    return found


def _simple_fields_kept(inp, out):
    """Every w:fldSimple of the input survives, as a simple or a complex field."""
    doc = inp.doc()
    want = [" ".join((el.get(W + "instr") or "").split()) for el in doc.iter(W + "fldSimple")] if doc is not None else []
    have = _field_instructions(out)
    kept = sum(1 for w in want if w in have)
    return bool(want) and kept == len(want), "n=%d" % kept


def build_checks(inp: Pkg, out: Pkg):
    """Return list of (id, label, category, weight, ok_bool, detail)."""
    C_ = []

    def chk(cid, label, cat, weight, ok, detail=""):
        C_.append((cid, label, cat, WEIGHTS[weight], bool(ok), detail))

    od, idoc = out.doc(), inp.doc()

    # ---------- package integrity -------------------------------------------------
    chk("pkg.opens", "ZIP package opens, CRC valid", "package", "critical",
        out.bad is None, out.bad or "")
    chk("pkg.document_xml", "word/document.xml present and well-formed", "package", "critical",
        od is not None)
    for part, label, w in [
        ("word/styles.xml", "styles.xml", "major"),
        ("word/numbering.xml", "numbering.xml", "major"),
        ("word/settings.xml", "settings.xml", "major"),
        ("word/fontTable.xml", "fontTable.xml", "minor"),
        ("word/webSettings.xml", "webSettings.xml", "minor"),
        ("word/theme/theme1.xml", "theme1.xml", "minor"),
        ("word/footnotes.xml", "footnotes.xml", "major"),
        ("word/endnotes.xml", "endnotes.xml", "major"),
        ("word/comments.xml", "comments.xml", "major"),
        ("word/header1.xml", "header (default)", "major"),
        ("word/header2.xml", "header (first page)", "major"),
        ("word/footer1.xml", "footer (default)", "major"),
        ("word/footer2.xml", "footer (first page)", "major"),
        ("word/glossary/document.xml", "glossary/building blocks", "minor"),
        ("customXml/item1.xml", "customXml data store", "minor"),
        ("word/afchunk.html", "altChunk part", "minor"),
    ]:
        if part in STORY_REFS:
            local, ref_type = STORY_REFS[part]
            target = out.story_target(local, ref_type)
            kept = (part in out.names) if target is None else bool(target)
        elif part == "word/afchunk.html":
            # Importing the chunk's content is what Word does with it (#24); ref.altChunk agrees.
            kept = part in out.names or _altchunk_ok(out)
        else:
            kept = part in out.names
        chk("pkg." + part.replace("/", "_"), "part kept: " + label, "package", w,
            kept)

    media = [n for n in out.names if n.startswith("word/media/")]
    chk("pkg.media", "embedded image (word/media)", "package", "critical", media,
        ",".join(sorted(media)[:4]))
    charts = [n for n in out.names if n.startswith("word/charts/") and n.endswith(".xml")]
    chk("pkg.chart", "chart part kept", "package", "critical", charts,
        ",".join(sorted(charts)[:3]))
    dgms = [n for n in out.names if n.startswith("word/diagrams/")]
    chk("pkg.smartart", "SmartArt/diagram parts kept", "package", "critical",
        len(dgms) >= 4, "%d parts" % len(dgms))
    ole = [n for n in out.names if n.startswith("word/embeddings/")
           and (n.endswith(".bin") or n.endswith(".docx"))]
    chk("pkg.ole", "OLE object part kept", "package", "critical", ole, ",".join(ole[:2]))
    xlsx = [n for n in out.names if n.startswith("word/embeddings/") and n.endswith(".xlsx")]
    chk("pkg.embedded_xlsx", "embedded workbook kept", "package", "minor", xlsx)

    # ---------- tracked changes --------------------------------------------------
    chk("tc.ins", "w:ins runs kept", "tracked", "critical",
        out.count("ins") >= 3, "n=%d" % out.count("ins"))
    chk("tc.del", "w:del runs kept", "tracked", "critical",
        out.count("del") >= 3, "n=%d" % out.count("del"))
    chk("tc.delText", "w:delText kept", "tracked", "critical", out.count("delText") >= 1)
    chk("tc.dateUtc", "w16du:dateUtc kept", "tracked", "critical",
        out.attr_count("dateUtc", ns=W16DU) >= 1,
        "n=%d" % out.attr_count("dateUtc", ns=W16DU))
    chk("tc.moveFrom", "w:moveFrom kept with w:t, not w:delText", "tracked", "major",
        _move_from_ok(od))
    chk("tc.moveTo", "w:moveTo kept", "tracked", "major", out.count("moveTo") >= 1)
    chk("tc.moveRanges", "move range markers kept", "tracked", "minor",
        out.count("moveFromRangeStart") >= 1 and out.count("moveToRangeStart") >= 1)
    chk("tc.rPrChange", "w:rPrChange kept", "tracked", "major",
        out.count("rPrChange") >= 1)
    chk("tc.pPrChange", "w:pPrChange kept", "tracked", "major",
        out.count("pPrChange") >= 1)
    # paragraph-mark revision: w:ins nested inside w:pPr/w:rPr
    pm = 0
    if od is not None:
        for e in od.iter():
            if e.tag == W + "pPr":
                for rpr in e.findall(W + "rPr"):
                    pm += len(rpr.findall(W + "ins"))
    chk("tc.paragraphMarkRev", "paragraph-mark revision (pPr/rPr/ins) kept", "tracked", "major",
        pm >= 1, "n=%d" % pm)
    # Row-level revisions are w:trPr/w:ins and w:trPr/w:del (ECMA-376 CT_TrPr),
    # not w:trIns/w:trDel - detect them where they actually live.
    row_ins = row_del = 0
    if od is not None:
        for tr in od.iter(W + "tr"):
            trpr = tr.find(W + "trPr")
            if trpr is None:
                continue
            row_ins += len(trpr.findall(W + "ins"))
            row_del += len(trpr.findall(W + "del"))
    chk("tc.trIns", "inserted table row (trPr/ins) kept", "tracked", "critical",
        row_ins >= 1, "n=%d" % row_ins)
    chk("tc.trDel", "deleted table row (trPr/del) kept", "tracked", "critical",
        row_del >= 1, "n=%d" % row_del)

    # ---------- fields / bookmarks ------------------------------------------------
    chk("fl.fldChar", "complex field (w:fldChar) kept", "fields", "critical",
        out.count("fldChar") >= 2, "n=%d" % out.count("fldChar"))
    chk("fl.instrText", "field instruction (w:instrText) kept", "fields", "critical",
        out.count("instrText") >= 1)
    simple_ok, simple_detail = _simple_fields_kept(inp, out)
    chk("fl.fldSimple", "simple fields kept (as simple or complex fields)", "fields", "major",
        simple_ok, simple_detail)
    chk("fl.bookmark", "bookmark kept", "fields", "major",
        out.count("bookmarkStart") >= 1 and out.count("bookmarkEnd") >= 1)
    chk("fl.tocInstr", "TOC field instruction text intact", "fields", "critical",
        "TOC" in out.raw("word/document.xml"))

    # ---------- content controls --------------------------------------------------
    chk("sdt.count", "content controls kept (>=5)", "sdt", "critical",
        out.count("sdt") >= 5, "n=%d" % out.count("sdt"))
    chk("sdt.databinding", "w:dataBinding kept", "sdt", "major",
        out.count("dataBinding") >= 1)
    chk("sdt.date", "date-picker content control kept", "sdt", "major",
        out.count("date") >= 1)
    chk("sdt.lock", "w:lock on content control kept", "sdt", "minor",
        out.count("lock") >= 1)
    # nested sdt: an sdt inside an sdtContent inside an sdt
    nested = 0
    if od is not None:
        for e in od.iter(W + "sdt"):
            if e.find(".//" + W + "sdt") is not None:
                nested += 1
    chk("sdt.nested", "nested content control kept", "sdt", "major", nested >= 1)

    # ---------- markup / unknown content ------------------------------------------
    chk("mx.proofErr", "w:proofErr kept", "markup", "minor",
        out.count("proofErr") >= 4, "n=%d" % out.count("proofErr"))
    chk("mx.altContent", "mc:AlternateContent kept (Choice+Fallback)", "markup", "critical",
        out.count("AlternateContent", ns=MC) >= 1 and od is not None and
        od.find(".//" + MC + "Choice") is not None and od.find(".//" + MC + "Fallback") is not None)
    chk("mx.math", "OMML math (m:oMath) kept", "markup", "major",
        out.count("oMath", ns=M) >= 1)
    chk("mx.unknownAttr", "unknown w14 attributes kept", "markup", "critical",
        out.attr_count("paraId", ns=W14) >= 1 or out.attr_count("textId", ns=W14) >= 1,
        "paraId=%d" % out.attr_count("paraId", ns=W14))
    chk("mx.unknownElem", "unknown w14 element kept (w14:textOutline)", "markup", "major",
        od is not None and od.find(".//" + W14 + "textOutline") is not None)
    chk("mx.xmlspace", 'xml:space="preserve" kept', "markup", "critical",
        'xml:space="preserve"' in out.raw("word/document.xml"))
    # Declaration checks are presence of the URI, under any prefix. They are not
    # a second critical credit for the attribute that uses that URI.
    chk("mx.nsW16du", "w16du namespace declaration kept", "markup", "minor",
        out.declares_uri("word/document.xml", _uri(W16DU)))
    chk("mx.nsW14", "w14 namespace declaration kept", "markup", "minor",
        out.declares_uri("word/document.xml", _uri(W14)))
    chk("mx.permStart", "w:permStart/permEnd kept", "markup", "minor",
        out.count("permStart") >= 1 and out.count("permEnd") >= 1)

    # ---------- tables ------------------------------------------------------------
    chk("tb.gridSpan", "table gridSpan kept", "tables", "critical",
        out.count("gridSpan") >= 3, "n=%d" % out.count("gridSpan"))
    chk("tb.vMerge", "table vMerge kept", "tables", "critical",
        out.count("vMerge") >= 2, "n=%d" % out.count("vMerge"))
    chk("tb.tblHeader", "repeating header row (w:tblHeader) kept", "tables", "major",
        out.count("tblHeader") >= 1)
    chk("tb.tblGrid", "tblGrid kept", "tables", "major", out.count("tblGrid") >= 2)
    chk("tb.tblLook", "tblLook kept", "tables", "minor", out.count("tblLook") >= 1)
    chk("tb.nested", "nested table kept", "tables", "major", out.count("tbl") >= 2,
        "n=%d" % out.count("tbl"))
    chk("tb.textDirection", "cell text direction kept", "tables", "minor",
        out.count("textDirection") >= 1)
    chk("tb.shading", "cell shading kept", "tables", "minor", out.count("shd") >= 1)

    # ---------- sections / layout -------------------------------------------------
    chk("sec.count", "all 3 sections kept", "layout", "critical",
        out.count("sectPr") >= 3, "n=%d" % out.count("sectPr"))
    chk("sec.landscape", "landscape section kept", "layout", "major",
        out.attr_count("orient") >= 1 and "landscape" in out.raw("word/document.xml"))
    chk("sec.pgBorders", "page borders kept", "layout", "major",
        out.count("pgBorders") >= 1)
    chk("sec.cols2", "multi-column section kept", "layout", "minor",
        out.attr_count("num") >= 1)
    chk("sec.pgMar", "page margins kept", "layout", "major", out.count("pgMar") >= 3)
    chk("sec.docGrid", "docGrid kept", "layout", "minor", out.count("docGrid") >= 3)

    # ---------- run / paragraph formatting ---------------------------------------
    chk("fmt.bidi", "RTL paragraph (w:bidi) kept", "formatting", "major",
        out.count("bidi") >= 1)
    chk("fmt.rtl", "RTL run (w:rtl) kept", "formatting", "major", out.count("rtl") >= 1)
    chk("fmt.sym", "w:sym symbol kept", "formatting", "minor", out.count("sym") >= 1)
    chk("fmt.tab", "w:tab kept", "formatting", "major", out.count("tab") >= 1)
    chk("fmt.br", "w:br kept", "formatting", "major", out.count("br") >= 1)
    chk("fmt.hyphens", "noBreakHyphen/softHyphen kept", "formatting", "minor",
        out.count("noBreakHyphen") >= 1 or out.count("softHyphen") >= 1)
    chk("fmt.vanish", "hidden text (w:vanish) kept", "formatting", "minor",
        out.count("vanish") >= 1)
    chk("fmt.noProof", "w:noProof kept", "formatting", "minor", out.count("noProof") >= 1)
    chk("fmt.vertAlign", "w:vertAlign kept", "formatting", "minor",
        out.count("vertAlign") >= 1)
    chk("fmt.eastAsian", "eastAsianLayout kept", "formatting", "minor",
        out.count("eastAsianLayout") >= 1)
    chk("fmt.numPr", "numbering reference (numPr) kept", "formatting", "major",
        out.count("numPr") >= 1)

    # Whitespace fidelity: every run whose text has leading/trailing whitespace must
    # survive including its whitespace. Substring matching (not set membership) so that a
    # serializer which MERGES two runs is not falsely reported as losing the space.
    def sig_ws(pkg):
        t = pkg.doc()
        if t is None:
            return []
        vals = []
        for e in t.iter(W + "t"):
            s = e.text or ""
            if s != s.strip():
                vals.append(s)
        return vals

    in_ws, out_ws = sig_ws(inp), sig_ws(out)
    out_all = out.text()
    ws_lost = [s for s in in_ws if s not in out_all]
    chk("fmt.whitespace", "significant leading/trailing whitespace preserved", "formatting",
        "critical", not ws_lost,
        ("lost %d: %s" % (len(ws_lost), [repr(x)[:28] for x in ws_lost[:3]])) if ws_lost else "")

    # Strictest text check: the whole visible text stream must be identical.
    in_all = inp.text()
    chk("text.exact", "visible text stream identical to input", "text", "critical",
        in_all == out_all,
        "" if in_all == out_all else "len %d vs %d" % (len(in_all), len(out_all)))
    chk("fmt.numLevels", "9-level numbering definition kept", "formatting", "minor",
        out.count("lvl", tree=out.tree("word/numbering.xml")) >= 9,
        "n=%d" % out.count("lvl", tree=out.tree("word/numbering.xml")))

    # ---------- embedded objects / references --------------------------------------
    chk("ref.image", "image relationship resolves to a part", "refs", "critical",
        _blips_resolve(out))
    chk("ref.chart", "chart relationship resolves to a part", "refs", "critical",
        _references_resolve(out, C + "chart"))
    chk("ref.smartart", "SmartArt relationships resolve to parts", "refs", "critical",
        _smartart_resolve(out))
    chk("ref.ole", "OLE relationship resolves to a part", "refs", "critical",
        _references_resolve(out, O + "OLEObject"))
    chk("ref.altChunk", "altChunk relationship resolves, or content imported", "refs", "minor",
        _altchunk_ok(out))
    chk("ref.footnoteRef", "footnote reference kept", "refs", "major",
        out.count("footnoteReference") >= 1)
    chk("ref.endnoteRef", "endnote reference kept", "refs", "major",
        out.count("endnoteReference") >= 1)
    chk("ref.commentRef", "comment reference kept", "refs", "major",
        out.count("commentReference") >= 1)
    chk("ref.headerTrackedChange", "tracked change inside header kept", "refs", "critical",
        _header_tracked_change(out))
    endnote_part = _note_part(out, "endnotes", "word/endnotes.xml")
    chk("ref.endnoteBody", "endnote body text kept", "refs", "major",
        "endnote body" in out.raw(endnote_part))
    in_links = _hyperlink_facts(inp)
    out_links = _hyperlink_facts(out)
    chk("fl.hyperlink", "hyperlink targets kept", "fields", "major",
        in_links <= out_links and not any(f.startswith("dangling:") for f in out_links),
        "none in input" if not in_links else "in=%d" % len(in_links))
    st = out.raw("word/settings.xml")
    chk("ref.documentProtection", "settings.xml documentProtection kept", "refs", "major",
        "documentProtection" in st)
    chk("ref.evenOddHeaders", "evenAndOddHeaders kept", "refs", "minor",
        "evenAndOddHeaders" in st)
    chk("ref.footnoteBody", "footnote body text kept", "refs", "major",
        "footnote body" in out.raw("word/footnotes.xml"))
    chk("ref.commentBody", "comment body text kept", "refs", "major",
        "comment body" in out.raw("word/comments.xml"))
    chk("ref.docDefaults", "styles.xml docDefaults kept", "refs", "major",
        "docDefaults" in out.raw("word/styles.xml"))
    chk("ref.coreProps", "core properties kept", "refs", "minor",
        "Fixture Complex Document" in out.raw("docProps/core.xml"))

    return C_


def score(checks):
    tot = sum(c[3] for c in checks)
    got = sum(c[3] for c in checks if c[4])
    crit = [c for c in checks if c[3] == 3]
    crit_ok = sum(1 for c in crit if c[4])
    return {
        "weighted": round(100.0 * got / tot, 1) if tot else 0,
        "weighted_earned": got,
        "weighted_total": tot,
        "critical_passed": crit_ok,
        "critical_total": len(crit),
        "critical_pct": round(100.0 * crit_ok / len(crit), 1) if crit else 0,
        "features_passed": sum(1 for c in checks if c[4]),
        "features_total": len(checks),
    }


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    inp_path, out_path = args[0], args[1]
    jpath = None
    if "--json" in sys.argv:
        jpath = sys.argv[sys.argv.index("--json") + 1]

    inp = Pkg(inp_path)
    out = Pkg(out_path)
    checks = build_checks(inp, out)

    in_tok = inp.tokens()
    out_tok = out.tokens()
    out_set = set(out_tok)
    lost = [t for t in in_tok if t not in out_set]
    retained = 100.0 * (len(in_tok) - len(lost)) / len(in_tok) if in_tok else 0.0

    s = score(checks)
    res = {
        "input": inp_path,
        "output": out_path,
        "score": s,
        "text_retention_pct": round(retained, 1),
        "text_tokens_input": len(in_tok),
        "text_tokens_lost": len(lost),
        "text_lost_sample": lost[:25],
        "checks": [{"id": c[0], "label": c[1], "category": c[2], "weight": c[3],
                    "pass": c[4], "detail": c[5]} for c in checks],
    }

    print("=" * 78)
    print("INPUT : %s" % inp_path)
    print("OUTPUT: %s" % out_path)
    print("=" * 78)
    cats = {}
    for c in checks:
        cats.setdefault(c[2], []).append(c)
    for cat in ["package", "tracked", "fields", "sdt", "markup", "tables", "layout",
                "formatting", "text", "refs"]:
        if cat not in cats:
            continue
        print("\n[%s]" % cat.upper())
        for c in cats[cat]:
            mark = "PASS" if c[4] else "FAIL"
            det = ("  (%s)" % c[5]) if c[5] else ""
            print("  %-4s %-52s%s" % (mark, c[1], det))
    print("\n" + "-" * 78)
    print("WEIGHTED SCORE   : %s%%  (%d/%d)" % (s["weighted"], s["weighted_earned"], s["weighted_total"]))
    print("CRITICAL FEATURES: %s%%  (%d/%d)" % (s["critical_pct"], s["critical_passed"], s["critical_total"]))
    print("TEXT RETENTION   : %s%%  (%d tokens lost)" % (res["text_retention_pct"], len(lost)))
    if lost:
        print("LOST TEXT SAMPLE : %s" % ", ".join(lost[:20]))
    print("-" * 78)

    if jpath:
        with open(jpath, "w") as f:
            json.dump(res, f, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
