"""#192: C10 scrolls the complex document without its document protection.

GenOffice and eigenpal honour ``w:documentProtection`` and open the
complex-corpus package read-only, as Word does. C10's readiness gate waits
for an editable root, so their scroll never started (usable_signal_not_observed
in every launch). Scrolling needs no editable surface; the scroll lane now
loads the same protection-stripped package as the other non-load lanes.
"""
import io
import zipfile

from perf.fixtures.docx_workload import EDIT_VARIANT, workload_docx
from perf.runner import adversarial_c10_scroll as scroll


def _settings(docx):
    return zipfile.ZipFile(io.BytesIO(docx)).read('word/settings.xml')


def test_the_complex_scroll_fixture_has_no_document_protection():
    original = workload_docx('complex-corpus')
    assert b'documentProtection' in _settings(original['docx'])
    fixture = scroll.scroll_fixture('complex-corpus')
    assert b'documentProtection' not in _settings(fixture['docx'])
    assert fixture['fixture_variant'] == EDIT_VARIANT
    assert fixture['fixture_source_sha256'] == original['sha256']
    assert fixture['workload_row']['workload_id'] == 'complex-corpus'


def test_prose_scroll_fixtures_are_unchanged():
    for workload in ('prose-500w', 'prose-50kw'):
        assert scroll.scroll_fixture(workload)['docx'] == workload_docx(workload)['docx']


def test_the_trial_environment_names_the_variant():
    fixture = scroll.scroll_fixture('complex-corpus')
    env = scroll.scroll_env(editor_id='plate', editor_version='x', execution_profile='ci_broad',
                            host_class='ci_coarse', fixture=fixture)
    assert env['fixture_variant'] == EDIT_VARIANT
    assert env['fixture_sha256'] == fixture['sha256'] != fixture['fixture_source_sha256']
