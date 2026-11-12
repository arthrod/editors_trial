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
