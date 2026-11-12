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


def test_consumers_do_not_mutate_cached_rows(runs):
    """After a full run, every cached object still equals its file on disk."""
    cache = _fresh_cache()
    report.facts_from_roots(list(runs))
    assert cache, 'the reader cache must hold the campaign files'
    for (path_str, _mtime_ns, _size), cached in cache.items():
        try:
            reparsed = json.loads(Path(path_str).read_text(encoding='utf-8'))
        except json.JSONDecodeError:
            assert isinstance(cached, json.JSONDecodeError), path_str
            continue
        assert reparsed == cached, '%s changed after parsing; a consumer mutated it' % path_str
