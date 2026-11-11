"""Integration: distinct document measures retain the one-attempt guard."""
import json
import sys
from functools import partial
from pathlib import Path
import pytest
from perf.runner import browser_run as api


@pytest.mark.parametrize('cid,field,measures', [
    ('C14', 'size_rung', ['prose-1kw', 'prose-5kw']),
    ('C15', 'measurement', ['first_match', 'search_complete']),
    ('C15', 'measurement', ['first_match', 'first_match']),
])
def test_launch_measure_identity(tmp_path, monkeypatch, cid, field, measures):
    def main():
        root = Path(sys.argv[sys.argv.index('--out-root') + 1])
        for index, measure in enumerate(measures):
            api.write_json(root / 'attempts' / f'{index}.json', {
                'criterion_id': cid, 'outcome': 'measured', 'samples_ms': [21.0],
                'diagnostic': {field: measure},
            })
        return 0
    monkeypatch.setattr(sys, 'argv', ['fake', '--out-root', str(tmp_path),
        '--run-id', 'measures', '--editors', 'plate'])
    code = api.run_cli(main, 'fake', {'plate': {}},
        run_factory=partial(api.BrowserRun, snapshot=lambda: {}), facts=(lambda: {},lambda: {}))
    duplicate = measures[0] == measures[1]
    assert code == (3 if duplicate else 0)
    summary = json.loads((tmp_path / 'fake/measures/summary.json').read_text())
    row = summary['samples'][0]
    if duplicate:
        assert row['failure_reason'] == 'multiple_attempts_per_launch'
        assert not list((tmp_path / 'fake/measures/cells').rglob('attempts/*.json'))
        assert len(list(Path(row['rejected_evidence_directory']).rglob('attempts/*.json'))) == 2
    else:
        assert row['outcome'] == 'ok'
        assert len(list(Path(row['cell_directory']).glob('attempts/*.json'))) == 2
