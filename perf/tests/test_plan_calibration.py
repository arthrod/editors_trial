"""Planner minutes stay on the campaign-1 30-repetition calibration.

``_BASE`` and ``_C14`` were read off one job that ran 30 repetitions
(ccedf968). Dividing those minutes by ``PUBLICATION_REPETITIONS`` prices a
5-repetition block as 15. The per-repetition cost, excluding host builds,
is the ccedf968 cost for the same absolute repetition count. Typing is a
fixed per-job cost and does not scale.
"""
import re
import subprocess
import sys
import types
from pathlib import Path

import pytest

from perf.container import plan, policy
from perf.runner.browser_run import PUBLICATION_REPETITIONS

ROOT = Path(__file__).resolve().parents[2]
# The publication editor list. Apryse is not in it; these nine are.
EDITORS = ['plate', 'docxodus', 'superdoc', 'genoffice', 'canvas', 'docen', 'wordcraft', 'eigenpal', 'folio']
# Campaign 1's schedule length, the divisor in ccedf968:perf/container/plan.py.
_CAMPAIGN_REPS = 30


def _historical():
    source = subprocess.check_output(
        ['git', 'show', 'ccedf968:perf/container/plan.py'], cwd=ROOT, text=True)
    divisors = {int(n) for n in re.findall(r'/ (\d+)', source)}
    assert divisors == {_CAMPAIGN_REPS}, divisors
    name = 'perf.container._plan_ccedf968'
    module = sys.modules.get(name)
    if module is not None:
        return module
    module = types.ModuleType(name)
    module.__package__ = 'perf.container'
    module.__file__ = 'ccedf968:perf/container/plan.py'
    module.__dict__['__name__'] = name
    module.__dict__['__package__'] = 'perf.container'
    sys.modules[name] = module
    exec(compile(source, module.__file__, 'exec'), module.__dict__)
    return module


def _cases():
    """Real publication jobs, plus repetition counts the layout never emits."""
    for blocks in (None, 1, 2, 10):
        for name, options in policy.publication_jobs(EDITORS, 1, 2, 'shared_guarded', blocks=blocks):
            for shakedown in (None, 1, 2):
                yield name, options, shakedown
    for name, flag in policy.SHAKEDOWN_COUNT_FLAG.items():
        for editors in (['plate'], ['plate', 'docxodus', 'docen']):
            for reps in (7, 15, 30):
                for traced in (False, True):
                    options = ['--seed', '1', '--workload', 'prose-50kw', '--editors', *editors,
                               '--block', '1/2', flag, str(reps)]
                    if traced:
                        options.insert(2, '--chrome-profile')
                    for shakedown in (None, 1):
                        yield name, options, shakedown
            if name == 'benchmark_document':
                options = ['--seed', '1', '--chrome-profile', '--editors', *editors, '--criteria', 'C14',
                           '--block', '1/2', flag, '15']
                yield name, options, None
                yield name, options, 1


def _launches(name, options, shakedown, nonblock_reps):
    """Absolute repetition count that estimator is pricing. Builds are separate."""
    if shakedown:
        if '--block' in options:
            traced = 2 if '--chrome-profile' in options else 1
            return shakedown + traced - 1
        return shakedown + 1
    if '--block' in options:
        flag = policy.SHAKEDOWN_COUNT_FLAG[name]
        return int(options[options.index(flag) + 1])
    return nonblock_reps


def _builds(module, options, shakedown):
    if '--block' in options:
        return module._BUILD * len(policy.job_editors(options))
    if shakedown:
        return module._BUILD
    return 0


def test_calibration_names_the_campaign_thirty():
    historical = _historical()
    assert getattr(plan, '_CALIBRATED_REPS', None) == _CAMPAIGN_REPS
    assert plan._BASE == historical._BASE
    assert plan._C14 == historical._C14
    assert plan._TYPING == historical._TYPING
    assert plan._BUILD == historical._BUILD
    assert plan._RUNG == historical._RUNG


def test_non_typing_per_repetition_matches_ccedf968():
    historical = _historical()
    mismatches = []
    checked = 0
    for name, options, shakedown in _cases():
        if name == 'benchmark_typing':
            continue
        now = plan.estimate(name, options, shakedown=shakedown)
        then = historical.estimate(name, options, shakedown=shakedown)
        now_reps = _launches(name, options, shakedown, PUBLICATION_REPETITIONS)
        then_reps = _launches(name, options, shakedown, _CAMPAIGN_REPS)
        per_now = (now - _builds(plan, options, shakedown)) / now_reps
        per_then = (then - _builds(historical, options, shakedown)) / then_reps
        checked += 1
        if per_now != pytest.approx(per_then):
            mismatches.append(
                '%s shakedown=%s reps=%s/%s per=%s historical=%s ratio=%s'
                % (name, shakedown, now_reps, then_reps, per_now, per_then,
                   per_now / per_then if per_then else 'inf'))
    assert checked > 0
    assert not mismatches, '%d of %d\n%s' % (len(mismatches), checked, '\n'.join(mismatches[:6]))


def test_shakedown_one_matches_ccedf968():
    historical = _historical()
    mismatches = []
    checked = 0
    for name, options, shakedown in _cases():
        if name == 'benchmark_typing' or shakedown != 1:
            continue
        now = plan.estimate(name, options, shakedown=1)
        then = historical.estimate(name, options, shakedown=1)
        checked += 1
        if now != pytest.approx(then):
            mismatches.append('%s now=%s historical=%s options=%s' % (name, now, then, options))
    assert checked > 0
    assert not mismatches, '%d of %d\n%s' % (len(mismatches), checked, '\n'.join(mismatches[:6]))


def test_typing_estimates_are_unchanged():
    historical = _historical()
    checked = 0
    for name, options, shakedown in _cases():
        if name != 'benchmark_typing':
            continue
        assert plan.estimate(name, options, shakedown=shakedown) == historical.estimate(
            name, options, shakedown=shakedown)
        checked += 1
    assert checked > 0
    bare = ['--seed', '1', '--editors', 'plate']
    assert plan.estimate('benchmark_typing', bare) == historical.estimate('benchmark_typing', bare) == 360
    assert plan.estimate('benchmark_typing', bare, shakedown=1) == 15
