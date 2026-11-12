"""The non-typing publication path requires the decided schedule.

Arthur's plan is 10 launches per seed, from 2 blocks of 5. A whole job of
30 or 12, or a short job pooled beside a full one, is withheld. p90 is
printed only at exactly 10 kept. These are the reviewer's plan_probe cases.
"""
import json

from build import perf_e2_tables as report

EDITOR = 'plate'
CRIT = 'B1'
TREE = 'tree-pc'
INTERVAL = 16.7


def _trial(sample_ms):
    return {
        'criterion_id': CRIT,
        'editor_id': EDITOR,
        'outcome': 'measured',
        'refusal_code': None,
        'publishable': True,
        'samples_ms': [sample_ms],
        'sub_frame_samples': [sample_ms < INTERVAL],
        'layer': 'browser_visible',
        'diagnostic': {'frame_interval_ms': INTERVAL},
        'host_provenance': {'tree_sha256': TREE},
        'environment': {'editor_version': '1.0'},
    }


def _write_job(root, name, reps, seed, *, block=None, sample_ms=20.0):
    job = root / 'benchmark_warm_cold' / name
    order = [[rep, EDITOR] for rep in range(reps)]
    summary = {
        'seed': seed,
        'run_id': name,
        'order': order,
        'publishable': False,
        'hosts': {EDITOR: {'tree_sha256': TREE}},
    }
    if block:
        summary['block'] = {'index': block[0], 'of': block[1], 'repetitions': reps}
    job.mkdir(parents=True)
    (job / 'summary.json').write_text(json.dumps(summary))
    for rep in range(reps):
        cell = job / 'cells' / ('%04d-%s' % (rep, EDITOR)) / 'attempts'
        cell.mkdir(parents=True)
        (cell / 'warm_cold.json').write_text(json.dumps(_trial(sample_ms)))
    return job


def _text(root):
    return report._cell_text({}, [root], EDITOR, CRIT)


def test_two_blocks_of_five_publish_p90_at_exactly_ten(tmp_path):
    root = tmp_path / 'blocks_2x5'
    _write_job(root, 'jobA1', 5, 1, block=(1, 2))
    _write_job(root, 'jobA2', 5, 1, block=(2, 2))
    _write_job(root, 'jobB1', 5, 2, block=(1, 2))
    _write_job(root, 'jobB2', 5, 2, block=(2, 2))
    text = _text(root)
    assert 'wrong schedule' not in text
    assert 'p90 20.0 ms' in text
    assert 'n = 10 of 10' in text


def test_whole_job_of_thirty_is_withheld(tmp_path):
    root = tmp_path / 'whole_30'
    _write_job(root, 'jobA', 30, 1)
    _write_job(root, 'jobB', 30, 2)
    text = _text(root)
    assert 'wrong schedule' in text
    assert 'n = 30 of 30' in text
    assert 'this campaign schedules 10 per seed' in text
    assert 'p90' not in text


def test_whole_job_of_twelve_is_withheld(tmp_path):
    root = tmp_path / 'whole_12'
    _write_job(root, 'jobA', 12, 1)
    _write_job(root, 'jobB', 12, 2)
    text = _text(root)
    assert 'wrong schedule' in text
    assert 'n = 12 of 12' in text
    assert 'this campaign schedules 10 per seed' in text
    assert 'p90' not in text


def test_short_neighbor_beside_a_full_job_is_withheld(tmp_path):
    root = tmp_path / 'short_neighbor'
    _write_job(root, 'jobFull', 10, 1, sample_ms=20.0)
    _write_job(root, 'jobShort', 9, 1, sample_ms=80.0)
    _write_job(root, 'jobFullB', 10, 2, sample_ms=20.0)
    _write_job(root, 'jobShortB', 9, 2, sample_ms=80.0)
    text = _text(root)
    assert 'wrong schedule' in text
    assert 'n = 19 of 19' in text
    assert 'this campaign schedules 10 per seed' in text
    assert 'p90' not in text
    assert '80.0' not in text


