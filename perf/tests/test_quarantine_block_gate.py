"""Review F (2026-11-14): a quarantined launch must not blank its seed block.

A launch refused for CPU throttling is moved to ``rejected-evidence/``. The
seed-block gate counted only ``cells/*/attempts``, so one quarantined launch
made a five-launch block look short ("block 2 has no launch files") and the
whole seed was blocked: Folio's prose-5kw C11/C12 published nothing although
nine of its ten launches were measured. The launch is refused, not missing.
"""
import json
from pathlib import Path

from perf.analysis import e2_cells as cells

WORKLOAD = 'prose-5kw'


def _job(root, seed, block, quarantined=()):
    job = root / 'benchmark_document' / ('%s-s%d-b%d-%03d' % (root.name, seed, block, block))
    reps = range((block - 1) * 5, block * 5)
    for rep in reps:
        where = 'rejected-evidence' if rep in quarantined else 'cells'
        path = job / where / ('%04d-folio' % rep) / 'attempts' / 'c11-folio.json'
        path.parent.mkdir(parents=True)
        row = dict(
            editor_id='folio', criterion_id='C11', workload_id=WORKLOAD,
            outcome='measured', publishable=True, refusal_code=None, samples_ms=[900.0 + rep],
            sub_frame_samples=[False], diagnostic={'frame_interval_ms': 16.7, 'workload_id': WORKLOAD},
            environment={'workload_id': WORKLOAD},
            host_provenance={'host_build': 'production', 'publishable': True, 'tree_sha256': 'tree-a'},
        )
        if rep in quarantined:
            row['quarantine'] = 'cpu_throttled'
        path.write_text(json.dumps(row))
    (job / 'summary.json').write_text(json.dumps({
        'order': [[rep, 'folio'] for rep in reps], 'publishable': True, 'seed': seed,
        'run_id': job.name, 'execution_profile': 'dedicated_publish', 'host_class': 'dedicated',
        'block': {'index': block, 'of': 2, 'repetitions': 5}}))


def _campaign(quarantined):
    roots = []
    for seed in (1, 2):
        root = Path('/runs/seed%d' % seed)
        for block in (1, 2):
            _job(root, seed, block, quarantined if seed == 1 else ())
        roots.append(root)
    return roots


def _refusals(cell):
    out = {}
    for group in cell['groups']:
        for code, n in (group.get('refusals') or {}).items():
            out[code] = out.get(code, 0) + n
    return out


def test_one_quarantined_launch_is_refused_and_the_seed_still_publishes(fs):
    cell = cells.read_criterion_cell(_campaign({5}), 'folio', 'C11', workload_id=WORKLOAD)
    assert 'no launch files' not in json.dumps(cell, default=str)
    assert _refusals(cell) == {'quarantined': 1}
    assert cell['published'] is True


def test_a_block_with_a_launch_gone_entirely_is_still_short(fs):
    roots = _campaign(())
    job = next((roots[0] / 'benchmark_document').glob('*-b2-*'))
    import shutil
    shutil.rmtree(job / 'cells' / '0005-folio')
    cell = cells.read_criterion_cell(roots, 'folio', 'C11', workload_id=WORKLOAD)
    assert 'no launch files' in json.dumps(cell, default=str)
