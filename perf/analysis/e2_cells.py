"""Aggregate browser-lane trials into report E2 cells (#136)."""

from __future__ import annotations

from collections import Counter, defaultdict
from contextlib import contextmanager
from pathlib import Path
import hashlib
import json
import os
import sys
import re

from perf.analysis.summarize import percentile
from perf.runner.browser_run import PUBLICATION_MIN_KEPT, PUBLICATION_REPETITIONS

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
from build.perf_e_tables import reproduced  # noqa: E402

_REFUSAL_OUTCOMES = frozenset(
    {"failed", "refused", "not_applicable", "unsupported", "unverified", "not_run"}
)
from perf.runner.refusals import RUN_REFUSALS as _RUN_REFUSALS, refusal_code


def build_identity(summary: dict | None, editor_id: str, rows: list[dict] | None = None) -> str | None:
    """Built-editor identity: summary ``hosts`` first, trial provenance as fallback (#149)."""
    host = ((summary or {}).get('hosts') or {}).get(editor_id) or {}
    if isinstance(host, dict):
        tree = host.get('tree_sha256')
        if isinstance(tree, str) and tree:
            return tree
    for row in rows or ():
        pin = editor_pin(row)
        if pin:
            return pin
    return None


def editor_pin(row):
    """The built-editor identity a trial must carry (#149).

    The runner stamps ``environment.editor_version`` with ``pin_label``
    (``perf/runner/speed_headless.py``) — the editor slug, not a pin — so
    only ``host_provenance.tree_sha256``, the hash of the built editor, and a
    genuinely pinned ``editor_version`` (not equal to the slug) identify the
    measured build. ``None`` means the trial records no identity.
    """
    provenance = row.get('host_provenance')
    if isinstance(provenance, dict):
        tree = provenance.get('tree_sha256')
        if isinstance(tree, str) and tree:
            return tree
    version = (row.get('environment') or {}).get('editor_version')
    if isinstance(version, str) and version and version != row.get('editor_id'):
        return version
    return None


def _shakedown_reason(row) -> str | None:
    """A shakedown mark anywhere in a run: never a publication run (#149).

    ``perf/runner/browser_run.py`` finishes a shakedown run with
    ``shakedown: True``, ``publishable: False`` and a
    ``publication_block_reason`` starting ``shakedown``; the same marks are
    honoured wherever they appear — summary or trial — regardless of the
    other fields around them.
    """
    if row.get('shakedown') is True:
        return 'shakedown: few repetitions to find bugs; never a publication run'
    reason = str(row.get('publication_block_reason') or '')
    if reason.startswith('shakedown'):
        return reason
    return None


def _run_shakedown(run_directory: Path) -> str | None:
    """The first shakedown mark on any trial of the run, if there is one."""
    for _, _, row in _iter_attempt_rows(run_directory):
        mark = _shakedown_reason(row)
        if mark:
            return mark
    return None


def _run_shakedown_job(job: Path) -> str | None:
    """The first shakedown mark under one job directory only."""
    cells_dir = job / 'cells'
    if not cells_dir.is_dir():
        return None
    for directory in sorted(_listing(cells_dir, '*/attempts')):
        for _path, row in _read_rows(directory, drop=_ATTEMPT_DROP):
            mark = _shakedown_reason(row)
            if mark:
                return mark
    return None


def _job_measured_launch_names(job: Path, editor_id: str) -> list[str]:
    """Launch cells that carry at least one trial JSON (not an empty attempts tree)."""
    names: list[str] = []
    cells_dir = job / 'cells'
    if not cells_dir.is_dir():
        return names
    suffix = '-' + editor_id
    for directory in sorted(_listing(cells_dir, '*/attempts')):
        if not any(_listing(directory, '*.json')):
            continue
        name = directory.parent.name
        if name.endswith(suffix):
            names.append(name)
    for directory in sorted(_listing(cells_dir, '*')):
        if not directory.is_dir() or directory.name in names:
            continue
        if directory.name.endswith(suffix) and (directory / 'resource.json').is_file():
            names.append(directory.name)
    return names


def _job_launch_names(job: Path, editor_id: str) -> list[str]:
    names = []
    cells_dir = job / 'cells'
    if not cells_dir.is_dir():
        return names
    for directory in sorted(_listing(cells_dir, '*/attempts')):
        name = directory.parent.name
        if name.endswith('-' + editor_id):
            names.append(name)
    suffix = '-' + editor_id
    for directory in sorted(_listing(cells_dir, '*')):
        if not directory.is_dir() or directory.name in names:
            continue
        if directory.name.endswith(suffix) and (directory / 'resource.json').is_file():
            names.append(directory.name)
    return names


def _job_run_fingerprint(job: Path, editor_id: str) -> tuple[frozenset[str], str]:
    """Launch set and content hash for one job; used to compare duplicate pulls."""
    launches = _job_launch_names(job, editor_id)
    launch_set = frozenset(launches)
    digests: list[str] = []
    for launch in sorted(launches):
        cell = job / 'cells' / launch
        parts: list[str] = []
        attempts = cell / 'attempts'
        if attempts.is_dir():
            for path in sorted(_listing(attempts, '*.json')):
                try:
                    parts.append(hashlib.sha256(path.read_bytes()).hexdigest())
                except OSError:
                    parts.append('unreadable')
        if (cell / 'resource.json').is_file():
            try:
                parts.append('resource:' + hashlib.sha256((cell / 'resource.json').read_bytes()).hexdigest())
            except OSError:
                parts.append('resource:unreadable')
        digests.append('%s=%s' % (launch, ','.join(parts) if parts else 'empty'))
    body = '%s:%s' % (','.join(sorted(launch_set)), ';'.join(digests))
    return launch_set, hashlib.sha256(body.encode()).hexdigest()


def _same_root_duplicate_whole_schedule(
    job_pairs: list[tuple[Path, Path]], editor_id: str
) -> bool:
    """Two whole jobs in one root that repeated the same full launch list (#154)."""
    roots = {run for run, _ in job_pairs}
    if len(roots) != 1:
        return False
    jobs = [job for _run, job in job_pairs]
    if any(_block_slice_key(_load_summary(job)) for job in jobs):
        return False
    # A whole schedule covers the order that job claims. A campaign-2 job that
    # reuses launch names holds only a prefix of a longer order, so it is pooled
    # with its siblings; two copies of a full list are not.
    wholes: list[frozenset[str]] = []
    for job in jobs:
        names = frozenset(_job_launch_names(job, editor_id))
        claimed = _scheduled_for_editor(_load_summary(job), editor_id, PUBLICATION_REPETITIONS)
        if len(names) >= PUBLICATION_REPETITIONS and len(names) >= claimed:
            wholes.append(names)
    if len(wholes) < 2:
        return False
    return len(set(wholes)) == 1


