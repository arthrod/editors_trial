"""HF orchestration. A dry run prints the same argv executed on the Space."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import random
import shlex
import signal
import subprocess
import sys
from . import artifacts
from .policy import RUNNERS, publication_jobs, verify_run, cell_counts, verify_profiles

DEFAULT_OUT_ROOT = Path('perf/container/out/runs')


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


def allocate_run_id(out_root: Path) -> tuple[str, Path]:
    out_root = Path(out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    for _ in range(100):
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        suffix = f'{os.getpid()}-{random.randint(0, 999999):06d}'
        run_id = f'{stamp}-{suffix}'
        campaign = out_root / run_id
        try:
            campaign.mkdir(parents=False, exist_ok=False)
            return run_id, campaign
        except FileExistsError:
            continue
    raise RuntimeError('could not allocate unique run id')


def _child_setup() -> None:
    signal.signal(signal.SIGHUP, signal.SIG_IGN)


def spawn_detached_campaign(argv: list[str], campaign_dir: Path, run_id: str) -> int:
    campaign_dir.mkdir(parents=True, exist_ok=True)
    log_path = campaign_dir / 'RUN.log'
    env = {**os.environ, 'HF_RUN_CHILD': '1', 'HF_CAMPAIGN_ID': run_id}
    with log_path.open('ab') as log_file:
        proc = subprocess.Popen(
            argv,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            env=env,
            start_new_session=True,
            preexec_fn=_child_setup,
        )
    artifacts.atomic_write(campaign_dir / 'RUN.pid', f'{proc.pid}\n')
    artifacts.atomic_write(campaign_dir / 'RUN.started', datetime.now(timezone.utc).isoformat() + '\n')
    return proc.pid


def refuse_existing(path: Path) -> bool:
    return path.exists()


def verify_lane_profiles(directory, profile, host_class):
    for root in ('cells', 'rejected-evidence'):
        for path in sorted((directory / root).rglob('*.json')):
            verify_profiles([json.loads(path.read_text())], profile, host_class)


def write_run_done(campaign_root: Path, exit_status: int) -> None:
    artifacts.atomic_write(campaign_root / 'RUN-DONE', f'exit_status={exit_status}\n')


def main(argv: list[str] | None = None):
    if argv is None:
        argv = sys.argv[1:]
    if os.environ.get('HF_RUN_CHILD') == '1':
        signal.signal(signal.SIGHUP, signal.SIG_IGN)
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--smoke', action='store_true')
    mode.add_argument('--publish', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--host-class', default='ci_coarse')
    parser.add_argument('--seed', type=int, default=1)
    parser.add_argument('--seed2', type=int)
    parser.add_argument('--out-root', type=Path, default=DEFAULT_OUT_ROOT)
    parser.add_argument('--detach', action='store_true')
    args = parser.parse_args(argv)
    if args.detach and os.environ.get('HF_RUN_CHILD') != '1':
        try:
            run_id, campaign_root = allocate_run_id(args.out_root)
        except RuntimeError as exc:
            print(f'RUN-REFUSED {exc}', flush=True)
            return 2
        child_argv = [
            sys.executable,
            '-u',
            '-m',
            'perf.container.run',
            *[a for a in argv if a != '--detach'],
            '--out-root',
            str(campaign_root),
        ]
        spawn_detached_campaign(child_argv, campaign_root, run_id)
        print(run_id, flush=True)
        return 0
    from perf.runner.benchmark_warm_cold import BROWSER_TARGETS
    from perf.runner.browser_hosts import host_policy
    editors = [name for name in BROWSER_TARGETS if name != 'apryse' and host_policy(name)['publishable']]
    if args.publish and args.seed2 is None:
        parser.error('--publish requires --seed2')
    jobs = publication_jobs(editors, args.seed, args.seed2, args.host_class) if args.publish else [
        (name, ['--execution-profile', 'ci_contract', '--host-class', 'ci_coarse', '--seed', str(args.seed)]
         + (['--session-kind', kind] if kind else []))
        for name in RUNNERS for kind in (('throughput', 'latency') if name == 'benchmark_typing' else (None,))
    ]
    host_cmd = [sys.executable, '-m', 'perf.container.check_host']
    print(shlex.join(host_cmd), flush=True)
    if not args.dry_run:
        subprocess.run(host_cmd, check=True)
    print('headless=true; LIBGL_ALWAYS_SOFTWARE=1; actual renderer recorded by BrowserRun')
    print('apryse: not_run: licence key not exported')
    stamp = os.environ.get('HF_CAMPAIGN_ID') or ('DRY-RUN' if args.dry_run else datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    campaign_root = args.out_root
    if not args.dry_run:
        campaign_root.mkdir(parents=True, exist_ok=True)
    failures = []
    records = []
    run_exit = 0
    try:
        for index, (name, options) in enumerate(jobs):
            run_id = f'{stamp}-{index:03d}'
            cmd = [sys.executable, '-m', 'perf.runner.' + name] if args.publish else [sys.executable, '-m', 'perf.container.smoke', name]
            cmd += ['--out-root', str(campaign_root), '--run-id', run_id, *options]
            print(shlex.join(cmd), flush=True)
            if args.dry_run:
                continue
            directory = campaign_root / name / run_id
            entry = {'runner': name, 'seed': int(options[options.index('--seed') + 1]),
                     'run_dir': str(directory), **cell_counts({})}
            records.append(entry)
            job_exit = 0
            if refuse_existing(directory):
                job_exit = 2
                entry['refusal'] = f'job_refused: directory exists: {directory}'
                failures.append(f'{name}: {entry["refusal"]}')
            else:
                try:
                    result = subprocess.run(cmd, check=False)
                    job_exit = result.returncode
                    entry['exit_code'] = job_exit
                    data = read_run(directory)
                    entry.update(cell_counts(data))
                    verify_lane_profiles(directory, options[options.index('--execution-profile') + 1],
                                         options[options.index('--host-class') + 1])
                    if args.smoke:
                        from .smoke import finish_smoke
                        finish_smoke(directory, name, persist=False)
                    else:
                        verify_run(data)
                except Exception as exc:
                    job_exit = 1
                    entry['refusal'] = str(exc)
                    failures.append(f'{name}: {exc}')
                if directory.exists():
                    artifacts.finalize_job(directory, job_exit)
            if job_exit != 0:
                run_exit = 1
        if args.publish and not args.dry_run:
            destination = campaign_root / 'out' / 'e2-publication.json'
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(json.dumps({'runs': records, 'failures': failures}, indent=2) + '\n')
    finally:
        if not args.dry_run:
            write_run_done(campaign_root, run_exit if not failures else 1)
    if failures:
        raise RuntimeError('; '.join(failures))
    return run_exit


if __name__ == '__main__':
    raise SystemExit(main())
