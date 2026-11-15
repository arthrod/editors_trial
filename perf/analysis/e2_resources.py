"""Read the resources lane (B8): what an editor costs to open and to edit a document.

One launch is one ``resource.json``. A cell is one editor on one document
size. Launches are grouped by the seed of their job, across every run
directory given, so a seed spread over several Spaces is still one group.

A cell publishes when two seeds each ran the decided schedule (2 blocks
of 5, the same layout as the other non-typing lanes) and kept at least
PUBLICATION_MIN_KEPT launches of the same built editor. A figure is stored
only for a measure whose two medians agree; a cell that does not publish
stores no figure at all.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from perf.analysis import e2_cells as cells
from perf.runner.browser_run import PUBLICATION_MIN_KEPT
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
    ('peak_ram_bytes', 'Highest memory reading', 'bytes', ('peak_ram_bytes',)),
    ('peak_js_heap_used_bytes', 'Peak JS heap', 'bytes', ('peak_js_heap_used_bytes',)),
    ('load_network_encoded_bytes', 'Network to open', 'bytes', ('load_network_encoded_bytes',)),
)
TABLE_MEASURES = ('open_cpu_ms', 'edit_cpu_ms', 'edit_settle_cpu_ms', 'peak_ram_bytes')
# #211: a page that is still working when the settle cap ends has no "to idle"
# figure. Which settle hides which column: the edit runs on a page that was
# already busy, so its CPU is not the edit's either.
NEVER_IDLE_HIDES = {
    'open_cpu_ms': 'after_load', 'edit_cpu_ms': 'after_load', 'edit_settle_cpu_ms': 'after_edit',
}
# (fact key, fields): what is still said of a never-idle cell.
NEVER_IDLE_FIGURES = (
    ('ready_cpu_ms', ('load_cpu_ms',)),
    ('capped_open_settle_cpu_ms', ('open_settle_cpu_ms',)),
)
SETTLE_CAP_S = 30
SETTLE_PHASES = ('after_load', 'after_edit')


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
    settle = record.get('settle')
    if not isinstance(settle, dict) or any(settle.get(phase) not in ('reached', 'capped') for phase in SETTLE_PHASES):
        return 'settle_not_recorded'
    if record.get('execution_profile') != 'dedicated_publish' or record.get('host_class') not in ('dedicated', 'shared_guarded'):
        return 'not_a_publication_launch'
    for _key, _label, _unit, fields in MEASURES:
        if not all(_number(record.get(field)) and record[field] >= 0 for field in fields):
            return 'counter_not_recorded'
    return None


_RESOURCE_KEEP = frozenset(
    {'outcome', 'refusal_code', 'failure_reason', 'edit_oracle', 'edit_cpu_publication',
     'execution_profile', 'host_class', 'workload_id', 'editor_id', 'editor_error',
     'settle', 'host_provenance', 'environment',
     'load_cpu_ms', 'open_settle_cpu_ms', 'edit_cpu_ms', 'quiescence_cpu_ms',
     'peak_ram_bytes', 'peak_js_heap_used_bytes', 'load_network_encoded_bytes',
     'open_settle_renderer_cpu_ms'}
)


def _records(job: Path):
    for path in sorted(cells._listing(job / 'cells', '*/resource.json')):
        try:
            record = cells._read_json(path, keep=_RESOURCE_KEEP)
        except (OSError, ValueError):
            record = {'outcome': 'failed', 'failure_reason': 'unreadable_record'}
        if isinstance(record, dict):
            yield path.parent.name, record


def _resource_job_pairs(roots):
    for root in map(Path, roots):
        for job in cells._job_roots(root):
            summary = cells._load_summary(job) or {}
            if summary.get('runner') == 'benchmark_resources' or job.parent.name == 'benchmark_resources':
                yield root, job, summary


def _job_matches_workload(job: Path, summary: dict, editor: str, workload: str) -> bool:
    mine = [(launch, record) for launch, record in _records(job)
            if launch.endswith('-' + editor) and record.get('workload_id') == workload
            and record.get('editor_id', editor) == editor]
    if mine:
        return True
    scheduled = cells._scheduled_for_editor(summary, editor, 0)
    if scheduled and workload in json.dumps(summary.get('argv') or summary.get('options') or ''):
        return True
    return False


# A resources job records the pair verdict of its own launches. In a block
# campaign one job is one block of one seed, so these three are always true of
# a single job; the reader re-checks each on the pooled seed (decided schedule,
# PUBLICATION_MIN_KEPT kept, two seeds) and they must not block it (#180).
_JOB_PAIR_REASONS = re.compile(r'scheduled_below_\d+|kept_below_\d+|second_seed_required')


def _run_level_block(summary: dict) -> tuple[bool, str | None]:
    reason = str(summary.get('publication_block_reason') or '')
    parts = [part.strip() for part in reason.split(';') if part.strip()]
    if (summary.get('outcome') != 'failed' and parts
            and all(_JOB_PAIR_REASONS.fullmatch(part) for part in parts)):
        summary = {**summary, 'publication_block_reason': None}
    return cells._run_blocks_publication(summary)


_BLOCK_SHORT = re.compile(r'block \d+ has no launch files')


def _refused_launches(job: Path, editor: str, recorded) -> list:
    """Launches the runner refused (a run refusal in samples/) that wrote no resource.json (#180).

    A resources launch refused for CPU throttling leaves its sample row and no
    record; it is an accounted refusal, not a missing file.
    """
    out = []
    for path in sorted(cells._listing(job / 'samples', '*.json')):
        name = path.stem
        if not name.endswith('-' + editor) or name in recorded:
            continue
        try:
            row = cells._read_json(path)
        except (OSError, ValueError):
            continue
        code = cells.refusal_code(row) if isinstance(row, dict) else None
        if code in cells._RUN_REFUSALS:
            out.append((name, code))
    return out


def _blocks_accounted(job_pairs, summaries, editor: str) -> bool:
    """Every block's scheduled launches are either recorded or refused by the runner."""
    for (_root, job), summary in zip(job_pairs, summaries):
        expected = (summary.get('block') or {}).get('repetitions') or 0
        recorded = set(cells._job_measured_launch_names(job, editor))
        refused = {name for name, _code in _refused_launches(job, editor, recorded)}
        if len(recorded | refused) < expected:
            return False
    return True


def _aggregate_seed(entries, editor: str, workload: str) -> dict:
    entries = [(root, job, summary) for root, job, summary in entries
               if _job_matches_workload(job, summary, editor, workload)]
    group = {
        'scheduled': 0, 'kept': [], 'kept_paths': [], 'refusals': Counter(), 'errors': Counter(), 'never_idle': 0,
        'capped': Counter(),
        'blocked': None, 'pins': set(),
    }
    if not entries:
        return group
    job_pairs = [(root, job) for root, job, _summary in entries]
    job_pairs, rerun_blocked, rerun_reason = cells._filter_job_pairs(job_pairs, editor, qualify_keys=False)
    if rerun_blocked:
        group['blocked'] = rerun_reason
        return group
    summaries = [cells._load_summary(job) or {} for _root, job in job_pairs]
    layout_blocked, layout_reason = cells._seed_block_gate(summaries, job_pairs, editor)
    if layout_blocked and _BLOCK_SHORT.fullmatch(str(layout_reason)) and _blocks_accounted(job_pairs, summaries, editor):
        layout_blocked, layout_reason = False, None
    if layout_blocked:
        group['blocked'] = layout_reason
        return group
    job_by_path = {job: summary for _root, job, summary in entries}
    for root, job in job_pairs:
        summary = job_by_path.get(job) or cells._load_summary(job) or {}
        mine = [(launch, record) for launch, record in _records(job)
                if launch.endswith('-' + editor) and record.get('workload_id') == workload
                and record.get('editor_id', editor) == editor]
        scheduled = cells._scheduled_for_editor(summary, editor, 0)
        group['scheduled'] += scheduled or len(mine)
        blocked, why = _run_level_block(summary)
        if blocked and not group['blocked']:
            group['blocked'] = str(why)
        pin = cells.build_identity(summary, editor, [record for _launch, record in mine])
        group['pins'].add(pin)
        for _name, code in _refused_launches(job, editor, {launch for launch, _record in mine}):
            group['refusals'][code] += 1
        for launch, record in mine:
            reason = launch_refusal(record)
            if reason:
                group['refusals'][reason] += 1
                if record.get('editor_error'):
                    group['errors'][str(record['editor_error'])[:200]] += 1
                continue
            group['kept'].append(record)
            group['kept_paths'].append(job / 'cells' / launch / 'resource.json')
            settle = record.get('settle') or {}
            if 'capped' in settle.values():
                group['never_idle'] += 1
            for phase in ('after_load', 'after_edit'):
                if settle.get(phase) == 'capped':
                    group['capped'][phase] += 1
    group['decided_schedule'] = cells._decided_publication_schedule(summaries, group['scheduled'])
    return group


def read_cell(roots, editor: str, workload: str) -> dict:
    by_seed: dict = {}
    for root, job, summary in _resource_job_pairs(roots):
        by_seed.setdefault(summary.get('seed'), []).append((root, job, summary))
    groups: dict = {seed: _aggregate_seed(entries, editor, workload) for seed, entries in by_seed.items()}
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
        'capped': {phase: [group['capped'][phase] for group in ordered] for phase in ('after_load', 'after_edit')},
        'never_idle_phases': [], 'never_idle_figures': {}, 'never_idle_split': {},
        'editor_errors': dict(errors), 'measures': {},
    }
    cell['reason'] = _block(seeds, ordered)
    if cell['reason']:
        return cell
    cell['published'] = True
    # Never idle: the cap ended a settle in a kept launch. One is enough: a
    # median over idle and capped launches would still hold the cap.
    cell['never_idle_phases'] = [
        phase for phase in SETTLE_PHASES if any(group['capped'][phase] for group in ordered)]

    def seed_values(fields):
        return [[sum(record[field] for field in fields) for record in group['kept']] for group in ordered]

    def agree(medians, unit):
        tolerance = CPU_ABS_TOL_MS if unit == 'ms' else 0
        return abs(medians[0] - medians[1]) <= max(tolerance, REL_TOL * max(abs(medians[0]), abs(medians[1])))

    def seed_medians(fields, unit):
        medians = [cells.percentile(values, 50) for values in seed_values(fields)]
        return medians if agree(medians, unit) else None

    def measure(fields, unit):
        # #226: a cell that does not reproduce still says what each seed read
        # and how far the launches ran; only `medians` is a published figure.
        values = seed_values(fields)
        both = [cells.percentile(group, 50) for group in values]
        flat = [value for group in values for value in group]
        ok = agree(both, unit)
        return {'medians': both if ok else None, 'reproduced': ok, 'unit': unit,
                'seed_medians': both, 'launch_range': [min(flat), max(flat)]}

    if 'after_load' in cell['never_idle_phases']:
        for key, fields in NEVER_IDLE_FIGURES:
            cell['never_idle_figures'][key] = seed_medians(fields, 'ms')
        cell['never_idle_split'] = _capped_wait_split(ordered, agree)
    for key, _label, unit, fields in MEASURES:
        if NEVER_IDLE_HIDES.get(key) in cell['never_idle_phases']:
            cell['measures'][key] = {'medians': None, 'reproduced': False, 'unit': unit, 'never_idle': True}
            continue
        cell['measures'][key] = measure(fields, unit)
    return cell