def _seed_block_gate(
    summaries: list[dict | None], job_pairs: list[tuple[Path, Path]], editor_id: str
) -> tuple[bool, str | None]:
    specs, orders = [], []
    block_jobs: list[tuple[dict, Path]] = []
    for (_root, job), summary in zip(job_pairs, summaries):
        if not summary:
            continue
        if isinstance(summary.get('order'), list) and not summary.get('order'):
            if any((other or {}).get('order') for other in summaries):
                return True, 'session job with empty order'
        block = summary.get('block')
        if isinstance(block, dict) and block.get('index'):
            specs.append(block)
            block_jobs.append((block, job))
        order = summary.get('order') or []
        if order:
            orders.append({(rep, ed) for rep, ed in order})
    if _same_root_duplicate_whole_schedule(job_pairs, editor_id):
        return True, 'overlapping launch schedules in one seed'
    jobs = [job for _root, job in job_pairs]
    if specs:
        jobs_with_block = {job for _block, job in block_jobs}
        whole_reruns = [job for job in jobs if job not in jobs_with_block and _job_launch_names(job, editor_id)]
        if whole_reruns:
            return True, 'whole re-run beside block campaign'
        ofs = {item['of'] for item in specs if item.get('of')}
        reps = {item['repetitions'] for item in specs if item.get('repetitions')}
        indices = [item['index'] for item in specs]
        if len(ofs) != 1 or len(reps) != 1:
            return True, 'inconsistent block layout across jobs of one seed'
        of_val, rep_val = ofs.pop(), reps.pop()
        if of_val * rep_val != PUBLICATION_REPETITIONS:
            return True, 'block layout does not cover %d repetitions' % PUBLICATION_REPETITIONS
        if len(set(indices)) != len(indices):
            return True, 'duplicate block index in one seed'
        out_of_range = sorted({index for index in indices if index < 1 or index > of_val})
        if out_of_range:
            return True, 'block index out of range %s' % ','.join(map(str, out_of_range))
        missing = sorted(set(range(1, of_val + 1)) - set(indices))
        if missing:
            return True, 'missing blocks %s' % ','.join(map(str, missing))
        for block, job in block_jobs:
            expected = block.get('repetitions') or 0
            found = len(_job_measured_launch_names(job, editor_id))
            if found < expected:
                return True, 'block %d has no launch files' % block.get('index')
    elif len(jobs) >= 2:
        sets = [frozenset(_job_launch_names(job, editor_id)) for job in jobs]
        full_schedules = [item for item in sets if len(item) >= PUBLICATION_REPETITIONS]
        if len(full_schedules) >= 2 and len({item for item in full_schedules}) > 1:
            return True, 'inconsistent launch schedules in one seed'
    if len(orders) > 1:
        seen: set = set()
        overlap = False
        for reps in orders:
            if seen & reps:
                overlap = True
                break
            seen |= reps
        if overlap:
            qualify = _overlap_qualify_jobs(job_pairs, editor_id)
            if not qualify:
                return True, 'overlapping launch schedules in one seed'
    return False, None


def _block_slice_key(summary: dict | None) -> tuple[int, int] | None:
    block = (summary or {}).get('block') or {}
    if block.get('index') and block.get('of'):
        return int(block['of']), int(block['index'])
    return None


def _filter_job_pairs(
    job_pairs: list[tuple[Path, Path]], editor_id: str, *, qualify_keys: bool = True
) -> tuple[list[tuple[Path, Path]], bool, str | None]:
    """Drop a duplicate pull of one job; refuse a second run of the same launches."""
    seen_pairs: set[tuple[str, str]] = set()
    unique_pairs: list[tuple[Path, Path]] = []
    for run_directory, job in job_pairs:
        key = (str(run_directory), str(job))
        if key in seen_pairs:
            continue
        seen_pairs.add(key)
        unique_pairs.append((run_directory, job))
    job_pairs = unique_pairs
    launch_owner: dict[str, str] = {}
    bare_owner: dict[str, str] = {}
    block_owner: dict[tuple[int, int], str] = {}
    qualify = _overlap_qualify_jobs(job_pairs, editor_id) if qualify_keys else set()
    filtered: list[tuple[Path, Path]] = []
    blocked, block_reason = False, None
    skip_jobs: set[Path] = set()
    by_run_id: dict[str, list[tuple[Path, Path, tuple[frozenset[str], str]]]] = defaultdict(list)
    for run_directory, job in job_pairs:
        summary = _load_summary(job) or {}
        run_id = str(summary.get('run_id') or job.name)
        launches = _job_launch_names(job, editor_id)
        if launches:
            by_run_id[run_id].append((run_directory, job, _job_run_fingerprint(job, editor_id)))
    for run_id, copies in by_run_id.items():
        if len(copies) == 1:
            continue
        fingerprints = {fp for _root, _job, fp in copies}
        if len(fingerprints) > 1:
            blocked = True
            block_reason = 'duplicate run_id with conflicting copies'
        else:
            for _root, job, _fp in sorted(copies, key=lambda item: (str(item[0]), str(item[1])))[1:]:
                skip_jobs.add(job)
    if blocked:
        return [], True, block_reason
    for run_directory, job in job_pairs:
        if job in skip_jobs:
            continue
        summary = _load_summary(job) or {}
        run_id = str(summary.get('run_id') or job.name)
        launches = _job_launch_names(job, editor_id)
        if not launches:
            filtered.append((run_directory, job))
            continue
        keys = [_launch_key(run_directory, job, launch, qualify=qualify) for launch in launches]
        owners = {launch_owner[key] for key in keys if key in launch_owner}
        if owners == {run_id} and owners:
            continue
        bare_owners = {bare_owner[launch] for launch in launches if launch in bare_owner}
        if bare_owners - {run_id}:
            slice_key = _block_slice_key(summary)
            multi_root = len({run for run, _ in job_pairs}) > 1
            if slice_key and slice_key in block_owner and block_owner[slice_key] != run_id:
                blocked = True
                block_reason = 'launches measured twice: a block was re-run'
            elif not qualify:
                blocked = True
                block_reason = 'launches measured twice: a block was re-run'
            elif multi_root:
                blocked = True
                block_reason = 'launches measured twice: a block was re-run'
        filtered.append((run_directory, job))
        for launch in launches:
            bare_owner.setdefault(launch, run_id)
            launch_owner.setdefault(_launch_key(run_directory, job, launch, qualify=qualify), run_id)
        slice_key = _block_slice_key(summary)
        if slice_key:
            block_owner.setdefault(slice_key, run_id)
    return filtered, blocked, block_reason


def _trial_block(trial):
    code = refusal_code(trial)
    if code:
        return code
    if trial.get('publishable') is not True or _nested_unpublishable(trial.get('host_provenance')):
        return 'publishable_not_true'
    if trial.get('outcome') != 'measured':
        return 'crash'
    if editor_pin(trial) is None:
        return 'pin_not_recorded'
    return None


_JSON_CACHE: dict = {}
_LIST_CACHE: dict = {}

