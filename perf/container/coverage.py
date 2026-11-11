"""Does a campaign spread over many Spaces cover every job exactly once?

Each Space's RUN-DONE names the global job indices it ran (selected_jobs), the campaign's
total_jobs and, for a shakedown, its repetition count. A pull's FINAL-VERIFIED only says one
Space's bytes arrived; this unions the markers of every pulled Space.

    python -m perf.container.coverage e2-logs/hf-data-shakedown/* [--run RID ...]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _marker(path: Path) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in path.read_text().splitlines():
        key, sep, value = line.partition('=')
        if sep and key != 'failure':
            fields[key] = value
    return fields


def check(roots: list[Path], runs: list[str] | None = None) -> dict:
    seen: dict[int, int] = {}
    totals: set[str] = set()
    shakedowns: set[str] = set()
    unfinished: list[str] = []
    failed: list[str] = []
    problems: list[str] = []
    for root in roots:
        for run in sorted((root / 'runs').glob('*')):
            if not run.is_dir() or (runs and run.name not in runs):
                continue
            rel = f'{root.name}/runs/{run.name}'
            done = run / 'RUN-DONE'
            if not done.is_file():
                unfinished.append(rel)
                continue
            fields = _marker(done)
            if 'selected_jobs' not in fields:
                problems.append(f'{rel}: RUN-DONE names no selected_jobs')
                continue
            if fields.get('exit_status') != '0':
                failed.append(rel)
            totals.add(fields.get('total_jobs', ''))
            shakedowns.add(fields.get('shakedown', 'publication'))
            for item in filter(None, fields['selected_jobs'].split(',')):
                seen[int(item)] = seen.get(int(item), 0) + 1
    if len(totals) > 1:
        problems.append(f'runs disagree on total_jobs: {sorted(totals)}')
    if len(shakedowns) > 1:
        problems.append(f'mixed shakedown and publication runs: {sorted(shakedowns)}')
    total = int(next(iter(totals))) if len(totals) == 1 and next(iter(totals)).isdigit() else None
    missing = [i for i in range(total) if i not in seen] if total is not None else []
    if total is None and not problems:
        problems.append('no finished run to read')
    report = {
        'total_jobs': total,
        'covered': len(seen),
        'missing': missing,
        'duplicates': sorted(i for i, n in seen.items() if n > 1),
        'unfinished': unfinished,
        'failed_runs': failed,
        'shakedown': sorted(shakedowns),
        'problems': problems,
    }
    report['ok'] = not (missing or report['duplicates'] or unfinished or failed or problems)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='coverage')
    parser.add_argument('roots', nargs='+', type=Path, help='pulled Space directories')
    parser.add_argument('--run', action='append', default=[], help='only these run ids')
    args = parser.parse_args(argv)
    report = check(args.roots, args.run or None)
    print(f"jobs {report['covered']} of {report['total_jobs']} covered; mode {','.join(report['shakedown'])}")
    for label in ('missing', 'duplicates', 'unfinished', 'failed_runs', 'problems'):
        if report[label]:
            print(f"{label} {' '.join(str(x) for x in report[label])}")
    print('COVERAGE-OK' if report['ok'] else 'COVERAGE-INCOMPLETE')
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
