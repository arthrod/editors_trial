"""The independent check of Report E2's results tables (#227): it shares no code with the generator."""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verify_e2_summary as verify  # noqa: E402 - the build folder is put on sys.path just above

DISPLAY = {'folio': 'Folio', 'plate': 'Plate.js'}


def _cell(median, frame=16.7):
    return {'sample_unit': 'ms', 'frame_interval_ms': frame, 'stats': {'median': median}, 'content_verified': True}


def _facts():
    facts = {}
    for editor, first, second in (('folio', 800, 820), ('plate', 1180, 1220)):
        base = 'perf.e2.%s.C11.prose-500w' % editor
        facts[base + '.reproduced'] = True
        facts[base + '.primary'], facts[base + '.reproduction'] = _cell(first), _cell(second)
    return facts


REPORT = """# Report

## The results

### Opening a document

From the moment.

| Editor | 500 words | 5,000 words | 50,000 words | 250,000 words | 500,000 words |
|---|---|---|---|---|---|
| Folio | 810 ms | — | — | — | — |
| Plate.js | 1.2 s | — | — | — | — |

At 500 words, 2 of 2 editors have a figure, from 810 ms to 1.2 s.

## Appendix A — What was measured
"""


def test_a_report_that_matches_the_facts_passes():
    assert verify.check(REPORT, _facts(), DISPLAY) == []


def test_a_figure_that_differs_from_the_facts_is_named():
    problems = verify.check(REPORT.replace('| Folio | 810 ms |', '| Folio | 710 ms |'), _facts(), DISPLAY)
    assert any('Folio' in p and "'710 ms'" in p and "'810 ms'" in p for p in problems), problems


def test_a_range_sentence_that_differs_from_the_facts_is_named():
    problems = verify.check(REPORT.replace('from 810 ms', 'from 800 ms'), _facts(), DISPLAY)
    assert any('range sentence' in p for p in problems), problems


def test_an_editor_left_out_of_a_table_is_named():
    lines = [line for line in REPORT.split('\n') if not line.startswith('| Plate.js')]
    problems = verify.check('\n'.join(lines), _facts(), DISPLAY)
    assert any('Plate.js has cells in the facts and no row' in p for p in problems), problems


def test_the_gate_runs_the_check_after_the_reports_are_generated():
    gate = (Path(__file__).resolve().parent / 'verify_publication.sh').read_text(encoding='utf-8')
    generated = next(line for line in gate.split('\n') if line.startswith('run "generated"'))
    assert generated.index('render_reports.py --check') < generated.index('build/verify_e2_summary.py')


def test_the_check_shares_no_code_with_the_generator():
    source = Path(verify.__file__).read_text(encoding='utf-8')
    assert 'import perf_e2_summary' not in source and 'perf_e2_summary import' not in source


def test_the_sentence_counts_the_editors_that_have_a_figure():
    problems = verify.check(REPORT.replace('2 of 2 editors', '2 of 3 editors'), _facts(), DISPLAY)
    assert any('range sentence' in p for p in problems), problems


def test_a_table_the_facts_can_fill_must_be_in_the_report():
    """CodeRabbit on #229: deleting a whole populated table passed."""
    facts = _facts()
    for editor in ('folio', 'plate'):
        base = 'perf.e2.%s.C10.prose-500w' % editor
        facts[base + '.reproduced'] = True
        facts[base + '.primary'], facts[base + '.reproduction'] = _cell(30), _cell(32)
    problems = verify.check(REPORT, facts, DISPLAY)
    assert any("'Scrolling'" in p and 'no table' in p for p in problems), problems


def test_every_document_size_of_a_table_must_be_a_column():
    """CodeRabbit on #229: removing a column and its clause passed, the header being the only source of columns."""
    lines = []
    for line in REPORT.split('\n'):
        if line.startswith('|'):
            line = '|'.join(line.split('|')[:3]) + '|'
        lines.append(line)
    problems = verify.check('\n'.join(lines), _facts(), DISPLAY)
    assert any('columns' in p for p in problems), problems


# #239: every results cell that is not a single figure says what happened, and Appendix J says why.

GLYPH = 'no_glyph_geometry_to_witness_the_keystrokes_own_paint'
REFUSED = ('first: not enough samples (n = 0 of 10; reasons not_applicable: 10); '
           'second: not enough samples (n = 0 of 10; reasons not_applicable: 10)')


