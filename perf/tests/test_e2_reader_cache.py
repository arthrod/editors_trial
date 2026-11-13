"""Reader cache for #176: the E2 reader parses each pulled file at most once.

``facts_from_roots`` re-read the same attempt and summary JSON once per
cell x job x measure (issue #176). The memoised reader must re-parse a file
whose stat key changed, must keep every error path, and no consumer may
mutate a cached row — a mutation would corrupt every later read of the file.

Every test here also runs at the pre-cache commit: none touches a private
name directly — the helpers below fall back to the plain behaviour — so each
fails there on behaviour (a parse count, a stale or fresh value, or tuple
identity), never on ``AttributeError`` for a missing name.
"""

import inspect
import json
import os
import shutil
from collections import Counter
from contextlib import contextmanager, nullcontext
from pathlib import Path
from unittest.mock import patch

import pytest

from build import perf_e2_tables as report
from perf.analysis import e2_cells as cells
from perf.tests.test_e2_report_fix3 import _lay_blocks, trial


def _read_json(path, **spec):
    """The module's memoised reader, or a plain parse where it does not exist."""
    reader = getattr(cells, '_read_json', None)
    if reader is None:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    return reader(path, **spec)


def _read_rows(directory, **kwargs):
    """``cells._read_rows`` called with only the keyword arguments it accepts."""
    reader = cells._read_rows
    supported = {
        name: value
        for name, value in kwargs.items()
        if name in inspect.signature(reader).parameters
    }
    yield from reader(directory, **supported)


def _listing(directory, pattern):
    """``cells._listing``, or a fresh glob at a commit that has no listing cache."""
    listing = getattr(cells, '_listing', None)
    if listing is None:
        return tuple(Path(directory).glob(pattern))
    return listing(directory, pattern)


def _listing_scope():
    """``cells._listing_scope``, or a no-op context at a commit without one."""
    scope = getattr(cells, '_listing_scope', None)
    if scope is None:
        return nullcontext()
    return scope()


@contextmanager
def _parse_log():
    """The raw texts ``json.loads`` was asked to parse inside the block."""
    log = []
    real_loads = json.loads

    def counting(text, *args, **kwargs):
        log.append(text)
        return real_loads(text, *args, **kwargs)

    with patch.object(json, 'loads', counting):
        yield log


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


def _lay_campaign(root: Path, seed: int):
    """The ``runs`` fixture on a real filesystem: directory mtimes must move."""
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


def _fresh_cache():
    """The module-private parse cache, emptied; None when no cache exists."""
    cache = getattr(cells, '_JSON_CACHE', None)
    if cache is not None:
        cache.clear()
    return cache


def _apply_spec(reparsed, spec):
    """The cached shape of a parsed dict under a keep/drop spec."""
    if spec is None or not isinstance(reparsed, dict):
        return reparsed
    mode, keys = spec
    if mode == 'keep':
        return {key: value for key, value in reparsed.items() if key in keys}
    return {key: value for key, value in reparsed.items() if key not in keys}


def test_read_json_reparses_a_rewritten_file(tmp_path):
    """A changed file is parsed again: the key carries mtime_ns and size."""
    path = tmp_path / 'trial.json'
    path.write_text(json.dumps({'outcome': 'measured', 'n': 1}))
    first = _read_json(path)
    assert first == {'outcome': 'measured', 'n': 1}
    assert _read_json(path) is first

    rewritten = {'outcome': 'refused', 'n': 2, 'detail': 'rewritten with a longer body'}
    path.write_text(json.dumps(rewritten))
    stamp = os.stat(path)
    os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns + 5_000_000_000))
    second = _read_json(path)
    assert second == rewritten
    assert second is not first


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
    """The shared rows the consumers saw are untouched: every memoised object
    still equals what its file parses to under its keep/drop spec."""
    cache = _fresh_cache()
    reads = Counter()
    cls = type(runs[0] / 'summary.json')
    original = cls.read_text

    def counting(self, *args, **kwargs):
        if self.suffix == '.json' and str(self).startswith('/runs/'):
            reads[str(self)] += 1
        return original(self, *args, **kwargs)

    with patch.object(cls, 'read_text', counting):
        report.facts_from_roots(list(runs))
    repeated = sorted((path, n) for path, n in reads.items() if n > 1)
    assert not repeated, 'files read more than once: %s' % (repeated[:5],)
    assert cache, 'the reader cache must hold the campaign files'
    for key, cached in cache.items():
        path_str, spec = key[0], key[-1]
        try:
            reparsed = json.loads(Path(path_str).read_text(encoding='utf-8'))
        except json.JSONDecodeError:
            assert isinstance(cached, json.JSONDecodeError), path_str
            continue
        assert _apply_spec(reparsed, spec) == cached, (
            '%s changed after parsing; a consumer mutated it' % path_str
        )


