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
    assert '| Folio | 800 ms | crashed | not measured | 4.7 s | no figure |' in text
    assert '| Docen | 1.1 s | — | — | varied | — |' in text


def test_the_range_sentence_names_no_editor():
    text = summary.short_version(_facts(), ['docen', 'folio', 'plate'], DISPLAY)
    assert 'At 500 words, 3 of 3 editors have a figure, from 750 ms to 1.1 s; at 250,000 words, 2 of 3, from 4.7 s to 19.1 s.' in text


def test_times_under_one_frame_and_memory_are_formatted_for_a_reader():
    facts = {}
    _put(facts, 'plate', 'C10', 'prose-500w', 12.0, 13.0)
    _put(facts, 'plate', 'C17', 'prose-500w', 600 * 2 ** 20, measure='quiescent', unit='bytes')
    _put(facts, 'plate', 'C17', 'prose-250kw', 2060 * 2 ** 20, measure='quiescent', unit='bytes')
    _put(facts, 'plate', 'C11', 'prose-500kw', 285466)
    text = summary.short_version(facts, ['plate'], DISPLAY)
    assert '| Plate.js | under 17 ms |' in text
    assert '| Plate.js | 600 MiB | — | — | 2.0 GiB |' in text
    assert '| 285 s |' in text


def test_a_section_with_no_figure_at_all_is_left_out_and_an_empty_report_says_so():
    assert summary.short_version({}, ['plate'], DISPLAY) == 'not in these runs.'
    text = summary.short_version(_facts(), ['docen', 'folio', 'plate'], DISPLAY)
    assert '### Opening a document' in text and '### Scrolling' not in text


def _template():
    from pathlib import Path
    return (Path(__file__).resolve().parent.parent
            / 'templates/reports/Report E2 - Speed in the Browser (2026).md').read_text(encoding='utf-8')


def test_the_report_comes_first_and_every_detail_is_in_a_lettered_appendix():
    """Arthur, 2026-11-15: a human friendly report first, then the details in an appendix."""
    import re
    template = _template()
    first_appendix = template.index('\n## Appendix A')
    assert template.index('{{perf.e2.short_version}}') < first_appendix
    headings = re.findall(r'^## (.+)$', template, flags=re.M)
    after = headings[headings.index(next(h for h in headings if h.startswith('Appendix A'))):]
    assert all(h.startswith('Appendix ') for h in after), after
    letters = [h.split()[1] for h in after]
    assert letters == [chr(ord('A') + i) for i in range(len(after))]
    # Method placeholders (rule, host, reruns, full tables) are appendix material.
    report = template[:first_appendix]
    for placeholder in re.findall(r'\{\{([^}]+)\}\}', report):
        assert placeholder in ('perf.e2.status', 'perf.e2.short_version'), placeholder


def test_that_everything_was_run_twice_is_left_to_the_appendix():
    """Arthur, 2026-11-15: 'Leave for the appendix the fact we ran again.'"""
    template = _template()
    report = template[:template.index('\n## Appendix A')].lower()
    for words in ('twice', 'two rounds', 'both rounds', 'second round', 'seed', 'measured again', 'reproduc'):
        assert words not in report, words
    appendix = template[template.index('\n## Appendix A'):]
    assert 'run twice' in appendix and '{{perf.e2.rule}}' in appendix and '{{perf.e2.reruns}}' in appendix


def test_a_column_whose_figures_all_read_the_same_says_so():
    facts = {}
    for editor in ('plate', 'folio'):
        _put(facts, editor, 'C10', 'prose-500w', 12.0)
        _put(facts, editor, 'C10', 'prose-250kw', 12.0 if editor == 'plate' else 60.0)
    text = summary.short_version(facts, ['folio', 'plate'], DISPLAY)
    assert 'At 500 words, 2 of 2 editors have a figure, all under 17 ms; at 250,000 words, 2 of 2, from under 17 ms to 60 ms.' in text


def test_under_one_frame_needs_both_seeds_under_it():
    """Review of #227: 14 ms and 18 ms have a middle of 16 ms, and one seed is over a frame."""
    facts = {}
    _put(facts, 'plate', 'C10', 'prose-500w', 14.0, 18.0)
    _put(facts, 'plate', 'C10', 'prose-5kw', 14.0, 15.0)
    text = summary.short_version(facts, ['plate'], DISPLAY)
    assert '| Plate.js | 16 ms | under 17 ms |' in text


