#!/usr/bin/env python3
"""Build the ten hostile packages. This writes compressed zip bytes only.

It does not parse the hostile XML, expand entities, follow a URL, or extract
a traversal entry. Callers pass a directory they are prepared to delete.
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
REL = "http://schemas.openxmlformats.org/package/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
R_DOC = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
BODY = "BOMB_BODY_OK"
LOL = "BOMB_LOL"
SLIP = "ZIPSLIP_CANARY"
XSS_JS = "javascript:alert(1)"
XSS_MARK = "window.__xss=1"
SSRF = "http://127.0.0.1:9/ssrf-probe-editors-trial"
UNC = "\\\\127.0.0.1\\share\\leak.dotm"
PNG_MARK = "NOT_A_PNG_SCRIPT"
SLIP_NAME = "pwned-editors-trial.xml"


def _xml_decl(body: str) -> bytes:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' + body
    ).encode("utf-8")


def _document(inner: str, prelude: str = "") -> bytes:
    return _xml_decl(
        prelude
        + f'<w:document xmlns:w="{W}" xmlns:r="{REL}"><w:body>'
        + f"<w:p><w:r><w:t>{BODY}</w:t></w:r></w:p>"
        + inner
        + "</w:body></w:document>"
    )


def _content_types(extra: str = "") -> bytes:
    return _xml_decl(
        f'<Types xmlns="{CT}">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        f"{extra}</Types>"
    )


def _root_rels() -> bytes:
    return _xml_decl(
        f'<Relationships xmlns="{REL}">'
        f'<Relationship Id="rId1" Type="{R_DOC}" Target="word/document.xml"/>'
        "</Relationships>"
    )


def _doc_rels(extra: str = "") -> bytes:
    return _xml_decl(f'<Relationships xmlns="{REL}">{extra}</Relationships>')


def _pack(parts: list[tuple[str, bytes]], stored: set[str] | None = None) -> bytes:
    buf = io.BytesIO()
    stored = stored or set()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in parts:
            info = zipfile.ZipInfo(filename=name)
            if name in stored:
                info.compress_type = zipfile.ZIP_STORED
            else:
                info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, data, compresslevel=None if name in stored else 9)
    return buf.getvalue()


def _base(document: bytes, extra: str = "", types: str = "") -> list[tuple[str, bytes]]:
    return [
        ("[Content_Types].xml", _content_types(types)),
        ("_rels/.rels", _root_rels()),
        ("word/document.xml", document),
        ("word/_rels/document.xml.rels", _doc_rels(extra)),
    ]


def build(dest: Path, canary_uri: str) -> dict[str, Path]:
    """Write B1.docx … B10.docx under dest. canary_uri is a file: URL."""
    dest.mkdir(parents=True, exist_ok=True)
    # A repeated byte tops out near 1032:1 in one deflate member. 2500:1 is not a real deflate stream.
    space = b" " * (66 * 1024 * 1024)
    b1_doc = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        b'<w:document xmlns:w="' + W.encode() + b'"><w:body><w:p><w:r><w:t>'
        + space
        + b"</w:t></w:r></w:p></w:body></w:document>"
    )
    packages: dict[str, list[tuple[str, bytes]]] = {}
    packages["B1"] = _base(b1_doc)

    b2 = _base(_document(""))
    for i in range(25000):
        b2.append((f"customXml/p{i:05d}.xml", b"<x/>"))
    packages["B2"] = b2

    attrs = " ".join(f'bombAttr{i}=""' for i in range(500000))
    packages["B3"] = _base(_document(f"<w:p {attrs}><w:r><w:t>a</w:t></w:r></w:p>"))

    deep = "<w:t>DEEP_LEAF</w:t>"
    for _ in range(5000):
        deep = f"<w:sdt><w:sdtContent>{deep}</w:sdtContent></w:sdt>"
    packages["B4"] = _base(_document(deep))
    nest = "<w:p><w:r><w:t>TBL_LEAF</w:t></w:r></w:p>"
    for _ in range(250):
        nest = f"<w:tbl><w:tr><w:tc>{nest}</w:tc></w:tr></w:tbl>"
    packages["B4"] = _base(
        _document(deep + nest)
    )

    lol = f'<!ENTITY lol0 "{LOL}">'
    for level in range(1, 7):
        prev = f"lol{level - 1}"
        lol += f'<!ENTITY lol{level} "' + (f"&{prev};" * 10) + '">'
    prelude = (
        "<!DOCTYPE w:document ["
        + lol
        + f'<!ENTITY xxe SYSTEM "file:///etc/hosts">'
        + f'<!ENTITY canary SYSTEM "{canary_uri}">'
        + "]>"
    )
    packages["B5"] = _base(_document("<w:p><w:r><w:t>&lol6;&xxe;&canary;</w:t></w:r></w:p>", prelude))

    packages["B6"] = _base(
        _document(""),
        extra=(
            '<Relationship Id="rIdSlip" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" '
            'Target="../../../etc/passwd" TargetMode="External"/>'
            '<Relationship Id="rIdHosts" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" '
            'Target="/etc/hosts" TargetMode="External"/>'
        ),
    )
    packages["B6"].append((f"../escaped/{SLIP_NAME}", SLIP.encode("ascii")))

    packages["B7"] = _base(
        _document(""),
        extra=(
            '<Relationship Id="rIdTpl" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/attachedTemplate" '
            f'Target="{SSRF}" TargetMode="External"/>'
            '<Relationship Id="rIdUnc" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/subDocument" '
            f'Target="{UNC}" TargetMode="External"/>'
        ),
    )

    html = f"<html><script>{XSS_MARK}</script></html>".encode("utf-8")
    packages["B8"] = _base(
        _document(
            f'<w:hyperlink r:id="rIdJs"><w:r><w:t>link</w:t></w:r></w:hyperlink>'
        ),
        extra=(
            '<Relationship Id="rIdJs" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" '
            f'Target="{XSS_JS}" TargetMode="External"/>'
            '<Relationship Id="rIdHtml" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/aFChunk" '
            'Target="afchunk.html"/>'
        ),
        types=(
            '<Override PartName="/word/afchunk.html" ContentType="text/html"/>'
        ),
    )
    packages["B8"].append(("word/afchunk.html", html))

    sources = "".join(
        f"<b:Source><b:Tag>s{i}</b:Tag><b:SourceType>Book</b:SourceType></b:Source>"
        for i in range(60000)
    )
    packages["B9"] = _base(
        _document(
            '<w:tbl><w:tr><w:tc><w:tcPr><w:gridSpan w:val="1000000"/></w:tcPr>'
            "<w:p><w:r><w:t>cell</w:t></w:r></w:p></w:tc></w:tr></w:tbl>"
            + "".join('<w:p><w:r><w:fldChar w:fldCharType="begin"/></w:r></w:p>' for _ in range(2000))
        )
    )
    packages["B9"].append(
        (
            "customXml/item1.xml",
            _xml_decl(f"<b:Sources xmlns:b=\"http://schemas.openxmlformats.org/officeDocument/2006/bibliography\">{sources}</b:Sources>"),
        )
    )

    packages["B10"] = _base(
        _document(""),
        extra=(
            '<Relationship Id="rIdImg" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
            'Target="media/image1.png"/>'
        ),
    )
    packages["B10"].extend(
        [
            ("word/styles.xml", b"\xff\xfe<<<"),
            ("word/comments.xml", b"<w:comments"),
            ("word/media/image1.png", PNG_MARK.encode("ascii")),
        ]
    )

    written: dict[str, Path] = {}
    for bid, parts in packages.items():
        path = dest / f"{bid}.docx"
        stored = {name for name, _ in parts if name.startswith("customXml/p")}
        path.write_bytes(_pack(parts, stored))
        written[bid] = path
    return written


def main() -> None:
    import sys

    dest = Path(sys.argv[1])
    canary = sys.argv[2] if len(sys.argv) > 2 else "file:///tmp/xxe-canary.txt"
    built = build(dest, canary)
    for bid, path in built.items():
        print(f"{bid} {path} {path.stat().st_size}")


if __name__ == "__main__":
    main()