def test_dropped_summary_key_is_served_full_to_who_needs_it(tmp_path):
    """The summary's bulky ``samples`` key stays out of the row a consumer
    gets from ``_load_summary`` — ``row.get`` on it is None — and the only
    way to it is a plain full-spec ``_read_json`` of the same file."""
    path = tmp_path / 'summary.json'
    path.write_text(json.dumps({'run_id': 'r1', 'samples': [{'n': 1}]}))
    row = cells._load_summary(tmp_path)
    assert row.get('samples') is None
    assert row['run_id'] == 'r1'
    assert _read_json(path)['samples'] == [{'n': 1}]


def test_attempt_rows_of_never_parses_profile_subtrees(tmp_path):
    """``_attempt_rows_of`` discards ``profile``/``profile-invoke`` subtrees by
    path alone — the parser never sees them. This locks that one producer
    only: ``_run_shakedown_job`` still parses such rows, exactly as it did
    before the reader cache (shakedown semantics unchanged)."""
    job = tmp_path / 'job'
    attempts = job / 'cells' / '0000-plate' / 'attempts'
    (attempts / 'profile').mkdir(parents=True)
    (attempts / 'profile-invoke').mkdir(parents=True)
    (attempts / 'profile' / 'deep.json').write_text('{not json')
    (attempts / 'profile-invoke' / 'trace.json').write_text('{not json')
    with _parse_log() as parsed:
        rows = list(cells._attempt_rows_of(tmp_path, [job]))
    assert rows == []
    assert parsed == [], 'diagnostic subtrees were parsed: %r' % (parsed,)


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
    keep = getattr(
        cells,
        '_SAMPLE_ROW_KEEP',
        frozenset(
            {
                'editor_id', 'accounting_scope', 'outcome', 'refusal_code',
                'publication_block_reason', 'failure_reason',
            }
        ),
    )
    kept = dict(
        _read_rows(
            samples_dir,
            keep=keep,
            skip=lambda candidate: candidate.parent != samples_dir,
        )
    )
    seen = kept[path]
    assert 'non_failure_outcomes' not in seen
    assert seen['outcome'] == 'failed'
    assert _read_json(path)['non_failure_outcomes'] == row['non_failure_outcomes']


def test_listing_cache_sees_a_file_added_between_calls(tmp_path):
    """A memoised listing re-checks mtimes: a file added after the first
    call is visible to the next (the pull is append-only, never stale).
    Outside a scope, listings always glob fresh."""
    attempts = tmp_path / 'cells' / '0000-plate' / 'attempts'
    attempts.mkdir(parents=True)
    (attempts / 'C07.json').write_text('{}')
    with _listing_scope():
        first = _listing(attempts, '*.json')
        assert _listing(attempts, '*.json') is first
        (attempts / 'C11.json').write_text('{}')
        second = _listing(attempts, '*.json')
    assert [path.name for path in first] == ['C07.json']
    assert sorted(path.name for path in second) == ['C07.json', 'C11.json']
    (attempts / 'C13.json').write_text('{}')
    assert len(_listing(attempts, '*.json')) == 3


