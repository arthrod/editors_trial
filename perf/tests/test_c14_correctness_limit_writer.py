"""C14's writer: a failed I01-I03 check carries its true cause (#181 review).

The complex corpus has no correctness lines, so I01-I03 do not apply to it;
Folio, SuperDoc and WordCraft expose no text that reaches the lines, so the
check cannot judge them. Neither is an editor dropping characters.
"""
from perf.runner import benchmark_document as lane
from perf.tests.test_schema import _env

DIAGNOSTIC = {'samples': [{'frame_interval_ms': 16.7}],
              'correctness_evidence': 'rendered DOM text, checked against I01-I03 by evaluate_measured_trial'}


def write(tmp_path, limit, text='Article 1.'):
    return lane._write_measured(
        attempt_dir=tmp_path, criterion_id='C14', editor_id='superdoc', lane='browser', env=_env(),
        samples=[5], diagnostic=DIAGNOSTIC, doc_output_text=text, correctness_limit=limit)[1]


def test_without_a_limit_the_editor_failure_stands(tmp_path):
    trial = write(tmp_path, None)
    assert 'I01: combining mark' in (trial.get('publication_block_reason') or ''), trial


def test_a_window_limit_blocks_with_its_own_reason(tmp_path):
    trial = write(tmp_path, {'applies': True, 'reason': lane.C14_TEXT_WINDOW})
    reason = trial.get('publication_block_reason') or ''
    assert lane.C14_TEXT_WINDOW in reason and 'I01: combining mark' not in reason, trial
    assert trial['publishable'] is False
    assert trial['diagnostic']['correctness_limit'] == lane.C14_TEXT_WINDOW
    assert 'checked against I01-I03' not in trial['diagnostic']['correctness_evidence']


def test_no_correctness_lines_lifts_only_i01_to_i03(tmp_path):
    trial = write(tmp_path, {'applies': False, 'reason': lane.C14_NO_CORRECTNESS_LINES})
    reason = trial.get('publication_block_reason') or ''
    assert 'I01' not in reason and 'I01-I03' not in reason, trial
    assert trial['diagnostic']['correctness_limit'] == lane.C14_NO_CORRECTNESS_LINES
    assert 'not checked' in trial['diagnostic']['correctness_evidence']
    baseline = lane._write_measured(
        attempt_dir=tmp_path / 'b', criterion_id='C14', editor_id='superdoc', lane='browser', env=_env(),
        samples=[5], diagnostic=DIAGNOSTIC,
        doc_output_text='́ \U0002000b \U0001f468‍\U0001f469‍\U0001f467‍\U0001f466 '
                        '\U0001f44d\U0001f3fb Hello مرحبا')[1]
    assert trial['publishable'] == baseline['publishable']
    assert reason == (baseline.get('publication_block_reason') or ''), (reason, baseline)
