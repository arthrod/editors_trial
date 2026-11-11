"""B6 regression tests; filesystem/Node checks are integration tests."""
import ast
import json
from pathlib import Path
import subprocess

import pytest
from perf.container import policy


def summary(samples=None):
    return {'run_id': 'r', 'rendering': {'renderer': 'SwiftShader', 'headless': True},
            'samples': samples if samples is not None else [{'outcome': 'ok', 'cell_directory': '/fake/live'}]}


def measured_trials(row):
    return [{'editor_id': 'plate', 'criterion_id': 'C03', 'outcome': 'measured'}] if row.get('outcome') == 'ok' else []


def test_recorded_refusals_do_not_abort():
    data = summary([{'outcome': 'ok', 'cell_directory': '/fake/live'}, {'outcome': 'failed', 'failure_reason': 'cpu_throttled'},
                    {'outcome': 'refused', 'reason': 'unsupported'},
                    {'outcome': 'failed', 'failure_reason': 'probe_crashed'},
                    {'accounting_scope': 'diagnostic', 'outcome': 'failed', 'failure_reason': 'clock'}])
    try:
        result = policy.verify_run(data, trial_reader=measured_trials)
    except ValueError as exc:
        pytest.fail(f'recorded outcomes aborted publication: {exc}')
    assert result == data
    assert hasattr(policy, 'cell_counts'), 'publication accounting missing'
    counts = policy.cell_counts(data, trial_reader=measured_trials)
    assert counts['cells_total'] == 4
    assert counts['measured'] == 1
    assert counts['run_refused_by_reason'] == {'cpu_throttled': 1, 'unsupported': 1}
    assert counts['refused_by_reason'] == {}
    assert counts['run_failed_by_reason'] == {'probe_crashed': 1}
    assert counts['failed_by_reason'] == {}



@pytest.mark.parametrize('samples', [[], [{'outcome': 'failed', 'failure_reason': 'cpu_throttled'}]])
def test_no_measurements_refused(samples):
    with pytest.raises(ValueError, match='nothing_measured'):
        policy.verify_run(summary(samples))


def test_profile_attestation_checks_nested_lane_records():
    assert hasattr(policy, 'verify_profiles'), 'profile_mismatch guard missing'
    policy.verify_profiles([{'environment': {'execution_profile': 'ci_contract', 'host_class': 'ci_coarse'}}], 'ci_contract', 'ci_coarse')
    for record in ({'execution_profile': 'dedicated_publish'}, {'environment': {'host_class': 'dedicated'}}):
        with pytest.raises(ValueError, match='profile_mismatch'):
            policy.verify_profiles([record], 'ci_contract', 'ci_coarse')