# Keys the memoised readers leave out: bulky in the pulled runs and read by
# no consumer of the row that carries them (#176, round 2). Production
# attempt reads always pass a spec — ``row.get`` on a dropped key is None
# and nothing re-parses for it. Only ``_iter_sample_rows`` and
# ``_trial_path`` call ``_read_json`` with no spec for the whole document;
# the spec is part of the cache key, so the two entries never alias.
_SUMMARY_DROP = frozenset({'samples'})
_ATTEMPT_DROP = frozenset({
    'witnesses', 'instrumented', 'load_witness', 'marker_only',
    'tolerated_class_pairs', 'tolerated_list_markers', 'tolerated_marker_strings',
    'clock_skew', 'summary_stats', 'cpu_accounting', 'host_build', 'mechanism',
    'boundary', 'refusal_detail', 'exit_code', 'run_id', 'repetition', 'seed',
    'nr_throttled', 'throttled_usec', 'typing_session_kept', 'non_failure_outcomes',
})
_SAMPLE_ROW_KEEP = frozenset(
    {'editor_id', 'accounting_scope', 'outcome', 'refusal_code', 'publication_block_reason', 'failure_reason'}
)


def _read_json(path: Path, *, keep=None, drop=None):
    """Parsed JSON of one file, memoised on (abspath, stat fields, spec) (#176).

    Pulled runs are append-only; a rewrite moves ``st_ctime_ns`` (which
    ``os.utime`` cannot set back) or the inode, so a file parses again even
    when size and mtime are restored. The stat is taken before and after the
    read; if the two disagree the value is returned fresh and never cached,
    so a mid-read writer cannot plant a stale entry. The cached object is
    shared by every consumer and must not be mutated. Error paths are
    unchanged: OSError propagates from stat/read as it did from read_text,
    and a JSONDecodeError is cached and re-raised so each caller's ``except``
    still fires.

    The key's spelling is ``str(path)`` when already absolute and
    ``os.path.abspath`` otherwise — string operations with no lstat walk,
    which on the hot reader cost more than the parse it replaced. The
    device and inode fields carry the file's identity: a symlink retarget
    or a rename replacement reads as a different file.

    ``keep``/``drop`` slim the memoised dict to what the caller's consumers
    read; the spec is part of the cache key, so the slim entry and the full
    entry are distinct and a plain call always returns the whole document.
    """
    if keep is not None:
        spec = ('keep', frozenset(keep))
    elif drop is not None:
        spec = ('drop', frozenset(drop))
    else:
        spec = None
    before = path.stat()
    key = (
        str(path) if path.is_absolute() else os.path.abspath(str(path)),
        before.st_dev, before.st_ino, before.st_size,
        before.st_mtime_ns, before.st_ctime_ns, spec,
    )
    try:
        value = _JSON_CACHE[key]
    except KeyError:
        try:
            value = json.loads(path.read_text(encoding='utf-8'))
        except json.JSONDecodeError as exc:
            value = exc
        if spec is not None and isinstance(value, dict):
            if spec[0] == 'keep':
                value = {k: v for k, v in value.items() if k in spec[1]}
            else:
                value = {k: v for k, v in value.items() if k not in spec[1]}
        try:
            after = path.stat()
        except OSError:
            after = None
        if after is not None and key[1:6] == (
            after.st_dev, after.st_ino, after.st_size,
            after.st_mtime_ns, after.st_ctime_ns,
        ):
            _JSON_CACHE[key] = value
    if isinstance(value, json.JSONDecodeError):
        raise value
    return value


def _dirs_stamp(directories) -> tuple:
    stamp = []
    for directory in directories:
        try:
            st = directory.stat()
        except OSError:
            stamp.append(None)
        else:
            stamp.append(
                (st.st_dev, st.st_ino, st.st_mtime_ns, st.st_ctime_ns)
            )
    return tuple(stamp)


def _dirs_chain(directories) -> tuple:
    """``lstat`` identity of every component of each watched path.

    ``_dirs_stamp`` sees where a path ends; this sees how it got there: a
    symlink retargeted — even put back — inside or above the tree leaves a
    new link inode and a bumped parent while the target's own fields
    stand. The glob can then name a different tree than the stamp
    describes, so the chain is taken before and after the glob and the
    names are cached only when both stand still.
    """
    chain = {}
    for directory in directories:
        for path in (directory, *directory.parents):
            if path in chain:
                continue
            try:
                st = path.lstat()
            except OSError:
                chain[path] = None
            else:
                chain[path] = (
                    st.st_dev, st.st_ino, st.st_mtime_ns, st.st_ctime_ns
                )
    return tuple(chain.items())


def _watch_dirs(directory: Path, pattern: str) -> tuple:
    """Every directory whose contents can change ``directory.glob(pattern)``.

    A single-component pattern is decided by the directory alone; each
    ``*/`` level also needs the directories one level up, and ``**`` needs
    the whole subtree.
    """
    if '**' in pattern.split('/'):
        watch = {directory}
        for root, _subdirs, _files in os.walk(directory):
            watch.add(Path(root))
        return tuple(sorted(watch))
    watch = {directory}
    frontier = [directory]
    for _level in range(pattern.count('/')):
        deeper = []
        for parent in frontier:
            try:
                deeper.extend(child for child in parent.iterdir() if child.is_dir())
            except OSError:
                continue
        watch.update(deeper)
        frontier = deeper
        if not frontier:
            break
    return tuple(sorted(watch))


_LIST_SCOPED = [False]


@contextmanager
def _listing_scope():
    """Memoised directory listings for one top-level read (#176).

    Inside the scope a listing is reused while every watched directory's
    resolved identity (device, inode, mtime, ctime) stands; a listing is
    cached only while the ``lstat`` identity of every component of its
    path also stands. Outside it every call globs fresh, so a caller that
    adds a file between two reads always sees it — the pulled trees are
    append-only at report time, a fixture being built is not. The stamp
    is a clock: a filesystem reporting whole-second ctimes can still hide
    a same-second change.
    """
    _LIST_CACHE.clear()
    outer = _LIST_SCOPED[0]
    _LIST_SCOPED[0] = True
    try:
        yield
    finally:
        _LIST_SCOPED[0] = outer


def _watchable(pattern: str) -> bool:
    """True when the watch walk stamps every directory the glob reads.

    A ``..`` component or a ``**`` behind a prefix makes glob read directories
    the walk never visits (Grok, #176 round 5), so such patterns are globbed
    on every call and never cached.
    """
    parts = pattern.split('/')
    if '..' in parts:
        return False
    return '**' not in parts[1:]


