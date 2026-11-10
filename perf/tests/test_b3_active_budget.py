"""Pure scheduling: the active profile controls the find probe budget."""
import pytest
from perf.runner import benchmark_document as document


@pytest.mark.parametrize('profile,expected', [('dedicated_publish', 10), ('ci_contract', 1)])
def test_find_budget_uses_active_profile(monkeypatch, profile, expected):
    class Run:
        execution_profile = profile
        def __init__(self):
            self.samples = []
        def begin_sample(self):
            pass
        def sample(self, name, row):
            self.samples.append(row)
    produced = []
    def find(**kwargs):
        row = {'status': 'measured', 'sequence': len(produced)}
        produced.append(row)
        return row
    monkeypatch.setattr(document, '_run_find', find)
    token = document.ACTIVE.set(Run())
    try:
        rows = document._run_find_payloads(editor_id='plate', target={},
            cfg={'find_input_selector': '#find'}, fixture_path=None, count=10)
    finally:
        document.ACTIVE.reset(token)
    assert len(rows) == expected
    assert [row['sequence'] for row in rows] == list(range(expected))