def _labelled_facts():
    facts = {}
    base = 'perf.e2.plate.C05.warm_steady.prose-500w'
    facts[base + '.reproduced'] = True
    facts[base + '.primary'], facts[base + '.reproduction'] = _cell(9.0), _cell(11.0)
    base = 'perf.e2.folio.C05.warm_steady.prose-500w'
    facts[base + '.reproduced'] = False
    facts[base + '.reason'] = 'medians outside tolerance'
    facts[base + '.rounds'] = {'first': {'median': 46.0, 'n': 10}, 'second': {'median': 81.0, 'n': 9},
                               'frame_interval_ms': 16.7, 'rel_tol': 0.1, 'sample_unit': 'ms'}
    base = 'perf.e2.folio.C05.warm_steady.prose-5kw'
    facts[base + '.reproduced'] = False
    facts[base + '.reason'] = REFUSED
    for slot in ('primary', 'reproduction'):
        facts[base + '.' + slot] = {'scheduled': 10, 'refusals': {'not_applicable': 10},
                                    'refusal_reasons': {'not_applicable': [GLYPH]}}
    return facts


LABELLED = """# Report

## The results

### Typing one character

From a key press.

| Editor | 500 words | 5,000 words | 50,000 words | 250,000 words |
|---|---|---|---|---|
| Folio | 46 ms to 81 ms | not measured | — | — |
| Plate.js | under 17 ms | — | — | — |

## Appendix A — What was measured

## Appendix J — Every results cell that is not a single figure, and why

Words.

| Table | Editor | Document | Printed | Why |
|---|---|---|---|---|
| Typing one character | Folio | 500 words | 46 ms to 81 ms | The first round gave 46 ms (10 launches) and the second 81 ms (9 launches). They differ. |
| Typing one character | Folio | 5,000 words | not measured | First round: 0 of 10 launches kept; 10 refused. Second round: 0 of 10 launches kept; 10 refused. The reason, both times: the editor draws its text where the harness cannot read an outline. |
"""


def test_a_report_with_a_range_a_refusal_and_its_appendix_passes():
    assert verify.check(LABELLED, _labelled_facts(), DISPLAY) == []


def test_varied_is_a_mismatch_when_both_rounds_have_a_median():
    problems = verify.check(LABELLED.replace('| Folio | 46 ms to 81 ms |', '| Folio | varied |'), _labelled_facts(), DISPLAY)
    assert any("'varied'" in p and "'46 ms to 81 ms'" in p for p in problems), problems


def test_does_not_apply_is_a_mismatch_when_the_harness_refused_for_its_own_witness():
    problems = verify.check(LABELLED.replace('| not measured | — | — |', '| does not apply | — | — |'), _labelled_facts(), DISPLAY)
    assert any("'does not apply'" in p and "'not measured'" in p for p in problems), problems


def test_under_one_frame_may_not_be_printed_in_the_results():
    problems = verify.check(LABELLED.replace('| Plate.js | under 17 ms |', '| Plate.js | under 1 frame |'), _labelled_facts(), DISPLAY)
    assert any('under 1 frame' in p for p in problems), problems


def test_a_cell_without_a_single_figure_must_have_its_appendix_row():
    lines = [line for line in LABELLED.split('\n') if not line.startswith('| Typing one character | Folio | 5,000 words')]
    problems = verify.check('\n'.join(lines), _labelled_facts(), DISPLAY)
    assert any('Appendix J' in p and 'Folio' in p and '5,000 words' in p and 'no row' in p for p in problems), problems


def test_an_appendix_row_for_a_cell_that_has_a_figure_is_named():
    extra = LABELLED + '| Typing one character | Plate.js | 500 words | varied | The rounds differ. |\n'
    problems = verify.check(extra, _labelled_facts(), DISPLAY)
    assert any('Appendix J' in p and 'Plate.js' in p and 'has a single figure' in p for p in problems), problems


def test_an_appendix_row_must_print_what_the_table_prints():
    wrong = LABELLED.replace('| Typing one character | Folio | 500 words | 46 ms to 81 ms |',
                             '| Typing one character | Folio | 500 words | 40 ms to 81 ms |')
    problems = verify.check(wrong, _labelled_facts(), DISPLAY)
    assert any('Appendix J' in p and "'40 ms to 81 ms'" in p for p in problems), problems


def test_the_why_of_a_range_must_give_both_rounds_and_their_launches():
    wrong = LABELLED.replace('the second 81 ms (9 launches)', 'the second 81 ms (10 launches)')
    problems = verify.check(wrong, _labelled_facts(), DISPLAY)
    assert any('Appendix J' in p and 'why' in p and '81 ms (9 launches)' in p for p in problems), problems