@pytest.mark.parametrize('pattern', ['*.json', '**/*.json', '*/attempts'])
def test_listing_stamp_predates_the_glob(tmp_path, pattern):
    """A create inside the glob lands after the stored stamp: the next
    lookup in the same scope must re-glob and return it. A stamp taken
    after the glob instead freezes this gap's pre-create view."""
    cells_dir = tmp_path / 'cells'
    attempts = cells_dir / '0000-plate' / 'attempts'
    attempts.mkdir(parents=True)
    (attempts / 'C07.json').write_text('{}')
    target = cells_dir if pattern == '*/attempts' else attempts
    state = {'armed': True}
    real_glob = Path.glob

    def creating_glob(self, *args, **kwargs):
        result = tuple(real_glob(self, *args, **kwargs))
        if state['armed'] and self == target and args[:1] == (pattern,):
            state['armed'] = False
            if pattern == '*/attempts':
                (self / '0001-plate' / 'attempts').mkdir(parents=True)
            else:
                (self / 'EXTRA-C07.json').write_text('{}')
        return iter(result)

    with patch.object(Path, 'glob', creating_glob), _listing_scope():
        _listing(target, pattern)  # the glob runs; the create fires inside it
        second = _listing(target, pattern)  # must re-glob: the stamp moved
        third = _listing(target, pattern)  # and is itself memoised again
    if pattern == '*/attempts':
        names = {path.parent.name for path in second}
        assert names == {'0000-plate', '0001-plate'}
    else:
        assert 'EXTRA-C07.json' in {path.name for path in second}
    assert third is second


def test_create_inside_the_glob_reaches_facts(tmp_path):
    """End to end through ``facts_from_roots``: a trial file created inside
    the ``**/*.json`` glob changes ``conflicting_trials`` for the memoised
    reader exactly as it does for a fresh-glob reader."""
    primary = tmp_path / 'primary'
    repro = tmp_path / 'repro'
    _lay_campaign(primary, 0)
    _lay_campaign(repro, 1)
    state = {'armed': True}
    real_glob, real_rglob = Path.glob, Path.rglob
    asks = Counter()

    def wrapping(method, name):
        def wrapped(self, *args, **kwargs):
            result = tuple(method(self, *args, **kwargs))
            pattern = args[0] if args else ''
            asks[(name, self.name, pattern)] += 1
            if (
                state['armed']
                and self.name == 'attempts'
                and result
                and pattern == ('**/*.json' if name == 'glob' else '*.json')
            ):
                state['armed'] = False
                (self / 'EXTRA-C07.json').write_text(result[0].read_text())
            return iter(result)
        return wrapped

    def recursive_attempt_asks():
        return asks[('glob', 'attempts', '**/*.json')] + asks[('rglob', 'attempts', '*.json')]

    def fresh_listing(directory, pattern):
        return tuple(Path(directory).glob(pattern))

    def run(uncached):
        state['armed'] = True
        _fresh_cache()
        asks.clear()
        scope = nullcontext()
        if uncached:
            scope = patch.object(cells, '_listing', fresh_listing, create=True)
        with scope:
            return report.facts_from_roots([primary, repro]), recursive_attempt_asks()

    with patch.object(Path, 'glob', wrapping(real_glob, 'glob')), \
            patch.object(Path, 'rglob', wrapping(real_rglob, 'rglob')):
        cached_facts, cached_asks = run(uncached=False)
        created = [path for path in primary.rglob('EXTRA-C07.json')]
        created += [path for path in repro.rglob('EXTRA-C07.json')]
        assert len(created) == 1, 'the injection did not fire'
        created[0].unlink()
        fresh_facts, fresh_asks = run(uncached=True)
    assert 'conflicting_trials' in json.dumps(fresh_facts), (
        'the injected file never reached the table'
    )
    assert cached_facts == fresh_facts
    assert cached_asks < fresh_asks, 'the memoised reader must still glob less'


