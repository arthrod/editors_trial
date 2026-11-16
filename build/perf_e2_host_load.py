"""Report E2: which jobs' samples were taken on a busy host (#228).

Every sample row a browser lane writes records the host's load average when
the sample began and when it ended (perf/runner/browser_throttle.py). The
campaign never refused a sample for it. This module reads those rows from
the run folders and says, per lane, how many began or ended with the
1-minute load above the quiet-machine bound (a third of the host's logical
CPUs, perf/runner/host.py), and names the jobs in which a quarter or more
did. It changes no figure: it tells the reader where a disagreement between
two seeds may be the machine.
"""
from __future__ import annotations

import json
from pathlib import Path

BOUND_FRACTION = 1 / 3
NAMED_SHARE = 0.25

# The words build/perf_e2_tables.py uses for the lanes (LANE_NAMES); a test keeps the two the same.
LANES = {
    'adversarial_c10_scroll': 'C10 scroll', 'benchmark_document': 'document', 'benchmark_input': 'input',
    'benchmark_memory': 'memory', 'benchmark_resources': 'resources', 'benchmark_typing': 'typing',
    'benchmark_warm_cold': 'warm and cold load',
}
DOCUMENTS = {
    'prose-500w': '500 words', 'prose-5kw': '5,000 words', 'prose-50kw': '50,000 words',
    'prose-250kw': '250,000 words', 'prose-500kw': '500,000 words', 'complex-corpus': 'complex document',
}
SEEDS = {1: 'first', 2: 'second'}
NOT_RECORDED = 'not recorded'


def _number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def row_load(row: dict):
    """(highest 1-minute load of the row's two ends, above the bound?, the bound) or None when a reading is missing."""
    accounting = row.get('cpu_accounting') if isinstance(row, dict) else None
    if not isinstance(accounting, dict) or not accounting.get('available'):
        return None
    loads, cpus = [], None
    for side in ('before', 'after'):
        reading = accounting.get(side)
        load = reading.get('loadavg') if isinstance(reading, dict) else None
        if not (isinstance(load, list) and load and _number(load[0])):
            return None
        loads.append(float(load[0]))
        cpus = reading.get('cpu_count_visible') if _number(reading.get('cpu_count_visible')) else cpus
    if not cpus:
        return None
    bound = round(cpus * BOUND_FRACTION, 2)
    return max(loads), max(loads) > bound, bound


def _workload(summary: dict, job: Path) -> str | None:
    """The one document a job loaded: from its fixtures, else from its attempts (a memory job lists no fixtures)."""
    names = {Path(str(fixture)).name.rsplit('-', 1)[0] for fixture in summary.get('fixtures') or []} - {'micro-search'}
    if not names:
        for attempt in sorted(job.glob('cells/*/attempts/*.json')):
            try:
                workload = json.loads(attempt.read_text()).get('environment', {}).get('workload_id')
            except (OSError, ValueError, AttributeError):
                continue
            if workload:
                names.add(workload)
            if len(names) > 1:
                break
    return next(iter(names)) if len(names) == 1 else None


def _editors(summary: dict) -> list[str]:
    order = summary.get('order') if isinstance(summary.get('order'), list) else []
    return sorted({pair[1] for pair in order if isinstance(pair, list) and len(pair) == 2 and isinstance(pair[1], str)})


def job_rows(roots) -> list[dict]:
    """One row per job directory of the run folders that has sample rows."""
    out = []
    for root in sorted(Path(root) for root in roots):
        for samples in sorted(root.glob('*/*/samples')):
            job = samples.parent
            try:
                summary = json.loads((job / 'summary.json').read_text())
            except (OSError, ValueError):
                summary = {}
            count = above = unread = 0
            highest, bound = None, None
            for path in sorted(samples.glob('*.json')):
                try:
                    row = json.loads(path.read_text())
                except (OSError, ValueError):
                    unread += 1
                    continue
                if not isinstance(row, dict) or row.get('accounting_scope') == 'diagnostic':
                    continue
                load = row_load(row)
                if load is None:
                    unread += 1
                    continue
                count += 1
                above += load[1]
                highest = load[0] if highest is None else max(highest, load[0])
                bound = load[2] if bound is None else max(bound, load[2])
            if not count and not unread:
                continue
            block = summary.get('block') if isinstance(summary.get('block'), dict) else {}
            out.append({'space': root.name.split('--')[0], 'lane': job.parent.name, 'job': job.name,
                        'seed': summary.get('seed'), 'block': block.get('index'), 'workload': _workload(summary, job),
                        'editors': _editors(summary), 'samples': count, 'above': above, 'unread': unread, 'highest': highest, 'bound': bound})
    return out


