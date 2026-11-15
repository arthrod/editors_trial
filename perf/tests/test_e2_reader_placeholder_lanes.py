"""A lane that only writes placeholder rows for a criterion never owns it (#179).

``benchmark_warm_cold`` writes ``not_run`` rows for C07-C10, C22 and C23 in
every job ("adapter-not-implemented: criterion C10 not driven on warm_cold host
yet"). In a block campaign the seed's jobs span many run folders, and a run
folder can hold a warm/cold job and no scroll job. If the placeholder jobs are
pooled with the scroll lane's jobs, the seed holds block 1 and block 2 twice and
the cell is refused as 'duplicate block index in one seed'.
"""

import json
from pathlib import Path

from perf.analysis import e2_cells as cells

PLACEHOLDER = 'adapter-not-implemented: criterion C10 not driven on warm_cold host yet'


def _summary(job, seed, block, editor):
    (job / 'summary.json').write_text(
        json.dumps(
            dict(
                run_id=job.name,
                seed=seed,
                execution_profile='dedicated_publish',
                block=dict(index=block, of=2, repetitions=5),
                order=[[i, editor] for i in range((block - 1) * 5, block * 5)],
            )
        )
    )


def write_scroll_job(root, job_id, seed, block, editor='plate'):
    job = root / 'adversarial_c10_scroll' / job_id
    for rep in range((block - 1) * 5, block * 5):
        path = job / 'cells' / f'{rep:04d}-{editor}' / 'attempts' / 'c10.json'
        path.parent.mkdir(parents=True)
        path.write_text(
            json.dumps(
                dict(
                    editor_id=editor,
                    criterion_id='C10',
                    outcome='measured',
                    publishable=True,
                    refusal_code=None,
                    layer='browser_visible',
                    samples_ms=[20],
                    sub_frame_samples=[False],
                    diagnostic={'frame_interval_ms': 16.7},
                    host_provenance={'host_build': 'production', 'publishable': True, 'tree_sha256': 'tree-a'},
                )
            )
        )
    _summary(job, seed, block, editor)
    return job


def write_warm_cold_job(root, job_id, seed, block, editor='plate'):
    job = root / 'benchmark_warm_cold' / job_id
    for rep in range((block - 1) * 5, block * 5):
        path = job / 'cells' / f'{rep:04d}-{editor}' / 'attempts' / 'c10.json'
        path.parent.mkdir(parents=True)
        path.write_text(
            json.dumps(
                dict(
                    editor_id=editor,
                    criterion_id='C10',
                    outcome='not_run',
                    refusal_code='not_run',
                    failure_reason=PLACEHOLDER,
                    layer='browser_visible',
                )
            )
        )
    _summary(job, seed, block, editor)
    return job


def campaign(fs_root=Path('/runs')):
    """Four run folders per seed: scroll and warm/cold blocks in separate folders."""
    roots = []
    for seed in (1, 2):
        base = seed * 100
        for offset, (writer, block) in enumerate(
            ((write_scroll_job, 1), (write_scroll_job, 2), (write_warm_cold_job, 1), (write_warm_cold_job, 2))
        ):
            root = fs_root / f'space-{base + offset}'
            writer(root, f'run-{base + offset:03d}', seed, block)
            roots.append(root)
    return roots


def test_placeholder_lane_jobs_are_not_pooled_with_the_measuring_lane(fs):
    roots = campaign()
    groups = cells._criterion_job_pairs(roots, 'plate', 'C10')
    for seed in (1, 2):
        lanes = {job.parent.name for _root, job in groups[seed]}
        assert lanes == {'adversarial_c10_scroll'}, (seed, lanes)


def test_block_campaign_cell_is_not_refused_as_duplicate_blocks(fs):
    roots = campaign()
    groups = cells._criterion_job_pairs(roots, 'plate', 'C10')
    for seed in (1, 2):
        cell = cells._build_cell_from_jobs(groups[seed], 'plate', 'C10')
        assert cell['block_reason'] != 'duplicate block index in one seed'
        assert cell['blocked'] is False, cell['block_reason']
        assert cell['stats'] is not None and cell['stats']['n'] == 10


def test_only_placeholders_everywhere_keeps_the_refusal_visible(fs):
    root = Path('/runs/space-1')
    write_warm_cold_job(root, 'run-001', 1, 1)
    write_warm_cold_job(root, 'run-002', 1, 2)
    groups = cells._criterion_job_pairs([root], 'plate', 'C10')
    assert {job.parent.name for _root, job in groups[1]} == {'benchmark_warm_cold'}
    cell = cells._build_cell_from_jobs(groups[1], 'plate', 'C10')
    assert cell['stats'] is None
    assert cell['refusals'].get('not_run') == 10


def test_a_lane_with_real_refusals_still_owns_the_criterion(fs):
    """Only adapter placeholders lose ownership; a real refusal is evidence."""
    root = Path('/runs/space-1')
    job = write_warm_cold_job(root, 'run-001', 1, 1)
    for path in job.glob('cells/*/attempts/c10.json'):
        row = json.loads(path.read_text())
        row.update(outcome='failed', refusal_code='editor_timeout', failure_reason='editor_timeout')
        path.write_text(json.dumps(row))
    write_scroll_job(Path('/runs/space-2'), 'run-002', 1, 1)
    groups = cells._criterion_job_pairs([root, Path('/runs/space-2')], 'plate', 'C10')
    assert {job.parent.name for _root, job in groups[1]} == {'benchmark_warm_cold', 'adversarial_c10_scroll'}


def test_only_the_criterion_stand_in_is_a_placeholder():
    """'no warm edit surface without verified selector' is a genuine refusal, not a stand-in (GLM M1)."""
    stand_in = {'outcome': 'not_run', 'failure_reason': PLACEHOLDER}
    genuine = {'outcome': 'not_run',
               'failure_reason': 'adapter-not-implemented: no warm edit surface without verified selector'}
    assert cells._is_placeholder_row(stand_in)
    assert not cells._is_placeholder_row(genuine)
    assert not cells._is_placeholder_row({**stand_in, 'outcome': 'failed'})
