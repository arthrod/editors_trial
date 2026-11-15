"""Report E2's short version (#227): one small table per question a reader asks, built from the facts."""
from __future__ import annotations

from build import perf_e2_summary as summary

DISPLAY = {'plate': 'Plate.js', 'folio': 'Folio', 'docen': 'Docen'}


def _cell(median, *, unit='ms', frame=16.7):
    return {'sample_unit': unit, 'kept_ms': [median] * 10, 'frame_interval_ms': frame, 'stats': {'n': 10, 'median': median},
            'content_verified': True}


def _put(facts, editor, criterion, workload, first, second=None, *, measure='', unit='ms', reason=None):
    key = 'perf.e2.%s.%s' % (editor, criterion) + ('.' + measure if measure else '') + '.' + workload
    if reason:
        facts[key + '.reproduced'] = False
        facts[key + '.reason'] = reason
        return
    facts[key + '.reproduced'] = True
    facts[key + '.primary'] = _cell(first, unit=unit)
    facts[key + '.reproduction'] = _cell(first if second is None else second, unit=unit)


def _facts():
    facts = {}
    _put(facts, 'plate', 'C11', 'prose-500w', 740, 760)
    _put(facts, 'plate', 'C11', 'prose-250kw', 19000, 19200)
    _put(facts, 'folio', 'C11', 'prose-500w', 800)
    _put(facts, 'folio', 'C11', 'prose-250kw', 4660)
    _put(facts, 'docen', 'C11', 'prose-500w', 1100)
    _put(facts, 'docen', 'C11', 'prose-250kw', 0, reason='medians outside tolerance')
    return facts


def test_a_figure_is_the_middle_of_the_two_seed_medians_in_a_unit_a_person_reads():
    facts = _facts()
    text = summary.short_version(facts, ['docen', 'folio', 'plate'], DISPLAY)
    assert '| Plate.js | 750 ms | — | — | 19.1 s | — |' in text
    assert facts['perf.e2.short.open.plate.prose-250kw'] == 19100.0


def test_editors_stay_in_the_order_given_and_no_row_is_ranked():
    text = summary.short_version(_facts(), ['docen', 'folio', 'plate'], DISPLAY)
    opening = text.split('### Opening a document')[1].split('###')[0]
    assert opening.index('| Docen |') < opening.index('| Folio |') < opening.index('| Plate.js |')
    for word in ('fastest', 'slowest', 'best', 'worst', 'winner'):
        assert word not in text.lower()


def test_a_cell_without_a_figure_says_why_in_one_word():
    facts = _facts()
    crash = 'first: not enough samples (n = 0 of 10; reasons editor_crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10)'
    not_applicable = 'first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10)'
    _put(facts, 'folio', 'C11', 'prose-5kw', 0, reason=crash)
    _put(facts, 'folio', 'C11', 'prose-50kw', 0, reason=not_applicable)
    _put(facts, 'folio', 'C11', 'prose-500kw', 0, reason='first: not enough samples (n = 2 of 10; reasons unverified: 8)')
    text = summary.short_version(facts, ['docen', 'folio', 'plate'], DISPLAY)
    assert '| Folio | 800 ms | crashed | does not apply | 4.7 s | no figure |' in text
    assert '| Docen | 1.1 s | — | — | varied | — |' in text


def test_the_range_sentence_names_no_editor():
    text = summary.short_version(_facts(), ['docen', 'folio', 'plate'], DISPLAY)
    assert 'At 500 words the figures run from 750 ms to 1.1 s; at 250,000 words, from 4.7 s to 19.1 s.' in text


def test_times_under_one_frame_and_memory_are_formatted_for_a_reader():
    facts = {}
    _put(facts, 'plate', 'C10', 'prose-500w', 12.0, 13.0)
    _put(facts, 'plate', 'C17', 'prose-500w', 600 * 2 ** 20, measure='quiescent', unit='bytes')
    _put(facts, 'plate', 'C17', 'prose-250kw', 2060 * 2 ** 20, measure='quiescent', unit='bytes')
    _put(facts, 'plate', 'C11', 'prose-500kw', 285466)
    text = summary.short_version(facts, ['plate'], DISPLAY)
    assert '| Plate.js | under 1 frame |' in text
    assert '| Plate.js | 600 MiB | — | — | 2.0 GiB |' in text
    assert '| 285 s |' in text


def test_a_section_with_no_figure_at_all_is_left_out_and_an_empty_report_says_so():
    assert summary.short_version({}, ['plate'], DISPLAY) == 'not in these runs.'
    text = summary.short_version(_facts(), ['docen', 'folio', 'plate'], DISPLAY)
    assert '### Opening a document' in text and '### Scrolling' not in text


def test_the_template_carries_the_short_version_before_the_reference():
    from pathlib import Path
    template = (Path(__file__).resolve().parent.parent / 'templates/reports/Report E2 - Speed in the Browser (2026).md').read_text(encoding='utf-8')
    assert template.index('## The short version') < template.index('{{perf.e2.short_version}}') < template.index('## What is measured')


