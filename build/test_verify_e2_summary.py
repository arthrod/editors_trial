"""The independent check of Report E2's results tables (#227): it shares no code with the generator."""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verify_e2_summary as verify  # noqa: E402

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

| Editor | 500 words | 5,000 words |
|---|---|---|
| Folio | 810 ms | — |
| Plate.js | 1.2 s | — |

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
