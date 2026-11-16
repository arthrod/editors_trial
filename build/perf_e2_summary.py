"""Report E2's short version (#227): what a reader asks, answered from the facts.

One small table per question, editors in the order given (alphabetical in the
report), one column per document size. A figure is the middle of the two
seeds' medians of a cell that reproduced; nothing here is measured again and
nothing is ranked.
"""
from __future__ import annotations

import math
import re
from statistics import median

from build.perf_e2_keys import cell_key

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
     'From the moment the page is asked for the document until the first frame that shows it. '
     'The length of the text the editor holds is checked against the document (within 2 percent). '
     'For the editors that draw on a canvas, that text is read from the editor and not from the picture '
     '(Appendix D); content and formatting are not checked here.'),
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
UNDER = 'under '

#: The typing lanes refuse a launch with this reason when the editor exposes no glyph outline (#238).
GLYPH_REASON = 'no_glyph_geometry_to_witness_the_keystrokes_own_paint'
#: Recorded reasons for which "does not apply" is true: there was nothing to measure.
NOTHING_TO_MEASURE = frozenset({'no_deferred_work'})


def under_text(frame: float) -> str:
    """A time shorter than one redraw of the screen, in the unit a reader has: "under 17 ms"."""
    return '%s%d ms' % (UNDER, math.ceil(frame))


def reason_words(reason: str) -> str | None:
    """What a recorded refusal reason means, for a reader; None when nobody has written words for it."""
    if reason == GLYPH_REASON:
        return ("the harness times typing to the typed character's own outline on the page, and this editor draws its "
                'text where the harness cannot read an outline. The character was typed and the edit was confirmed; '
                'the time was not taken (issue #238)')
    if reason == 'document_content_unverifiable':
        return "the harness could not read this editor's text from the page to check the document"
    if reason == 'expected_edit_not_confirmed':
        return 'the typed character was not found in the editor afterwards'
    if reason == 'no_painted_frame':
        return 'no redraw of the screen was seen after the action in the time allowed'
    if reason == 'correctness: fixture_body_mismatch':
        return 'the text the editor held did not match the document'
    if reason == 'cpu_throttled':
        return "the machine's processor quota was throttled during the launch"
    if 'Target crashed' in reason or 'Page crashed' in reason or reason.startswith('page_lost'):
        return "the editor's page crashed"
    if reason.startswith('editor_load_failed'):
        return 'the editor failed to load the document'
    if 'probe produced no line before the timeout' in reason:
        return 'the reading did not come back in the time allowed'
    return None


_CODE_WORDS = {
    'crash': "the editor's page crashed", 'editor_crash': "the editor's page crashed",
    'editor_timeout': 'the editor did not answer in the time allowed',
    'paint_witness_unavailable': 'no redraw of the screen was seen after the action in the time allowed',
    'unverified': 'a check of the result failed',
    'cpu_throttled': "the machine's processor quota was throttled during the launch",
}


_ROUND = re.compile(r'(first|second): not enough samples \(n = (\d+) of (\d+); reasons ([^)]*)\)')
_COUNT = re.compile(r'\s*([^:;]+): (\d+)\s*$')


def _round_reasons(text: str) -> dict:
    """{reason: count} of one round's primary reasons, in the reader's format.

    The reader writes "key: count; key: count; also key: count"
    (e2_cells.publication_text). What follows "also" describes launches
    already counted, so it is left out. A part that is not "key: count"
    ("none counted") makes the round unreadable: {}.
    """
    counts = {}
    for part in text.split(';'):
        if part.strip().startswith('also '):
            break
        match = _COUNT.match(part)
        if not match:
            return {}
        counts[match.group(1).strip()] = int(match.group(2))
    return counts


def _recorded(cells) -> set:
    """Every reason the refused launches of these round cells recorded."""
    return {reason for cell in cells if isinstance(cell, dict)
            for reasons in (cell.get('refusal_reasons') or {}).values() for reason in reasons}