def _size(workload) -> int:
    return list(DOCUMENTS).index(workload) if workload in DOCUMENTS else len(DOCUMENTS)


def _percent(part: int, whole: int) -> str:
    return '%.1f percent' % (100 * part / whole if whole else 0.0)


def _who(row: dict, editors, display: dict) -> str:
    """'every editor' when the job scheduled all of the report's editors, else the ones it did."""
    if not row['editors']:
        return NOT_RECORDED
    if set(editors) <= set(row['editors']):
        return 'every editor'
    return ', '.join(sorted(display.get(editor, editor) for editor in row['editors']))


def section(roots, editors=(), display=None) -> tuple[str, dict]:
    """The report's text and its facts. Lanes and jobs are listed in a fixed order, never by how busy they were."""
    display = display or {}
    rows = job_rows(roots)
    samples, above, unread = (sum(row[key] for row in rows) for key in ('samples', 'above', 'unread'))
    named = sorted((row for row in rows if row['samples'] and row['above'] / row['samples'] >= NAMED_SHARE),
                   key=lambda row: (LANES.get(row['lane'], row['lane']).lower(), _size(row['workload']), str(row['seed']),
                                    str(row['block']), row['space'], row['job']))
    facts = {'perf.e2.host_load.samples': samples, 'perf.e2.host_load.above': above,
             'perf.e2.host_load.unread': unread, 'perf.e2.host_load.jobs': len(rows),
             'perf.e2.host_load.jobs_named': len(named)}
    if not samples:
        return 'The host load of the launches was not recorded in these runs.', facts
    bounds = sorted({row['bound'] for row in rows if row['bound'] is not None})
    bound = ('%.1f' % bounds[0]) if len(bounds) == 1 else ' to '.join('%.1f' % value for value in (bounds[0], bounds[-1]))
    lines = ['Of the %s launches of these runs, %s (%s) began or ended with the load above %s.'
             % (format(samples, ','), format(above, ','), _percent(above, samples), bound)]
    if unread:
        lines[0] += ' %s further launches carry no load reading and are not counted.' % format(unread, ',')
    lines += ['', '| Lane | Launches | Above the bound | Share |', '|---|---|---|---|']
    for lane in sorted({row['lane'] for row in rows}, key=lambda lane: LANES.get(lane, lane).lower()):
        of_lane = [row for row in rows if row['lane'] == lane]
        count, busy = sum(row['samples'] for row in of_lane), sum(row['above'] for row in of_lane)
        lines.append('| %s | %s | %s | %s |' % (LANES.get(lane, lane), format(count, ','), format(busy, ','), _percent(busy, count)))
    lines.append('')
    if not named:
        lines.append('In no job were a quarter or more of the launches above it.')
        return '\n'.join(lines), facts
    lines += ['Jobs in which a quarter or more of the launches were above it:', '',
              '| Lane | Document | Seed | Block | Space | Editors | Launches above | Highest load |',
              '|---|---|---|---|---|---|---|---|']
    for row in named:
        lines.append('| %s | %s | %s | %s | %s | %s | %s of %s | %.1f |' % (
            LANES.get(row['lane'], row['lane']), DOCUMENTS.get(row['workload'], NOT_RECORDED),
            SEEDS.get(row['seed'], NOT_RECORDED), row['block'] if row['block'] is not None else NOT_RECORDED,
            row['space'], _who(row, editors, display), format(row['above'], ','), format(row['samples'], ','),
            row['highest']))
    return '\n'.join(lines), facts
