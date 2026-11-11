"""Container policy: pin drift, incomplete inventories and unsafe schedules fail closed."""
import importlib
import pytest


def api():
    try:
        return importlib.import_module('perf.container.policy')
    except ModuleNotFoundError:
        pytest.fail('container policy is missing')


def facts():
    return {'ver.plate.commit': 'abcdef123', 'ver.plate.slug': 'udecode/plate'}


def test_pin_plan_and_full_sha_verification():
    p = api()
    assert p.git_pins(facts(), required=('plate',)) == [('plate', 'udecode/plate', 'abcdef123')]
    assert p.verify_commit('abcdef123', 'abcdef123' + '0'*31) == 'abcdef123' + '0'*31
    for full in ('abcdef123', 'b'*40, 'g'*40):
        with pytest.raises(ValueError):
            p.verify_commit('abcdef123', full)


@pytest.mark.parametrize('key,value', [('ver.plate.commit', None), ('ver.plate.commit', 'main'),
    ('ver.plate.slug', None), ('ver.plate.slug', '../plate'), ('ver.plate.slug', 'https://github.com/u/p')])
def test_missing_or_unsafe_pin_refused(key, value):
    f = facts()
    f[key] = value
    with pytest.raises(ValueError):
        api().git_pins(f, required=('plate',))


def test_publication_two_distinct_seeds_and_all_runners():
    p = api()
    jobs = p.publication_jobs(['plate', 'folio'], 17, 29, 'shared_guarded')
    typing = [job for job in jobs if job[0] == 'benchmark_typing']
    assert len(typing) == 2 * 2 * 2  # two editors, two seeds, two session kinds
    # one editor per job: per seed and editor, five rung jobs in each of five lanes,
    # C14, and five C10 rungs
    assert len(jobs) == 2 * 2 * (5 * 5 + 1 + 5) + len(typing)
    assert {j[0] for j in jobs} == {'benchmark_warm_cold', 'benchmark_document', 'benchmark_input', 'adversarial_c10_scroll', 'benchmark_typing', 'benchmark_memory', 'benchmark_resources'}
    for name, args in jobs:
        assert args[args.index('--execution-profile')+1] == 'dedicated_publish'
        assert args[args.index('--host-class')+1] == 'shared_guarded'
        if name == 'benchmark_typing':
            assert args[args.index('--repetitions')+1] == '12'
        else:
            assert '--repetitions' not in args
        assert '--pairs' not in args and '--samples' not in args
        if name == 'adversarial_c10_scroll':
            assert args[-2] == '--editor' and args[-1] in ('plate', 'folio')
        elif name == 'benchmark_typing':
            assert args[-2] == '--editors' and args[-1] in ('plate', 'folio')
        else:
            at = args.index('--editors')
            assert args[at + 1] in ('plate', 'folio') and (at + 2 == len(args) or args[at + 2].startswith('--'))
    with pytest.raises(ValueError):
        p.publication_jobs(['plate'], 17, 17, 'shared_guarded')
    with pytest.raises(ValueError):
        p.publication_jobs(['plate'], 17, 29, 'ci_coarse')
    with pytest.raises(ValueError):
        p.publication_jobs([], 17, 29, 'shared_guarded')


def test_npm_resolution_mismatch_refused():
    p = api()
    assert p.verify_version('2.0.0', '2.0.0') == '2.0.0'
    for expected, actual in [(None, '2.0.0'), ('2.0.0', '2.0.1')]:
        with pytest.raises(ValueError):
            p.verify_version(expected, actual)


def test_all_npm_pins_required():
    p = api()
    f = {'ver.npm.' + k: '1.2.3' for k, _, _ in p.NPM}
    assert len(p.npm_pins(f)) == 4
    for key in list(f):
        with pytest.raises(ValueError):
            p.npm_pins({k: v for k, v in f.items() if k != key})


# Filesystem and shell checks below are integration checks, not unit tests.
def test_dockerfile_tools_only_and_hf_layout():
    from pathlib import Path
    text = Path('perf/container/Dockerfile').read_text()
    assert 'v1.64.1-noble@sha256:ee15712262f017b8157421b212b12099146645f44b1bc5c0514cbbe6a229b1d0' in text
    assert not any(line.startswith(('COPY ', 'ADD ')) for line in text.splitlines())
    for required in ('USER 1000', 'HOME=/home/user', 'WORKDIR /app', 'EXPOSE 7860',
                     '"http.server", "7860"', 'PLAYWRIGHT_BROWSERS_PATH=/ms-playwright'):
        assert required in text


def test_dockerfile_has_verified_literal_digest():
    import re
    from pathlib import Path
    assert re.search(r'^FROM .*@sha256:[a-f0-9]{64}$', Path('perf/container/Dockerfile').read_text(), re.M)


def test_setup_dry_run_and_missing_pin(tmp_path):
    import json
    import subprocess
    from pathlib import Path
    result = subprocess.run(['bash', 'perf/container/setup.sh', '--dry-run'], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    f = json.loads(Path('out/facts.json').read_text())
    for name, slug, pin in api().git_pins(f):
        assert f'clone {name} https://github.com/{slug}.git pin={pin}' in result.stdout
    for name, command in api().INSTALLS.items():
        assert ' '.join(command) in result.stdout
    # Source aliases resolve third-party imports from the editor workspace,
    # not from the harness that supplies Vite. A fresh HF clone needs this.
    assert '(cd repos/docen && pnpm install --frozen-lockfile --ignore-scripts)' in result.stdout
    del f['ver.plate.commit']
    path = tmp_path / 'facts.json'
    path.write_text(json.dumps(f))
    result = subprocess.run(['bash', 'perf/container/setup.sh', '--dry-run', '--facts', str(path)], capture_output=True, text=True)
    assert result.returncode != 0
    assert 'missing or invalid commit: plate' in result.stderr
    assert 'clone ' not in result.stdout


@pytest.mark.parametrize('mode', [['--smoke'], ['--publish', '--host-class', 'shared_guarded', '--seed', '1', '--seed2', '2']])
def test_runner_dry_run(mode):
    import subprocess
    result = subprocess.run(['bash', 'perf/container/run.sh', '--dry-run', *mode], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.index('perf.container.check_host') < result.stdout.index('benchmark_warm_cold')
    for runner in api().RUNNERS:
        assert runner in result.stdout
    if '--publish' in mode:
        assert '--seed 1' in result.stdout and '--seed 2' in result.stdout
        assert '--editor plate' in result.stdout
        assert '--execution-profile dedicated_publish' in result.stdout
        assert '--editors plate' in result.stdout
        for line in result.stdout.splitlines():
            if 'perf.runner.benchmark_typing ' in line:
                assert '--repetitions 12 --cadence-ms 0 --budget-s 3600' in line
            else:
                assert '--repetitions' not in line


def test_run_evidence_fails_closed():
    p = api()
    good = {'run_id': 'r1', 'rendering': {'renderer': 'SwiftShader', 'headless': True}, 'samples': [{'outcome': 'ok', 'cell_directory': '/fake/live'}]}
    assert p.verify_run(good, trial_reader=lambda row: [{'editor_id': 'plate', 'criterion_id': 'C03', 'outcome': 'measured'}]) == good
    for change in ({'rendering': {}}, {'samples': []},
                   {'samples': [{'outcome': 'failed'}]}):
        with pytest.raises(ValueError):
            p.verify_run({**good, **change})