def _listing(directory, pattern: str):
    """``directory.glob(pattern)``, memoised inside ``_listing_scope`` (#176).

    The reader walks the same cells/, attempts/ and samples/ trees once per
    cell x editor x measure. A listing is reused while every watched
    directory's resolved identity — device, inode, mtime and ctime —
    stands: adding or removing an entry bumps the directory that names it
    (always a watched one), ``os.utime`` cannot put ctime back, and a
    rename swap changes the inode, so the next call globs again and sees
    the change. The stamp is taken before the glob and again once the
    glob returns, joined by the ``lstat`` identity of every component of
    each watched path: a symlink retargeted for the glob and put back
    leaves a new link inode and a bumped parent, and a link still swapped
    names a different inode, so names globbed while a path resolved
    elsewhere are served fresh and never cached. A directory born between
    the walk that froze the watch set and the stamp would be inside its
    parent's stored stamp yet unwatched, so the walk is repeated too: a
    different second walk means nothing is cached until a call sees a
    stable tree. The stamp is a clock — a filesystem reporting
    whole-second ctimes can still hide a same-second change.
    """
    directory = Path(directory)
    if not _LIST_SCOPED[0] or not _watchable(pattern):
        return tuple(directory.glob(pattern))
    key = (str(directory), pattern)
    entry = _LIST_CACHE.get(key)
    if entry is not None:
        stamp, watch, paths = entry
        if _dirs_stamp(watch) == stamp:
            return paths
    watch = _watch_dirs(directory, pattern)
    stamp = _dirs_stamp(watch)
    chain = _dirs_chain(watch)
    paths = tuple(directory.glob(pattern))
    if (
        _dirs_stamp(watch) == stamp
        and _dirs_chain(watch) == chain
        and _watch_dirs(directory, pattern) == watch
    ):
        _LIST_CACHE[key] = (stamp, watch, paths)
    return paths


def _load_summary(run_directory: Path) -> dict | None:
    path = run_directory / "summary.json"
    if not path.is_file():
        return None
    try:
        return _read_json(path, drop=_SUMMARY_DROP)
    except (OSError, json.JSONDecodeError):
        return None


def _scheduled_for_editor(summary: dict | None, editor_id: str, default: int) -> int:
    order = (summary or {}).get("order") or []
    if not order:
        return default
    return sum(1 for _rep, ed in order if ed == editor_id)


def _decided_publication_schedule(summaries: list, scheduled: int) -> bool:
    """The campaign's schedule is 10 launches per seed, from exactly 2 blocks of 5.

    A blockless job is not that schedule, including a whole job whose order
    is exactly ``PUBLICATION_REPETITIONS``. Any other total is withheld.
    When the jobs carry block metadata, every present summary must carry it,
    and the layout must be the decided one: two blocks, five repetitions
    each, indices 1 and 2. Another factorization of 10 is not that layout.
    """
    if scheduled != PUBLICATION_REPETITIONS:
        return False
    blocks = []
    present = 0
    for summary in summaries:
        if not summary:
            continue
        present += 1
        block = summary.get('block')
        if isinstance(block, dict) and block.get('index'):
            blocks.append(block)
    if not blocks:
        return False
    if len(blocks) != present:
        return False
    each = PUBLICATION_REPETITIONS // 2
    if any(int(block.get('of') or 0) != 2 or int(block.get('repetitions') or 0) != each for block in blocks):
        return False
    return sorted(int(block.get('index') or 0) for block in blocks) == [1, 2]


def _wrong_schedule_text(n_kept: int, scheduled: int) -> str:
    return (
        'wrong schedule (n = %d of %d; this campaign schedules %d per seed)'
        % (n_kept, scheduled, PUBLICATION_REPETITIONS)
    )


def _run_blocks_publication(summary: dict | None) -> tuple[bool, str | None]:
    if summary is None:
        return False, None
    if summary.get("outcome") == "failed":
        return True, summary.get("failure_reason") or "run failed"
    reason = summary.get("publication_block_reason")
    mark = _shakedown_reason(summary)
    if mark:
        return True, mark
    if summary.get("publishable") is False and reason and reason != 'summary is not a trial; trials carry publishability':
        return True, str(reason)
    if summary.get("failure_reason") in ("repos_modified", "repos_dirty_at_start"):
        return True, str(summary.get("failure_reason"))
    return False, None


def _iter_sample_rows(run_directory: Path):
    samples_dir = run_directory / "samples"
    if not samples_dir.is_dir():
        return
    for path in sorted(samples_dir.glob("*.json")):
        try:
            row = _read_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(row, dict):
            yield row


def _trial_path(run_directory: Path, sample_row: dict, criterion_id: str) -> Path | None:
    cell_directory = sample_row.get("cell_directory")
    if cell_directory:
        attempts = Path(cell_directory) / "attempts"
    else:
        rejected = sample_row.get("rejected_evidence_directory")
        if rejected:
            attempts = Path(rejected) / "cell" / "attempts"
        else:
            return None
    if not attempts.is_dir():
        return None
    slug = criterion_id.lower()
    direct = attempts / f"{slug}.json"
    if direct.is_file():
        return direct
    for path in attempts.glob("*.json"):
        try:
            row = _read_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        if row.get("criterion_id") == criterion_id:
            return path
    return None


def _frame_interval_ms(trials) -> float | None:
    for trial in trials:
        diagnostic = trial.get("diagnostic") or {}
        value = diagnostic.get("frame_interval_ms")
        if isinstance(value, (int, float)) and value > 0:
            return float(value)
    return None
def _nested_unpublishable(value):
    if isinstance(value, dict):
        return value.get('publishable') is False or any(_nested_unpublishable(v) for v in value.values())
    if isinstance(value, list):
        return any(_nested_unpublishable(v) for v in value)
    return False


def trial_measure(trial):
    diagnostic = trial.get('diagnostic') or {}
    measure = str(trial.get('measure') or diagnostic.get('size_rung') or diagnostic.get('measurement') or '')
    phase = trial.get('measurement_phase') if trial.get('criterion_id') == 'C17' else None
    return ':'.join(filter(None, (measure, str(phase or ''))))


def trial_workload(trial):
    return str(trial.get('workload_id') or (trial.get('environment') or {}).get('workload_id')
               or (trial.get('diagnostic') or {}).get('workload_id') or '')


def _read_rows(directory, *, keep=None, drop=None, skip=None):
    for path in sorted(_listing(directory, '**/*.json')):
        if skip is not None and skip(path):
            continue
        try:
            row = _read_json(path, keep=keep, drop=drop)
        except (OSError, json.JSONDecodeError):
            if path.name.startswith('chrome-profile-'):
                continue  # a truncated trace record is diagnostic, never a trial
            yield path, {'refusal_code': 'unreadable_trial'}
            continue
        if isinstance(row, dict):
            yield path, row
        else:
            yield path, {'refusal_code': 'unreadable_trial'}


def _diagnostic_trial_path(path: Path) -> bool:
    """Chrome-profile traces and traced re-invocations live under these subtrees."""
    return 'profile-invoke' in path.parts or 'profile' in path.parts


def _diagnostic_trial_row(row: dict) -> bool:
    return row.get('outcome') == 'profiled' or row.get('accounting_scope') == 'diagnostic'


