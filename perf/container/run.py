"""HF orchestration. A dry run prints the same argv executed on the Space."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shlex
import subprocess
import sys
from .policy import RUNNERS, publication_jobs, verify_run, cell_counts, verify_profiles


def read_run(directory):
    try:
        data = json.loads((directory / 'summary.json').read_text())
        if not isinstance(data, dict) or not isinstance(data.get('samples'), list):
            raise ValueError('expected a run object with a samples list')
        if any(not isinstance(row, dict) for row in data['samples']):
            raise ValueError('expected sample objects')
        return data
    except (OSError, ValueError) as exc:
        raise ValueError(f'missing_summary: {directory}: {exc}') from exc


def verify_lane_profiles(directory, profile, host_class):
    # Throttled cells are moved by B1, not deleted. Inspect those too. C10's
    # host_class is in its attempt environment, not its summary_c10.json.
    for root in ('cells', 'rejected-evidence'):
        for path in sorted((directory / root).rglob('*.json')):
            verify_profiles([json.loads(path.read_text())], profile, host_class)


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
    records = []
    for index, (name, options) in enumerate(jobs):
        run_id = f'{stamp}-{index:03d}'
        cmd = [sys.executable, '-m', 'perf.runner.' + name] if args.publish else [sys.executable, '-m', 'perf.container.smoke', name]
        cmd += ['--out-root', str(args.out_root), '--run-id', run_id, *options]
        print(shlex.join(cmd), flush=True)
        if not args.dry_run:
            directory = args.out_root / name / run_id
            entry = {'runner': name, 'seed': int(options[options.index('--seed') + 1]),
                     'run_dir': str(directory), **cell_counts({})}
            records.append(entry)
            try:
                result = subprocess.run(cmd, check=False)
                entry['exit_code'] = result.returncode
                data = read_run(directory)
                entry.update(cell_counts(data))
                verify_lane_profiles(directory, options[options.index('--execution-profile') + 1],
                                     options[options.index('--host-class') + 1])
                if args.smoke:
                    from .smoke import finish_smoke
                    finish_smoke(directory, name, persist=False)
                else:
                    verify_run(data)
            except (ValueError, OSError) as exc:
                entry['refusal'] = str(exc)
                failures.append(f'{name}: {exc}')
    if args.publish and not args.dry_run:
        destination = Path('out/e2-publication.json')
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps({'runs': records, 'failures': failures}, indent=2) + '\n')
    if failures:
        raise RuntimeError('; '.join(failures))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