# (fact key, unit): where the processor time of a capped wait went (#226).
CAPPED_SPLIT = (
    ('capped_gpu_cpu_ms', 'ms'), ('capped_renderer_cpu_ms', 'ms'),
    ('capped_longtask_count', 'count'), ('capped_longtask_sum_ms', 'ms'),
)


def _capped_wait_launch(path: Path, record: dict):
    """One launch's capped wait after opening: GPU process, page process, long tasks; None when not recorded.

    The process list is read from the launch file itself, outside the shared
    cache: it is large and only a never-idle cell needs it.
    """
    try:
        phases = json.loads(path.read_text()).get('phases') or {}
    except (OSError, ValueError):
        return None

    def gpu(phase):
        rows = [row for row in (phases.get(phase) or {}).get('processes') or [] if row.get('role') == 'gpu']
        return sum(row['cpu_ms'] for row in rows) if rows and all(_number(row.get('cpu_ms')) for row in rows) else None

    wait = phases.get('after_load') or {}
    out = {
        'capped_gpu_cpu_ms': None if None in (gpu('load'), gpu('after_load')) else gpu('after_load') - gpu('load'),
        'capped_renderer_cpu_ms': record.get('open_settle_renderer_cpu_ms'),
        'capped_longtask_count': wait.get('longtask_count'),
        'capped_longtask_sum_ms': wait.get('longtask_sum_ms'),
    }
    return out if all(_number(value) and value >= 0 for value in out.values()) else None


