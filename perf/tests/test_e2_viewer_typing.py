"""A viewer has no typing session: the lane records why instead of starting it."""
from perf.runner.benchmark_typing import viewer_refusal
from perf.runner.benchmark_warm_cold import BROWSER_TARGETS


def test_nutrient_typing_does_not_apply():
    result = viewer_refusal(BROWSER_TARGETS['nutrient'])
    assert result['outcome'] == 'not_applicable'
    assert 'viewer' in result['failure_reason']


def test_every_editor_that_edits_still_types():
    for name, target in BROWSER_TARGETS.items():
        if name != 'nutrient':
            assert viewer_refusal(target) is None, name
