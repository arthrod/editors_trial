"""HF orchestration. A dry run prints the same argv executed on the Space."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shlex
import subprocess
import sys
from .policy import RUNNERS, publication_jobs, verify_run


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--smoke', action='store_true')
    mode.add_argument('--publish', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--host-class', default='ci_coarse')
    parser.add_argument('--seed', type=int, default=1)
    parser.add_argument('--seed2', type=int)
    parser.add_argument('--out-root', type=Path, default=Path('perf/container/out/runs'))
    args = parser.parse_args()
    from perf.runner.benchmark_warm_cold import BROWSER_TARGETS
    from perf.runner.browser_hosts import host_policy
    editors = [name for name in BROWSER_TARGETS if name != 'apryse' and host_policy(name)['publishable']]
    if args.publish and args.seed2 is None:
        parser.error('--publish requires --seed2')
    jobs = publication_jobs(editors, args.seed, args.seed2, args.host_class) if args.publish else [
        (name, ['--execution-profile', 'ci_contract', '--host-class', 'ci_coarse', '--seed', str(args.seed)]) for name in RUNNERS]
    host_cmd = [sys.executable, '-m', 'perf.container.check_host']
    print(shlex.join(host_cmd), flush=True)
    if not args.dry_run:
        subprocess.run(host_cmd, check=True)
    print('headless=true; LIBGL_ALWAYS_SOFTWARE=1; actual renderer recorded by BrowserRun')
    print('apryse: not_run: licence key not exported')
    stamp = 'DRY-RUN' if args.dry_run else datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    failures = []
    for index, (name, options) in enumerate(jobs):
        run_id = f'{stamp}-{index:03d}'
        cmd = [sys.executable, '-m', 'perf.runner.' + name] if args.publish else [sys.executable, '-m', 'perf.container.smoke', name]
        cmd += ['--out-root', str(args.out_root), '--run-id', run_id, *options]
        print(shlex.join(cmd), flush=True)
        if not args.dry_run:
            result = subprocess.run(cmd, check=False)
            summary = args.out_root / name / run_id / 'summary.json'
            try:
                if result.returncode:
                    raise ValueError(f'runner exited {result.returncode}')
                verify_run(json.loads(summary.read_text()))
            except (ValueError, OSError) as exc:
                if args.publish:
                    raise
                failures.append(f'{name}: {exc}')
    if failures:
        raise RuntimeError('; '.join(failures))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