def test_parent_summary_does_not_hide_nested_block_jobs(tmp_path):
    root = tmp_path / 'with_parent'
    root.mkdir()
    (root / 'summary.json').write_text(json.dumps({
        'seed': 1,
        'run_id': 'parent',
        'order': [[i, EDITOR] for i in range(10)],
        'publishable': False,
    }))
    cell = root / 'cells' / ('0000-%s' % EDITOR) / 'attempts'
    cell.mkdir(parents=True)
    (cell / 'warm_cold.json').write_text(json.dumps(_trial(999.0)))
    _write_job(root, 'b1', 5, 1, block=(1, 2), sample_ms=20.0)
    _write_job(root, 'b2', 5, 1, block=(2, 2), sample_ms=20.0)
    _write_job(root, 'c1', 5, 2, block=(1, 2), sample_ms=20.0)
    _write_job(root, 'c2', 5, 2, block=(2, 2), sample_ms=20.0)
    text = _text(root)
    assert '999.0' not in text
    assert 'p90 20.0 ms' in text
    assert 'n = 10 of 10' in text


def test_whole_job_of_ten_without_blocks_is_withheld(tmp_path):
    root = tmp_path / 'whole_10'
    _write_job(root, 'jobA', 10, 1)
    _write_job(root, 'jobB', 10, 2)
    text = _text(root)
    assert 'wrong schedule' in text
    assert 'n = 10 of 10' in text
    assert 'this campaign schedules 10 per seed' in text
    assert 'p90' not in text


def test_five_blocks_of_two_are_withheld(tmp_path):
    root = tmp_path / 'five_by_two'
    for seed, prefix in ((1, 'A'), (2, 'B')):
        for index in range(1, 6):
            _write_job(root, 'job%s%d' % (prefix, index), 2, seed, block=(index, 5))
    text = _text(root)
    assert 'wrong schedule' in text
    assert 'n = 10 of 10' in text
    assert 'p90' not in text


def test_one_block_of_ten_is_withheld(tmp_path):
    root = tmp_path / 'one_by_ten'
    _write_job(root, 'jobA', 10, 1, block=(1, 1))
    _write_job(root, 'jobB', 10, 2, block=(1, 1))
    text = _text(root)
    assert 'wrong schedule' in text
    assert 'n = 10 of 10' in text
    assert 'p90' not in text


def test_three_blocks_are_withheld(tmp_path):
    root = tmp_path / 'three_blocks'
    for seed, prefix in ((1, 'A'), (2, 'B')):
        for index in range(1, 4):
            _write_job(root, 'job%s%d' % (prefix, index), 3, seed, block=(index, 3))
    text = _text(root)
    assert 'does not cover 10 repetitions' in text
    assert 'p90' not in text


def test_ten_launches_in_one_block_of_a_pair_are_withheld(tmp_path):
    root = tmp_path / 'ten_in_one_block'
    for seed, name in ((1, 'jobA'), (2, 'jobB')):
        job = _write_job(root, name, 10, seed, block=(1, 2))
        summary = json.loads((job / 'summary.json').read_text())
        summary['block']['repetitions'] = 5
        (job / 'summary.json').write_text(json.dumps(summary))
    text = _text(root)
    assert 'missing blocks 2' in text
    assert 'p90' not in text


def _refuse_after(job, keep):
    paths = sorted((job / 'cells').glob('*/attempts/*.json'))
    for path in paths[keep:]:
        row = json.loads(path.read_text())
        row['outcome'] = 'refused'
        row['refusal_code'] = 'editor_crashed'
        path.write_text(json.dumps(row))


def test_unpublished_reason_keeps_every_seed_including_wrong_schedule(tmp_path):
    root = tmp_path / 'mixed_reasons'
    _write_job(root, 'jobA', 10, 1)
    first = _write_job(root, 'jobB1', 5, 2, block=(1, 2))
    second = _write_job(root, 'jobB2', 5, 2, block=(2, 2))
    _refuse_after(first, 2)
    _refuse_after(second, 2)
    facts = {}
    report._cell_text(facts, [root], EDITOR, CRIT)
    reason = facts['perf.e2.plate.B1.reason']
    assert 'wrong schedule' in reason
    assert 'not enough samples' in reason
    assert 'first:' in reason and 'second:' in reason