def _capped_wait_split(ordered, agree) -> dict:
    """Seed medians of the capped wait's split, per key, each with whether the seeds agree.

    {} unless every kept launch of both seeds recorded it.
    """
    per_seed = []
    for group in ordered:
        rows = [_capped_wait_launch(path, record) for path, record in zip(group['kept_paths'], group['kept'])]
        if not rows or None in rows:
            return {}
        per_seed.append(rows)
    split = {}
    for key, unit in CAPPED_SPLIT:
        medians = [cells.percentile([row[key] for row in rows], 50) for rows in per_seed]
        split[key] = {'seed_medians': medians, 'reproduced': agree(medians, unit)}
    return split


def _block(seeds, groups) -> str | None:
    if not groups:
        return 'not in these runs'
    if len(groups) != 2 or None in seeds:
        return 'two seeds required'
    for name, group in zip(('first', 'second'), groups):
        if group['blocked']:
            return '%s seed: run blocked (%s)' % (name, group['blocked'])
    for name, group in zip(('first', 'second'), groups):
        if group.get('decided_schedule') is False:
            return '%s seed: %s' % (
                name, cells._wrong_schedule_text(len(group['kept']), group['scheduled']))
    for name, group in zip(('first', 'second'), groups):
        if len(group['kept']) < PUBLICATION_MIN_KEPT:
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