#: Editor-scoped supersedes (#185): an editor's cells of some jobs, measured
#: again by runs that keep the job indices. Each entry is
#: ``{"editor": id, "jobs": [index, ...], "kept_runs": [run id, ...]}``;
#: ``build/e2_publication_roots.py`` writes them into report_e2_runs.json.
_SUPERSEDED_CELLS: tuple = ()


@contextmanager
def superseded_cells(entries):
    """Read the campaign with these editor-scoped supersedes applied."""
    global _SUPERSEDED_CELLS
    previous = _SUPERSEDED_CELLS
    _SUPERSEDED_CELLS = tuple(
        {'editor': entry['editor'], 'jobs': frozenset(int(i) for i in entry['jobs']),
         'kept_runs': frozenset(entry.get('kept_runs') or ())}
        for entry in (entries or ())
    )
    try:
        yield
    finally:
        _SUPERSEDED_CELLS = previous


def job_superseded(job: Path, editor_id: str) -> bool:
    """True when ``editor_id``'s cells of this job were measured again by a later run (#185).

    A job directory is ``<run id>-<index>``; the run that measured the cells
    again keeps the index, and its own jobs are never superseded.
    """
    if not _SUPERSEDED_CELLS:
        return False
    run_id, _, tail = Path(job).name.rpartition('-')
    if not tail.isdigit():
        return False
    return any(
        entry['editor'] == editor_id and int(tail) in entry['jobs'] and run_id not in entry['kept_runs']
        for entry in _SUPERSEDED_CELLS
    )


def _iter_attempt_rows(run_directory: Path):
    yield from _attempt_rows_of(run_directory, _job_roots(run_directory))


def _attempt_rows_of(run_directory: Path, jobs, *, qualify: set[Path] | None = None):
    for job in jobs:
        for directory in sorted(_listing(job / 'cells', '*/attempts')):
            for path, row in _read_rows(directory, drop=_ATTEMPT_DROP, skip=_diagnostic_trial_path):
                # Measured attempts only, never a profiling subtree or a traced repetition.
                if _diagnostic_trial_path(path) or _diagnostic_trial_row(row):
                    continue
                if job_superseded(job, row.get('editor_id')):
                    continue
                yield _launch_key(run_directory, job, directory.parent.name, qualify=qualify), path, row


def _job_measures(run_directory: Path, job: Path, editor_id: str, criterion_id: str) -> bool:
    return any(
        row.get('editor_id') == editor_id and row.get('criterion_id') == criterion_id
        for _, _, row in _attempt_rows_of(run_directory, [job])
    )


def _lane_jobs(run_directory: Path, jobs, editor_id: str, criterion_id: str):
    """Only the runner lane that measures this criterion contributes
    launches: a campaign run directory holds jobs of many runners, and a
    warm/cold refusal must not veto an input-lane cell."""
    if len(jobs) < 2:
        return jobs
    lanes = {
        job.parent.name
        for job in jobs
        if _job_measures(run_directory, job, editor_id, criterion_id)
    }
    return [job for job in jobs if not lanes or job.parent.name in lanes]


_JOB_PART_DIRS = frozenset({'cells', 'samples', 'rejected-evidence', 'fixtures', 'attempts', 'profiles'})


def _job_roots(run_directory: Path) -> list[Path]:
    """The job directories of a run directory.

    A run directory is one job (``cells/`` beside ``summary.json``) or a
    campaign run whose jobs sit under ``<runner>/<job>/``: campaign 2 runs
    one editor per job, so one cell's launches can be spread over several
    job directories.
    """
    run_directory = Path(run_directory)
    parts = ('cells', 'samples', 'rejected-evidence', 'summary.json')

    def marked(path: Path) -> bool:
        return any(_listing(path, part) for part in parts)

    # A campaign directory can carry its own summary for comparability and
    # still hold the block jobs underneath. Those jobs are the schedule.
    nested = [
        job
        for job in sorted(_listing(run_directory, '*/*'))
        # A job's own cells/<NNNN-editor> (each with a summary.json) and its
        # other measurement folders are not jobs (shakedown 3 layout).
        if job.is_dir() and job.parent.name not in _JOB_PART_DIRS and marked(job)
    ]
    if nested:
        return nested
    if marked(run_directory):
        return [run_directory]
    jobs = []
    if (run_directory / 'runs').is_dir():
        for campaign in sorted(_listing(run_directory / 'runs', '*')):
            if campaign.is_dir():
                jobs.extend(_job_roots(campaign))
    return jobs


def _overlap_qualify_jobs(job_pairs: list[tuple[Path, Path]], editor_id: str) -> set[Path]:
    """Jobs whose launch names collide within the pool (campaign 2 one-editor jobs)."""
    owner: dict[str, Path] = {}
    qualify: set[Path] = set()
    for _root, job in job_pairs:
        for name in _job_launch_names(job, editor_id):
            if name in owner and owner[name] != job:
                qualify.add(job)
                qualify.add(owner[name])
            else:
                owner[name] = job
    return qualify


def _launch_key(run_directory: Path, job: Path, launch: str, *, qualify: set[Path] | None = None) -> str:
    """Per-seed names when disjoint; per-job when one-editor jobs reuse rep indices."""
    if qualify and job in qualify and job != Path(run_directory):
        return '%s/%s' % (job.name, launch)
    return launch


def _iter_trials(run_directory: Path):
    for _, _, row in _iter_attempt_rows(run_directory):
        if row.get('criterion_id') and row.get('editor_id'):
            yield row


def _number(value):
    import math

    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _one_repetition_value(trial: dict) -> tuple[float | None, bool | None]:
    if trial.get("outcome") != "measured":
        return None, None
    if trial.get("publishable") is False:
        return None, None
    samples = trial.get("samples_ms") or []
    numeric = [float(sample) for sample in samples if isinstance(sample, (int, float))]
    if not numeric:
        return None, None
    value = percentile(numeric, 50) if len(numeric) > 1 else numeric[0]
    flags = trial.get("sub_frame_samples")
    if flags is None:
        flags = (trial.get("diagnostic") or {}).get("sub_frame_samples")
    if flags is None:
        return value, None
    if not isinstance(flags, list) or len(flags) != len(samples):
        return value, None
    sub = any(flags)
    return value, sub


def _refusal_key(sample_or_trial: dict) -> str:
    reason = sample_or_trial.get("failure_reason") or sample_or_trial.get("publication_block_reason") or sample_or_trial.get("outcome")
    return str(reason).split(":", 1)[0].strip()


_FIGURE_FIELDS = frozenset({'stats', 'kept_ms', 'raw_samples_ms', 'sub_frame', 'frame_interval_ms'})


def public_cell_dict(cell: dict, *, published: bool = False) -> dict:
    """Facts payload for one seed group: figures only when the cell publishes."""
    if published:
        return dict(cell)
    return {key: value for key, value in cell.items() if key not in _FIGURE_FIELDS}