def test_a_column_whose_figures_all_read_the_same_says_so():
    facts = {}
    for editor in ('plate', 'folio'):
        _put(facts, editor, 'C10', 'prose-500w', 12.0)
        _put(facts, editor, 'C10', 'prose-250kw', 12.0 if editor == 'plate' else 60.0)
    text = summary.short_version(facts, ['folio', 'plate'], DISPLAY)
    assert 'At 500 words the figures are all under 1 frame; at 250,000 words, from under 1 frame to 60 ms.' in text


def test_under_one_frame_needs_both_seeds_under_it():
    """Review of #227: 14 ms and 18 ms have a middle of 16 ms, and one seed is over a frame."""
    facts = {}
    _put(facts, 'plate', 'C10', 'prose-500w', 14.0, 18.0)
    _put(facts, 'plate', 'C10', 'prose-5kw', 14.0, 15.0)
    text = summary.short_version(facts, ['plate'], DISPLAY)
    assert '| Plate.js | 16 ms | under 1 frame |' in text


# --- CodeRabbit on #229 ---

def test_the_range_sentence_says_all_only_when_every_printed_cell_reads_the_same():
    """A 15 ms cell printed as a time (one seed over a frame) beside cells under a frame is not 'all under 1 frame'."""
    facts = {}
    _put(facts, 'docen', 'C10', 'prose-500w', 8.0, 9.0)
    _put(facts, 'folio', 'C10', 'prose-500w', 12.0, 18.0)   # middle 15 ms, second seed over a frame
    _put(facts, 'plate', 'C10', 'prose-500w', 16.0, 16.4)   # the highest value, and under a frame in both
    text = summary.short_version(facts, ['docen', 'folio', 'plate'], DISPLAY)
    assert '| Folio | 15 ms |' in text
    assert '| Plate.js | under 1 frame |' in text
    assert 'are all under 1 frame' not in text
    assert 'At 500 words the figures run from under 1 frame to 15 ms.' in text


def test_under_one_frame_compares_each_seed_with_its_own_frame():
    facts = {}
    key = 'perf.e2.plate.C10.prose-500w'
    facts[key + '.reproduced'] = True
    facts[key + '.primary'] = _cell(12.0, frame=10.0)
    facts[key + '.reproduction'] = _cell(14.0, frame=20.0)
    text = summary.short_version(facts, ['plate'], DISPLAY)
    assert '| Plate.js | 13 ms |' in text


def test_a_label_needs_every_launch_of_both_rounds_to_say_it():
    # The reader joins reasons with '; ' and appends additional ones after '; also ' (e2_cells.publication_text).
    mixed_crash = ('first: not enough samples (n = 0 of 10; reasons crash: 1; timeout: 9); '
                   'second: not enough samples (n = 0 of 10; reasons crash: 10)')
    partly_applies = ('first: not enough samples (n = 2 of 10; reasons not_applicable: 8); '
                      'second: not enough samples (n = 0 of 10; reasons not_applicable: 10)')
    one_round = 'second: not enough samples (n = 0 of 10; reasons editor_crash: 10)'
    assert summary._why(mixed_crash) == 'no figure'
    # Additional reasons describe the same launches: ten crashes of ten are every launch.
    assert summary._why('first: not enough samples (n = 0 of 10; reasons crash: 10; also paint_witness_unavailable: 3); '
                        'second: not enough samples (n = 0 of 10; reasons crash: 10)') == 'crashed'
    # One counted crash of ten says nothing of the other nine.
    assert summary._why('first: not enough samples (n = 0 of 10; reasons crash: 1); '
                        'second: not enough samples (n = 0 of 10; reasons crash: 10)') == 'no figure'
    assert summary._why('first: not enough samples (n = 0 of 10; reasons not_applicable: 4); '
                        'second: not enough samples (n = 0 of 10; reasons not_applicable: 10)') == 'no figure'
    assert summary._why('first: not enough samples (n = 0 of 10; reasons none counted); '
                        'second: not enough samples (n = 0 of 10; reasons none counted)') == 'no figure'
    assert summary._why(partly_applies) == 'no figure'
    assert summary._why(one_round) == 'no figure'
    assert summary._why('first: not enough samples (n = 0 of 10; reasons editor_crash: 10); '
                        'second: not enough samples (n = 0 of 9; reasons crash: 9)') == 'crashed'


def test_an_opening_whose_text_was_not_checked_says_so_and_stays_out_of_the_range():
    facts = _facts()
    facts['perf.e2.plate.C11.prose-500w.reproduction']['content_verified'] = False
    text = summary.short_version(facts, ['docen', 'folio', 'plate'], DISPLAY)
    assert '| Plate.js | 750 ms (text not checked) |' in text
    assert 'At 500 words the figures run from 800 ms to 1.1 s' in text
