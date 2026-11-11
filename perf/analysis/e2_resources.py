"""Read the resources lane (B8): what an editor costs to open and to edit a document.

One launch is one ``resource.json``. A cell is one editor on one document
size. Launches are grouped by the seed of their job, across every run
directory given, so a seed spread over several Spaces is still one group.

A cell publishes when two seeds each kept at least ten launches of the same
built editor. A figure is stored only for a measure whose two medians agree;
a cell that does not publish stores no figure at all.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from perf.analysis import e2_cells as cells

MIN_KEPT = 10
REL_TOL = 0.10
# The process CPU counters tick in 10 ms steps.
CPU_ABS_TOL_MS = 20

WORKLOADS = (
    ('prose-500w', '500 words'),
    ('prose-5kw', '5,000 words'),
    ('prose-50kw', '50,000 words'),
    ('prose-250kw', '250,000 words'),
    ('complex-corpus', 'Complex document'),
)

# (key, column heading, unit, fields summed)
MEASURES = (
    ('open_cpu_ms', 'CPU to open', 'ms', ('load_cpu_ms', 'open_settle_cpu_ms')),
    ('edit_cpu_ms', 'CPU of the edit', 'ms', ('edit_cpu_ms',)),
    ('edit_settle_cpu_ms', 'CPU settling after the edit', 'ms', ('quiescence_cpu_ms',)),
    ('peak_ram_bytes', 'Peak memory', 'bytes', ('peak_ram_bytes',)),
    ('peak_js_heap_used_bytes', 'Peak JS heap', 'bytes', ('peak_js_heap_used_bytes',)),
    ('load_network_encoded_bytes', 'Network to open', 'bytes', ('load_network_encoded_bytes',)),
)
TABLE_MEASURES = ('open_cpu_ms', 'edit_cpu_ms', 'edit_settle_cpu_ms', 'peak_ram_bytes')


def _number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def launch_refusal(record: dict) -> str | None:
    """Why a launch is not kept, or None."""
    if record.get('outcome') != 'measured':
        return str(record.get('refusal_code') or record.get('failure_reason') or record.get('outcome') or 'not_measured')[:60]
    if (record.get('edit_oracle') or {}).get('status') != 'verified':
        return str((record.get('edit_oracle') or {}).get('status') or 'edit_unverified')
    if record.get('edit_cpu_publication') != 'published':
        return 'edit_cpu_withheld'
    if record.get('execution_profile') != 'dedicated_publish' or record.get('host_class') not in ('dedicated', 'shared_guarded'):
        return 'not_a_publication_launch'
    for _key, _label, _unit, fields in MEASURES:
        if not all(_number(record.get(field)) and record[field] >= 0 for field in fields):
            return 'counter_not_recorded'
    return None


def _records(job: Path):
    for path in sorted((job / 'cells').glob('*/resource.json')):
        try:
            record = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            record = {'outcome': 'failed', 'failure_reason': 'unreadable_record'}
        if isinstance(record, dict):
            yield path.parent.name, record


def _resource_jobs(roots):
    for root in roots:
        for job in cells._job_roots(Path(root)):
            summary = cells._load_summary(job) or {}
            if summary.get('runner') == 'benchmark_resources' or job.parent.name == 'benchmark_resources':
                yield job, summary


def read_cell(roots, editor: str, workload: str) -> dict:
    groups: dict = {}
    for job, summary in _resource_jobs(roots):
        mine = [(launch, record) for launch, record in _records(job)
                if launch.endswith('-' + editor) and record.get('workload_id') == workload
                and record.get('editor_id', editor) == editor]
        scheduled = cells._scheduled_for_editor(summary, editor, 0)
        if not mine and not scheduled:
            continue
        if not mine:
            # A job that wrote no record still names its document in its options.
            if workload not in json.dumps(summary.get('argv') or summary.get('options') or ''):
                continue
        group = groups.setdefault(summary.get('seed'), {
            'scheduled': 0, 'kept': [], 'refusals': Counter(), 'errors': Counter(), 'never_idle': 0,
            'blocked': None, 'pins': set(), 'launches': {},
        })
        # A launch name is one launch of the seed's schedule. The same run
        # pulled twice counts once; a second run of the same launches is a
        # re-run, and which one to keep is not the reader's choice.
        run_id = summary.get('run_id') or str(job)
        owners = {group['launches'].get(launch) for launch, _record in mine} - {None}
        if owners == {run_id}:
            continue
        if owners and not group['blocked']:
            group['blocked'] = 'launches measured twice: a block was re-run'
        for launch, _record in mine:
            group['launches'].setdefault(launch, run_id)
        group['scheduled'] += scheduled or len(mine)
        blocked, why = cells._run_blocks_publication(summary)
        if blocked and not group['blocked']:
            group['blocked'] = str(why)
        tree = ((summary.get('hosts') or {}).get(editor) or {}).get('tree_sha256')
        group['pins'].add(tree if isinstance(tree, str) and tree else None)
        for _launch, record in mine:
            reason = launch_refusal(record)
            if reason:
                group['refusals'][reason] += 1
                if record.get('editor_error'):
                    group['errors'][str(record['editor_error'])[:200]] += 1
                continue
            group['kept'].append(record)
            if 'capped' in (record.get('settle') or {}).values():
                group['never_idle'] += 1
    seeds = sorted(groups, key=lambda seed: (seed is None, seed))
    ordered = [groups[seed] for seed in seeds]
    errors = Counter()
    for group in ordered:
        errors.update(group['errors'])
    cell = {
        'published': False, 'reason': None, 'seeds': seeds,
        'scheduled': [group['scheduled'] for group in ordered],
        'kept': [len(group['kept']) for group in ordered],
        'never_idle': [group['never_idle'] for group in ordered],
        'editor_errors': dict(errors), 'measures': {},
    }
    cell['reason'] = _block(seeds, ordered)
    if cell['reason']:
        return cell
    cell['published'] = True
    for key, _label, unit, fields in MEASURES:
        medians = [cells.percentile([sum(record[field] for field in fields) for record in group['kept']], 50)
                   for group in ordered]
        tolerance = CPU_ABS_TOL_MS if unit == 'ms' else 0
        agrees = abs(medians[0] - medians[1]) <= max(tolerance, REL_TOL * max(abs(medians[0]), abs(medians[1])))
        cell['measures'][key] = {'medians': medians if agrees else None, 'reproduced': agrees, 'unit': unit}
    return cell


def _block(seeds, groups) -> str | None:
    if not groups:
        return 'not in these runs'
    if len(groups) != 2 or None in seeds:
        return 'two seeds required'
    for name, group in zip(('first', 'second'), groups):
        if group['blocked']:
            return '%s seed: run blocked (%s)' % (name, group['blocked'])
    for name, group in zip(('first', 'second'), groups):
        if len(group['kept']) < MIN_KEPT:
            reasons = ', '.join('%s %d' % item for item in sorted(group['refusals'].items()))
            return '%s seed: %d of %d launches kept%s' % (
                name, len(group['kept']), group['scheduled'], ' (%s)' % reasons if reasons else '')
    pins = [group['pins'] for group in groups]
    if any(None in pin or len(pin) != 1 for pin in pins):
        return 'the built editor is not recorded'
    if pins[0] != pins[1]:
        return 'the two seeds measured different editor builds'
    return None


def fmt(value, unit: str) -> str:
    if unit == 'ms':
        return '%.2f s' % (value / 1000) if value >= 1000 else '%d ms' % round(value)
    return '%.1f MiB' % (value / 2 ** 20)


def resources_tables(facts: dict, roots, editors, display) -> str:
    """One table per document size; every unpublished cell is named below its table."""
    labels = {key: label for key, label, _unit, _fields in MEASURES}
    blocks = []
    for workload, title in WORKLOADS:
        rows, notes = [], []
        for editor in editors:
            cell = read_cell(roots, editor, workload)
            name = display.get(editor, editor)
            prefix = 'perf.e2.%s.B8.%s' % (editor, workload)
            facts[prefix + '.published'] = cell['published']
            facts[prefix + '.kept'] = cell['kept']
            facts[prefix + '.scheduled'] = cell['scheduled']
            if not cell['published']:
                if cell['reason'] == 'not in these runs':
                    continue
                errors = '; '.join(sorted(cell['editor_errors']))
                notes.append('- %s: %s%s.' % (name, cell['reason'], '; ' + errors if errors else ''))
                continue
            texts = []
            for key in TABLE_MEASURES:
                measure = cell['measures'][key]
                facts['%s.%s.reproduced' % (prefix, key)] = measure['reproduced']
                if measure['reproduced']:
                    facts['%s.%s.medians' % (prefix, key)] = measure['medians']
                    texts.append(' / '.join(fmt(median, measure['unit']) for median in measure['medians']))
                else:
                    texts.append('not reproduced')
            rows.append('| %s | %s | n = %d, %d |' % (name, ' | '.join(texts), *cell['kept']))
            if any(cell['never_idle']):
                notes.append('- %s never went idle within the settle cap in %d and %d of its kept launches; its '
                             'settle figures cover the capped window.' % (name, *cell['never_idle']))
        if not rows and not notes:
            continue
        head = ['### %s' % title, '']
        if rows:
            head += ['| Editor | ' + ' | '.join(labels[key] for key in TABLE_MEASURES) + ' | Kept launches |',
                     '|---' * (len(TABLE_MEASURES) + 2) + '|', *rows, '']
        if notes:
            head += ['Not published or flagged:', '', *notes, '']
        blocks.append('\n'.join(head).rstrip())
    return '\n\n'.join(blocks) if blocks else 'not in these runs.'