def build_run_cell(
    run_directory: Path, editor_id: str, criterion_id: str, *, scheduled: int = PUBLICATION_REPETITIONS, measure: str = '', workload_id: str | None = None
) -> dict:
    job_pairs = [(run_directory, job) for job in _lane_jobs(run_directory, _job_roots(run_directory), editor_id, criterion_id)]
    return _build_cell_from_jobs(job_pairs, editor_id, criterion_id, scheduled=scheduled, measure=measure, workload_id=workload_id)


def _jobs_for_workload(job_pairs, editor_id: str, criterion_id: str, workload_id: str | None):
    """Jobs whose schedule is this workload, before the duplicate-launch gate.

    One campaign root holds a 2x5 job per workload, plus one shared C14 job
    for every rung. Pooling them sums the schedules or repeats a block index.
    A job that also carries other workloads stays, so the shared job's
    schedule is still its own launch order. A job with no workload stamp
    stays: it is not a dedicated other size.
    """
    if not workload_id:
        return job_pairs
    selected = []
    for run_directory, job in job_pairs:
        workloads: set[str] = set()
        measured = False
        for _launch, _path, trial in _attempt_rows_of(run_directory, [job]):
            if trial.get('editor_id') != editor_id or trial.get('criterion_id') != criterion_id:
                continue
            measured = True
            workloads.add(trial_workload(trial))
        workloads.discard('')
        if not measured:
            continue
        if not workloads or workload_id in workloads:
            selected.append((run_directory, job))
    return selected


def _build_cell_from_jobs(
    job_pairs: list[tuple[Path, Path]],
    editor_id: str,
    criterion_id: str,
    *,
    scheduled: int = PUBLICATION_REPETITIONS,
    measure: str = '',
    workload_id: str | None = None,
) -> dict:
    job_pairs = _jobs_for_workload(job_pairs, editor_id, criterion_id, workload_id)
    if not job_pairs:
        return {
            'editor_id': editor_id, 'criterion_id': criterion_id, 'measure': measure, 'workload_id': workload_id,
            'scheduled': 0, 'stats': None, 'blocked': False, 'block_reason': None, 'refusals': {},
        }
    job_pairs, rerun_blocked, rerun_reason = _filter_job_pairs(job_pairs, editor_id)
    jobs = [job for _, job in job_pairs]
    summaries = [_load_summary(job) for job in jobs]
    qualify = _overlap_qualify_jobs(job_pairs, editor_id)
    layout_blocked, layout_reason = _seed_block_gate(summaries, job_pairs, editor_id)
    orders = [summary for summary in summaries if (summary or {}).get('order')]
    scheduled = sum(_scheduled_for_editor(summary, editor_id, 0) for summary in orders) if orders else 0
    run_blocked, block_reason = next(
        ((True, reason) for summary in summaries for blocked, reason in [_run_blocks_publication(summary)] if blocked),
        (False, None),
    )
    if layout_blocked:
        run_blocked, block_reason = True, layout_reason
    elif rerun_blocked:
        run_blocked, block_reason = True, rerun_reason
    if not run_blocked:
        for _run_directory, job in job_pairs:
            mark = _run_shakedown_job(job)
            if mark:
                run_blocked, block_reason = True, mark
                break
    if not run_blocked:
        # Attempt files a job's order never named are not this seed's
        # measurements: they must not aggregate, and the cell is refused.
        unscheduled = []
        for (_run_directory, job), summary in zip(job_pairs, summaries):
            order = (summary or {}).get('order') or []
            if not order:
                continue
            allowed = {
                '%04d-%s' % (rep, editor_id)
                for rep, ed in order
                if ed == editor_id and isinstance(rep, int)
            }
            unscheduled.extend(
                name
                for name in _job_measured_launch_names(job, editor_id)
                if name not in allowed
            )
        if unscheduled:
            run_blocked = True
            block_reason = 'launch files not named in the job order'
    decided_schedule = _decided_publication_schedule(summaries, scheduled)
    if run_blocked:
        return {
            'editor_id': editor_id,
            'criterion_id': criterion_id,
            'measure': measure,
            'workload_id': workload_id,
            'sample_unit': 'bytes' if criterion_id in ('C17', 'C19') else 'ms',
            'witnessed': False,
            'scheduled': scheduled,
            'decided_schedule': decided_schedule,
            'kept_ms': [],
            'raw_samples_ms': [],
            'sub_frame': [],
            'refusals': {},
            'additional_refusals': {},
            'content_verified': False,
            'failed_launches': 0,
            'frame_interval_ms': None,
            'stats': None,
            'blocked': True,
            'block_reason': block_reason,
        }
    kept, raw, sub_frame, intervals = [], [], [], []
    refusals = Counter()
    sample_unit = 'bytes' if criterion_id in ('C17', 'C19') else 'ms'
    failed_launches = set()
    trials = defaultdict(list)
    refused_launches = {}
    additional = defaultdict(set)
    witnessed_cell = False
    verified_content = []
    for run_directory, job in job_pairs:
        for launch, path, trial in _attempt_rows_of(run_directory, [job], qualify=qualify):
            if trial.get('refusal_code') == 'unreadable_trial' and launch.endswith('-' + editor_id):
                if launch in refused_launches:
                    additional[launch].add(refused_launches[launch])
                refused_launches[launch] = 'unreadable_trial'
            if trial.get('editor_id') != editor_id or not trial.get('criterion_id'):
                continue
            if workload_id is not None and trial_workload(trial) != workload_id:
                continue
            code = refusal_code(trial)
            if code in _RUN_REFUSALS:
                if refused_launches.get(launch) == 'unreadable_trial':
                    additional[launch].add(code)
                else:
                    if launch in refused_launches:
                        additional[launch].add(refused_launches[launch])
                    refused_launches[launch] = code
            if trial['criterion_id'] == criterion_id and trial_measure(trial) == measure:
                trials[launch].append(trial)
    for run_directory, job in job_pairs:
        for path in _listing(job / 'rejected-evidence', '*'):
            if path.is_dir() and path.name.endswith('-' + editor_id):
                key = _launch_key(run_directory, job, path.name, qualify=qualify)
                if key in refused_launches:
                    additional[key].add(refused_launches[key])
                refused_launches[key] = 'quarantined'
        samples_dir = job / 'samples'
        for path, row in _read_rows(
            samples_dir,
            keep=_SAMPLE_ROW_KEEP,
            skip=lambda candidate: candidate.parent != samples_dir,
        ):
            if (path.parent != job / 'samples'
                    or row.get('editor_id') != editor_id or row.get('accounting_scope') == 'diagnostic'
                    or not re.fullmatch(r'\d+-' + re.escape(editor_id), path.stem)
                    or (row.get('outcome') in ('ok', 'measured')
                        and not row.get('refusal_code')
                        and not row.get('publication_block_reason'))):
                # A measured samples row that still records a refusal (its
                # launch produced no publishable attempt) names that launch;
                # skipping it publishes the cell as though it never ran.
                continue
            key = _launch_key(run_directory, job, path.stem, qualify=qualify)
            code = refusal_code(row)
            if code and refused_launches.get(key) in ('quarantined', 'unreadable_trial'):
                additional[key].add(code)
            elif code in _RUN_REFUSALS:
                refused_launches[key] = code
            elif code and key not in trials:
                refused_launches.setdefault(key, code)
    for launch, code in refused_launches.items():
        refusals[code] += 1
        failed_launches.add(launch)
    for launch, rows in trials.items():
        if launch in refused_launches:
            continue
        reason = 'conflicting_trials' if len(rows) != 1 else _trial_block(rows[0])
        trial = rows[0]
        samples = trial.get('samples_ms')
        diagnostic = trial.get('diagnostic') or {}
        flags = trial.get('sub_frame_samples', diagnostic.get('sub_frame_samples'))
        interval = diagnostic.get('frame_interval_ms')
        interval = float(interval) if _number(interval) and interval > 0 else None
        # Frame-witness flags exist only where the writer witnesses paints
        # (browser_visible layer); model-layer clocks like C04 and byte counts
        # publish without them. An absent layer keeps the strict contract.
        witnessed = sample_unit != 'bytes' and trial.get('layer', 'browser_visible') == 'browser_visible'
        if not reason and (
            not isinstance(samples, list)
            or not samples
            or not all(_number(x) for x in samples)
            or (sample_unit == 'bytes' and (trial.get('sample_unit') != 'bytes' or not all(type(x) is int and x >= 0 for x in samples)))
            or (witnessed and (not isinstance(flags, list)
                or len(flags) != len(samples) or not all(type(x) is bool for x in flags)))
        ):
            reason = 'malformed_samples'
        if not reason and witnessed and (
            interval is None or any(flag != (sample < interval) for sample, flag in zip(samples, flags))
        ):
            reason = 'sub_frame_flag_mismatch'
        if not reason and criterion_id == 'C14':
            # A C14 sample is one clock: a compositor-frame time or the no-damage
            # DOM mark. A trial that pools both (or disagrees with the measure it
            # is filed under) is refused, never published as one number.
            per_sample = {
                row.get('measure')
                for row in (diagnostic.get('samples') or [])
                if isinstance(row, dict) and row.get('measure') is not None
            }
            if len(per_sample) > 1 or (per_sample and measure and per_sample != {measure}):
                reason = 'mixed_c14_measures'
        if reason:
            failed_launches.add(launch)
            refusals[reason] += 1
            continue
        median = percentile(samples, 50)
        verified_content.append(trial.get('content_verified') is True)
        raw.append(samples)
        kept.append(median)
        witnessed_cell = witnessed_cell or witnessed
        if witnessed:
            intervals.append(interval)
            sub_frame.append(median < interval)
    return {
        'editor_id': editor_id,
        'criterion_id': criterion_id,
        'measure': measure,
        'workload_id': workload_id,
        'sample_unit': sample_unit,
        'witnessed': witnessed_cell,
        'scheduled': scheduled,
        'kept_ms': kept,
        'raw_samples_ms': raw,
        'sub_frame': sub_frame,
        'refusals': dict(refusals),
        'additional_refusals': dict(Counter(code for launch, codes in additional.items() for code in codes if code != refused_launches.get(launch))),
        'content_verified': bool(verified_content) and all(verified_content),
        'failed_launches': len(failed_launches),
        'frame_interval_ms': percentile(intervals, 50) if intervals else None,
        'stats': {'n': len(kept), 'median': percentile(kept, 50), 'p90': percentile(kept, 90)} if kept else None,
        'blocked': run_blocked, 'block_reason': block_reason,
        'decided_schedule': decided_schedule,
    }


