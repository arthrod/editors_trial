"""Run with python3 -I; extract the DOJ field_body, stopping before 13,001 words."""
from html.parser import HTMLParser
from pathlib import Path
import hashlib
import json
import sys
from datetime import datetime, timezone

class Body(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0; self.parts = []; self.current = []
    def handle_starttag(self, tag, attrs):
        if tag == 'div':
            if self.depth: self.depth += 1
            elif 'field_body' in dict(attrs).get('class', '').split(): self.depth = 1
        if self.depth and tag in ('p', 'blockquote', 'h1', 'h2', 'h3', 'li'): self.flush()
        if self.depth and tag == 'br': self.current.append(' ')
    def handle_endtag(self, tag):
        if self.depth and tag in ('p', 'blockquote', 'h1', 'h2', 'h3', 'li'): self.flush()
        if self.depth and tag == 'div':
            self.depth -= 1
            if not self.depth: self.flush()
    def handle_data(self, value):
        if self.depth: self.current.append(value)
    def flush(self):
        value = ' '.join(''.join(self.current).split())
        if value: self.parts.append(value)
        self.current = []

if __name__ == '__main__':
    raw = Path(sys.argv[1]).read_bytes(); parser = Body(); parser.feed(raw.decode())
    chosen = []; count = 0
    for paragraph in parser.parts:
        words = len(paragraph.split())
        if count + words > 13000: break
        chosen.append(paragraph); count += words
    assert count > 12500, count
    data = ('\n\n'.join(chosen) + '\n').encode()
    destination = Path(__file__).parent / 'sg-brief-13000w.txt'
    destination.write_bytes(data)
    destination.with_suffix('.provenance.json').write_text(json.dumps({
        'url': 'https://www.justice.gov/osg/brief/lopez-v-gonzales-toledo-flores-v-united-states-brief-merits',
        'title': 'Lopez v. Gonzales; Toledo-Flores v. United States - Brief for the Respondents (Merits)',
        'retrieved_at': datetime.now(timezone.utc).isoformat(),
        'source_sha256': hashlib.sha256(raw).hexdigest(),
        'sha256': hashlib.sha256(data).hexdigest(), 'word_count': count,
        'source_word_count': sum(len(p.split()) for p in parser.parts),
        'paragraphs': len(chosen), 'public_domain': 'United States Government work, Office of the Solicitor General',
        'cut_rule': 'Longest prefix of complete HTML paragraphs at or below 13000 whitespace-delimited words; no padding.',
        'normalization': 'HTML entities decoded; intra-paragraph whitespace collapsed; paragraphs separated by two newlines. Headings, numbered sections and quoted paragraphs retain source text; no rich-text formatting inferred.'
    }, indent=2) + '\n')
    print(count, len(data), len(chosen))