def test_restored_directory_mtime_does_not_hide_an_added_file(tmp_path):
    """``os.utime`` puts a directory's mtime back but cannot put its ctime
    back: a file added under a restored mtime must still reach the next
    lookup in the same scope."""
    attempts = tmp_path / 'attempts'
    attempts.mkdir(parents=True)
    (attempts / 'C07.json').write_text('{}')
    stamp = attempts.stat()
    with _listing_scope():
        first = _listing(attempts, '*.json')
        (attempts / 'EXTRA-C07.json').write_text('{}')
        os.utime(attempts, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
        second = _listing(attempts, '*.json')
        third = _listing(attempts, '*.json')
    assert attempts.stat().st_mtime_ns == stamp.st_mtime_ns, (
        'the mtime was not put back; the injection did not fire'
    )
    assert [path.name for path in first] == ['C07.json']
    assert sorted(path.name for path in second) == ['C07.json', 'EXTRA-C07.json']
    assert third is second


def test_swapped_directory_with_copied_mtime_is_relisted(tmp_path):
    """A watched directory replaced by rename — the replacement carrying
    the old directory's mtime via ``shutil.copystat`` — is a different
    inode: the next lookup must glob it, not serve the old listing."""
    cell = tmp_path / 'cell'
    attempts = cell / 'attempts'
    attempts.mkdir(parents=True)
    (attempts / 'C07.json').write_text('{}')
    with _listing_scope():
        first = _listing(attempts, '*.json')
        replacement = cell / 'attempts-new'
        replacement.mkdir()
        (replacement / 'C07.json').write_text('{}')
        (replacement / 'EXTRA-C07.json').write_text('{}')
        shutil.copystat(attempts, replacement)
        os.rename(attempts, cell / 'attempts-old')
        os.rename(replacement, attempts)
        second = _listing(attempts, '*.json')
        third = _listing(attempts, '*.json')
    retired = cell / 'attempts-old'
    assert attempts.stat().st_mtime_ns == retired.stat().st_mtime_ns, (
        'copystat did not carry the mtime; the injection did not fire'
    )
    assert attempts.stat().st_ino != retired.stat().st_ino
    assert [path.name for path in first] == ['C07.json']
    assert sorted(path.name for path in second) == ['C07.json', 'EXTRA-C07.json']
    assert third is second


def test_restored_attempts_mtime_reaches_facts(tmp_path):
    """End to end through ``facts_from_roots``: a trial file created inside
    the ``**/*.json`` glob under a directory mtime that is then put back
    still changes ``conflicting_trials`` for the memoised reader exactly
    as it does for a fresh-glob reader."""
    primary = tmp_path / 'primary'
    repro = tmp_path / 'repro'
    _lay_campaign(primary, 0)
    _lay_campaign(repro, 1)
    state = {'armed': True}
    real_glob, real_rglob = Path.glob, Path.rglob
    asks = Counter()

    def wrapping(method, name):
        def wrapped(self, *args, **kwargs):
            result = tuple(method(self, *args, **kwargs))
            pattern = args[0] if args else ''
            asks[(name, self.name, pattern)] += 1
            if (
                state['armed']
                and self.name == 'attempts'
                and result
                and pattern == ('**/*.json' if name == 'glob' else '*.json')
            ):
                state['armed'] = False
                held = self.stat()
                (self / 'EXTRA-C07.json').write_text(result[0].read_text())
                os.utime(self, ns=(held.st_atime_ns, held.st_mtime_ns))
                state['restored'] = self.stat().st_mtime_ns == held.st_mtime_ns
            return iter(result)
        return wrapped

    def recursive_attempt_asks():
        return asks[('glob', 'attempts', '**/*.json')] + asks[('rglob', 'attempts', '*.json')]

    def fresh_listing(directory, pattern):
        return tuple(Path(directory).glob(pattern))

    def run(uncached):
        state['armed'] = True
        _fresh_cache()
        asks.clear()
        scope = nullcontext()
        if uncached:
            scope = patch.object(cells, '_listing', fresh_listing, create=True)
        with scope:
            return report.facts_from_roots([primary, repro]), recursive_attempt_asks()

    with patch.object(Path, 'glob', wrapping(real_glob, 'glob')), \
            patch.object(Path, 'rglob', wrapping(real_rglob, 'rglob')):
        cached_facts, cached_asks = run(uncached=False)
        created = [path for path in primary.rglob('EXTRA-C07.json')]
        created += [path for path in repro.rglob('EXTRA-C07.json')]
        assert len(created) == 1, 'the injection did not fire'
        assert state.get('restored'), 'the directory mtime was not put back'
        created[0].unlink()
        fresh_facts, fresh_asks = run(uncached=True)
    assert 'conflicting_trials' in json.dumps(fresh_facts), (
        'the injected file never reached the table'
    )
    assert cached_facts == fresh_facts
    assert cached_asks < fresh_asks, 'the memoised reader must still glob less'


@pytest.mark.parametrize('first_spec', ['full', 'slim'])
def test_same_size_same_mtime_rewrite_is_reparsed(tmp_path, first_spec):
    """A rewrite that keeps size and restores ``st_mtime_ns`` still moves
    ctime and the inode's clock: both specs of the same file must agree on
    the new document, whichever was cached first."""
    path = tmp_path / 'row.json'
    text1 = json.dumps({'run_id': 'r1', 'samples': [1], 'n': 1})
    text2 = json.dumps({'run_id': 'r9', 'samples': [2], 'n': 2})
    assert len(text1) == len(text2)
    path.write_text(text1)
    before = path.stat()
    if first_spec == 'slim':
        assert _read_json(path, drop={'samples'}) == {'run_id': 'r1', 'n': 1}
    else:
        assert _read_json(path)['n'] == 1
    path.write_text(text2)
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    full = _read_json(path)
    slim = _read_json(path, drop={'samples'})
    assert full == {'run_id': 'r9', 'samples': [2], 'n': 2}
    assert slim == {'run_id': 'r9', 'n': 2}


def test_rewrite_between_stat_and_read_is_not_cached(tmp_path):
    """A body swapped between the pre-read stat and the read is returned
    fresh but never stored: the post-read stat disagrees."""
    path = tmp_path / 'race.json'
    text1 = json.dumps({'n': 1})
    text2 = json.dumps({'n': 2})
    path.write_text(text1)
    original = path.stat()
    real_stat = Path.stat
    state = {}

    def racing(self, *args, **kwargs):
        st = real_stat(self, *args, **kwargs)
        if self == path and 'swapped' not in state:
            state['swapped'] = True
            path.write_text(text2)
            os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns))
        return st

    with patch.object(Path, 'stat', racing), _parse_log() as parses:
        assert _read_json(path) == {'n': 2}
        assert _read_json(path) == {'n': 2}
        path.write_text(text1)
        os.utime(path, ns=(original.st_atime_ns, original.st_mtime_ns))
        assert _read_json(path) == {'n': 1}
        assert _read_json(path) == {'n': 1}
    assert len(parses) == 3, 'the raced value must not be served from cache'


