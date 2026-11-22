"""A viewer's input criteria do not apply: recorded with the reason, the page never started."""
import json

from perf.runner import benchmark_input


def test_nutrient_input_criteria_do_not_apply(tmp_path, monkeypatch):
    def no_host(*args, **kwargs):
        raise AssertionError('a viewer must not start its host for the input lane')
    monkeypatch.setattr(benchmark_input, '_start_server', no_host)
    row = benchmark_input.run_editor('nutrient', tmp_path, 'prose-500w')
    assert row['outcome'] == 'not_applicable'
    trials = [json.loads(p.read_text()) for p in tmp_path.glob('*.json')]
    assert sorted(t['criterion_id'] for t in trials) == sorted(benchmark_input.CRITERIA)
    for trial in trials:
        assert trial['outcome'] == 'not_applicable'
        assert 'viewer' in trial['failure_reason']
