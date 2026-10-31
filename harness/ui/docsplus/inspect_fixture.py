"""Enumerate the corpus constructs in document order (fixture introspection)."""
import re
import sys

BASE = '/tmp/fxdocsplus/'
x = open(BASE + 'word/document.xml', encoding='utf-8').read()
body = x[x.find('<w:body>'):]

paras = re.findall(r'<w:p[ >].*?</w:p>', body, re.S)
for i, p in enumerate(paras):
    marks = []
    marks += re.findall(r'<wp:docPr[^>]*name="([^"]+)"', p)
    if '<w:object' in p:
        marks.append('w:object/OLE')
    if '<m:oMathPara' in p:
        marks.append('oMathPara')
    if '<mc:AlternateContent' in p:
        marks.append('AlternateContent')
    if '<w:ins ' in p:
        marks.append('w:ins')
    if '<w:del ' in p:
        marks.append('w:del')
    if '<w:trPr>' in p:
        marks.append('trPr')
    if '<w:commentReference' in p:
        marks.append('commentReference')
    if '<w:altChunk' in p:
        marks.append('altChunk')
    txt = ''.join(re.findall(r'<w:t[^>]*>(.*?)</w:t>', p, re.S))
    txt = re.sub(r'\s+', ' ', txt).strip()
    if marks:
        print('p[%02d] %-48s :: %s' % (i, '|'.join(marks), txt[:70]))

print('\n--- table rows with ins/del ---')
for m in re.finditer(r'<w:tr\b[^>]*>(.*?)</w:tr>', x, re.S):
    row = m.group(1)
    trpr = re.search(r'<w:trPr>(.*?)</w:trPr>', row, re.S)
    kind = ''
    if trpr:
        bits = re.findall(r'<w:(ins|del)\b', trpr.group(1))
        kind = 'trPr:' + ','.join(bits)
    t = ''.join(re.findall(r'<w:(?:del)?[tT][^>]*>(.*?)</w:(?:del)?[tT]>', row, re.S))
    t = re.sub(r'\s+', ' ', t).strip()
    if kind:
        print('  ', kind, '::', t[:70])

print('\n--- w:object (OLE) snippet ---')
m = re.search(r'<w:object.{0,700}', x, re.S)
print(m.group(0)[:700] if m else 'none')

print('\n--- tracked run ins/del ---')
for m in re.finditer(r'<w:(ins|del) [^>]*>(.*?)</w:\1>', x, re.S):
    inner = m.group(2)
    t = ''.join(re.findall(r'<w:(?:delText|t)[^>]*>(.*?)</w:(?:delText|t)>', inner, re.S))
    print('  ', m.group(1), '::', re.sub(r'\s+', ' ', t)[:80])

print('\n--- comments.xml ---')
c = open(BASE + 'word/comments.xml', encoding='utf-8').read()
print(re.sub(r'\s+', ' ', c)[:600])

print('\n--- altChunk ---')
m = re.search(r'<w:altChunk[^>]*>', x)
print(m.group(0) if m else 'none')
print(open(BASE + 'word/afchunk.html', encoding='utf-8').read()[:300])