# --- CodeRabbit on #229 ---

def test_the_range_sentence_says_all_only_when_every_printed_cell_reads_the_same():
    """A 15 ms cell printed as a time (one seed over a frame) beside cells under a frame is not 'all under 17 ms'."""
    facts = {}
    _put(facts, 'docen', 'C10', 'prose-500w', 8.0, 9.0)
    _put(facts, 'folio', 'C10', 'prose-500w', 12.0, 18.0)   # middle 15 ms, second seed over a frame
    _put(facts, 'plate', 'C10', 'prose-500w', 16.0, 16.4)   # the highest value, and under a frame in both
    text = summary.short_version(facts, ['docen', 'folio', 'plate'], DISPLAY)
    assert '| Folio | 15 ms |' in text
    assert '| Plate.js | under 17 ms |' in text
    assert 'all under 17 ms' not in text
    assert 'At 500 words, 3 of 3 editors have a figure, from under 17 ms to 15 ms.' in text


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
    assert 'At 500 words, 2 of 3 editors have a figure, from 800 ms to 1.1 s' in text


# #239: a cell without a single figure says what happened, and an appendix says why, cell by cell.

GLYPH = 'no_glyph_geometry_to_witness_the_keystrokes_own_paint'


def _refused(facts, editor, criterion, workload, rounds, *, measure=''):
    """rounds: {'first': (kept, scheduled, {code: count}, {code: [reasons]}), ...}; a round left out kept enough."""
    key = 'perf.e2.%s.%s' % (editor, criterion) + ('.' + measure if measure else '') + '.' + workload
    parts = []
    for name, slot in (('first', 'primary'), ('second', 'reproduction')):
        kept, scheduled, codes, reasons = rounds.get(name, (10, 10, {}, {}))
        facts[key + '.' + slot] = {'sample_unit': 'ms', 'scheduled': scheduled, 'refusals': codes, 'refusal_reasons': reasons,
                                   'failed_launches': scheduled - kept}
        if name in rounds:
            parts.append('%s: not enough samples (n = %d of %d; reasons %s)' % (
                name, kept, scheduled, '; '.join('%s: %d' % item for item in sorted(codes.items()))))
    facts[key + '.reproduced'] = False
    facts[key + '.reason'] = '; '.join(parts)


def _varied(facts, editor, criterion, workload, first, second, *, measure='', unit='ms', frame=16.7):
    key = 'perf.e2.%s.%s' % (editor, criterion) + ('.' + measure if measure else '') + '.' + workload
    facts[key + '.reproduced'] = False
    facts[key + '.reason'] = 'medians outside tolerance'
    facts[key + '.rounds'] = {'first': {'median': first, 'n': 10}, 'second': {'median': second, 'n': 9},
                              'frame_interval_ms': frame, 'rel_tol': 0.1, 'sample_unit': unit}


def test_a_cell_whose_rounds_disagree_prints_both_rounds_as_a_range():
    facts = _facts()
    _varied(facts, 'docen', 'C11', 'prose-5kw', 81.2, 47.9)
    text = summary.short_version(facts, ['docen', 'folio', 'plate'], DISPLAY)
    assert '| Docen | 1.1 s | 48 ms to 81 ms | — | varied | — |' in text  # 250,000 words has no medians in the facts


def test_a_range_is_not_counted_as_a_figure_in_the_line_under_the_table():
    facts = _facts()
    _varied(facts, 'docen', 'C11', 'prose-250kw', 9000, 30000)
    text = summary.short_version(facts, ['docen', 'folio', 'plate'], DISPLAY)
    assert '| Docen | 1.1 s | — | — | 9.0 s to 30.0 s | — |' in text
    assert 'at 250,000 words, 2 of 3, from 4.7 s to 19.1 s.' in text


def test_a_range_with_a_round_under_one_redraw_says_so():
    facts = _facts()
    _varied(facts, 'docen', 'C05', 'prose-500w', 9.0, 40.0, measure='warm_steady')
    _put(facts, 'plate', 'C05', 'prose-500w', 30, measure='warm_steady')
    text = summary.short_version(facts, ['docen', 'folio', 'plate'], DISPLAY)
    assert '| Docen | under 17 ms to 40 ms | — | — | — |' in text


