"""Shakedown campaign (Arthur, 2026-11-11): every one-editor job, few repetitions, on
every rung, so all lane x editor x size bugs surface together. Never publishable.
"""
import json
import subprocess
import sys
from functools import partial
from pathlib import Path

import pytest

from perf.container import run
from perf.runner import browser_run as api
from perf.runner.browser_run import run_cli

BASE = ['--publish', '--dry-run', '--host-class', 'shared_guarded', '--seed', '1', '--seed2', '2']
COUNT = {'benchmark_warm_cold': '--pairs', 'benchmark_document': '--samples', 'benchmark_memory': '--pairs',
         'adversarial_c10_scroll': '--pairs', 'benchmark_input': '--repetitions', 'benchmark_resources': '--repetitions',
         'benchmark_typing': '--repetitions'}


def _commands(capsys, *extra):
    assert run.main([*BASE, *extra]) in (0, None)
    return [line.split() for line in capsys.readouterr().out.splitlines() if '--run-id DRY-RUN-' in line]


def test_shakedown_sets_every_jobs_count(capsys):
    commands = _commands(capsys, '--shakedown', '2')
    assert len(commands) == 594
    for cmd in commands:
        runner = cmd[cmd.index('-m') + 1].rsplit('.', 1)[1]
        flag = COUNT[runner]
        assert cmd.count(flag) == 1, cmd
        want = '1' if runner == 'benchmark_typing' else '2'
        assert cmd[cmd.index(flag) + 1] == want
        if runner == 'benchmark_typing':
            assert cmd[cmd.index('--budget-s') + 1] == '900'


def test_shakedown_needs_publish():
    with pytest.raises(SystemExit):
        run.main(['--smoke', '--dry-run', '--shakedown', '2'])


def test_shakedown_children_get_the_shakedown_env(tmp_path, monkeypatch):
    campaign = tmp_path / 'campaign'
    envs = []

    def fake_run(cmd, *a, **k):
        if any('check_host' in part for part in cmd):
            return subprocess.CompletedProcess(cmd, 0)
        envs.append((k.get('env') or {}).get('PERF_SHAKEDOWN'))
        run_id = cmd[cmd.index('--run-id') + 1]
        job = campaign / cmd[2].rsplit('.', 1)[1] / run_id
        job.mkdir(parents=True, exist_ok=True)
        (job / 'summary.json').write_text('{"samples": []}')
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, 'run', fake_run)
    monkeypatch.setattr(run, 'run_mirror_tail', lambda *a, **k: None)
    monkeypatch.setattr(run, 'pin_to_quota', lambda: 'cpu_affinity_pinned=none', raising=False)
    monkeypatch.delenv('PERF_SHAKEDOWN', raising=False)
    try:
        run.main(['--publish', '--host-class', 'shared_guarded', '--seed', '1', '--seed2', '2',
                  '--shakedown', '2', '--jobs', '3,17', '--out-root', str(campaign)])
    except (SystemExit, RuntimeError):
        pass
    assert envs == ['1', '1']
    publication = json.loads((campaign / 'out' / 'e2-publication.json').read_text())
    assert publication['selection']['shakedown'] == 2
    assert 'shakedown=2' in (campaign / 'RUN-DONE').read_text().splitlines()


def _cli(tmp, argv, monkeypatch, env):
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(sys, 'argv', ['fake', '--out-root', tmp, *argv])
    return run_cli(lambda: 0, 'fake', {'a': {}}, count_flag='--samples',
                   run_factory=partial(api.BrowserRun, snapshot=lambda: {}), facts=(lambda: {}, lambda: {}))


def test_run_cli_shakedown_allows_few_repetitions_and_is_never_publishable(tmp_path, monkeypatch):
    code = _cli(str(tmp_path), ['--seed', '7', '--execution-profile', 'dedicated_publish', '--host-class',
                                'dedicated', '--editors', 'a', '--samples', '2'], monkeypatch, {'PERF_SHAKEDOWN': '1'})
    assert code == 0
    summary = json.loads(next(Path(tmp_path).glob('fake/*/summary.json')).read_text())
    assert len(summary['order']) == 2
    assert summary['shakedown'] is True
    assert summary['publishable'] is False
    assert 'shakedown' in summary['publication_block_reason']


def test_run_cli_without_shakedown_still_refuses_few_repetitions(tmp_path, monkeypatch):
    monkeypatch.delenv('PERF_SHAKEDOWN', raising=False)
    with pytest.raises(SystemExit):
        _cli(str(tmp_path), ['--execution-profile', 'dedicated_publish', '--host-class', 'dedicated',
                             '--editors', 'a', '--samples', '2'], monkeypatch, {})


def test_publication_children_never_inherit_a_stray_shakedown_env(tmp_path, monkeypatch):
    # review-shake: a publication command run in a shell with PERF_SHAKEDOWN=1 stamped the
    # shakedown reason onto 30-launch summaries.
    campaign = tmp_path / 'campaign'
    envs = []

    def fake_run(cmd, *a, **k):
        if any('check_host' in part for part in cmd):
            return subprocess.CompletedProcess(cmd, 0)
        env = k.get('env')
        envs.append('inherited' if env is None else env.get('PERF_SHAKEDOWN', 'absent'))
        run_id = cmd[cmd.index('--run-id') + 1]
        job = campaign / cmd[2].rsplit('.', 1)[1] / run_id
        job.mkdir(parents=True, exist_ok=True)
        (job / 'summary.json').write_text('{"samples": []}')
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, 'run', fake_run)
    monkeypatch.setattr(run, 'run_mirror_tail', lambda *a, **k: None)
    monkeypatch.setattr(run, 'pin_to_quota', lambda: 'cpu_affinity_pinned=none', raising=False)
    monkeypatch.setenv('PERF_SHAKEDOWN', '1')
    try:
        run.main(['--publish', '--host-class', 'shared_guarded', '--seed', '1', '--seed2', '2',
                  '--jobs', '3,17', '--out-root', str(campaign)])
    except (SystemExit, RuntimeError):
        pass
    assert envs == ['absent', 'absent']