def test_the_why_of_a_refusal_must_give_each_rounds_kept_launches():
    wrong = LABELLED.replace('Second round: 0 of 10 launches kept', 'Second round: 2 of 10 launches kept')
    problems = verify.check(wrong, _labelled_facts(), DISPLAY)
    assert any('Appendix J' in p and 'why' in p and 'Second round: 0 of 10 launches kept' in p for p in problems), problems


def test_a_report_with_such_cells_and_no_appendix_is_named():
    cut = LABELLED[:LABELLED.index('## Appendix J')]
    problems = verify.check(cut, _labelled_facts(), DISPLAY)
    assert any('Appendix J' in p and 'missing' in p for p in problems), problems


def test_a_column_of_cells_under_redraws_of_different_lengths_is_checked_and_does_not_crash():
    """Review (octo): with only such cells the sentence indexed an empty list and the gate died."""
    facts = {}
    for editor, frame in (('folio', 6.9), ('plate', 16.7)):
        base = 'perf.e2.%s.C10.prose-500w' % editor
        facts[base + '.reproduced'] = True
        facts[base + '.primary'], facts[base + '.reproduction'] = _cell(3.0, frame), _cell(3.0, frame)
    report = """# Report

## The results

### Scrolling

From a scroll.

| Editor | 500 words | 5,000 words | 50,000 words | 250,000 words |
|---|---|---|---|---|
| Folio | under 7 ms | — | — | — |
| Plate.js | under 17 ms | — | — | — |

At 500 words, 2 of 2 editors have a figure, from under 7 ms to under 17 ms.

## Appendix A — What was measured
"""
    assert verify.check(report, facts, DISPLAY) == []
    wrong = report.replace('from under 7 ms to under 17 ms', 'all under 7 ms')
    assert any('range sentence' in p for p in verify.check(wrong, facts, DISPLAY))


# CodeRabbit on #240.

def test_the_why_of_a_range_must_give_each_figure_to_its_own_round():
    swapped = LABELLED.replace('The first round gave 46 ms (10 launches) and the second 81 ms (9 launches).',
                               'The first round gave 81 ms (9 launches) and the second 46 ms (10 launches).')
    problems = verify.check(swapped, _labelled_facts(), DISPLAY)
    assert any('Appendix J' in p and 'first round gave 46 ms (10 launches)' in p for p in problems), problems


def test_two_appendix_rows_for_one_cell_are_named():
    row = '| Typing one character | Folio | 500 words | 46 ms to 81 ms |'
    line = next(line for line in LABELLED.split('\n') if line.startswith(row))
    doubled = LABELLED.replace(line, line.replace('46 ms (10 launches)', '99 ms (10 launches)') + '\n' + line)
    problems = verify.check(doubled, _labelled_facts(), DISPLAY)
    assert any('Appendix J' in p and 'two rows' in p for p in problems), problems


def test_each_round_of_a_range_is_checked_against_its_own_redraw_interval():
    facts = _labelled_facts()
    rounds = facts['perf.e2.folio.C05.warm_steady.prose-500w.rounds']
    rounds['first'].update(median=10.0, frame_interval_ms=6.9)
    rounds['second'].update(median=40.0, frame_interval_ms=16.7)
    right = LABELLED.replace('46 ms to 81 ms', '10 ms to 40 ms').replace(
        'The first round gave 46 ms (10 launches) and the second 81 ms (9 launches).',
        'The first round gave 10 ms (10 launches) and the second 40 ms (9 launches).')
    assert verify.check(right, facts, DISPLAY) == []
    wrong = right.replace('10 ms to 40 ms', 'under 17 ms to 40 ms')
    assert any("'10 ms to 40 ms'" in p for p in verify.check(wrong, facts, DISPLAY))


def test_the_why_of_a_refusal_must_say_the_recorded_reason_in_words():
    """CodeRabbit on #240: the counts alone would pass an explanation of something else."""
    assert verify.check(LABELLED, _labelled_facts(), DISPLAY) == []
    other = LABELLED.replace('cannot read an outline', 'crashed')
    problems = verify.check(other, _labelled_facts(), DISPLAY)
    assert any('Appendix J' in p and 'outline' in p for p in problems), problems


def test_a_recorded_reason_the_check_has_no_term_for_asks_for_nothing_more():
    facts = _labelled_facts()
    for slot in ('primary', 'reproduction'):
        facts['perf.e2.folio.C05.warm_steady.prose-5kw.' + slot]['refusal_reasons'] = {'not_applicable': ['something new']}
    report = LABELLED.replace('| not measured |', '| no figure |').replace('not measured | —', 'no figure | —')
    assert not any('does not say' in p and 'outline' in p for p in verify.check(report, facts, DISPLAY))


# #241: a reason's term belongs to the clause of its own round.