def _never_idle_note(name: str, cell: dict) -> str:
    phases = cell['never_idle_phases']
    where = []
    if 'after_load' in phases:
        where.append('after opening in %d and %d of its kept launches' % tuple(cell['capped']['after_load']))
    if 'after_edit' in phases:
        where.append('after the edit in %d and %d' % tuple(cell['capped']['after_edit'])
                     + ('' if where else ' of its kept launches'))
    if len(phases) == 2:
        hidden = 'Its three CPU columns are'
    elif 'after_load' in phases:
        hidden = 'Its CPU to open and CPU of the edit columns are'
    else:
        hidden = 'Its settling column is'
    text = ('- %s never went idle: it was still working when the %d-second cap ended, %s. %s not printed: '
            'they would time the cap, not the editor.' % (name, SETTLE_CAP_S, ' and '.join(where), hidden))
    if 'after_load' not in phases:
        return text.replace('they would', 'it would')
    ready, capped = (cell['never_idle_figures'].get(key) for key, _fields in NEVER_IDLE_FIGURES)
    pair = lambda medians: ' / '.join(fmt(median, 'ms') for median in medians)  # noqa: E731 - a one-line formatter local to this note
    if ready:
        text += ' Up to its ready signal it used %s of processor time;' % pair(ready)
    else:
        text += ' Up to its ready signal its processor time did not reproduce between the seeds;'
    if capped and ready:
        text += ' in the capped wait that followed, %s.' % pair(capped)
    elif capped:
        text += ' in the capped wait that followed it used %s.' % pair(capped)
    else:
        text += ' in the capped wait that followed, it did not reproduce either.'
    split = cell.get('never_idle_split') or {}
    if split:
        def said(key, unit='ms'):
            item = split[key]
            both = ' / '.join(fmt(median, unit) if unit == 'ms' else '%d' % round(median) for median in item['seed_medians'])
            return both if item['reproduced'] else both + ' (not reproduced)'
        text += (" Of the capped wait, the browser's GPU process used %s and the page's own process %s; "
                 'the page had %s long tasks, %s in all.' % (
                     said('capped_gpu_cpu_ms'), said('capped_renderer_cpu_ms'),
                     said('capped_longtask_count', 'count'), said('capped_longtask_sum_ms')))
    low, high = cell['measures']['peak_ram_bytes']['launch_range']
    text += ' Its memory readings ran from %s to %s across the kept launches.' % (fmt(low, 'bytes'), fmt(high, 'bytes'))
    return text


