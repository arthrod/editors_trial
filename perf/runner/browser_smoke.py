#!/usr/bin/env python3
"""B1 acceptance measurer; fake production Vite host, no editor timing claims.

python3 -I perf/runner/browser_smoke.py --out-root /tmp/b1 --fail-repetition 1
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import urllib.request

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from perf.runner.browser_run import BrowserRun, capture, schedule
from perf.runner.browser_hosts import StaticHost, build_host
from perf.runner.host import host_record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out-root', type=Path, required=True)
    parser.add_argument('--fail-repetition', type=int, default=-1)
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()
    run = BrowserRun(args.out_root, 'fake-host', seed=args.seed)
    fixture = run.fixture('micro', b'B1 fake corpus')
    meta = build_host('fake', {'cwd': REPO / 'perf/tests/fixtures/hosts/vite'}, args.out_root)
    run.hosts['fake'] = meta
    server = StaticHost(meta['build_directory'], fixture=fixture)
    try:
        for repetition, editor in schedule(['fake'], 3, run.seed):
            def probe():
                url = server.url + ('/?fail=1' if repetition == args.fail_repetition else '/')
                result = subprocess.run(['node', str(Path(__file__).with_name('browser_environment.mjs')), url],
                                        capture_output=True, text=True, timeout=60)
                if result.returncode:
                    return {'outcome': 'failed', 'failure_reason': 'readiness: ' + result.stderr,
                            'returncode': result.returncode}
                with urllib.request.urlopen(server.url + '/corpus.docx') as response:
                    assert response.read() == fixture.read_bytes(), 'corpus mismatch'
                return {'outcome': 'ok', **json.loads(result.stdout)}
            run.begin_sample()
            row = capture(probe)
            row['repetition'] = repetition
            run.sample(str(repetition), row)
        summary = run.finish({'host': capture(host_record), 'headless': True})
    finally:
        server.stop()
    print(json.dumps({'run_id': run.run_id, 'directory': str(run.directory),
                      'tree_sha256': meta['tree_sha256'],
                      'outcomes': [row['outcome'] for row in run.samples],
                      'failure_reason': summary.get('failure_reason'),
                      'repos_unchanged': summary['repos_unchanged']}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
