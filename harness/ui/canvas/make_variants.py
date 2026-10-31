#!/usr/bin/env python3
"""
Generate COPIES of the corpus fixture under harness/ui/canvas/variants/ with one
table feature removed at a time, to find which construct makes Canvas-Editor's
DOCX import crash. The original fixture is never touched.

Usage: python3 make_variants.py
"""
import os
import re
import shutil
import zipfile

SRC = '/Users/arthrod/temp/T/editors_trial/fixture/complex.docx'
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'variants')

# <w:tbl>, </w:tbl>, <w:tr>, </w:tr> -- the lookahead keeps <w:tblPr>/<w:trPr> out
TAG_RE = re.compile(r'<(/?)w:(tbl|tr)(?=[\s>])')


def find_spans(xml):
    """Return list of dicts describing every w:tbl / w:tr element span.

    Each span: {kind, start, end, parent} where `parent` is the start offset
    of the enclosing w:tbl / w:tr (None for a top-level element).
    """
    stack = []
    out = []
    for m in TAG_RE.finditer(xml):
        closing, name = m.group(1) == '/', m.group(2)
        if not closing:
            stack.append({'kind': name, 'start': m.start(),
                          'parent': stack[-1]['start'] if stack else None})
        else:
            for i in range(len(stack) - 1, -1, -1):
                if stack[i]['kind'] == name:
                    item = stack.pop(i)
                    out.append({'kind': item['kind'], 'start': item['start'],
                                'end': m.end(), 'parent': item['parent']})
                    break
    return out


def top_level_table(xml):
    """(start, end) of the first top-level <w:tbl>...</w:tbl>."""
    for sp in find_spans(xml):
        if sp['kind'] == 'tbl' and sp['parent'] is None:
            return sp['start'], sp['end']
    raise RuntimeError('no top-level table')


def direct_rows(xml, tbl_start, tbl_end):
    """(start, end) of the direct <w:tr> children of the table."""
    rows = []
    for sp in find_spans(xml):
        if sp['kind'] == 'tr' and sp['parent'] == tbl_start:
            rows.append((sp['start'], sp['end']))
    return rows


def cut(xml, start, end):
    return xml[:start] + xml[end:]


def write_variant(name, transform):
    zin = zipfile.ZipFile(SRC)
    doc = zin.read('word/document.xml').decode('utf8')
    new_doc = transform(doc)
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, name + '.docx')
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == 'word/document.xml':
                data = new_doc.encode('utf8')
            zout.writestr(item, data)
    zin.close()
    print('wrote', os.path.basename(path))


# ---- variants ------------------------------------------------------------

def v_no_vmerge(doc):
    n = len(re.findall(r'<w:vMerge\b', doc))
    out = re.sub(r'<w:vMerge\b[^>]*/>', '', doc)
    print(f'  removed {n} w:vMerge elements')
    return out


def v_no_gridspan(doc):
    n = len(re.findall(r'<w:gridSpan\b', doc))
    out = re.sub(r'<w:gridSpan\b[^>]*/>', '', doc)
    print(f'  removed {n} w:gridSpan elements')
    return out


def v_no_nested_table(doc):
    out = doc
    for _ in range(5):
        s2, e2 = top_level_table(out)
        target = None
        for sp in find_spans(out):
            if sp['kind'] == 'tbl' and sp['parent'] == s2:
                target = (sp['start'], sp['end'])
                break
        if not target:
            break
        out = cut(out, target[0], target[1])
    print('  nested table removed')
    return out


def v_no_tracked_rows(doc):
    s, e = top_level_table(doc)
    rows = direct_rows(doc, s, e)
    drop = [r for r in rows
            if re.search(r'<w:trPr>(?:(?!</w:trPr>).)*<w:(ins|del)\b', doc[r[0]:r[1]], re.S)]
    for r in sorted(drop, reverse=True):
        doc = cut(doc, r[0], r[1])
    print(f'  dropped {len(drop)} tracked rows of {len(rows)}')
    return doc


def v_no_table(doc):
    s, e = top_level_table(doc)
    return cut(doc, s, e)


def v_table_first_three_rows(doc):
    s, e = top_level_table(doc)
    rows = direct_rows(doc, s, e)
    keep = rows[:3]
    inner = ''.join(doc[a:b] for a, b in keep)
    return doc[:s] + '<w:tbl>' + inner + '</w:tbl>' + doc[e:]


def v_no_gridspan_and_vmerge(doc):
    return v_no_vmerge(v_no_gridspan(doc))


def v_no_vmerge_and_keep_gridspan3(doc):
    """Remove vertical merges only; the gridSpan=3 row stays."""
    return v_no_vmerge(doc)


VARIANTS = [
    ('v1_no_vmerge', v_no_vmerge),
    ('v2_no_gridspan', v_no_gridspan),
    ('v3_no_nested_table', v_no_nested_table),
    ('v4_no_tracked_rows', v_no_tracked_rows),
    ('v5_no_table', v_no_table),
    ('v6_table_first_three_rows', v_table_first_three_rows),
    ('v7_no_gridspan_and_vmerge', v_no_gridspan_and_vmerge),
]

if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT):
        if f.endswith('.docx'):
            os.remove(os.path.join(OUT, f))
    for name, fn in VARIANTS:
        print(name)
        write_variant(name, fn)
    shutil.copy(SRC, os.path.join(OUT, 'v0_original.docx'))
    print('copied original -> v0_original.docx')