_PLACEHOLDER_REASON = re.compile(r'adapter-not-implemented: criterion C\d+ not driven on \w+ host yet')


def _is_placeholder_row(row: dict) -> bool:
    """A lane's stand-in for a criterion it does not drive (warm/cold C07-C10, C22, C23)."""
    return row.get('outcome') == 'not_run' and bool(_PLACEHOLDER_REASON.fullmatch(str(row.get('failure_reason') or '')))


def _job_owns(run_directory: Path, job: Path, editor_id: str, criterion_id: str) -> bool:
    return any(
        row.get('editor_id') == editor_id and row.get('criterion_id') == criterion_id and not _is_placeholder_row(row)
        for _, _, row in _attempt_rows_of(run_directory, [job])
    )


def _owning_lane_pairs(pairs: list[tuple[Path, Path]], editor_id: str, criterion_id: str) -> list[tuple[Path, Path]]:
    """Across every run folder: a lane with only placeholder rows gives way to a lane with real rows (#179).

    A block campaign spreads one seed's jobs over many run folders, so the
    per-folder ``_lane_jobs`` filter cannot see that another folder holds the
    lane that drives the criterion. Pooling the placeholder jobs repeats the
    block indices and refuses the cell. When no lane has a real row, every
    lane stays and the placeholder refusal is what the cell shows.
    """
    owners = {job.parent.name for root, job in pairs if _job_owns(root, job, editor_id, criterion_id)}
    if not owners:
        return pairs
    return [(root, job) for root, job in pairs if job.parent.name in owners]


def _criterion_job_pairs(roots, editor_id: str, criterion_id: str) -> dict:
    pairs: list[tuple[Path, Path]] = []
    for root in map(Path, roots):
        for job in _lane_jobs(root, _job_roots(root), editor_id, criterion_id):
            if job_superseded(job, editor_id):
                continue
            summary = _load_summary(job) or {}
            scheduled = _scheduled_for_editor(summary, editor_id, 0)
            if not scheduled and not _job_measures(root, job, editor_id, criterion_id):
                continue
            pairs.append((root, job))
    groups: dict = {}
    for root, job in _owning_lane_pairs(pairs, editor_id, criterion_id):
        seed = (_load_summary(job) or {}).get('seed')
        groups.setdefault(seed, []).append((root, job))
    return groups


def _criterion_pins(job_pairs: list[tuple[Path, Path]], editor_id: str) -> set:
    pins: set = set()
    for run_directory, job in job_pairs:
        summary = _load_summary(job)
        pin = build_identity(summary, editor_id)
        if pin:
            pins.add(pin)
        # A summary pin never hides the attempts' recorded builds: a conflict
        # means the seed measured more than one build, which refuses the cell.
        for _launch, _path, row in _attempt_rows_of(run_directory, [job]):
            if row.get('editor_id') == editor_id:
                trial_pin = editor_pin(row)
                if trial_pin:
                    pins.add(trial_pin)
    return pins