def test_fake_page_satisfies_runner_ready_expressions():
    # Integration: load the actual HTML into Chromium, with expressions read from
    # C10's fake target and the shared fake target used by the other three lanes.
    expressions = []
    for filename in ('perf/runner/adversarial_c10_scroll.py', 'perf/container/smoke.py'):
        tree = ast.parse(Path(filename).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Dict):
                for key, value in zip(node.keys, node.values):
                    if isinstance(key, ast.Constant) and key.value == 'ready_js' and isinstance(value, ast.Constant):
                        expressions.append(value.value)
            if isinstance(node, ast.keyword) and node.arg == 'ready_js' and isinstance(node.value, ast.Constant):
                expressions.append(node.value.value)
    assert len(expressions) >= 2
    script = """
const { chromium } = require('./harness/ui/node_modules/playwright');
(async () => { const browser = await chromium.launch({headless:true});
try { const page = await browser.newPage();
await page.goto(require('node:url').pathToFileURL(process.cwd()+'/perf/container/fake/index.html').href);
const results=[]; for(const expression of JSON.parse(process.argv[1])) results.push(await page.evaluate(expression));
console.log(JSON.stringify(results)); } finally {await browser.close();} })();
"""
    result = subprocess.run(['node', '-e', script, json.dumps(expressions)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert all(json.loads(result.stdout)), result.stdout


def test_setup_uses_every_harness_lock_and_preserves_playwright_manifest():
    result = subprocess.run(['bash', 'perf/container/setup.sh', '--dry-run'], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    manifests = subprocess.check_output(['git', 'ls-files', 'harness/**/package.json'], text=True).splitlines()
    assert manifests
    for manifest in manifests:
        directory = Path(manifest).parent
        if (directory / 'package-lock.json').exists():
            command = 'npm ci'
        elif (directory / 'pnpm-lock.yaml').exists():
            command = 'pnpm install --frozen-lockfile'
        else:
            command = 'bun install --frozen-lockfile'
        assert f'(cd {directory} && {command})' in result.stdout
    assert '@superdoc/docx-engine@' not in result.stdout
    assert '(cd harness/wordcraft && cargo build --release)' in result.stdout
    assert 'add --save-exact playwright' not in result.stdout


def test_missing_lock_refused():
    assert hasattr(policy, 'harness_install'), 'lockfile policy missing'
    with pytest.raises(ValueError, match='missing_lockfile'):
        policy.harness_install([])
    assert policy.harness_install(['bun.lockb']) == ['bun', 'install', '--frozen-lockfile']


def test_plate_requires_explicit_readiness():
    result = subprocess.run(['node', 'perf/container/plate_ready.mjs', 'data:text/html,ok', '', ''], capture_output=True, text=True)
    assert result.returncode != 0, 'HTTP success alone was accepted as ready'
    assert 'missing_readiness_gate' in result.stderr

@pytest.mark.parametrize('defect', [None, 'missing_summary', 'missing_renderer', 'nothing_measured', 'profile_mismatch'])
def test_publication_finishes_both_seeds_and_preserves_evidence(tmp_path, monkeypatch, defect):
    # Integration: real wrapper/filesystem, fake process boundary; no editor runs.
    from perf.container import run
    from types import SimpleNamespace
    calls = []

    def fake_process(command, **kwargs):
        if command[2] == 'perf.container.check_host':
            return SimpleNamespace(returncode=0)
        name = command[2].rsplit('.', 1)[-1]
        run_id = command[command.index('--run-id') + 1]
        seed = int(command[command.index('--seed') + 1])
        directory = tmp_path / name / run_id
        directory.mkdir(parents=True)
        calls.append((name, seed, directory))
        cell = directory / 'cells' / '0000-plate'
        cell.mkdir(parents=True)
        lane = {'execution_profile': 'dedicated_publish', 'host_class': 'shared_guarded'}
        data = summary([{'outcome': 'ok', 'cell_directory': '/fake/live'}, {'outcome': 'failed', 'failure_reason': 'cpu_throttled'}])
        if len(calls) == 1:
            if defect == 'missing_summary':
                return SimpleNamespace(returncode=1)
            if defect == 'missing_renderer':
                data['rendering'] = {}
            if defect == 'nothing_measured':
                data['samples'] = data['samples'][1:]
            if defect == 'profile_mismatch':
                lane['host_class'] = 'ci_coarse'
        attempts = cell / 'attempts'
        attempts.mkdir()
        (attempts / 'c03.json').write_text(json.dumps({'editor_id': 'plate', 'criterion_id': 'C03', 'outcome': 'measured', 'samples_ms': [42]}))
        if data['samples'][0]['outcome'] == 'ok':
            data['samples'][0]['cell_directory'] = str(cell)
        (cell / 'summary.json').write_text(json.dumps(lane))
        (directory / 'summary.json').write_text(json.dumps(data))
        return SimpleNamespace(returncode=1)  # recorded refusals may exit nonzero

    monkeypatch.setattr(run.subprocess, 'run', fake_process)
    monkeypatch.setattr(run.sys, 'argv', ['run', '--publish', '--host-class', 'shared_guarded', '--seed', '11', '--seed2', '19', '--out-root', str(tmp_path)])
    # Output lives under cwd/out by contract, isolated from repository evidence.
    monkeypatch.chdir(tmp_path)
    error = None
    try:
        run.main()
    except (ValueError, RuntimeError) as exc:
        error = str(exc)
    assert {seed for _, seed, _ in calls} == {11, 19}, 'aborted before reproduction seed'
    report = json.loads((tmp_path / 'out/e2-publication.json').read_text())
    assert len(report['runs']) == len(calls)
    assert all(directory.exists() for _, _, directory in calls)
    assert report['runs'][-1]['run_refused_by_reason'] == {'cpu_throttled': 1}
    assert report['runs'][-1]['refused_by_reason'] == {}
    assert report['runs'][-1]['measured'] == 1
    if defect:
        assert defect in error
    else:
        assert error is None


def test_setup_cargo_flags_and_playwright_install():
    result = subprocess.run(['bash', 'perf/container/setup.sh', '--dry-run'], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert '(cd harness/wordcraft && cargo build --release)' in result.stdout
    assert 'add --save-exact playwright' not in result.stdout
    assert '(cd harness/ui && pnpm install --frozen-lockfile)' in result.stdout


def test_skipped_only_cell_is_not_a_measurement():
    data = summary([{'outcome': 'ok', 'cell_directory': '/fake/live', 'non_failure_outcomes': [
        {'outcome': 'unsupported', 'reason': 'no_surface'}]}])
    with pytest.raises(ValueError, match='nothing_measured'):
        policy.verify_run(data)
    counts = policy.cell_counts(data, trial_reader=lambda row: [
        {'editor_id': 'plate', 'criterion_id': 'C06', 'outcome': 'unsupported', 'reason': 'no_surface'}])
    assert counts['measured'] == 0
    assert counts['refused_by_reason'] == {'no_surface': 1}


@pytest.mark.parametrize('runner', policy.RUNNERS)
@pytest.mark.parametrize('mismatch', [False, True])
def test_smoke_wrapper_checks_lane_metadata_and_marks_fake_host(tmp_path, monkeypatch, runner, mismatch):
    # Integration: exercise the actual adapter with an in-memory fake lane.
    # The existing lane framework has no fake CLI, so replace its process-like
    # boundary, retaining real adapter metadata and on-disk output validation.
    from perf.container import smoke
    from types import SimpleNamespace
    directory = tmp_path / runner / 'r'

    def lane():
        cell = directory / 'cells' / '0000-plate'
        cell.mkdir(parents=True)
        (cell / 'summary.json').write_text(json.dumps({'environment': {
            'execution_profile': 'dedicated_publish' if mismatch else 'ci_contract',
            'host_class': 'ci_coarse'}}))
        attempts = cell / 'attempts'
        attempts.mkdir()
        (attempts / 'c03.json').write_text(json.dumps({'editor_id': 'plate', 'criterion_id': 'C03', 'outcome': 'measured', 'samples_ms': [42]}))
        (directory / 'summary.json').write_text(json.dumps(summary([{'outcome': 'ok', 'cell_directory': str(cell)}])))
        return 0

    module = SimpleNamespace(main=lane, _main=lane, BROWSER_TARGETS={'plate': {}})
    monkeypatch.setattr(smoke.importlib, 'import_module', lambda name: module)
    monkeypatch.setattr(smoke, 'run_cli', lambda main, *args, **kwargs: main())
    monkeypatch.setattr(smoke.sys, 'argv', ['smoke', runner, '--out-root', str(tmp_path), '--run-id', 'r',
                                         '--execution-profile', 'ci_contract', '--host-class', 'ci_coarse'])
    if mismatch:
        with pytest.raises(ValueError, match='profile_mismatch'):
            smoke.main()
    else:
        assert smoke.main() == 0
        if runner != 'adversarial_c10_scroll':
            assert module.BROWSER_TARGETS['plate']['ready_selector'] == '.status-ok'
        else:
            assert smoke.sys.argv[-4:] == ['--fake-host', str(smoke.FAKE), '--fake-page', 'index.html']


@pytest.mark.parametrize('content', ['null', '[]', '{', '{"samples": null}', '{"samples": [null]}'])
def test_unusable_summary_is_named_and_does_not_crash_accounting(tmp_path, content):
    from perf.container.run import read_run
    (tmp_path / 'summary.json').write_text(content)
    with pytest.raises(ValueError, match='missing_summary'):
        read_run(tmp_path)