def test_typing_refused_for_the_missing_witness_is_not_measured_and_never_does_not_apply():
    facts = _facts()
    _put(facts, 'plate', 'C05', 'prose-500w', 30, measure='warm_steady')
    refused = (0, 10, {'not_applicable': 10}, {'not_applicable': [GLYPH]})
    _refused(facts, 'docen', 'C05', 'prose-500w', {'first': refused, 'second': refused}, measure='warm_steady')
    text = summary.short_version(facts, ['docen', 'folio', 'plate'], DISPLAY)
    assert '| Docen | not measured | — | — | — |' in text
    assert 'does not apply' not in text


def test_does_not_apply_is_kept_for_a_refusal_that_really_is_one():
    facts = _facts()
    refused = (0, 10, {'not_applicable': 10}, {'not_applicable': ['no_deferred_work']})
    _refused(facts, 'docen', 'C11', 'prose-5kw', {'first': refused, 'second': refused})
    text = summary.short_version(facts, ['docen', 'folio', 'plate'], DISPLAY)
    assert '| Docen | 1.1 s | does not apply | — | varied | — |' in text


def _appendix_facts():
    facts = _facts()
    _put(facts, 'plate', 'C05', 'prose-500w', 30, measure='warm_steady')
    refused = (0, 10, {'not_applicable': 10}, {'not_applicable': [GLYPH]})
    _refused(facts, 'docen', 'C05', 'prose-500w', {'first': refused, 'second': refused}, measure='warm_steady')
    _varied(facts, 'folio', 'C05', 'prose-500w', 46.0, 81.0, measure='warm_steady')
    _refused(facts, 'plate', 'C05', 'prose-5kw', {'second': (1, 10, {'unverified': 9}, {'unverified': ['expected_edit_not_confirmed']})},
             measure='warm_steady')
    crash = (0, 10, {'editor_crash': 10}, {'editor_crash': ['page_lost: Error: page.evaluate: Target crashed']})
    _refused(facts, 'folio', 'C17', 'prose-250kw', {'first': crash, 'second': crash}, measure='quiescent')
    _put(facts, 'plate', 'C17', 'prose-250kw', 2 ** 30, measure='quiescent', unit='bytes')
    return facts


def test_the_appendix_has_one_row_for_every_results_cell_without_a_single_figure():
    facts = _appendix_facts()
    editors = ['docen', 'folio', 'plate']
    summary.short_version(facts, editors, DISPLAY)
    text, counts = summary.no_figure_appendix(facts, editors, DISPLAY)
    rows = [line for line in text.splitlines() if line.startswith('| ') and not line.startswith('| Table')]
    # Opening: Docen at 250,000 words (varied, no medians). Typing: Docen, Folio, Plate.js. Memory: Folio.
    assert [row.split(' | ')[:4] for row in rows] == [
        ['| Opening a document', 'Docen', '250,000 words', 'varied'],
        ['| Typing one character', 'Docen', '500 words', 'not measured'],
        ['| Typing one character', 'Folio', '500 words', '46 ms to 81 ms'],
        ['| Typing one character', 'Plate.js', '5,000 words', 'no figure'],
        ['| Memory with the document open', 'Folio', '250,000 words', 'crashed'],
    ]
    assert counts == {'perf.e2.no_figure.rows': 5, 'perf.e2.no_figure.ranges': 1, 'perf.e2.no_figure.varied': 1,
                      'perf.e2.no_figure.not_measured': 1, 'perf.e2.no_figure.does_not_apply': 0,
                      'perf.e2.no_figure.no_figure': 1, 'perf.e2.no_figure.crashed': 1}