def _criterion_block(seeds, groups) -> str | None:
    if not groups:
        return 'not in these runs'
    if len(groups) != 2 or None in seeds:
        return 'two seeds required'
    for name, group in zip(('first', 'second'), groups):
        if group['blocked']:
            reason = group.get('block_reason') or 'run blocked'
            return '%s seed: run blocked (%s)' % (name, reason)
    for name, group in zip(('first', 'second'), groups):
        if group.get('decided_schedule') is False:
            stats = group.get('stats') or {}
            return '%s seed: %s' % (
                name, _wrong_schedule_text(stats.get('n', 0), group.get('scheduled', 0)))
    for name, group in zip(('first', 'second'), groups):
        stats = group.get('stats') or {}
        n_kept = stats.get('n', 0)
        if n_kept < PUBLICATION_MIN_KEPT:
            reasons = ', '.join('%s %d' % item for item in sorted((group.get('refusals') or {}).items()))
            return '%s seed: %d of %d launches kept%s' % (
                name, n_kept, group.get('scheduled', 0), ' (%s)' % reasons if reasons else '')
    return None


def read_criterion_cell(
    roots, editor_id: str, criterion_id: str, *, measure: str = '', workload_id: str | None = None
) -> dict:
    """Pool launches by seed across any number of campaign roots (#154)."""
    by_seed = _criterion_job_pairs(roots, editor_id, criterion_id)
    seeds = sorted(by_seed, key=lambda seed: (seed is None, seed))
    groups = [
        _build_cell_from_jobs(by_seed[seed], editor_id, criterion_id, measure=measure, workload_id=workload_id)
        for seed in seeds
    ]
    cell = {'published': False, 'reason': None, 'seeds': seeds, 'groups': groups, 'by_seed': by_seed}
    cell['reason'] = _criterion_cell_block(seeds, groups, by_seed, editor_id)
    if not cell['reason']:
        cell['published'] = True
    return cell


def _criterion_cell_block(seeds, groups, by_seed, editor_id: str) -> str | None:
    missing = _criterion_block(seeds, groups)
    if missing:
        return missing
    pins = []
    for name, seed in zip(('first', 'second'), seeds):
        pin = _criterion_pins(by_seed[seed], editor_id)
        if not pin:
            return 'the built editor is not recorded'
        if len(pin) > 1:
            return '%s seed: more than one editor build recorded' % name
        pins.append(pin)
    if pins[0] != pins[1]:
        return 'the two seeds measured different editor builds'
    return None


def _sub_frame_share(cell: dict) -> float | None:
    flags = cell.get('sub_frame') or []
    if not flags or len(flags) != len(cell.get('kept_ms', [])):
        return None
    return sum(1 for flag in flags if flag) / len(flags)


def _format_p90(cell: dict, p90: float, frame_interval: float) -> str:
    if p90 < frame_interval:
        return f'p90 < 1 frame ({frame_interval:g} ms)'
    return f'p90 {p90:.1f} ms'


def failure_text(cell: dict) -> str:
    reasons = cell.get('refusals') or {}
    if not reasons:
        return ''
    counts = '; '.join(f'{key}: {count}' for key, count in sorted(reasons.items()))
    count = cell.get('failed_launches', sum(reasons.values()))
    extra = cell.get('additional_refusals') or {}
    also = '; also ' + '; '.join(f'{k}: {v}' for k, v in sorted(extra.items())) if extra else ''
    return f'{count} of {cell.get("scheduled", PUBLICATION_REPETITIONS)} launches failed: {counts}{also}'


def _format_median(median: float, frame_interval: float) -> str:
    if median < frame_interval:
        return f"< 1 frame ({frame_interval:g} ms)"
    return f"{median:.1f} ms"


def _median_for_agreement(cell: dict) -> float | None:
    stats = cell.get("stats")
    if not stats:
        return None
    frame_interval = cell.get("frame_interval_ms")
    median = stats["median"]
    if frame_interval and median < frame_interval:
        return frame_interval
    return median


def publication_text(cell: dict) -> str:
    if cell.get("blocked"):
        reason = cell.get("block_reason") or "run blocked"
        return f"run not publishable ({reason})"

    stats = cell.get('stats')
    scheduled = cell.get('scheduled', PUBLICATION_REPETITIONS)
    n_kept = stats['n'] if stats else 0
    # A cell that is not the decided schedule never prints a figure. p90 below
    # is reached only for that schedule, and only when exactly 10 are kept.
    if cell.get('decided_schedule') is False:
        return _wrong_schedule_text(n_kept, scheduled)
    if n_kept < PUBLICATION_MIN_KEPT:
        reasons = cell.get('refusals') or {}
        reason_text = '; '.join(f'{key}: {count}' for key, count in sorted(reasons.items())) or 'none counted'
        additional = cell.get('additional_refusals') or {}
        extra = '; also ' + '; '.join(f'{k}: {v}' for k, v in sorted(additional.items())) if additional else ''
        return f'not enough samples (n = {n_kept} of {scheduled}; reasons {reason_text}{extra})'
    failures = failure_text(cell)
    failure_suffix = f'; n = {n_kept} of {scheduled}' + (f'; {failures}' if failures else '')
    if cell.get('criterion_id') == 'C11' and cell.get('content_verified') is not True:
        failure_suffix += ' — content not verified'
    kept = cell.get('kept_ms') or []
    unit = 'bytes' if cell.get('sample_unit') == 'bytes' else 'ms'
    # A percentile of a short kept set is not stable. Print it only at exactly
    # PUBLICATION_REPETITIONS kept launches.
    spread = (
        f'range {min(kept):.1f} to {max(kept):.1f} {unit}'
        if n_kept != PUBLICATION_REPETITIONS and kept else None
    )
    if cell.get('sample_unit') == 'bytes':
        clock = spread if spread else f"p90 {stats['p90']:.1f} bytes"
        return f"{stats['median']:.1f} bytes; {clock}{failure_suffix}"
    frame_interval = cell.get('frame_interval_ms')
    if frame_interval is None:
        if cell.get('witnessed', True):
            return f'no witnessed frame interval (n = {n_kept} of {scheduled})'
        # Not a frame-witnessed clock: no interval to bucket or check against.
        clock = spread if spread else f"p90 {stats['p90']:.1f} ms"
        return f"{stats['median']:.1f} ms; {clock}{failure_suffix}"
    median = stats['median']
    share = _sub_frame_share(cell)
    share_text = f'; {share * 100:.0f}% sub-frame launches' if share is not None else ''
    clock = spread if spread else _format_p90(cell, stats['p90'], frame_interval)
    if median < frame_interval:
        return (
            f'< 1 frame ({frame_interval:g} ms){share_text}; {clock}{failure_suffix}'
        )
    return f'{median:.1f} ms{share_text}; {clock}{failure_suffix}'


def publish_dual_runs(
    primary: Path, reproduction: Path, editor_id: str, criterion_id: str, *, scheduled: int = PUBLICATION_REPETITIONS, measure: str = '', workload_id: str | None = None
) -> str:
    """Compatibility entry point; all publication gates live in the report path.

    ``scheduled`` remains accepted for callers, but the run summaries are the
    authoritative schedule. Missing/corrupt summaries raise before publication.
    """
    from build.perf_e2_tables import load_run, check_comparable, _cell_text

    first, second = load_run(primary), load_run(reproduction)
    check_comparable(first, second)
    return _cell_text({}, [first.path, second.path], editor_id, criterion_id, measure, workload_id)