def settle_window_note(facts: dict) -> str:
    """What the settling column can and cannot carry (#226)."""
    cells_, higher, lower = (facts.get('perf.e2.B8.settle_' + key, 0) for key in ('cells', 'first_higher', 'first_lower'))
    text = ('The settling window is not a fixed length: it ends at the first half-second poll at which two seconds '
            'have passed without a long task, and the polls themselves cost processor time.')
    if cells_:
        text += (" Across the %d cells with a settling figure, the first seed's median is the higher in %d and the "
                 'lower in %d.' % (cells_, higher, lower))
    return text + (' A difference of a few tens of milliseconds in that column is the window and the 10 ms counter, '
                   'not the editor.')


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
            facts[prefix + '.never_idle'] = bool(cell['never_idle_phases'])
            for key, medians in cell['never_idle_figures'].items():
                if medians:
                    facts['%s.%s.medians' % (prefix, key)] = medians
            for key, item in cell['never_idle_split'].items():
                facts['%s.%s.seed_medians' % (prefix, key)] = item['seed_medians']
                if item['reproduced']:
                    facts['%s.%s.medians' % (prefix, key)] = item['seed_medians']
            for key in TABLE_MEASURES:
                measure = cell['measures'][key]
                if measure.get('never_idle'):
                    texts.append('never idle')
                    continue
                facts['%s.%s.reproduced' % (prefix, key)] = measure['reproduced']
                facts['%s.%s.seed_medians' % (prefix, key)] = measure['seed_medians']
                facts['%s.%s.launch_range' % (prefix, key)] = measure['launch_range']
                if key == 'edit_settle_cpu_ms':
                    first, second = measure['seed_medians']
                    facts['perf.e2.B8.settle_cells'] = facts.get('perf.e2.B8.settle_cells', 0) + 1
                    facts['perf.e2.B8.settle_first_higher'] = facts.get('perf.e2.B8.settle_first_higher', 0) + (first > second)
                    facts['perf.e2.B8.settle_first_lower'] = facts.get('perf.e2.B8.settle_first_lower', 0) + (first < second)
                if measure['reproduced']:
                    facts['%s.%s.medians' % (prefix, key)] = measure['medians']
                    texts.append(' / '.join(fmt(median, measure['unit']) for median in measure['medians']))
                else:
                    unit = measure['unit']
                    texts.append('not reproduced (first %s; second %s; launches %s to %s)' % (
                        *(fmt(median, unit) for median in measure['seed_medians']),
                        *(fmt(value, unit) for value in measure['launch_range'])))
            rows.append('| %s | %s | n = %d, %d |' % (name, ' | '.join(texts), *cell['kept']))
            if cell['never_idle_phases']:
                notes.append(_never_idle_note(name, cell))
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