def test_the_appendix_says_why_from_the_facts():
    facts = _appendix_facts()
    editors = ['docen', 'folio', 'plate']
    summary.short_version(facts, editors, DISPLAY)
    text, _counts = summary.no_figure_appendix(facts, editors, DISPLAY)
    why = {tuple(row.split(' | ')[:3]): row.split(' | ')[4].rstrip(' |') for row in text.splitlines()
           if row.startswith('| ') and not row.startswith('| Table')}
    ranged = why[('| Typing one character', 'Folio', '500 words')]
    assert ranged == ('The first round gave 46 ms (10 launches) and the second 81 ms (9 launches). They differ by more than the '
                      'tolerance: the larger of 10 percent and one redraw of the screen (16.7 ms).')
    refused = why[('| Typing one character', 'Docen', '500 words')]
    assert 'First round: 0 of 10 launches kept; 10 refused' in refused and 'Second round: 0 of 10 launches kept; 10 refused' in refused
    assert "the typed character's own outline" in refused and 'The character was typed and the edit was confirmed' in refused
    partial = why[('| Typing one character', 'Plate.js', '5,000 words')]
    assert partial.startswith('The first round kept enough launches. Second round: 1 of 10 launches kept; 9 refused')
    assert 'the typed character was not found in the editor afterwards' in partial
    assert "the editor's page crashed" in why[('| Memory with the document open', 'Folio', '250,000 words')]
    assert 'no medians were recorded' in why[('| Opening a document', 'Docen', '250,000 words')]


def test_a_recorded_reason_the_appendix_has_no_words_for_is_printed_as_recorded():
    facts = _facts()
    odd = (0, 10, {'strange': 10}, {'strange': ['a_reason_nobody_wrote_words_for']})
    _refused(facts, 'docen', 'C11', 'prose-5kw', {'first': odd, 'second': odd})
    editors = ['docen', 'folio', 'plate']
    summary.short_version(facts, editors, DISPLAY)
    text, _counts = summary.no_figure_appendix(facts, editors, DISPLAY)
    assert 'recorded as `a_reason_nobody_wrote_words_for`' in text


def test_every_reason_recorded_in_the_published_runs_has_words():
    for reason in (GLYPH, 'document_content_unverifiable', 'expected_edit_not_confirmed', 'no_painted_frame',
                   'correctness: fixture_body_mismatch', 'page_lost: Error: page.evaluate: Target crashed'):
        assert summary.reason_words(reason) is not None, reason


def test_no_appendix_row_when_every_cell_has_a_figure():
    facts = {}
    _put(facts, 'plate', 'C11', 'prose-500w', 740)
    summary.short_version(facts, ['plate'], DISPLAY)
    text, counts = summary.no_figure_appendix(facts, ['plate'], DISPLAY)
    assert text == 'Every cell of the results tables has a single figure.' and counts['perf.e2.no_figure.rows'] == 0


def test_the_appendix_gives_what_the_harness_saw_on_keystrokes_it_refused():
    """The data is there: a refused typing cell says what was recorded, and why it is not printed as the time."""
    facts = _facts()
    _put(facts, 'plate', 'C05', 'prose-500w', 30, measure='warm_steady')
    refused = (0, 10, {'not_applicable': 10}, {'not_applicable': [GLYPH]})
    _refused(facts, 'docen', 'C05', 'prose-500w', {'first': refused, 'second': refused}, measure='warm_steady')
    _refused(facts, 'folio', 'C05', 'prose-500w', {'first': refused, 'second': refused}, measure='warm_steady')
    base = 'perf.e2.docen.C05.warm_steady.prose-500w'
    facts[base + '.primary']['unwitnessed'] = {'keystrokes': 80, 'timed': 80, 'min_ms': 16.8, 'median_ms': 26.1, 'max_ms': 48.6,
                                               'min_changed_pixels': 102}
    facts[base + '.reproduction']['unwitnessed'] = {'keystrokes': 80, 'timed': 78, 'min_ms': 0.6, 'median_ms': 36.3,
                                                    'max_ms': 66.7, 'min_changed_pixels': 24}
    editors = ['docen', 'folio', 'plate']
    summary.short_version(facts, editors, DISPLAY)
    text, _counts = summary.no_figure_appendix(facts, editors, DISPLAY)
    row = next(line for line in text.splitlines() if line.startswith('| Typing one character | Docen | 500 words'))
    assert ('First round: 0 of 10 launches kept; 10 refused' in row
            and 'It did see the screen change after 80 of 80 key presses, 17 ms to 49 ms later (typically 26 ms).' in row)
    assert ('It did see the screen change after 78 of 80 key presses, 0.6 ms to 67 ms later (typically 36 ms); the shortest are '
            'quicker than the screen is redrawn (16.7 ms), so some of those changes were not the character.') in row
    other = next(line for line in text.splitlines() if line.startswith('| Typing one character | Folio | 500 words'))
    assert 'It did see' not in other