def _two_reasons():
    facts = _labelled_facts()
    base = 'perf.e2.folio.C05.warm_steady.prose-5kw'
    facts[base + '.reproduction']['refusal_reasons'] = {'not_applicable': ['expected_edit_not_confirmed']}
    shared = ('First round: 0 of 10 launches kept; 10 refused. Second round: 0 of 10 launches kept; 10 refused. '
              'The reason, both times: the editor draws its text where the harness cannot read an outline.')
    assert shared in LABELLED
    right = LABELLED.replace(shared, 'First round: 0 of 10 launches kept; 10 refused: the harness cannot read an outline. '
                                     'Second round: 0 of 10 launches kept; 10 refused: the typed character was not found.')
    return facts, right


def test_two_rounds_with_different_reasons_each_say_their_own():
    facts, right = _two_reasons()
    assert not any('does not say' in p for p in verify.check(right, facts, DISPLAY))


def test_the_reasons_of_two_rounds_may_not_be_swapped():
    facts, right = _two_reasons()
    swapped = right.replace('10 refused: the harness cannot read an outline.', '10 refused: X.').replace(
        '10 refused: the typed character was not found.', '10 refused: the harness cannot read an outline.').replace(
        '10 refused: X.', '10 refused: the typed character was not found.')
    problems = verify.check(swapped, facts, DISPLAY)
    assert any('Appendix J' in p and 'first round' in p and 'outline' in p for p in problems), problems
    assert any('Appendix J' in p and 'second round' in p and 'not found' in p for p in problems), problems


def test_a_reason_both_rounds_share_may_be_said_once_for_both():
    assert not any('does not say' in p for p in verify.check(LABELLED, _labelled_facts(), DISPLAY))


def test_a_sentence_for_both_rounds_does_not_cover_rounds_that_recorded_different_reasons():
    """GLM review of #241: "both times" is only true when both rounds recorded the same."""
    facts, right = _two_reasons()
    merged = right.replace(
        '10 refused: the harness cannot read an outline. Second round: 0 of 10 launches kept; 10 refused: the typed character was not found.',
        '10 refused. Second round: 0 of 10 launches kept; 10 refused. The reason, both times: the harness cannot read an outline; '
        'also the typed character was not found.')
    assert merged != right
    problems = verify.check(merged, facts, DISPLAY)
    assert any('first round' in p and 'outline' in p for p in problems), problems
    assert any('second round' in p and 'not found' in p for p in problems), problems


def test_a_marker_quoted_inside_a_rounds_words_does_not_end_its_clause():
    facts, right = _two_reasons()
    quoted = right.replace('10 refused: the harness cannot read an outline.',
                           "10 refused: the page showed 'Second round:' and the harness cannot read an outline.")
    assert not any('does not say' in p for p in verify.check(quoted, facts, DISPLAY))


# #238: a typing time read on the pixel witness carries its mark, and its table the note.

PIXEL_NOTE = 'A time marked "(by pixels)" ends at the first frame in which at least 100 pixels of the page changed after a key press the editor confirmed. The editor draws its text where the harness cannot read a character\'s outline, so that frame is not checked for the character itself. The smallest change on any key press behind these times was 102 pixels, close to that bound (issue #238).'
PIXEL_REPORT = """# Report

## The results

### Typing one character

From a key press.

| Editor | 500 words | 5,000 words | 50,000 words | 250,000 words |
|---|---|---|---|---|
| Folio | 55 ms (by pixels) | — | — | — |
| Plate.js | 25 ms | — | — | — |

At 500 words, 2 of 2 editors have a figure, from 25 ms to 55 ms (by pixels).

%s

## Appendix A — What was measured
""" % PIXEL_NOTE


def _pixel_facts():
    facts = {}
    for editor, first, second in (('folio', 50, 60), ('plate', 24, 26)):
        base = 'perf.e2.%s.C05.warm_steady.prose-500w' % editor
        facts[base + '.reproduced'] = True
        facts[base + '.primary'], facts[base + '.reproduction'] = _cell(first), _cell(second)
    for half in ('primary', 'reproduction'):
        facts['perf.e2.folio.C05.warm_steady.prose-500w.' + half].update(witness='changed_pixels', least_changed_pixels=102)
    return facts


def test_a_marked_time_with_its_note_passes():
    assert verify.check(PIXEL_REPORT, _pixel_facts(), DISPLAY) == []


def test_a_pixel_witnessed_time_printed_without_its_mark_is_named():
    problems = verify.check(PIXEL_REPORT.replace('| Folio | 55 ms (by pixels) |', '| Folio | 55 ms |'), _pixel_facts(), DISPLAY)
    assert any('Folio' in p and 'by pixels' in p for p in problems), problems


