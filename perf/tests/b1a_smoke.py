"""Independent bookkeeping fake-host smoke; no editor timing claims.

Run with python3 -I perf/tests/b1a_smoke.py plus run_cli options.
--baseline-ref REF loads the two modules from an explicitly selected local commit.
A --baseline-ref that does not resolve to a local commit (or whose commit lacks
the modules) exits 2 with a single stderr line, no traceback.
"""

import argparse
from pathlib import Path
import subprocess
import sys
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from perf.runner import browser_run, benchmark_ci_contract
from perf.runner.browser_hosts import StaticHost

if '--baseline' in sys.argv:
    raise SystemExit('use --baseline-ref REF with an available local commit')
if '--baseline-ref' in sys.argv:
    index = sys.argv.index('--baseline-ref')
    if index + 1 == len(sys.argv):
        raise SystemExit('--baseline-ref requires a local git ref')
    baseline = sys.argv[index + 1]
    del sys.argv[index:index + 2]
    probe = subprocess.run(
        ['git', 'rev-parse', '--verify', '--end-of-options', baseline + '^{commit}'],
        capture_output=True, text=True)
    if probe.returncode:
        print(f'--baseline-ref {baseline}: not a local commit', file=sys.stderr)
        raise SystemExit(2)
    baseline = probe.stdout.strip()
    for module in (browser_run, benchmark_ci_contract):
        relative = Path(module.__file__).relative_to(Path(__file__).resolve().parents[2])
        show = subprocess.run(['git', 'show', baseline + ':' + str(relative)],
                              capture_output=True, text=True)
        if show.returncode:
            print(f'--baseline-ref {baseline}: {relative} missing at that commit',
                  file=sys.stderr)
            raise SystemExit(2)
        exec(compile(show.stdout, module.__file__, 'exec'), module.__dict__)


def cell():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out-root', type=Path)
    parser.add_argument('--editors', nargs='+')
    args = parser.parse_args()
    root = Path(__file__).parent / 'fixtures' / 'hosts' / 'vite'
    fixture = browser_run.fixture_path('micro', b'fixture', args.out_root / 'fixture.docx')
    host = StaticHost(root, fixture=fixture)
    try:
        with urllib.request.urlopen(host.url + '/') as response:
            assert response.status == 200
        env = benchmark_ci_contract._host_base(
            editor_id='fake',
            editor_version='1',
            execution_profile='ci_broad',
            fixture_sha256='a' * 64,
            workload_row=dict(workload_id='micro-paragraphs', paragraphs=1, unicode_class='ascii', match_count=0),
            docx_size=7,
            cache_state='warm_steady',
            repetition_unit='fresh_process',
            run_kind='timing',
            feature_profile_name='P0',
        )
        browser_run.write_json(args.out_root / 'trial.json', {'environment': env})
        browser_run.write_json(
            args.out_root / 'skip.json', {'outcome': 'not_run', 'failure_reason': 'single ready signal'}
        )
        return 0
    finally:
        host.stop()


if __name__ == '__main__':
    raise SystemExit(
        browser_run.run_cli(
            cell,
            'b1a-smoke',
            {'fake': {}},
            facts=(lambda: {}, lambda: {}),
            run_factory=lambda *a, **kw: browser_run.BrowserRun(*a, snapshot=lambda: {}, **kw),
        )
    )
