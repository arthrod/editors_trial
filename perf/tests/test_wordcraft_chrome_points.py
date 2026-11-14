"""#200: WordCraft's C07/C08/C09 on the complex corpus aim at its painted ribbon, so the reader withholds them.

WordCraft paints its whole window into one canvas; on the complex corpus (three lines on the first page)
the ink scan takes the ribbon for the document body. The reader refuses those trials with a harness code;
WordCraft's prose cells, and every other editor's complex cells, are untouched.
"""
import pytest

from perf.analysis.e2_cells import _trial_block
from perf.runner.refusals import RefusalCode


def trial(editor='wordcraft', criterion='C07', workload='complex-corpus', **extra):
    row = {
        'editor_id': editor,
        'criterion_id': criterion,
        'outcome': 'measured',
        'refusal_code': None,
        'publishable': True,
        'host_provenance': {'publishable': True, 'tree_sha256': '003a46b2'},
        'environment': {'workload_id': workload, 'editor_pin': 'abc123'},
        'editor_pin': 'abc123',
    }
    row.update(extra)
    return row


@pytest.mark.parametrize('criterion', ['C07', 'C08', 'C09'])
def test_wordcraft_complex_click_criteria_are_withheld(criterion):
    assert _trial_block(trial(criterion=criterion)) == 'click_points_on_editor_chrome'


def test_a_failed_wordcraft_c09_on_the_complex_corpus_names_the_harness_not_the_editor():
    failed = trial(criterion='C09', outcome='failed', refusal_code='unverified',
                   failure_reason='correctness: typed_character_or_position')
    assert _trial_block(failed) == 'click_points_on_editor_chrome'


@pytest.mark.parametrize('workload', ['prose-500w', 'prose-5kw', 'prose-50kw', 'prose-250kw'])
def test_wordcraft_prose_cells_stand(workload):
    assert _trial_block(trial(workload=workload)) is None


@pytest.mark.parametrize('editor', ['plate', 'docxodus', 'superdoc', 'genoffice', 'eigenpal', 'folio', 'canvas', 'docen'])
def test_other_editors_complex_cells_stand(editor):
    assert _trial_block(trial(editor=editor)) is None


@pytest.mark.parametrize('criterion', ['C03', 'C04', 'C10', 'C11', 'C12', 'C14'])
def test_wordcraft_complex_criteria_without_click_points_stand(criterion):
    assert _trial_block(trial(criterion=criterion)) is None


def test_the_code_is_in_the_closed_vocabulary():
    assert RefusalCode('click_points_on_editor_chrome').value == 'click_points_on_editor_chrome'


def test_a_row_that_never_clicked_keeps_its_own_reason():
    """GLM review of #200: a pre-#197 C08 row was skipped as not applicable and made no click;
    it is not relabelled as a click on WordCraft's chrome."""
    skipped = trial(criterion='C08', outcome='not_applicable', refusal_code='not_applicable',
                    failure_reason='document_text_not_readable: editor exposes only a modified flag')
    assert _trial_block(skipped) != 'click_points_on_editor_chrome'