def test_a_mark_on_a_time_the_facts_do_not_give_to_the_pixel_witness_is_named():
    problems = verify.check(PIXEL_REPORT.replace('| Plate.js | 25 ms |', '| Plate.js | 25 ms (by pixels) |'), _pixel_facts(), DISPLAY)
    assert any('Plate.js' in p and "'25 ms'" in p for p in problems), problems


def test_a_table_with_a_marked_time_and_no_note_is_named():
    problems = verify.check(PIXEL_REPORT.replace(PIXEL_NOTE, ''), _pixel_facts(), DISPLAY)
    assert any('by pixels' in p and 'note' in p for p in problems), problems


def test_a_note_under_a_table_with_no_marked_time_is_named():
    facts = _pixel_facts()
    for half in ('primary', 'reproduction'):
        del facts['perf.e2.folio.C05.warm_steady.prose-500w.' + half]['witness']
    report = PIXEL_REPORT.replace('| Folio | 55 ms (by pixels) |', '| Folio | 55 ms |').replace('55 ms (by pixels).', '55 ms.')
    problems = verify.check(report, facts, DISPLAY)
    assert any('note' in p for p in problems), problems


def test_a_note_that_says_something_else_with_the_same_words_is_named():
    false_note = 'A time marked "(by pixels)" has no requirement of at least 100 pixels, although it was not checked for the character.'
    problems = verify.check(PIXEL_REPORT.replace(PIXEL_NOTE, false_note), _pixel_facts(), DISPLAY)
    assert any('note' in p for p in problems), problems


def test_a_pixel_witnessed_cell_whose_least_change_is_under_the_bound_is_named():
    facts = _pixel_facts()
    facts['perf.e2.folio.C05.warm_steady.prose-500w.reproduction']['least_changed_pixels'] = 24
    problems = verify.check(PIXEL_REPORT, facts, DISPLAY)
    assert any('100 pixels' in p and 'Folio' in p for p in problems), problems


def test_a_note_whose_smallest_change_is_not_the_facts_is_named():
    problems = verify.check(PIXEL_REPORT.replace('was 102 pixels', 'was 180 pixels'), _pixel_facts(), DISPLAY)
    assert any('note' in p for p in problems), problems


# The GLM review of #238: the sentence at the top that names the editors is held to the facts.

GLYPH_REASON = 'no_glyph_geometry_to_witness_the_keystrokes_own_paint'
TOP = ('# Report\n\n- **Typing was not timed for one editor, and Folio\'s typing time is not checked for the character.** '
       'Plate.js has no typing time. Folio is marked "(by pixels)".\n')


def _typing_facts():
    facts = _pixel_facts()
    base = 'perf.e2.plate.C05.warm_steady.prose-500w'
    facts[base + '.reproduced'] = False
    facts[base + '.reason'] = 'first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10)'
    for half in ('.primary', '.reproduction'):
        facts[base + half] = {'refusal_reasons': {'not_applicable': [GLYPH_REASON]}}
    return facts


def test_the_sentence_naming_the_editors_without_a_typing_time_matches_the_facts():
    assert verify.check_typing_sentence(TOP, _typing_facts(), DISPLAY) == []


def test_an_editor_named_as_untimed_that_has_a_figure_is_named():
    facts = _pixel_facts()  # every editor has a typing figure here
    problems = verify.check_typing_sentence(TOP, facts, DISPLAY)
    assert any('every editor' in p for p in problems), problems
    # One editor untimed, and the sentence also names an editor whose time is checked for the character.
    display = dict(DISPLAY, docen='Docen')
    facts = _typing_facts()
    base = 'perf.e2.docen.C05.warm_steady.prose-500w'
    facts[base + '.reproduced'] = True
    facts[base + '.primary'], facts[base + '.reproduction'] = _cell(30), _cell(32)
    problems = verify.check_typing_sentence(TOP.replace('Plate.js has', 'Plate.js and Docen have'), facts, display)
    assert any('Docen' in p for p in problems), problems


def test_a_count_word_that_is_not_the_number_of_untimed_editors_is_named():
    problems = verify.check_typing_sentence(TOP.replace('for one editor', 'for two editors'), _typing_facts(), DISPLAY)
    assert any('one' in p or '1' in p for p in problems), problems


def test_an_editor_read_by_pixels_and_not_named_in_the_sentence_is_named():
    problems = verify.check_typing_sentence(TOP.replace("Folio's", "Its").replace('Folio is', 'It is'), _typing_facts(), DISPLAY)
    assert any('Folio' in p for p in problems), problems