def _why(reason: str, cells=()) -> str:
    """A word or two for a cell that has no figure.

    "crashed", "not measured" and "does not apply" are said only when both
    rounds kept no launch and the counted reasons of each round account for
    every launch it scheduled, all of them that one reason; anything else is
    "no figure". "does not apply" needs more: every recorded reason must be
    one for which there was nothing to measure. A launch the harness refused
    because it could not take the measurement is "not measured" (#239).
    """
    if 'medians outside tolerance' in reason:
        return 'varied'
    rounds = {name: (int(kept), int(scheduled), _round_reasons(reasons))
              for name, kept, scheduled, reasons in _ROUND.findall(reason)}
    if set(rounds) != {'first', 'second'}:
        return 'no figure'
    if any(kept or sum(counts.values()) != scheduled for kept, scheduled, counts in rounds.values()):
        return 'no figure'
    names = set().union(*(counts for _kept, _scheduled, counts in rounds.values()))
    if names == {'not_applicable'}:
        recorded = _recorded(cells)
        return 'does not apply' if recorded and recorded <= NOTHING_TO_MEASURE else 'not measured'
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
        return under_text(frame)
    if value >= 100_000:
        return '%d s' % round(value / 1000)
    if value >= 1000:
        return '%.1f s' % (value / 1000)
    return '%d ms' % round(value)


def _fine(value: float, unit: str) -> str:
    """One more digit than fmt, for the two ends of a range that would otherwise read the same."""
    if unit == 'bytes':
        return '%.1f MiB' % (value / 2 ** 20)
    return '%.2f s' % (value / 1000) if value >= 1000 else '%.1f ms' % value


def _range(rounds: dict) -> str:
    """The two rounds' medians of a cell that did not reproduce, lower first: "48 ms to 81 ms"."""
    unit = rounds.get('sample_unit') or 'ms'
    frame = rounds.get('frame_interval_ms') or 0.0
    low, high = sorted(rounds[name]['median'] for name in ('first', 'second'))
    texts = [fmt(value, unit, frame if unit != 'bytes' else 0.0) for value in (low, high)]
    if texts[0] == texts[1]:
        texts = [_fine(low, unit), _fine(high, unit)]
    return '%s to %s' % tuple(texts)


def _has_rounds(rounds) -> bool:
    return isinstance(rounds, dict) and all(
        isinstance((rounds.get(name) or {}).get('median'), (int, float)) for name in ('first', 'second'))


def _cell(facts: dict, key: str, editor: str, criterion: str, measure: str, workload: str):
    """(text, value or None) of one cell; DASH when the cell is not in these runs."""
    base = cell_key(editor, criterion, measure, workload)
    reproduced = facts.get(base + '.reproduced')
    if reproduced is None:
        return DASH, None
    if not reproduced:
        rounds = facts.get(base + '.rounds')
        if _has_rounds(rounds):
            return _range(rounds), None
        return _why(str(facts.get(base + '.reason') or ''), (facts.get(base + '.primary'), facts.get(base + '.reproduction'))), None
    first, second = facts[base + '.primary'], facts[base + '.reproduction']
    value = (_seed_median(first) + _seed_median(second)) / 2
    unit = first.get('sample_unit') or 'ms'
    # "under 17 ms" (one redraw) only when each seed's median is under that seed's own
    # frame; a middle that dips below while one seed is above is printed as
    # the time it is.
    under = all((cell.get('frame_interval_ms') or 0) > _seed_median(cell) for cell in (first, second))
    frame = max(first.get('frame_interval_ms') or 0, second.get('frame_interval_ms') or 0) if under else 0.0
    facts['perf.e2.short.%s.%s.%s' % (key, editor, workload)] = value
    text = under_text(frame) if under and unit != 'bytes' else fmt(value, unit, frame)
    # The reference table marks an opening whose text was not checked; so does this one, and it stays out of the range.
    if criterion == 'C11' and not (first.get('content_verified') is True and second.get('content_verified') is True):
        return text + ' (text not checked)', None
    return text, (value, text)


def _ends(values) -> tuple[str, str]:
    """The printed text of the lowest and of the highest cell of one column.

    A cell printed as under one redraw ("under 17 ms") is below every cell
    printed as a time, whatever its middle: the two cannot be told apart
    finer than that.
    """
    timed = [figure for figure in values if not figure[1].startswith(UNDER)]
    if len(timed) < len(values):
        under = next(figure[1] for figure in values if figure[1].startswith(UNDER))
        return under, (max(timed)[1] if timed else under)
    return min(timed)[1], max(timed)[1]


def _range_sentence(columns, editors: int) -> str:
    """How many of the table's editors have a figure, and the lowest and highest printed, for the first
    and the last column that holds two or more; no editor is named."""
    usable = [(title, values) for title, values in columns if len(values) >= 2]
    if not usable:
        return ''
    parts = []
    for title, values in ([usable[0], usable[-1]] if len(usable) > 1 else [usable[0]]):
        low, high = _ends(values)
        said = 'all %s' % low if len({text for _value, text in values}) == 1 else 'from %s to %s' % (low, high)
        count = '%d of %d' % (len(values), editors)
        parts.append('%s %s, %s%s, %s' % ('at' if parts else 'At', title, count, '' if parts else ' editors have a figure', said))
    return '; '.join(parts) + '.'


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
        sentence = _range_sentence(columns, len(rows))
        if sentence:
            lines += ['', sentence]
        blocks.append('\n'.join(lines))
    return '\n\n'.join(blocks) if blocks else 'not in these runs.'


