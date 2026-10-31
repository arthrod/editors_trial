#!/usr/bin/env python3
"""
Gap-free splitting of a w:body into its top-level children.

A regex that matches only a known tag list silently DROPS every element it
does not know about (w:altChunk, w:customXml, ...) and, worse, drops it from
every variant - so a bisect built on it can never find that element. This
scanner walks every tag, tracks depth, and returns spans that tile the body
exactly, with no gaps.
"""


def split_body(doc):
    """-> (head, blocks, tail); head ends with '<w:body>', tail starts with '</w:body>'."""
    bstart = doc.index("<w:body>") + len("<w:body>")
    bend = doc.index("</w:body>")
    head, body, tail = doc[:bstart], doc[bstart:bend], doc[bend:]

    blocks = []
    i = 0
    n = len(body)
    while i < n:
        # skip whitespace / text between top-level elements
        if body[i].isspace():
            i += 1
            continue
        if body[i] != "<":
            # stray text (should not happen in w:body) - keep it as its own block
            j = body.find("<", i)
            if j < 0:
                j = n
            blocks.append(body[i:j])
            i = j
            continue
        depth = 0
        j = i
        while j < n:
            lt = body.find("<", j)
            if lt < 0:
                j = n
                break
            if body.startswith("<!--", lt):
                j = body.find("-->", lt)
                j = n if j < 0 else j + 3
                continue
            if body.startswith("<?", lt) or body.startswith("<!", lt):
                j = body.find(">", lt)
                j = n if j < 0 else j + 1
                continue
            gt = body.find(">", lt)
            if gt < 0:
                j = n
                break
            tag = body[lt:gt + 1]
            closing = tag.startswith("</")
            selfclose = tag.endswith("/>")
            if not closing and not selfclose:
                depth += 1
            elif closing:
                depth -= 1
            j = gt + 1
            if depth == 0:
                break
        blocks.append(body[i:j])
        i = j
    return head, blocks, tail


def label(block):
    """Short human label for a block."""
    import re
    m = re.match(r"<(w:[A-Za-z]+)", block)
    kind = m.group(1) if m else "?"
    txt = "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", block))[:40]
    return "%-10s %s" % (kind, txt)