def test_symlink_retarget_is_reparsed(tmp_path):
    """``link.json`` repointed at a different file with the same mtime and
    size is a new entry: the inode in the stat key does not match."""
    target_a = tmp_path / 'a.json'
    target_b = tmp_path / 'b.json'
    target_a.write_text(json.dumps({'n': 1}))
    target_b.write_text(json.dumps({'n': 2}))
    stamp = target_a.stat()
    os.utime(target_b, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    link = tmp_path / 'link.json'
    os.symlink(target_a, link)
    with _parse_log() as parses:
        assert _read_json(link) == {'n': 1}
        link.unlink()
        os.symlink(target_b, link)
        assert _read_json(link) == {'n': 2}
        assert _read_json(link) == {'n': 2}
    assert len(parses) == 2


def test_relative_spelling_after_chdir_is_reparsed(tmp_path, monkeypatch):
    """The same relative name after ``chdir`` is a different file, keyed by
    where it resolves now — not by the spelling first seen."""
    one = tmp_path / 'one'
    two = tmp_path / 'two'
    one.mkdir()
    two.mkdir()
    (one / 'row.json').write_text(json.dumps({'n': 1}))
    (two / 'row.json').write_text(json.dumps({'n': 2}))
    stamp = (one / 'row.json').stat()
    os.utime(two / 'row.json', ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    monkeypatch.chdir(one)
    with _parse_log() as parses:
        assert _read_json(Path('row.json')) == {'n': 1}
        monkeypatch.chdir(two)
        assert _read_json(Path('row.json')) == {'n': 2}
        assert _read_json(Path('row.json')) == {'n': 2}
    assert len(parses) == 2