# #239: the appendix that says, cell by cell, why a results cell has no single figure.

_KINDS = (('ranges', None), ('varied', 'varied'), ('not_measured', 'not measured'), ('does_not_apply', 'does not apply'),
          ('no_figure', 'no figure'), ('crashed', 'crashed'))


def _refused_words(cell: dict) -> str:
    """Why one round's launches were refused: the recorded reasons, in words, with their counts."""
    refusals = cell.get('refusals') or {}
    recorded = cell.get('refusal_reasons') or {}
    parts = []
    for code, count in sorted(refusals.items()):
        words = [reason_words(reason) or 'recorded as `%s`' % reason.replace('|', '/') for reason in recorded.get(code, [])]
        said = '; also '.join(words) if words else _CODE_WORDS.get(code, 'recorded as `%s`' % code)
        parts.append((count, said))
    if len(parts) == 1:
        return parts[0][1]
    return '; '.join('%d, %s' % part for part in parts)


def _round_sentence(name: str, cell, counted) -> str:
    if counted is None:
        return 'The %s round kept enough launches.' % name
    kept, scheduled, _counts = counted
    refused = scheduled - kept
    why = _refused_words(cell) if isinstance(cell, dict) else ''
    return '%s round: %d of %d launches kept; %d refused%s.' % (
        name.capitalize(), kept, scheduled, refused, ': ' + why if why else '')


def _why_text(facts: dict, base: str) -> str:
    rounds = facts.get(base + '.rounds')
    if _has_rounds(rounds):
        unit = rounds.get('sample_unit') or 'ms'
        frame = rounds.get('frame_interval_ms') or 0.0
        figures = [fmt(rounds[name]['median'], unit, frame if unit != 'bytes' else 0.0) for name in ('first', 'second')]
        if figures[0] == figures[1]:
            figures = [_fine(rounds[name]['median'], unit) for name in ('first', 'second')]
        percent = round((rounds.get('rel_tol') or 0) * 100)
        tolerance = ('the larger of %d percent and one redraw of the screen (%.1f ms)' % (percent, frame)
                     if frame and unit != 'bytes' else '%d percent' % percent)
        return ('The first round gave %s (%d launches) and the second %s (%d launches). They differ by more than the '
                'tolerance: %s.' % (figures[0], rounds['first'].get('n') or 0, figures[1], rounds['second'].get('n') or 0, tolerance))
    reason = str(facts.get(base + '.reason') or '')
    if 'medians outside tolerance' in reason:
        return 'The two rounds disagreed by more than the tolerance; no medians were recorded for this cell in the facts.'
    counted = {name: (int(kept), int(scheduled), _round_reasons(reasons))
               for name, kept, scheduled, reasons in _ROUND.findall(reason)}
    if not counted:
        return 'Recorded as: %s.' % (reason.replace('|', '/') or 'no reason recorded')
    cells = {'first': facts.get(base + '.primary'), 'second': facts.get(base + '.reproduction')}
    return ' '.join(_round_sentence(name, cells[name], counted.get(name)) for name in ('first', 'second'))


def no_figure_appendix(facts: dict, editors, display) -> tuple[str, dict]:
    """(text, counts): one row per results cell that is in these runs and has no single figure.

    Rows follow the results tables: table, then editor in the order given,
    then document size. Nothing is ranked.
    """
    rows, counts = [], {'perf.e2.no_figure.%s' % kind: 0 for kind, _label in _KINDS}
    for key, heading, criterion, measure, sizes, _what in SECTIONS:
        for editor in editors:
            for workload, title in sizes:
                text, figure = _cell(facts, key, editor, criterion, measure, workload)
                if figure or text == DASH or text.endswith('(text not checked)'):
                    continue
                kind = next((kind for kind, label in _KINDS if label == text), 'ranges')
                counts['perf.e2.no_figure.%s' % kind] += 1
                rows.append('| %s | %s | %s | %s | %s |' % (
                    heading, display.get(editor, editor), title, text, _why_text(facts, cell_key(editor, criterion, measure, workload))))
    counts['perf.e2.no_figure.rows'] = len(rows)
    if not rows:
        return 'Every cell of the results tables has a single figure.', counts
    return '\n'.join(['| Table | Editor | Document | Printed | Why |', '|---|---|---|---|---|', *rows]), counts
