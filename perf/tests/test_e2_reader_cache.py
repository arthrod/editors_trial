"""Reader cache for #176: the E2 reader parses each pulled file at most once.

``facts_from_roots`` re-read the same attempt and summary JSON once per
cell x job x measure (issue #176). The memoised reader must re-parse a file
whose stat key changed, must keep every error path, and no consumer may
mutate a cached row — a mutation would corrupt every later read of the file.
"""

import json
import os
from collections import Counter
from pathlib import Path
from unittest.mock import patch

import pytest

from build import perf_e2_tables as report
from perf.analysis import e2_cells as cells
from perf.tests.test_e2_report_fix3 import _lay_blocks, trial


@pytest.fixture
def runs(fs):
    roots = [Path('/runs/primary'), Path('/runs/repro')]
    for seed, root in enumerate(roots):
        root.mkdir(parents=True)
        (root / 'summary.json').write_text(
            json.dumps(
                dict(
                    run_id=root.name,
                    seed=seed,
                    execution_profile='dedicated_publish',
                    host_class='dedicated',
                    publishable=True,
                    host={},
                    rendering={},
                    order=[[i, 'plate'] for i in range(10)],
                )
            )
        )
        _lay_blocks(root)
        for rep in range(10):
            trial(root, rep)
    return roots


def test_read_json_reparses_a_rewritten_file(tmp_path):
    """A changed file is parsed again: the key carries mtime_ns and size."""
    path = tmp_path / 'trial.json'
    path.write_text(json.dumps({'outcome': 'measured', 'n': 1}))
    first = cells._read_json(path)
    assert first == {'outcome': 'measured', 'n': 1}
    assert cells._read_json(path) is first

    rewritten = {'outcome': 'refused', 'n': 2, 'detail': 'rewritten with a longer body'}
    path.write_text(json.dumps(rewritten))
    stamp = os.stat(path)
    os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns + 5_000_000_000))
    second = cells._read_json(path)
    assert second == rewritten
    assert second is not first


def _fresh_cache():
    """The module-private parse cache, emptied; None when no cache exists."""
    cache = getattr(cells, '_JSON_CACHE', None)
    if cache is not None:
        cache.clear()
    return cache


def test_reader_parses_each_file_at_most_once(runs):
    """``json.loads`` reaches a file's text at most once per facts_from_roots."""
    _fresh_cache()
    reads = Counter()
    cls = type(runs[0] / 'summary.json')
    original = cls.read_text

    def counting(self, *args, **kwargs):
        if self.suffix == '.json' and str(self).startswith('/runs/'):
            reads[str(self)] += 1
        return original(self, *args, **kwargs)

    with patch.object(cls, 'read_text', counting):
        report.facts_from_roots(list(runs))
    assert reads, 'the fixture campaign holds JSON files to read'
    repeated = sorted((path, n) for path, n in reads.items() if n > 1)
    assert not repeated, 'files parsed more than once: %s' % (repeated[:5],)


def _apply_spec(reparsed, spec):
    """The cached shape of a parsed dict under a keep/drop spec."""
    if spec is None or not isinstance(reparsed, dict):
        return reparsed
    mode, keys = spec
    if mode == 'keep':
        return {key: value for key, value in reparsed.items() if key in keys}
    return {key: value for key, value in reparsed.items() if key not in keys}


def test_consumers_do_not_mutate_cached_rows(runs):
    """After a full run, every cached object still equals its file on disk."""
    cache = _fresh_cache()
    report.facts_from_roots(list(runs))
    assert cache, 'the reader cache must hold the campaign files'
    for (path_str, _mtime_ns, _size, spec), cached in cache.items():
        try:
            reparsed = json.loads(Path(path_str).read_text(encoding='utf-8'))
        except json.JSONDecodeError:
            assert isinstance(cached, json.JSONDecodeError), path_str
            continue
        assert _apply_spec(reparsed, spec) == cached, (
            '%s changed after parsing; a consumer mutated it' % path_str
        )


def test_dropped_summary_key_is_served_full_to_who_needs_it(tmp_path):
    """The summary's bulky ``samples`` key stays out of the memoised dict;
    a consumer naming it still gets a fresh full parse of the same file."""
    path = tmp_path / 'summary.json'
    path.write_text(json.dumps({'run_id': 'r1', 'samples': [{'n': 1}]}))
    slim = cells._load_summary(tmp_path)
    assert slim == {'run_id': 'r1'}
    full = cells._read_json(path)
    assert full['samples'] == [{'n': 1}]


def test_profile_subtree_rows_are_never_parsed(tmp_path):
    """Attempts under ``profile``/``profile-invoke`` subtrees are discarded
    by path alone, so they must never reach the parser."""
    job = tmp_path / 'job'
    attempts = job / 'cells' / '0000-plate' / 'attempts'
    (attempts / 'profile').mkdir(parents=True)
    (attempts / 'profile-invoke').mkdir(parents=True)
    (attempts / 'profile' / 'deep.json').write_text('{not json')
    (attempts / 'profile-invoke' / 'trace.json').write_text('{not json')
    parsed = []
    original = cells._read_json

    def counting(path, *args, **kwargs):
        parsed.append(path)
        return original(path, *args, **kwargs)

    with patch.object(cells, '_read_json', counting):
        rows = list(cells._attempt_rows_of(tmp_path, [job]))
    assert rows == []
    assert parsed == [], 'diagnostic subtrees were parsed: %s' % parsed


def test_sample_rows_keep_only_what_consumers_read(tmp_path):
    """Rows under a job's ``samples/`` are memoised without the keys no
    consumer reads; the full file remains one ``_read_json`` away."""
    job = tmp_path / 'job'
    samples_dir = job / 'samples'
    samples_dir.mkdir(parents=True)
    row = {
        'editor_id': 'plate',
        'outcome': 'failed',
        'refusal_code': 'crash',
        'failure_reason': 'x',
        'non_failure_outcomes': [{'payload': 'x' * 1000}],
        'cpu_accounting': {'series': list(range(100))},
    }
    path = samples_dir / '0000-plate.json'
    path.write_text(json.dumps(row))
    kept = dict(
        cells._read_rows(
            samples_dir,
            keep=cells._SAMPLE_ROW_KEEP,
            skip=lambda candidate: candidate.parent != samples_dir,
        )
    )
    seen = kept[path]
    assert 'non_failure_outcomes' not in seen
    assert seen['outcome'] == 'failed'
    assert cells._read_json(path)['non_failure_outcomes'] == row['non_failure_outcomes']


def test_listing_cache_sees_a_file_added_between_calls(tmp_path):
    """A memoised listing re-checks mtimes: a file added after the first
    call is visible to the next (the pull is append-only, never stale).
    Outside a scope, listings always glob fresh."""
    attempts = tmp_path / 'cells' / '0000-plate' / 'attempts'
    attempts.mkdir(parents=True)
    (attempts / 'C07.json').write_text('{}')
    with cells._listing_scope():
        first = cells._listing(attempts, '*.json')
        assert cells._listing(attempts, '*.json') is first
        (attempts / 'C11.json').write_text('{}')
        second = cells._listing(attempts, '*.json')
    assert [path.name for path in first] == ['C07.json']
    assert sorted(path.name for path in second) == ['C07.json', 'C11.json']
    (attempts / 'C13.json').write_text('{}')
    assert len(cells._listing(attempts, '*.json')) == 3
