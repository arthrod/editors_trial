"""Explicitly nonpublication fake-host adapter, without editing the runners.

The three multi-editor runners require a catalogued editor. Their plate driver
is exercised against a fake page; every run labels this substitution. No result
from this adapter is evidence about Plate or eligible for publication.
"""
import importlib
from pathlib import Path
import sys
from perf.runner.browser_run import BrowserRun, run_cli

FAKE = Path(__file__).parent / 'fake'


class SmokeRun(BrowserRun):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hosts['plate'] = {
            'host_build': 'fake_host', 'build_directory': str((Path(__file__).parents[1] / 'tests/fixtures'
                if args[1] == 'benchmark_typing' else Path(__file__).parents[1]).resolve()),
            'publishable': False, 'publication_block_reason': 'B6 fake page using plate driver, not Plate',
        }

    def finish(self, metadata):
        return super().finish({**metadata, 'smoke_fake_host': True,
                               'editor_identity_note': 'fake page; plate is only the driver alias', 'publishable': False})


def finish_smoke(directory, name, *, persist=True):
    """Account from attempts; an outer process exit is not a measured cell."""
    from .run import read_run
    from .policy import cell_counts, read_trials, verify_run
    from perf.runner.browser_run import write_json
    data = read_run(directory)
    counts = cell_counts(data)
    expected = 'execution_profile: workload cap for ci_contract: prose-50kw'
    by_design = {}
    if (name == 'adversarial_c10_scroll' and data.get('execution_profile') == 'ci_contract'
            and counts['trials_total'] > 0
            and counts['not_run_by_reason'] == {expected: counts['trials_total']}):
        by_design = {expected: counts['trials_total']}
    allow_empty = bool(by_design)
    if name in ('benchmark_document', 'benchmark_input'):
        for row in data['samples']:
            for trial in read_trials(row):
                reason = str(trial.get('failure_reason') or '')
                if ((trial.get('outcome') == 'not_applicable' and 'no find widget appears' in reason)
                        or (trial.get('outcome') == 'unverified' and 'forced repaint is excluded from measured C14' in reason)
                        or (trial.get('outcome') == 'not_run' and reason.startswith('execution_profile: workload cap for ci_contract:'))
                        or (name == 'benchmark_input' and trial.get('criterion_id') == 'C07' and reason.endswith(': no_painted_frame'))
                        or (name == 'benchmark_input' and trial.get('outcome') == 'not_applicable' and reason == 'no_deferred_work')):
                    by_design[reason] = by_design.get(reason, 0) + 1
    measured_cells = sum(any(trial.get('outcome') == 'measured' for trial in read_trials(row))
                         for row in data['samples']
                         if row.get('accounting_scope') != 'diagnostic'
                         and not row.get('rejected_evidence_directory'))
    record = {'runner': name, 'smoke_fake_host': True, 'publishable': False,
              'cells_measured': measured_cells, 'by_design_refusals': by_design,
              'attempt_counts': counts}
    if persist:
        write_json(directory / 'smoke-summary.json', record)
    try:
        verify_run(data)
    except ValueError as exc:
        if str(exc) != 'nothing_measured' or not allow_empty:
            raise
    return record


def main():
    name = sys.argv.pop(1)
    from .policy import RUNNERS
    if name not in RUNNERS or '--execution-profile' not in sys.argv or sys.argv[sys.argv.index('--execution-profile') + 1] != 'ci_contract':
        raise ValueError('fake hosts are only allowed in ci_contract')
    from .run import verify_lane_profiles
    # Save wrapper flags before the runner's parsers rewrite argv.
    options = list(sys.argv)
    directory = Path(options[options.index('--out-root') + 1]) / name / options[options.index('--run-id') + 1]
    profile = options[options.index('--execution-profile') + 1]
    host_class = options[options.index('--host-class') + 1] if '--host-class' in options else 'ci_coarse'
    module = importlib.import_module('perf.runner.' + name)
    if name == 'adversarial_c10_scroll':
        sys.argv += ['--fake-host', str(FAKE), '--fake-page', 'index.html']
        status = module.main()
        verify_lane_profiles(directory, profile, host_class)
        finish_smoke(directory, name)
        return status
    target = dict(module.BROWSER_TARGETS['plate'])
    target.update(url='http://127.0.0.1:5208/container/fake/index.html', ready_selector='.status-ok',
                  edit_selector='[contenteditable="true"]', ready_js='window.b6Ready === true')
    if name in ('benchmark_input', 'benchmark_document'):
        target['url'] += '?lane=' + ('input' if name == 'benchmark_input' else 'document')
    if name == 'benchmark_typing':
        target.update(url='http://127.0.0.1:5208/typing_fair.html')
        sys.argv += ['--words', '100', '--cadence-ms', '0', '--quiescence-s', '0']
    module.BROWSER_TARGETS['plate'] = target
    sys.argv += ['--editors', 'plate']
    flag = {'benchmark_warm_cold': '--pairs', 'benchmark_document': '--samples', 'benchmark_input': None, 'benchmark_typing': None}[name]
    status = run_cli(module._main, name, module.BROWSER_TARGETS, count_flag=flag, default_count=1, run_factory=SmokeRun)
    verify_lane_profiles(directory, profile, host_class)
    finish_smoke(directory, name)
    # Retain lane refusals; diagnostic acceptance is per measured criterion.
    return 0 if status in (0, 3) else status


if __name__ == '__main__':
    raise SystemExit(main())
