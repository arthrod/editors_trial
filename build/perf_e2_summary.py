"""Report E2's short version (#227): what a reader asks, answered from the facts.

One small table per question, editors in the order given (alphabetical in the
report), one column per document size. A figure is the middle of the two
seeds' medians of a cell that reproduced; nothing here is measured again and
nothing is ranked.
"""
from __future__ import annotations

import re
from statistics import median

SIZES = (
    ('prose-500w', '500 words'),
    ('prose-5kw', '5,000 words'),
    ('prose-50kw', '50,000 words'),
    ('prose-250kw', '250,000 words'),
)
HALF_MILLION = ('prose-500kw', '500,000 words')

# (key, heading, criterion, measure, sizes, what the table times)
SECTIONS = (
    ('open', 'Opening a document', 'C11', '', SIZES + (HALF_MILLION,),
     'From the moment the page is asked for the document until the first frame that shows it, '
     'with the text on screen checked against the document.'),
    ('type', 'Typing one character', 'C05', 'warm_steady', SIZES,
     'From a key press until the frame in which that character is on screen, in a document that is already open.'),
    ('caret', 'Clicking to place the caret', 'C07', '', SIZES,
     'From a click in the text until the next frame the editor paints.'),
    ('paste', 'Pasting a block of text', 'C08', '', SIZES,
     'From the paste of a 1,500-character block until the first frame in which the page visibly changed.'),
    ('undo', 'Undoing', 'C09', '', SIZES,
     'From the undo of one typed character until the first frame that differs.'),
    ('scroll', 'Scrolling', 'C10', '', SIZES,
     'From a scroll of the document until the first frame in which its content has moved.'),
    ('memory', 'Memory with the document open', 'C17', 'quiescent', SIZES,
     'The memory of the whole browser with the document open, read two seconds after a short burst of typing. '
     'It includes the browser itself, so it is not the editor alone.'),
)

DASH = '—'
UNDER = 'under 1 frame'


def _key(editor: str, criterion: str, measure: str, workload: str) -> str:
    return 'perf.e2.%s.%s' % (editor, criterion) + ('.' + measure if measure else '') + '.' + workload


_ROUND = re.compile(r'(first|second): not enough samples \(n = (\d+) of \d+; reasons ([^)]*)\)')


def _why(reason: str) -> str:
    """One word for a cell that has no figure.

    "crashed" and "does not apply" are said only when both rounds kept no
    launch and every launch of both gave that one reason; anything mixed is
    "no figure".
    """
    if 'medians outside tolerance' in reason:
        return 'varied'
    # The reader writes "key: count; key: count; also key: count" (e2_cells.publication_text).
    rounds = {name: (int(kept), {part.strip().removeprefix('also ').split(':')[0].strip()
                                 for part in reasons.split(';') if part.strip()})
              for name, kept, reasons in _ROUND.findall(reason)}
    if set(rounds) == {'first', 'second'} and all(kept == 0 for kept, _names in rounds.values()):
        names = set().union(*(names for _kept, names in rounds.values()))
        if names == {'not_applicable'}:
            return 'does not apply'
        if names and names <= {'crash', 'editor_crash'}:
            return 'crashed'
    return 'no figure'


def _seed_median(cell: dict) -> float:
    stats = cell.get('stats') or {}
    if isinstance(stats.get('median'), (int, float)):
        return float(stats['median'])
    return float(median(cell['kept_ms']))


def fmt(value: float, unit: str, frame: float = 0.0) -> str:
    if unit == 'bytes':
        mib = value / 2 ** 20
        return '%.1f GiB' % (mib / 1024) if mib >= 1024 else '%d MiB' % round(mib)
    if frame and value < frame:
        return UNDER
    if value >= 100_000:
        return '%d s' % round(value / 1000)
    if value >= 1000:
        return '%.1f s' % (value / 1000)
    return '%d ms' % round(value)


def _cell(facts: dict, key: str, editor: str, criterion: str, measure: str, workload: str):
    """(text, value or None) of one cell; DASH when the cell is not in these runs."""
    base = _key(editor, criterion, measure, workload)
    reproduced = facts.get(base + '.reproduced')
    if reproduced is None:
        return DASH, None
    if not reproduced:
        return _why(str(facts.get(base + '.reason') or '')), None
    first, second = facts[base + '.primary'], facts[base + '.reproduction']
    value = (_seed_median(first) + _seed_median(second)) / 2
    unit = first.get('sample_unit') or 'ms'
    # "under 1 frame" only when each seed's median is under that seed's own
    # frame; a middle that dips below while one seed is above is printed as
    # the time it is.
    under = all((cell.get('frame_interval_ms') or 0) > _seed_median(cell) for cell in (first, second))
    frame = max(first.get('frame_interval_ms') or 0, second.get('frame_interval_ms') or 0) if under else 0.0
    facts['perf.e2.short.%s.%s.%s' % (key, editor, workload)] = value
    text = UNDER if under and unit != 'bytes' else fmt(value, unit, frame)
    # The reference table marks an opening whose text was not checked; so does this one, and it stays out of the range.
    if criterion == 'C11' and not (first.get('content_verified') is True and second.get('content_verified') is True):
        return text + ' (text not checked)', None
    return text, (value, text)


def _ends(values) -> tuple[str, str]:
    """The printed text of the lowest and of the highest cell of one column.

    A cell printed as "under 1 frame" is below every cell printed as a time,
    whatever its middle: the two cannot be told apart finer than that.
    """
    timed = [figure for figure in values if figure[1] != UNDER]
    if len(timed) < len(values):
        return UNDER, (max(timed)[1] if timed else UNDER)
    return min(timed)[1], max(timed)[1]


def _range_sentence(columns) -> str:
    """Lowest and highest printed figure of the first and of the last column that holds two or more; no editor is named."""
    usable = [(title, values) for title, values in columns if len(values) >= 2]
    if not usable:
        return ''
    parts = []
    for title, values in ([usable[0], usable[-1]] if len(usable) > 1 else [usable[0]]):
        low, high = _ends(values)
        said = 'are all %s' % low if len({text for _value, text in values}) == 1 else 'run from %s to %s' % (low, high)
        parts.append('%s%s the figures %s' % ('at ' if parts else 'At ', title, said))
    text = parts[0] if len(parts) == 1 else parts[0] + '; ' + parts[1].replace(
        ' the figures run', ',').replace(' the figures are', ', they are')
    return text + '.'


def short_version(facts: dict, editors, display) -> str:
    blocks = []
    for key, heading, criterion, measure, sizes, what in SECTIONS:
        rows, columns = [], [(title, []) for _workload, title in sizes]
        for editor in editors:
            texts = []
            for index, (workload, _title) in enumerate(sizes):
                text, figure = _cell(facts, key, editor, criterion, measure, workload)
                texts.append(text)
                if figure:
                    columns[index][1].append(figure)
            if any(text != DASH for text in texts):
                rows.append('| %s | %s |' % (display.get(editor, editor), ' | '.join(texts)))
        if not any(values for _title, values in columns):
            continue
        lines = ['### %s' % heading, '', what, '',
                 '| Editor | ' + ' | '.join(title for _workload, title in sizes) + ' |',
                 '|---' * (len(sizes) + 1) + '|', *rows]
        sentence = _range_sentence(columns)
        if sentence:
            lines += ['', sentence]
        blocks.append('\n'.join(lines))
    return '\n\n'.join(blocks) if blocks else 'not in these runs.'
