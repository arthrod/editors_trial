"""Round four reviewer trees; upstream pyfakefs isolates all filesystem I/O."""

import json
import pytest
from perf.tests import test_e2_report_fix3 as fixtures
from perf.tests.test_e2_report_fix3 import trial, cell

runs = fixtures.runs
from perf.analysis import e2_cells as cells
from build import perf_e2_tables as report
from perf.runner.browser_run import BrowserRun, capture, REPO
from perf.runner.browser_hosts import HostBuildError


@pytest.fixture
def pair(runs):
    for root in runs:
        for rep in range(10):
            trial(root, rep, publishable=True, refusal_code=None, sub_frame_samples=[False])
    return runs


@pytest.mark.parametrize(
    'message',
    [
        'HostBuildError2: host_build: failed',
        'Error: host_build: failed',
        'RuntimeError: Error: host_build: failed',
        '[Errno 2] host_build',
        'production build failed: host_build',
        'cpu_throttled: not actually throttled',
        'search_timeout: selector; host_build',
    ],
)
@pytest.mark.parametrize('code', ['host_build', 'crash', None])
def test_codes_ignore_message(pair, message, code):
    root = pair[0]
    directory = root / 'samples'
    directory.mkdir()
    for rep in range(10):
        row = dict(editor_id='plate', failure_reason=message)
        if code is not None:
            row['refusal_code'] = code
        (directory / f'{rep:04d}-plate.json').write_text(json.dumps(row))
    assert cell(root)['refusals'] == ({'host_build': 10} if code == 'host_build' else {})
    assert cell(root, 'C04')['refusals'] == {code or 'crash': 10}
    assert '10' in report._cell_text({}, list(pair), 'plate', 'C04')
    assert report.facts_from_runs(*pair)['perf.e2.table.C04'] == 'not in these runs.'


@pytest.mark.parametrize(
    'exc,expected',
    [
        (HostBuildError({'reason': 'anything', 'build_log': '/log'}), 'host_build'),
        (OSError('cpu_throttled: misleading'), 'crash'),
        (RuntimeError('host_build: misleading'), 'crash'),
    ],
)
def test_capture_type(exc, expected):
    def fail():
        raise exc

    assert capture(fail).get('refusal_code') == expected


def test_unreadable_veto(pair):
    (pair[0] / 'cells/0000-plate/attempts/bad.json').write_text('{not json host-error')
    assert cell(pair[0])['refusals'] == {'unreadable_trial': 1}
    assert cell(pair[0])['stats']['n'] == 9


@pytest.mark.parametrize('reverse', [False, True])
def test_duplicates(pair, reverse):
    trial(
        pair[0],
        0,
        name='A.json' if reverse else 'Z.json',
        publishable=True,
        refusal_code=None,
        samples_ms=[900],
        sub_frame_samples=[False],
    )
    assert cell(pair[0])['refusals'] == {'conflicting_trials': 1}


@pytest.mark.parametrize(
    'criterion,field,values',
    [('C14', 'size_rung', ['small', 'large']), ('C15', 'measurement', ['first_match', 'search_complete'])],
)
def test_distinct_measures(pair, criterion, field, values):
    for root in pair:
        for rep in range(10):
            for i, measure in enumerate(values):
                trial(
                    root,
                    rep,
                    criterion,
                    name=f'{i}.json',
                    publishable=True,
                    refusal_code=None,
                    samples_ms=[100 + 800 * i],
                    sub_frame_samples=[False],
                    diagnostic={field: measure, 'frame_interval_ms': 16.7},
                )
    text = report.facts_from_runs(*pair)[f'perf.e2.table.{criterion}']
    assert all(v in text for v in values)
    assert '100.0 ms' in text and '900.0 ms' in text


@pytest.mark.parametrize(
    'samples,flags,reason',
    [
        ([10, None, 14], [True] * 3, 'malformed_samples'),
        ([10, 'bad', 14], [True] * 3, 'malformed_samples'),
        ([10, 12, 14], [1] * 3, 'malformed_samples'),
        ([12] * 3, [True, False, False], 'sub_frame_flag_mismatch'),
        ([20], None, 'malformed_samples'),
        ([20], [], 'malformed_samples'),
    ],
)
def test_flags(pair, samples, flags, reason):
    trial(
        pair[0],
        0,
        publishable=True,
        refusal_code=None,
        samples_ms=samples,
        sub_frame_samples=flags,
        diagnostic={'frame_interval_ms': 8.3},
    )
    assert cell(pair[0])['refusals'] == {reason: 1}


@pytest.mark.parametrize(
    'extra',
    [
        {'publishable': 'false'},
        {'publishable': False},
        {'publishable': True, 'host_provenance': {'publishable': False}},
        {'publishable': 1},
    ],
)
def test_publishable(pair, extra):
    trial(pair[0], 0, refusal_code=None, sub_frame_samples=[False], **extra)
    assert cell(pair[0])['refusals'] == {'publishable_not_true': 1}


def test_missing_code(pair):
    trial(pair[0], 0, publishable=True, sub_frame_samples=[False])
    path = pair[0] / 'cells/0000-plate/attempts/C07.json'
    row = json.loads(path.read_text())
    del row['refusal_code']
    path.write_text(json.dumps(row))
    assert cell(pair[0])['refusals'] == {'crash': 1}


def test_blocked_empty(pair):
    root = pair[1]
    for path in (root / 'cells').rglob('*.json'):
        path.unlink()
    data = json.loads((root / 'summary.json').read_text())
    data.update(publishable=False, failure_reason='repos_modified')
    (root / 'summary.json').write_text(json.dumps(data))
    try:
        text = cells.publish_dual_runs(*pair, 'plate', 'C07')
    except ValueError as exc:
        pytest.fail(f'blocked run raised before publication: {exc}')
    assert 'blocked' in text and 'not enough samples' not in text
    assert text in report.facts_from_runs(*pair)['perf.e2.table.C07']


def test_relative_root(fs):
    fs.create_dir('/elsewhere')
    fs.cwd = '/elsewhere'
    run = BrowserRun(
        'perf/out',
        'fixture',
        seed=0,
        run_id='fixed',
        snapshot=lambda: {},
        accounting_reader=lambda: {'available': False},
    )
    assert run.out_root == REPO / 'perf/out'


def test_attempt_writer_codes(fs):
    from perf.runner.artifacts import write_attempt

    row = dict(
        criterion_id='C15',
        editor_id='plate',
        outcome='not_run',
        failure_reason='host_build: misleading',
        layer='browser_visible',
        boundary='input_to_next_paint',
        samples_ms=[],
    )
    path = write_attempt('/attempts', 'refused', row)
    assert json.loads(path.read_text()).get('refusal_code') == 'not_run'


def test_accounting_code(fs):
    run = BrowserRun(
        '/out', 'fixture', seed=0, run_id='fixed', snapshot=lambda: {}, accounting_reader=lambda: {'available': False}
    )
    path = run.sample('0000-plate', {'editor_id': 'plate', 'outcome': 'ok', 'refusal_code': None})
    assert json.loads(path.read_text())['refusal_code'] == 'cpu_accounting_unavailable'


def test_blocked_run_still_reports_its_block(pair):
    path = pair[1] / 'summary.json'
    data = json.loads(path.read_text())
    # A genuinely blocked run still renders its block reason; only the
    # comparability guards (host/seed/pin/profile) precede the early-return,
    # so a blocked repro also fails those checks instead of hiding them (#149).
    data.update(publishable=False, publication_block_reason='repos_modified')
    path.write_text(json.dumps(data))
    text = cells.publish_dual_runs(*pair, 'plate', 'C07')
    assert 'blocked' in text


def test_blocked_run_still_fails_comparability_guards(pair):
    path = pair[1] / 'summary.json'
    data = json.loads(path.read_text())
    data.update(publishable=False, publication_block_reason='repos_modified', execution_profile='ci_contract')
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='execution profile'):
        cells.publish_dual_runs(*pair, 'plate', 'C07')
