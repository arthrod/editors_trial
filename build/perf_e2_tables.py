"""Report E2: browser-lane speed tables from two ``dedicated_publish`` runs.

Reads trial JSON under each run directory (as ``browser_run`` writes) and
returns ``perf.e2.*`` facts for the template. Figures use ``e2_cells``; two
runs must agree (``reproduced``, abs_tol = witnessed frame interval).
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from perf.analysis import e2_cells
from perf.runner.browser_run import (
    PUBLICATION_MIN_KEPT,
    PUBLICATION_REPETITIONS,
    TYPING_PUBLICATION_MIN_KEPT,
    TYPING_PUBLICATION_SESSIONS,
)
from perf.scenarios.catalog import scenarios

from build.perf_e_tables import DISPLAY, REL_TOL, _SAME_HOST, _pct, reproduced

E2_CRITERIA = [f"C{i:02d}" for i in range(3, 16)] + ["C17", "C19"]
# #211: measured, in the dataset, and not printed: the reading is not what the
# criterion names. C19 reads the browser after the page closes and subtracts no
# empty-browser baseline, so it cannot be read as memory an editor retained.
E2_WITHHELD = ("C19",)


def probe_scan_text(roots, editors) -> str:
    """#206: per editor, the largest share of a C11 load that is the harness's own text read."""
    import statistics
    pairs: dict = {}
    for root in roots:
        for row in e2_cells._iter_trials(root):
            if row.get("criterion_id") != "C11" or row.get("outcome") != "measured" or row.get("editor_id") not in editors:
                continue
            scans = [s.get("probe_scan_ms_at_text") for s in ((row.get("diagnostic") or {}).get("samples") or [])
                     if isinstance(s, dict)]
            scans = [v for v in scans if isinstance(v, (int, float)) and not isinstance(v, bool)]
            loads = [v for v in (row.get("samples_ms") or []) if isinstance(v, (int, float)) and v > 0]
            if scans and loads:
                key = (row["editor_id"], e2_cells.trial_workload(row))
                pairs.setdefault(key, ([], []))
                pairs[key][0].append(statistics.median(scans))
                pairs[key][1].append(statistics.median(loads))
    if not pairs:
        return "The harness's own text read is not recorded in these runs."
    worst: dict = {}
    for (editor, workload), (scans, loads) in pairs.items():
        share = 100.0 * statistics.median(scans) / statistics.median(loads)
        if editor not in worst or share > worst[editor][0]:
            worst[editor] = (share, workload)
    names = sorted(worst, key=lambda e: DISPLAY.get(e, e).casefold())
    small = [DISPLAY.get(e, e) for e in names if worst[e][0] < 1]
    parts = ["%s %.1f percent (%s)" % (DISPLAY.get(e, e), worst[e][0], worst[e][1]) for e in names if worst[e][0] >= 1]
    if small:
        parts.append("under 1 percent for " + ", ".join(small))
    return ("Share of the C11 load that is the harness's own text read, at the document size where it is largest: "
            + "; ".join(parts) + ".")


def withheld_readings_text(aside: dict, criterion: str) -> str:
    """The range of a withheld criterion's seed medians, over the cells that reproduced."""
    medians = []
    cells_seen = 0
    for key, value in aside.items():
        if not key.endswith(".reproduced") or (".%s." % criterion) not in key or value is not True:
            continue
        prefix = key[: -len(".reproduced")]
        pair = [((aside.get("%s.%s" % (prefix, side)) or {}).get("stats") or {}).get("median")
                for side in ("primary", "reproduction")]
        if all(isinstance(v, (int, float)) for v in pair):
            cells_seen += 1
            medians += pair
    if not medians:
        return "In these runs no editor and document cell reproduced."
    return ("In these runs the seed medians of the %d editor and document cell%s that reproduced lay between "
            "%s and %s." % (cells_seen, "" if cells_seen == 1 else "s",
                            e2_cells.format_mib(min(medians)), e2_cells.format_mib(max(medians))))
REL_TOL_PCT = round(REL_TOL * 100)


@dataclass
class Run:
    path: Path
    summary: dict


def load_run(path: Path) -> Run:
    path = Path(path)
    summary = e2_cells._read_json(path / "summary.json", drop=e2_cells._SUMMARY_DROP)
    if summary.get("publishable") is True and not summary.get("publication_block_reason") and summary.get("execution_profile") != "dedicated_publish":
        raise ValueError(
            "%s is a %s run; Report E2 publishes dedicated_publish runs only"
            % (path, summary.get("execution_profile"))
        )
    return Run(path, summary)


def _run_for_root(path: Path) -> Run:
    path = Path(path)
    if (path / "summary.json").is_file():
        return load_run(path)
    jobs = e2_cells._job_roots(path)
    if not jobs:
        raise FileNotFoundError(path)
    return Run(jobs[0], e2_cells._load_summary(jobs[0]) or {})


def check_comparable(primary: Run, repro: Run) -> None:
    """A reproduction is a second run of the same measurement, nothing else.

    The host/seed/pin guards run before the run-blocked early-return: a
    blocked run is still diagnosable ("blocked repro never fails same
    seed" hid operator errors, #149).
    """
    if primary.path.resolve() == repro.path.resolve():
        raise ValueError("the reproduction is the same run directory")
    a, b = primary.summary, repro.summary
    if a["run_id"] == b["run_id"]:
        raise ValueError("the reproduction is the same run (%s)" % a["run_id"])
    if a["seed"] == b["seed"]:
        raise ValueError("the reproduction used the same seed (%s); its order would be the same" % a["seed"])
    ha, hb = (x.get("host") or {} for x in (a, b))
    if {k: ha.get(k) for k in _SAME_HOST} != {k: hb.get(k) for k in _SAME_HOST}:
        raise ValueError("the reproduction ran on another host")
    if a.get("versions") != b.get("versions"):
        raise ValueError("the reproduction attested other versions")
    ra, rb = a.get("rendering") or {}, b.get("rendering") or {}
    for key in ("browser_version", "playwright_version", "vendor", "renderer", "headless"):
        if ra.get(key) != rb.get(key):
            raise ValueError("the reproduction used other Playwright or Chromium versions")
    if a.get("host_class") != b.get("host_class"):
        raise ValueError("the reproduction used another host class")
    if a.get("execution_profile") != b.get("execution_profile"):
        raise ValueError("the reproduction used another execution profile")
    _require_same_pins(primary.path, repro.path)


_PIN_SENTINEL = object()


def _pins(root: Path, *, ran_only: bool = False) -> dict:
    """Built-editor identity per editor (#149).

    ``host_provenance.tree_sha256`` — the built editor — is the pin whenever
    present, for every lane; ``environment.editor_version`` counts only when
    it is a real pin, not the editor slug the runner stamps there. A trial
    with neither records "not recorded".
    """
    pins = {}
    for row in e2_cells._iter_trials(root):
        if ran_only and row.get("outcome") == "not_run":
            continue
        pin = e2_cells.editor_pin(row)
        pins.setdefault(row["editor_id"], set()).add(pin if pin else _PIN_SENTINEL)
    return {editor: sorted("not recorded" if value is _PIN_SENTINEL else value for value in values) for editor, values in pins.items()}


def _campaign_pins(roots) -> dict:
    """Pins from every run folder, not the first one only: a campaign spreads editors over many folders."""
    merged: dict = {}
    for root in roots:
        for editor, values in _pins(root, ran_only=True).items():
            merged.setdefault(editor, set()).update(values)
    return {editor: sorted(values) for editor, values in merged.items()}


def _pins_text(pins: dict) -> str:
    if not pins:
        return "Editor pins: not recorded."
    items = sorted(pins.items(), key=lambda item: DISPLAY.get(item[0], item[0]).casefold())
    hashes = all(re.fullmatch(r"[0-9a-f]{64}", v) or v == "not recorded" for _, values in items for v in values)
    label = "built-editor tree SHA-256" if hashes else (
        "built-editor tree SHA-256, or the editor version where no tree was recorded,")
    return "Editor pins (%s of every attempt that ran, in every run folder): %s." % (label, "; ".join(
        "%s: %s" % (DISPLAY.get(editor, editor), ", ".join(values)) for editor, values in items))


def _require_same_pins(primary: Path, repro: Path) -> None:
    """Both runs must have measured the same built editor (#149).

    Only recorded pins conflict: an editor whose trials record no identity
    refuses per launch (``pin_not_recorded`` in ``e2_cells``) rather than
    vetoing every other editor's cells.
    """
    a, b = _pins(primary), _pins(repro)
    for editor in sorted(set(a) | set(b)):
        recorded_a = set(a.get(editor, ())) - {"not recorded"}
        recorded_b = set(b.get(editor, ())) - {"not recorded"}
        if recorded_a and recorded_b and recorded_a != recorded_b:
            raise ValueError(
                "the reproduction attested other editor pins (%s: %s vs %s; built-editor tree)"
                % (editor, ", ".join(sorted(recorded_a)), ", ".join(sorted(recorded_b)))
            )


def _summary(root: Path) -> dict:
    return e2_cells._read_json(root / "summary.json", drop=e2_cells._SUMMARY_DROP)


def _scheduled(root: Path, editor: str) -> int:
    return sum(1 for _, eid in _summary(root).get("order", []) if eid == editor)


def _distinct_seeds(roots) -> list:
    values = {
        (summary or {}).get("seed")
        for root in roots
        for job in e2_cells._job_roots(Path(root))
        for summary in [e2_cells._load_summary(job)]
        if summary and summary.get("seed") is not None
    }
    return sorted(values, key=lambda seed: (seed is None, seed))


def _scheduled_sum(roots, seed_index: int, editor: str) -> int:
    seeds = _distinct_seeds(roots)
    if seed_index >= len(seeds):
        return 0
    target = seeds[seed_index]
    total = 0
    for root in roots:
        for job in e2_cells._job_roots(Path(root)):
            if e2_cells.job_superseded(job, editor):
                continue
            summary = e2_cells._load_summary(job) or {}
            if summary.get("seed") == target:
                total += e2_cells._scheduled_for_editor(summary, editor, 0)
    return total


def _editors(primary: Path, repro: Path) -> list[str]:
    ids: set[str] = set()

    def collect(root: Path) -> None:
        for job in e2_cells._job_roots(root):
            summary = e2_cells._load_summary(job) or {}
            for _, eid in summary.get("order", []) or []:
                if eid:
                    ids.add(eid)
        for row in _iter_trials(root):
            eid = row.get("editor_id")
            if eid:
                ids.add(eid)

    collect(primary)
    if repro != primary:
        collect(repro)
    return sorted(ids, key=lambda e: DISPLAY.get(e, e).casefold())


def _criteria_present(primary: Path, repro: Path) -> list[str]:
    present: set[str] = set()

    def collect(root: Path) -> None:
        for row in _iter_trials(root):
            cid = row.get("criterion_id")
            if cid in E2_CRITERIA:
                present.add(cid)

    collect(primary)
    if repro != primary:
        collect(repro)
    return sorted(present)


def _iter_trials(run_directory: Path):
    yield from e2_cells._iter_trials(run_directory)


def _format_median(cell: dict, median: float) -> str:
    if cell.get("sample_unit") == "bytes":
        return e2_cells.format_mib(median)
    suffix = " — content not verified" if cell.get("criterion_id") == "C11" and cell.get("content_verified") is not True else ""
    frame = cell.get("frame_interval_ms") or 0
    if median < frame:
        return "< 1 frame (%g ms)" % frame + suffix
    return "%.1f ms" % median + suffix


def _cell_text(facts: dict, roots, editor: str, criterion: str, measure: str = '', workload_id: str | None = None, *, word: str = 'run') -> str:
    key = 'perf.e2.%s.%s' % (editor, criterion) + ('.' + measure if measure else '') + ('.' + workload_id if workload_id else '')
    facts[key + '.reproduced'] = False
    pooled = e2_cells.read_criterion_cell(roots, editor, criterion, measure=measure, workload_id=workload_id)
    groups = pooled.get('groups') or []
    if len(groups) < 2:
        reason = pooled.get('reason') or 'two seeds required'
        facts[key + '.reason'] = reason
        return reason
    p_cell, r_cell = groups[0], groups[1]
    facts[key + '.primary'] = e2_cells.public_cell_dict(p_cell)
    facts[key + '.reproduction'] = e2_cells.public_cell_dict(r_cell)
    for label, cell in zip(('first', 'second'), groups):
        if not cell.get('scheduled'):
            reason = '%s: scheduled count not recorded' % label
            facts[key + '.reason'] = reason
            return reason
    if not pooled['published']:
        reasons = []
        for label, cell in zip(('first', 'second'), groups):
            if cell.get('blocked'):
                reasons.append(
                    '%s %s unpublishable: %s (blocked)' % (label, word, cell.get('block_reason') or 'run blocked'))
                failures = e2_cells.failure_text(cell)
                if failures:
                    reasons.append('%s: %s' % (label, failures))
            else:
                text = e2_cells.publication_text(cell)
                if 'not enough samples' in text or 'not publishable' in text or 'wrong schedule' in text:
                    reasons.append('%s: %s' % (label, text))
            if not cell.get('scheduled'):
                reasons.append('%s: scheduled count not recorded' % label)
        reason = '; '.join(reasons) if reasons else pooled['reason']
        facts[key + '.reason'] = reason
        if reason not in ('two seeds required', 'not in these runs'):
            facts.setdefault('_not_reproduced', []).append(
                (DISPLAY.get(editor, editor), criterion, workload_id or '—', measure or '—', reason, '—')
            )
        elif _scheduled_sum(roots, 0, editor) or _scheduled_sum(roots, 1, editor):
            facts.setdefault('_not_reproduced', []).append(
                (DISPLAY.get(editor, editor), criterion, workload_id or '—', measure or '—', reason, '—')
            )
        return reason
    p_text = e2_cells.publication_text(p_cell)
    frame = max(p_cell.get('frame_interval_ms') or 0, r_cell.get('frame_interval_ms') or 0)
    p_med = p_cell['stats']['median']
    r_med = r_cell['stats']['median']
    ok = reproduced(p_med, r_med, rel_tol=REL_TOL, abs_tol=frame)
    if not ok:
        facts[key + '.reason'] = 'medians outside tolerance'
        first = _format_median(p_cell, p_med)
        second = _format_median(r_cell, r_med)
        facts.setdefault('_not_reproduced', []).append((DISPLAY.get(editor, editor), criterion, workload_id or '—', measure or '—', first, second))
        failures = [
            '%s: %s' % (label, e2_cells.failure_text(cell))
            for label, cell in zip(('first', 'second'), groups)
            if cell.get('refusals')
        ]
        suffix = '; ' + '; '.join(failures) if failures else ''
        return 'not reproduced (first %s; second %s)%s' % (first, second, suffix)
    facts[key + '.reproduced'] = True
    facts[key + '.primary'] = e2_cells.public_cell_dict(p_cell, published=True)
    facts[key + '.reproduction'] = e2_cells.public_cell_dict(r_cell, published=True)
    failures = e2_cells.failure_text(r_cell)
    suffix = '; second: content not verified' if criterion == 'C11' and r_cell.get('content_verified') is not True and p_cell.get('content_verified') is True else ''
    return p_text + suffix + ('; second: ' + failures if failures else '')


def _criterion_table(facts: dict, roots, criterion: str, editors: list[str], *, word: str = 'run') -> str:
    rows = [row for root in roots for row in e2_cells._iter_trials(root) if row['criterion_id'] == criterion]
    # A lane's adapter-not-implemented stand-ins never add a row beside the
    # lane that drives the criterion (#179); alone, they still show.
    real = [row for row in rows if not e2_cells._is_placeholder_row(row)]
    groups = sorted({(e2_cells.trial_workload(row), e2_cells.trial_measure(row)) for row in (real or rows)})
    if not groups:
        return 'not in these runs.'
    has_workload = any(workload for workload, _ in groups)
    distinct = criterion in ('C14', 'C15') or any(measure for _, measure in groups)
    columns = ['Editor'] + (['Workload'] if has_workload else []) + (['Measure'] if distinct else []) + [criterion]
    lines = ['| ' + ' | '.join(columns) + ' |', '|' + '---|' * len(columns)]
    for workload, measure in groups:
        for editor in editors:
            text = _cell_text(facts, roots, editor, criterion, measure, workload, word=word)
            row = [DISPLAY.get(editor, editor)] + ([workload or 'unspecified'] if has_workload else [])
            row += ([measure or 'unspecified'] if distinct else []) + [text]
            lines.append('| ' + ' | '.join(row) + ' |')
    return "\n".join(lines)


def _not_reproduced_table(facts: dict, classic: bool = True) -> str:
    rows = facts.pop("_not_reproduced", [])
    word = "run" if classic else "seed"  # the cell comparison is first seed vs second seed
    if not rows:
        return "Every figure that was measured in both %ss reproduced." % word
    lines = [
        "| Editor | Criterion | Workload | Measure | First %s / reason | Second %s, median |" % (word, word),
        "|---|---|---|---|---|---|",
    ]
    lines += ["| %s | %s | %s | %s | %s | %s |" % r for r in rows]
    return "\n".join(lines)


def _criterion_blurbs() -> dict[str, str]:
    by_id = {row["id"]: row for row in scenarios()}
    out = {}
    for cid in E2_CRITERIA:
        row = by_id.get(cid)
        if not row:
            continue
        layer = row.get("layer", "").replace("_", " ")
        boundary = (row.get("boundary") or "").replace("_", " ")
        out[cid] = (
            "**%s (%s).** %s at the %s boundary (layer %s)."
            % (cid, row.get("title", cid), row.get("title", "").capitalize(), boundary, layer)
        )
    return out


def _host_block(summary: dict) -> str:
    h = summary.get("host") or {}
    return "%s; CPU quota %s; logical CPUs %s; OS %s %s; power %s" % tuple(
        h.get(key) if h.get(key) is not None else "not recorded"
        for key in ("cpu_model", "cpu_quota", "cpu_cores_logical", "os", "os_version", "power_source")
    )


def _machine(summary: dict | None = None) -> str:
    return (summary or {}).get("host_class") or "not recorded"


def _space_name(root: Path) -> str:
    """The Space a campaign root ran on — a machine name, never a run id.

    Farm roots are ``<space>--<run id>``; bucket roots are
    ``runs/<space>/e2/<run id>`` and their ``<space>/runs/<run id>`` mirror.
    """
    root = Path(root)
    if (root / "runs").is_dir():
        return root.name
    if root.name == "e2" and root.parent.parent.name == "runs":
        return root.parent.name
    if root.parent.name == "e2" and root.parent.parent.parent.name == "runs":
        return root.parent.parent.name
    if root.parent.name == "runs":
        if (root / "e2").is_dir():
            return root.name
        return root.parent.parent.name
    return root.name.split("--", 1)[0]


def _all_job_summaries(roots) -> list[dict]:
    rows = []
    for root in map(Path, roots):
        for job in e2_cells._job_roots(root):
            summary = e2_cells._load_summary(job)
            if summary:
                rows.append({**summary, "space": _space_name(root)})
    return rows


def check_roots_comparable(roots, *, strict_rendering: bool = True) -> None:
    """Versions and pins must match across every shard; host class must agree.

    ``strict_rendering`` keeps the browser/renderer veto for callers that
    publish a session or cell comparison directly. The campaign entry
    discloses machine fields per seed in the host note instead, because a
    publication campaign runs on many virtual machines whose browsers and
    CPUs may legitimately differ (#178).
    """
    summaries = _all_job_summaries(roots)
    if len(summaries) < 2:
        return
    first = summaries[0]
    for summary in summaries[1:]:
        if summary.get("versions") != first.get("versions"):
            raise ValueError("the reproduction attested other versions")
        if strict_rendering:
            ra, rb = first.get("rendering") or {}, summary.get("rendering") or {}
            for key in ("browser_version", "playwright_version", "vendor", "renderer", "headless"):
                if ra.get(key) != rb.get(key):
                    raise ValueError("the reproduction used other Playwright or Chromium versions")
        if summary.get("host_class") != first.get("host_class"):
            raise ValueError("the reproduction used another host class")
        if summary.get("execution_profile") != first.get("execution_profile"):
            raise ValueError("the reproduction used another execution profile")
    for index, root in enumerate(roots[1:], 1):
        _require_same_pins(Path(roots[0]), Path(root))


def _host_note(summary: dict) -> str:
    playwright, chromium, renderer = _rendering(summary)
    return ("Host class: %s. %s. Playwright %s; Chromium %s; renderer %s; headless %s. "
            "Stolen CPU time: %s. Throttle: %s. Editor pins: %s." % (
                _machine(summary), _host_block(summary), playwright, chromium, renderer,
                (summary.get("rendering") or {}).get("headless", "not recorded"),
                _steal(summary), _throttle(summary), summary.get("trial_pins", "not recorded")))


def _host_note_spaces(roots) -> str:
    """Two runs that were launched on separate virtual machines (classic case)."""
    summaries = _all_job_summaries(roots)
    if not summaries:
        return "not yet measured"
    spaces = sorted({row.get("space", "not recorded") for row in summaries})
    host_class = summaries[0].get("host_class", "not recorded")
    lines = [
        "Each seed ran on the same hardware class (%s) on separate virtual machines "
        "(Spaces %s), not on one host." % (host_class, ", ".join(spaces)),
    ]
    by_seed: dict = {}
    for row in summaries:
        by_seed.setdefault(row.get("seed"), []).append(row)
    pin_roots = [Path(root) for root in roots if e2_cells._job_roots(Path(root))]
    trial_pins = _pins(pin_roots[0]) if pin_roots else {}
    for label, seed in zip(("First", "Second"), sorted(by_seed, key=lambda value: (value is None, value))[:2]):
        row = by_seed[seed][0]
        lines.append(
            "%s seed (Space %s): %s"
            % (label, row.get("space", "?"), _host_note({**row, "trial_pins": trial_pins}))
        )
    return "\n\n".join(lines)


def _host_field(row: dict, key: str) -> str:
    value = (row.get("host") or {}).get(key)
    return "not recorded" if value is None else str(value)


def _distinct_field(rows, field) -> str:
    """The value once when every job agrees, else each value with its job count."""
    counts = Counter(field(row) for row in rows)
    if len(counts) == 1:
        return str(next(iter(counts)))
    return ", ".join(
        "%s (%d job%s)" % (value, n, "s" if n != 1 else "")
        for value, n in sorted(counts.items(), key=lambda kv: (-kv[1], str(kv[0])))
    )


def _throttle_sum(rows) -> str:
    """Throttle refusals summed over all of a seed's jobs."""
    refused = total = unavailable = refused_total = 0
    seen = refused_seen = False
    for row in rows:
        accounting = row.get("cpu_accounting") or {}
        unavailable += accounting.get("samples_unavailable") or 0
        r = row.get("cpu_throttle_refused_samples")
        if r is None:
            r = accounting.get("samples_refused")
        t = accounting.get("samples_total")
        if t is None and "order" in row:
            t = len(row["order"])
        if r is not None:
            seen = refused_seen = True
            refused += r
            refused_total += t or 0
        if accounting.get("samples_unavailable"):
            seen = True
        if t is not None:
            total += t
    if not seen:
        return "not recorded"
    if not refused_seen:
        text = "refused samples not recorded"
    elif refused_total:
        text = "%d of %d samples refused for cgroup CPU throttling" % (refused, refused_total)
        if total > refused_total:
            text += " (refusals not recorded for the other %d samples)" % (total - refused_total)
    else:
        text = "%d samples refused for cgroup CPU throttling" % refused
    if unavailable:
        text = "%d of %s samples had CPU accounting unavailable; %s" % (unavailable, total or "?", text)
    return text


def _space_note(spaces, editors) -> str:
    """A Space is a machine: a Space named for an editor did not measure it."""
    note = "A Space name is a machine name: the editors measured are those in the tables."
    known = set(DISPLAY) | {"apryse"}
    confused = sorted(
        space for space in spaces
        if (base := re.sub(r"^e2-", "", re.sub(r"-\d+$", "", space))) in known and base not in editors
    )
    if confused:
        note += " Spaces %s are machines named for editors this report does not measure." % ", ".join(confused)
    return note


def _load_text(rows) -> str:
    """The host's 1-minute load average read before and after each job (#209).

    The Spaces are containers with a CPU quota on a host shared with other tenants; no
    sample is refused for host load, so the range is disclosed next to steal and throttling.
    """
    readings = []
    missing = 0
    for row in rows:
        accounting = row.get("cpu_accounting") or {}
        for moment in ("before", "after"):
            load = (accounting.get(moment) or {}).get("loadavg")
            if isinstance(load, (list, tuple)) and load and e2_cells._number(load[0]):
                readings.append(float(load[0]))
            else:
                missing += 1
    if not readings:
        return "host load average not recorded"
    readings.sort()
    middle = len(readings) // 2
    median = readings[middle] if len(readings) % 2 else (readings[middle - 1] + readings[middle]) / 2
    text = ("host load average (1 min) at the start and end of each job: %.1f to %.1f, median %.1f"
            % (readings[0], readings[-1], median))
    if missing:  # codex review: never let a partial record read as the whole seed
        text += " (%d of %d readings not recorded)" % (missing, missing + len(readings))
    return text


def _seed_host_note(seed, rows) -> str:
    spaces = sorted({row.get("space", "?") for row in rows})
    fields = [
        ("CPU model", lambda row: _host_field(row, "cpu_model")),
        ("CPU quota", lambda row: _host_field(row, "cpu_quota")),
        ("logical CPUs", lambda row: _host_field(row, "cpu_cores_logical")),
        ("OS", lambda row: "%s %s" % (_host_field(row, "os"), _host_field(row, "os_version"))),
        ("Chromium", lambda row: _rendering(row)[1]),
        ("renderer", lambda row: _rendering(row)[2]),
        ("stolen CPU time", _steal),
    ]
    detail = "; ".join("%s %s" % (label, _distinct_field(rows, get)) for label, get in fields)
    if all(len({get(row) for row in rows}) == 1 for _, get in fields):
        detail = "all %d job%s agree: %s" % (len(rows), "s" if len(rows) != 1 else "", detail)
    return "Seed %s — %d job%s on Spaces %s: %s; throttle refusals: %s; %s." % (
        seed if seed is not None else "not recorded",
        len(rows), "s" if len(rows) != 1 else "", ", ".join(spaces), detail, _throttle_sum(rows), _load_text(rows))


def _host_note_campaign(roots, editors) -> str:
    """Per seed, the distinct machines all of its campaign jobs ran on (#178)."""
    summaries = _all_job_summaries(roots)
    if not summaries:
        return "not yet measured"
    spaces = sorted({row.get("space", "not recorded") for row in summaries})
    host_class = summaries[0].get("host_class", "not recorded")
    lead = (
        "Each seed ran on the same hardware class (%s) on separate virtual machines "
        "(Spaces %s), not on one host. %s"
        % (host_class, ", ".join(spaces), _space_note(spaces, editors))
    )
    by_seed: dict = {}
    for row in summaries:
        by_seed.setdefault(row.get("seed"), []).append(row)
    pin_roots = [Path(root) for root in roots if e2_cells._job_roots(Path(root))]
    trial_pins = _campaign_pins(pin_roots)
    lines = [lead]
    lines.extend(_seed_host_note(seed, by_seed[seed]) for seed in sorted(by_seed, key=lambda value: (value is None, value)))
    lines.append(_pins_text(trial_pins))
    return "\n\n".join(lines)


def _steal(summary: dict) -> str:
    v = summary.get("cpu_steal_percent")
    if v is None:
        acct = summary.get("cpu_accounting") or {}
        v = acct.get("steal_percent")
    if v is None:
        return "not recorded"
    return _pct(v)


def _throttle(summary: dict) -> str:
    accounting = summary.get("cpu_accounting") or {}
    unavailable = accounting.get("samples_unavailable")
    if unavailable:
        return "%s of %s samples had CPU accounting unavailable; %s refused for cgroup CPU throttling" % (unavailable, accounting.get("samples_total", "?"), accounting.get("samples_refused", "not recorded"))
    refused = summary.get("cpu_throttle_refused_samples")
    if refused is None:
        refused = (summary.get("cpu_accounting") or {}).get("samples_refused")
    total = (summary.get("cpu_accounting") or {}).get("samples_total")
    if total is None and "order" in summary:
        total = len(summary["order"])
    if refused is None:
        return "not recorded"
    if total is not None:
        return "%d of %d samples refused for cgroup CPU throttling" % (refused, total)
    return "%d samples refused for cgroup CPU throttling" % refused


def _rendering(summary: dict) -> tuple[str, str, str]:
    r = summary.get("rendering") or {}
    tools = (summary.get("versions") or {}).get("tools") or {}
    playwright = r.get("playwright_version") or tools.get("playwright") or "not recorded"
    chromium = r.get("browser_version") or "not recorded"
    renderer = r.get("renderer") or "not recorded"
    return playwright, chromium, renderer


def _not_run_editors(primary: Path, repro: Path, editors: list[str]) -> str:
    lines = []
    for editor in editors:
        for criterion in E2_CRITERIA:
            p = e2_cells.build_run_cell(primary, editor, criterion, scheduled=_scheduled_sum([primary], 0, editor))
            if p.get("stats"):
                continue
            refusals = p.get("refusals") or {}
            if not refusals:
                continue
            top = max(refusals, key=refusals.get)
            if refusals.get(top, 0) >= 1:
                lines.append("- **%s, %s:** %s (%d attempts)." % (
                    DISPLAY.get(editor, editor), criterion, top, refusals[top]))
                break
    return "\n".join(lines) if lines else "- none"


# Why a roster editor has no browser data. Each reason is a standing decision
# of the trial, not a measurement; an editor not listed here says so plainly.
E2_NOT_MEASURED = {
    "apryse": "Apryse WebViewer needs a licence key, and the key is never placed on the measuring machines.",
    "docsplus": "docs.plus runs only as an application with its own application servers, which the browser run does not start.",
    "fidus": "Fidus Writer runs only as an application with its own application server, which the browser run does not start.",
    "office-open": "office-open is a library with no editing surface to paint, so no browser criterion applies.",
    "libreoffice": "LibreOffice is the conversion baseline of the headless report, not a browser editor.",
}


def _not_measured_campaign(editors: list[str]) -> str:
    """Roster editors with no browser data across every run folder of the campaign."""
    from perf.adapters.capabilities import LANES

    measured = set(editors)
    lines = []
    for editor in sorted(set(LANES) - measured, key=lambda e: (E2_DISPLAY.get(e) or e).casefold()):
        reason = E2_NOT_MEASURED.get(editor, "no browser data in these runs.")
        lines.append("- **%s:** %s" % (E2_DISPLAY.get(editor) or editor, reason))
    return "\n".join(lines) if lines else "- none"


E2_DISPLAY = {**DISPLAY, "apryse": "Apryse"}


def _date(summary: dict) -> str:
    for key in ("started_at", "finished_at"):
        if summary.get(key):
            return str(summary[key])[:10]
    return "not recorded"


_RUN_STAMP_DAY = re.compile(r"^(\d{4})(\d{2})(\d{2})T\d{6}")


def _job_days(summary: dict) -> tuple[str | None, str | None]:
    """The (start, end) days a job summary records: explicit ``started_at`` /
    ``finished_at`` instants, else the UTC stamp its ``run_id`` carries —
    the only recorded instant a publication job leaves."""
    stamp = _RUN_STAMP_DAY.match(str(summary.get("run_id") or ""))
    stamped = "%s-%s-%s" % stamp.groups() if stamp else None
    start = str(summary["started_at"])[:10] if summary.get("started_at") else stamped
    end = str(summary["finished_at"])[:10] if summary.get("finished_at") else stamped
    return start, end


def _campaign_view(roots) -> dict:
    """A campaign's inventory, read from its job summaries: jobs per seed and
    the earliest job start / latest job end day."""
    summaries = _all_job_summaries(roots)
    by_seed: dict = {}
    starts, ends = [], []
    for row in summaries:
        by_seed.setdefault(row.get("seed"), []).append(row)
        start, end = _job_days(row)
        if start:
            starts.append(start)
        if end:
            ends.append(end)
    return {
        "summaries": summaries,
        "by_seed": by_seed,
        "seeds": sorted(by_seed, key=lambda value: (value is None, value)),
        "jobs": len(summaries),
        "start": min(starts) if starts else None,
        "end": max(ends) if ends else None,
    }


def _seed_job_counts(campaign: dict) -> str:
    return "; ".join(
        "seed %s: %d job%s" % (
            seed if seed is not None else "not recorded",
            len(campaign["by_seed"][seed]),
            "s" if len(campaign["by_seed"][seed]) != 1 else "")
        for seed in campaign["seeds"])


def _runs_fact(primary: Run, repro: Run, campaign: dict | None, roots) -> str:
    """The template's run line: the two-run sentence classically; the campaign
    inventory — jobs per seed, run folders, date range — in a campaign."""
    if campaign is None:
        s, r = primary.summary, repro.summary
        return (
            "Primary run `%s`, seed %s (%s). Reproduction run `%s`, seed %s (%s)."
            % (s.get("run_id", "not recorded"), s.get("seed", "—"), _date(s),
               r.get("run_id", "not recorded"), r.get("seed", "—"), _date(r)))
    first = campaign["start"] or "not recorded"
    last = campaign["end"] or "not recorded"
    dates = first if first == last else "%s to %s" % (first, last)
    return (
        "%d jobs in %d run folders — %s. Dates: %s."
        % (campaign["jobs"], len(roots), _seed_job_counts(campaign) or "no jobs recorded", dates))


# Per editor-round issue: which cells its runs measured again, and why (#185, #190).
EDITOR_ROUND_REASONS = {
    "185": ("%(jobs)d document jobs (C11 and C14, with C12 and C15 of the same jobs)",
            "after its load timing was found to stop at its empty page, before the document was imported"),
    "190": ("the %(jobs)d %(workload)s document jobs (C11 and C12, with C15 of the same jobs)",
            "after the document lane was found to wait 300 seconds for each load, reflow and find probe of that "
            "workload instead of its 600-second load timeout"),
    "193": ("the %(jobs)d document jobs below the 500k rung (C11, with C12 and C15 of the same jobs)",
            "after its C11 was found to compare its settled screen with its ready flag on two different clocks, "
            "which refused every attempt"),
    "193-extension": ("the %(jobs)d %(workload)s document jobs of the 500k rung (C11, with C12 and C15 of the "
                      "same jobs)",
                      "after its C11 was found to compare its settled screen with its ready flag on two different "
                      "clocks; the 500k rung had run before that fix"),
    "196/benchmark_warm_cold": (
        "the %(jobs)d warm and cold load jobs (C03, with C05 and C06 of the same jobs)",
        "after its opening check was found never to read WordCraft's text, although the harness reads the whole "
        "document through WordCraft's own select all and copy; every C03 attempt had been refused as unverifiable"),
    "196": ("the %(jobs)d document jobs below the 500k rung (C11, with C12 and C15 of the same jobs)",
            "after its C11 content check was found never to read WordCraft's text through WordCraft's own select "
            "all and copy, which refused every attempt as unverifiable"),
    "196-extension": ("the %(jobs)d %(workload)s document jobs of the 500k rung (C11, with C12 and C15 of the "
                      "same jobs)",
                      "after its C11 content check was found never to read WordCraft's text through WordCraft's "
                      "own select all and copy; the 500k rung had run before that fix"),
    "196-c14": ("the %(jobs)d %(workload)s C14 jobs of the 500k rung",
                "so that one harness measures all of WordCraft's 500k cells; the #196 fix does not change C14, "
                "which already read WordCraft's text through its own select all and copy"),
    "197": ("the %(jobs)d input jobs (C08 and C09, with C07 of the same jobs)",
            "after C08 and C09 were found to be skipped as not applicable because WordCraft shows no text in the "
            "page, although its own select all and copy reads the document before and after each edit"),
    "198": ("the %(jobs)d C10 scroll jobs",
            "after C10 was found never to scroll WordCraft's document: the host's scroll overlay, built for this "
            "probe, was never selected, so every attempt found no scroll container"),
    "202/benchmark_input": (
        "the %(jobs)d %(workload)s input jobs (C08 and C09, with C04 and C07 of the same jobs)",
        "after the screencast recorder was found to stop seeing new frames once it held 1,200, so the page "
        "clock could not be proven and every C08 and C09 attempt was refused"),
    "202-extension": (
        "the %(jobs)d jobs of the 500k rung (C11 and C14, with C12 and C15 of the same jobs)",
        "after the screencast recorder was found to stop seeing new frames once it held 1,200, so the page "
        "clock could not be proven and every C11 and C14 attempt was refused"),
    "203": ("the %(jobs)d %(workload)s C14 jobs of the 500k rung",
            "after C14's damage window was found to accept frames recorded minutes after it closed, while the "
            "page kept the harness waiting; the window now counts only frames inside it"),
    "194": ("the %(jobs)d %(workload)s memory jobs (C17 and C19)",
            "after the memory pair's deadline was found to cover one load where the pair runs two loads and a "
            "120-character burst"),
}


# Per lane-round issue (#208): the defect that touched every editor of the lane.
LANE_ROUND_REASONS = {
    "206": "The document probe's own scan for the opening headings grew with the square of the page and ran "
           "inside the timed load: in the Chrome traces of the replaced jobs it took about 19 minutes of a "
           "250,000-word Plate.js load whose own scripts ran about 21 seconds (issue #206)",
    "207": "C08 took the frame in which an editor redrew its own caret for the pasted text, and WordCraft's C09 "
           "did the same for an undo: a caret changes 16 to 58 pixels, a painted paste 677 or more, and the "
           "criteria now wait for a frame that changes at least 100 (issue #207)",
}
LANE_NAMES = {"benchmark_document": "document", "benchmark_input": "input", "benchmark_memory": "memory",
              "benchmark_warm_cold": "warm and cold load", "adversarial_c10_scroll": "C10 scroll",
              "benchmark_typing": "typing", "benchmark_resources": "resources"}


def _lane_round_text(campaign: dict) -> str:
    rounds = campaign.get("lane_rounds") or []
    if not rounds:
        return ""
    lanes = ["of the %s lane (%d jobs)" % (LANE_NAMES.get(r["lane"], r["lane"]), r["jobs"]) for r in rounds]
    reasons = [LANE_ROUND_REASONS.get(str(r["issue"]), "A harness defect was fixed (issue #%s)" % r["issue"])
               for r in rounds]
    count = len(rounds)
    return (
        " In a lane round, every job %s was measured again for every editor, interleaved as in the campaign, "
        "after %s that touched every editor %s fixed. %s. For %s the tables read the %d lane-round jobs only; "
        "every earlier measurement of %s is replaced."
        % (" and ".join(lanes), "a harness defect" if count == 1 else "%s harness defects" % {2: "two", 3: "three"}.get(count, count),
           "was" if count == 1 else "were", ". ".join(reasons),
           "that lane" if count == 1 else "those lanes", campaign.get("lane_rerun_kept") or 0,
           "it" if count == 1 else "them"))


def reruns_text(campaign: dict | None) -> str:
    """The template's re-run bullet, from report_e2_runs.json's campaign counts."""
    if not campaign:
        return "- **Re-run jobs.** None: the tables read every job of these runs."
    superseded = campaign.get("first_pass_superseded") or 0
    kept = campaign.get("rerun_kept") or 0
    # A lane round (#208) replaced every earlier job of its lanes: for those the history is told, and
    # only the lane round is what the tables read.
    lane_lanes = {r["lane"] for r in campaign.get("lane_rounds") or []}
    text = (
        "- **Re-run jobs.** %d first-pass jobs were measured again after three harness defects were fixed "
        "(issues #173, #174 and #175)." % superseded)
    if not lane_lanes:
        text += " The tables read the %d re-run jobs in their place and never the superseded ones." % kept
    elif kept:
        text += (" The tables read %d of those re-run jobs, never the superseded ones; the lane round below "
                 "replaced the others." % kept)
    else:
        text += " The lane round below replaced those re-run jobs in turn."
    text += " `perf/container/e2_publication.json` names every run and every replaced job."
    second = campaign.get("rerun_superseded") or 0
    third = campaign.get("rerun2_superseded") or 0
    if second and third and lane_lanes and not (campaign.get("rerun3_kept") or 0):
        text += (
            " In a second round, %d C14 jobs of the re-run were measured again after the C14 correctness check "
            "was fixed (issue #181). In a third round, those %d C14 jobs were measured again after C14 was given "
            "the editor's own whole-document read and a 1,000-second load timeout (issues #183 and #184)."
            % (second, third))
    elif second and third:
        text += (
            " In a second round, %d C14 jobs of the re-run were measured again after the C14 correctness check "
            "was fixed (issue #181). In a third round, those %d C14 jobs were measured again after C14 was given "
            "the editor's own whole-document read and a 1,000-second load timeout (issues #183 and #184); the "
            "tables read the %d third-round jobs, never the superseded ones."
            % (second, third, campaign.get("rerun3_kept") or 0))
    elif second and lane_lanes and not (campaign.get("rerun2_kept") or 0):
        text += (
            " In a second round, %d C14 jobs of the re-run were measured again after the C14 correctness check "
            "was fixed (issue #181)." % second)
    elif second:
        text += (
            " In a second round, %d C14 jobs of the re-run were measured again after the C14 correctness check "
            "was fixed (issue #181); the tables read the %d second-round jobs in their place."
            % (second, campaign.get("rerun2_kept") or 0))
    rounds = campaign.get("editor_rounds")
    if rounds is None:  # report_e2_runs.json written before #190 names only the editor and its job count
        rounds = [{"issue": "185", "editor": editor, "jobs": jobs, "workload": None}
                  for editor, jobs in sorted((campaign.get("editor_superseded") or {}).items())]
    def reason_key(entry: dict):
        # The wording may be the manifest key's own (#196's C14 round), else differ by lane (#196: warm/cold
        # and document) and for the 500k rung, else the issue's.
        issue = str(entry["issue"])
        keys = ([str(entry["key"])] if entry.get("key") else []) + (
            [issue + "-extension"] if entry.get("extension") else []) + ["%s/%s" % (issue, entry.get("lane")), issue]
        return next((k for k in keys if k in EDITOR_ROUND_REASONS), None)

    # One round that measured several editors in the same runs (#194: Docen and canvas-editor) is one sentence;
    # two rounds of one issue with different wording (#196 at 500k) never are.
    grouped: list[tuple[dict, list[str]]] = []
    for entry in rounds:
        name = {"canvas": "canvas-editor"}.get(entry["editor"], DISPLAY.get(entry["editor"], entry["editor"]))
        same = ("issue", "jobs", "lane", "workload", "extension")
        if (grouped and all(str(grouped[-1][0].get(k)) == str(entry.get(k)) for k in same)
                and reason_key(grouped[-1][0]) == reason_key(entry) and name not in grouped[-1][1]):
            grouped[-1][1].append(name)
        else:
            grouped.append((entry, [name]))
    # Rounds of a lane the lane round replaced: one sentence of history, by editor and issue.
    replaced: dict[str, list[str]] = {}
    for entry, names in grouped:
        if entry.get("lane") in lane_lanes:
            for name in names:
                issues = replaced.setdefault(name, [])
                if "#%s" % entry["issue"] not in issues:
                    issues.append("#%s" % entry["issue"])
    if replaced:
        text += (
            " Then single editors' cells of those lanes were measured again alone, each after a change in how "
            "the harness measured that editor: %s. The lane round replaced those cells."
            % "; ".join("%s (%s %s)" % (name, "issue" if len(issues) == 1 else "issues", ", ".join(issues))
                        for name, issues in replaced.items()))
    for entry, names in grouped:
        if entry.get("lane") in lane_lanes:
            continue
        both = " and ".join(names)
        owners = " and ".join(name + "'s" for name in names)
        key = reason_key(entry)
        cells, reason = EDITOR_ROUND_REASONS[key] if key else ("%(jobs)d jobs", "after a harness defect was fixed")
        text += (
            " Then %s cells of %s were measured again %s (issue #%s). Those runs measured %s alone, under the "
            "same job indices and seeds; the tables read them for %s, and the other editors of those jobs stay "
            "as measured."
            % (owners, cells % {"jobs": entry["jobs"], "workload": entry.get("workload")}, reason, entry["issue"],
               both, both))
    late = campaign.get("late_superseded") or 0
    if late:
        text += (
            " In a late round, the %d C10 jobs on the complex document were measured again for every editor after C10 was "
            "found to load that document with its document protection, which GenOffice and eigenpal honour by "
            "opening it read-only, so C10 never started for them; it now loads the unprotected copy the editing "
            "criteria load (issue #192). The tables read the %d late-round jobs in their place."
            % (late, campaign.get("late_rerun_kept") or 0))
    text += _lane_round_text(campaign)
    unsealed = sum(campaign.get(key) or 0 for key in
                   ("first_pass_unsealed", "rerun_unsealed", "rerun2_unsealed", "rerun3_unsealed",
                    "editor_rerun_unsealed", "late_rerun_unsealed", "lane_rerun_unsealed"))
    missing = len(campaign.get("missing_runs") or [])
    stopped = campaign.get("editor_rerun_stopped") or 0
    if stopped:  # 14 Nov rebalancing: a job cut off when its work moved to another Space
        text += (" %d editor-round %s stopped part-way when %s work moved to another Space; each was measured "
                 "whole there, and the tables never read the stopped parts."
                 % (stopped, "job was" if stopped == 1 else "jobs were", "its" if stopped == 1 else "their"))
    if unsealed:
        text += " %d %s not sealed and %s left out." % (
            unsealed, "re-run job was" if unsealed == 1 else "jobs were", "is" if unsealed == 1 else "are")
    if missing:
        text += " %d %s of the manifest %s missing." % (missing, "run" if missing == 1 else "runs", "is" if missing == 1 else "are")
    return text


WORD_VERIFICATION = (
    "The DOCX twin is a deliverable of the release gate: `build/verify_publication.sh --with-word` opens it "
    "in Microsoft Word and fails on any warning or offer to repair the file.")


def unset_facts() -> dict:
    """Facts when ``report_e2_runs.json`` is absent: the template still renders."""
    blurbs = _criterion_blurbs()
    facts = {
        "perf.e2.provenance": "Per-Space provenance not supplied.",
        "perf.e2.reruns": reruns_text(None),
        "perf.e2.table.TYPING": "not in these runs.",
        "perf.e2.word_verification": WORD_VERIFICATION,
        "perf.e2.measured": "not yet measured",
        "perf.e2.status": "This report is not yet measured.",
        "perf.e2.short_version": "not yet measured",
        "perf.e2.intro": "No browser runs are available; not yet measured.",
        "perf.e2.machine": _machine(),
        "perf.e2.host": "not yet measured",
        "perf.e2.host_class": "not yet measured",
        "perf.e2.host_note": "not yet measured",
        "perf.e2.rule": "not yet measured",
        "perf.e2.runs": "not yet measured",
        "perf.e2.run_id": "not yet measured",
        "perf.e2.repro_run_id": "not yet measured",
        "perf.e2.seed": "—",
        "perf.e2.repro_seed": "—",
        "perf.e2.date": "not yet measured",
        "perf.e2.repro_date": "not yet measured",
        "perf.e2.steal": "not yet measured",
        "perf.e2.throttle": "not yet measured",
        "perf.e2.renderer": "not yet measured",
        "perf.e2.playwright": "not yet measured",
        "perf.e2.chromium": "not yet measured",
        "perf.e2.cells_checked": 0,
        "perf.e2.cells_reproduced": 0,
        "perf.e2.not_run": "- none",
        "perf.e2.not_reproduced": "not yet measured",
        "perf.e2.reproduce": "See perf/container/README.md.",
        "perf.e2.rel_tol_pct": REL_TOL_PCT,
        "perf.e2.relaxed_bounds": __import__("perf.runner.lax_bounds", fromlist=["relaxed_bounds_paragraph"]).relaxed_bounds_paragraph(),
        "perf.e2.sample_plan": __import__("perf.runner.lax_bounds", fromlist=["publication_sample_paragraph"]).publication_sample_paragraph(),
        "perf.e2.typing_sample_plan": __import__("perf.runner.lax_bounds", fromlist=["typing_sample_paragraph"]).typing_sample_paragraph(),
        "perf.e2.scheduled": PUBLICATION_REPETITIONS,
    }
    for cid in E2_CRITERIA:
        facts["perf.e2.criterion.%s" % cid] = blurbs.get(cid, cid)
        facts["perf.e2.table.%s" % cid] = "not yet measured"
    for cid in E2_WITHHELD:
        facts["perf.e2.withheld.%s" % cid] = "not yet measured"
    facts["perf.e2.probe_scan"] = "not yet measured"
    facts["perf.e2.criterion.B8"] = RESOURCES_BLURB
    facts["perf.e2.table.B8"] = "not yet measured"
    return facts


def legacy_snapshot_facts(facts: dict) -> dict:
    """A pre-E2 snapshot has no browser measurements, never implicit numbers.

    Partial E2 snapshots remain strict: missing fields indicate corrupt or
    stale measurement evidence and must still fail rendering.
    """
    if any(key.startswith('perf.e2.') for key in facts):
        return facts
    return {**unset_facts(), **facts}


def facts_from_runs(primary_dir: Path, repro_dir: Path) -> dict:
    return facts_from_roots([primary_dir, repro_dir])


def _require_campaign_roots(roots) -> list[Path]:
    if not isinstance(roots, list):
        raise TypeError('report_e2_runs.json "roots" must be a list of campaign directories')
    if not roots:
        raise ValueError('report_e2_runs.json "roots" must name at least one campaign directory')
    resolved = []
    for root in roots:
        path = Path(root)
        if not path.is_dir():
            raise FileNotFoundError('campaign root does not exist: %s' % path)
        if not e2_cells._job_roots(path):
            raise ValueError('no measured jobs under %s' % path)
        resolved.append(path)
    return resolved


def facts_from_roots(roots, superseded_cells=None) -> dict:
    # Directory listings are memoised for the duration of one call only, so a
    # file added before the next call is always seen (#176).
    # ``superseded_cells``: an editor's cells of some jobs, measured again by
    # later runs under the same job indices (#185); the old rows are not read.
    with e2_cells._listing_scope(), e2_cells.superseded_cells(superseded_cells):
        return _facts_from_roots(roots)


def _facts_from_roots(roots) -> dict:
    roots = _require_campaign_roots(roots)
    classic = len(roots) == 2 and all((root / "summary.json").is_file() for root in roots)
    if classic:
        primary, repro = load_run(roots[0]), load_run(roots[1])
        try:
            check_comparable(primary, repro)
        except ValueError:
            raise
    else:
        check_roots_comparable(roots, strict_rendering=False)
    editors = sorted({
        eid
        for root in roots
        for eid in _editors(root, root)
    }, key=lambda e: DISPLAY.get(e, e).casefold())
    criteria = sorted({
        cid
        for root in roots
        for cid in _criteria_present(root, root)
    })
    primary = _run_for_root(roots[0]) if roots else Run(Path("."), {})
    repro = _run_for_root(roots[1]) if len(roots) > 1 else primary
    s = primary.summary if roots else {}
    campaign = None if classic else _campaign_view(roots)
    kept_clause = (
        "Both runs must keep at least %d launches per cell"
        if classic else
        "Each of the two seeds must keep at least %d launches per cell, its launches pooled across the campaign's run folders"
    ) % PUBLICATION_MIN_KEPT
    playwright, chromium, renderer = _rendering(s)
    facts: dict = {
        "perf.e2.provenance": "Per-Space provenance not supplied.",
        "perf.e2.table.TYPING": "not in these runs.",
        "perf.e2.word_verification": WORD_VERIFICATION,
        "perf.e2.measured": "measured",
        "perf.e2.status": "",
        "perf.e2.run_id": s.get("run_id", "not recorded"),
        "perf.e2.repro_run_id": repro.summary.get("run_id", "not recorded"),
        "perf.e2.seed": s.get("seed", "—"),
        "perf.e2.repro_seed": repro.summary.get("seed", "—"),
        "perf.e2.date": _date(s),
        "perf.e2.repro_date": _date(repro.summary),
        "perf.e2.machine": _machine(s),
        "perf.e2.host": _host_block(s),
        "perf.e2.host_class": s.get("host_class", "?"),
        "perf.e2.runs": _runs_fact(primary, repro, campaign, roots),
        "perf.e2.host_note": (
            _host_note_campaign(roots, editors)
            if campaign is not None
            else _host_note_spaces(roots)
            if len({_space_name(root) for root in roots}) > 1 or any((Path(root) / "runs").is_dir() for root in roots)
            else "First run: " + _host_note({**s, "trial_pins": _pins(primary.path)})
            + "\n\nSecond run: " + _host_note({**repro.summary, "trial_pins": _pins(repro.path)})
        ),
        "perf.e2.steal": _steal(s),
        "perf.e2.throttle": _throttle(s),
        "perf.e2.renderer": renderer,
        "perf.e2.playwright": playwright,
        "perf.e2.chromium": chromium,
        "perf.e2.scheduled": {
            "primary": {e: _scheduled_sum(roots, 0, e) for e in editors},
            "reproduction": {e: _scheduled_sum(roots, 1, e) for e in editors},
        },
        "perf.e2.rel_tol_pct": REL_TOL_PCT,
        "perf.e2.relaxed_bounds": __import__("perf.runner.lax_bounds", fromlist=["relaxed_bounds_paragraph"]).relaxed_bounds_paragraph(),
        "perf.e2.sample_plan": __import__("perf.runner.lax_bounds", fromlist=["publication_sample_paragraph"]).publication_sample_paragraph(),
        "perf.e2.typing_sample_plan": __import__("perf.runner.lax_bounds", fromlist=["typing_sample_paragraph"]).typing_sample_paragraph(),
        "perf.e2.rule": (
            "Each launch contributes the median of its own samples; n counts kept launches. "
            "Scheduled counts come from each run's order. Publishability is decided per trial — job "
            "summaries delegate it to their trials — and a cell publishes only from trials that are "
            "publishable and record the built editor's identity (host_provenance.tree_sha256, else a "
            "pinned editor_version); a trial recording neither is refused as pin not recorded, and a "
            "reproduction across different built-editor trees is refused. " + kept_clause +
            ", and a run-level block — a shakedown run, dirty repos, unavailable "
            "CPU accounting or a failed run — refuses the whole run. "
            "The medians must agree within 10 percent of the larger median or the larger witnessed frame interval. "
            "Samples of frame-witnessed criteria require complete boolean flags checked against a witnessed interval; "
            "model-layer clocks such as C04 and byte counts publish without them, and sub-frame medians are buckets; "
            f"p90 is printed only when at least {PUBLICATION_REPETITIONS} launches are kept; "
            f"with {PUBLICATION_MIN_KEPT} to {PUBLICATION_REPETITIONS - 1} kept, the table prints the median and the range. "
            "p90 is over launch medians. C14 rungs and C14 measures (presented_frame, usable_no_damage) and C15 steps "
            "are separate measures; a no-damage C14 sample is the DOM document-surface time, never a compositor frame."
        ),
        "perf.e2.reproduce": "See perf/container/README.md.",
    }
    blurbs = _criterion_blurbs()
    for cid in E2_CRITERIA:
        facts["perf.e2.criterion.%s" % cid] = blurbs.get(cid, cid)
    for cid in E2_WITHHELD:
        facts["perf.e2.withheld.%s" % cid] = "In these runs no editor and document cell reproduced."
    for cid in criteria:
        if cid in E2_WITHHELD:
            # Read aside: no cell fact, no "not reproduced" row, no table.
            aside: dict = {}
            _criterion_table(aside, roots, cid, editors, word="run" if classic else "seed")
            facts["perf.e2.withheld.%s" % cid] = withheld_readings_text(aside, cid)
            facts["perf.e2.table.%s" % cid] = "not published."
            continue
        facts["perf.e2.table.%s" % cid] = _criterion_table(facts, roots, cid, editors, word="run" if classic else "seed")
    for cid in E2_CRITERIA:
        facts.setdefault("perf.e2.table.%s" % cid, "not in these runs.")
    typing_groups = sorted({(row['editor_id'], row.get('session_kind'))
                            for root in roots for row in _iter_trials(root)
                            if row['criterion_id'] == 'TYPING' and row.get('session_kind') in ('throughput', 'latency')})
    if typing_groups:
        facts['perf.e2.table.TYPING'] = '\n\n'.join(typing_table(facts, roots, editor, kind) for editor, kind in typing_groups)
    facts.update(resource_facts(roots, editors))
    facts["perf.e2.probe_scan"] = probe_scan_text(roots, editors)
    # #227: the short version reads the cells the tables above just decided.
    from build import perf_e2_summary
    facts["perf.e2.short_version"] = perf_e2_summary.short_version(facts, editors, DISPLAY)
    facts["perf.e2.not_run"] = (
        _not_run_editors(roots[0], roots[-1], editors) if classic else _not_measured_campaign(editors))
    facts["perf.e2.not_reproduced"] = _not_reproduced_table(facts, classic)
    facts["perf.e2.reruns"] = reruns_text(None)
    published = [k for k in facts if k.endswith(".reproduced")]
    facts["perf.e2.cells_checked"] = len(published)
    facts["perf.e2.cells_reproduced"] = sum(1 for k in published if facts[k])
    if campaign is None:
        facts["perf.e2.intro"] = "%d of %d scheduled editor/criterion/measure cells reproduced between the two runs. Dates: first %s; second %s." % (
            facts["perf.e2.cells_reproduced"], facts["perf.e2.cells_checked"], _date(s), _date(repro.summary))
    else:
        facts["perf.e2.intro"] = (
            "%d of %d scheduled editor/criterion/measure cells reproduced between %s. "
            "%d run folders contributed %d jobs (%s); earliest job start %s, latest job end %s."
            % (
                facts["perf.e2.cells_reproduced"], facts["perf.e2.cells_checked"],
                "the two seeds" if len(campaign["seeds"]) == 2 else "the seeds",
                len(roots), campaign["jobs"], _seed_job_counts(campaign),
                campaign["start"] or "not recorded", campaign["end"] or "not recorded"))
        if any(row.get("hosts") for row in campaign["summaries"]):
            counts = Counter(row.get("space", "not recorded") for row in campaign["summaries"])
            facts["perf.e2.provenance"] = (
                "Jobs per Space, from each job summary's host-build records: "
                + "; ".join("%s: %d" % item for item in sorted(counts.items())) + ".")
    return facts


RESOURCES_BLURB = (
    "**B8 — resources while opening and editing.** One fresh browser per launch opens the document, waits "
    "until the editor is idle, types sixteen characters into a body line on the first screen, and waits "
    "again. CPU is the processor time of the whole browser process tree: to open (from navigation until "
    "idle, including work an editor does after it reports ready), during the edit (the keystrokes plus "
    "half a second), and while settling afterwards. The memory column is the highest reading of that tree's "
    "resident memory: it is read when the load and the edit start and end and every half second while the "
    "page settles, so a higher moment in the middle of a long load or edit is not seen; a page shared by two "
    "processes counts once for each. An "
    "edit counts only when it is verified in the document: the text of the block at the caret, read from "
    "the page or from the editor's model, gained exactly the typed text; WordCraft, which puts no document text in the page, "
    "is verified by its own modified flag. An editor still working when a 30-second cap ends "
    "never went idle, even in one launch: the CPU columns that wait would end are not printed, because they would time the cap, and a note gives "
    "what it used up to its ready signal, how far its memory readings ran and, where every kept launch recorded its "
    "processes, how the capped wait divides between the browser's GPU process (the one that draws; on this host it "
    "draws in software) and the page's own process. "
    "The complex document is loaded without its read-only protection, which the editors honour."
)


def resource_facts(roots, editors) -> dict:
    """The B8 section: every seed's launches from every run directory given."""
    from perf.analysis import e2_resources
    facts: dict = {"perf.e2.criterion.B8": RESOURCES_BLURB}
    table = e2_resources.resources_tables(facts, roots, editors, DISPLAY)
    # #226: said once, under the tables, with the counts of these runs.
    facts["perf.e2.table.B8"] = table + "\n\n" + e2_resources.settle_window_note(facts)
    return facts


def fmt_resource(value, unit="bytes") -> str:
    """Render resource markers without converting absence into a numeric zero."""
    if isinstance(value, dict):
        if value.get('marker') == 'not_available_on_platform':
            reason = value.get('reason')
            return 'not available on this platform' + (f' ({reason})' if reason else '')
        return 'not recorded'
    if value == 'not_applicable_endpoint':
        return 'not applicable at this endpoint'
    if value == 'not_available_on_platform':
        return 'not available on this platform'
    if not e2_cells._number(value):
        return 'not recorded'
    if unit == 'bytes':
        return f'{value / 1024:.1f} KiB' if abs(value) >= 1024 else f'{value:g} B'
    return f'{value:g} {unit}'


def _typing_job_of(job, summary, editor, kind) -> bool:
    """A typing cell reads only the typing jobs of its editor and session kind (#180).

    A campaign run folder holds jobs of every lane; pooling them gave a typing
    cell other lanes' schedules and other editors' failure reasons.
    """
    lane = job.parent.name if job.parent.name.startswith(('benchmark_', 'adversarial_')) else None
    if (summary.get('runner') or lane) not in (None, 'benchmark_typing'):
        return False
    if summary.get('session_kind') not in (None, kind):
        return False
    order = summary.get('order') or []
    return not order or any(entry[1] == editor for entry in order)


def _typing_group_for_seed(roots, editor, kind, seed):
    from perf.analysis import e2_cells
    from perf.analysis.e2_typing import _sessions_from_jobs

    job_pairs = []
    for root in roots:
        root = Path(root)
        for job in e2_cells._job_roots(root):
            summary = e2_cells._load_summary(job) or {}
            if summary.get('seed') not in (None, seed):
                continue
            if not _typing_job_of(job, summary, editor, kind):
                continue
            if summary.get('order') or (job / 'cells').is_dir():
                job_pairs.append((root, job))
    if not job_pairs:
        return dict(scheduled=0, kept=[], refusals={}, blocked=True, block_reason="not in these runs", progress=[], seed=seed)
    group = _sessions_from_jobs(job_pairs, editor, kind)
    group["seed"] = seed
    return group


_TYPING_FIGURE_FIELDS = frozenset({'kept', 'progress'})


def _typing_progress_for_table(progress) -> list:
    """Progress without wall-clock fields on withheld cells (NIT G)."""
    cleaned = []
    for item in progress or ():
        if not isinstance(item, dict):
            continue
        note = {key: value for key, value in item.items() if key not in ('elapsed_s', 'session_wall_s')}
        if note:
            cleaned.append(note)
    return cleaned


def _refusal_tally_text(refusals) -> str:
    """A refusal tally as prose: "refusals: crash (6), cpu_throttled (1)" (#180 review, nit 4)."""
    if not refusals:
        return "no refusal recorded"
    return "refusals: " + ", ".join("%s (%d)" % (code, n) for code, n in sorted(dict(refusals).items()))


def _typing_progress_text(progress) -> str:
    """Progress of refused sessions as prose (#180), never a Python repr."""
    typed = [item.get('characters_typed') for item in progress or () if isinstance(item, dict)]
    typed = [value for value in typed if isinstance(value, (int, float))]
    if not typed:
        return ''
    return 'characters typed in the refused sessions that recorded progress: ' + ', '.join(f'{value:,}' for value in typed)


def _typing_facts_group(group, fields, *, published: bool = False):
    if published:
        return {**group, "kept": [{name: row[name] for name in fields if name in row} for row in group["kept"]]}
    return {key: value for key, value in group.items() if key not in _TYPING_FIGURE_FIELDS}


def typing_table(facts, roots, editor, kind):
    from perf.analysis.e2_typing import read_sessions, resource_values
    label = f'{DISPLAY.get(editor, editor)} — {kind}'
    seeds = _distinct_seeds(roots)
    if len(seeds) < 2 or (len(seeds) == 2 and seeds[0] == seeds[1]):
        return label + ': two distinct seeds and runs required.' + (
            ' Latency-session throughput and resources are instrumented; figures withheld.' if kind == 'latency' else '')
    groups = [_typing_group_for_seed(roots, editor, kind, seed) for seed in seeds[:2]]
    key = f'perf.e2.{editor}.TYPING.{kind}'
    fields = ('load_ms', 'key_to_paint') if kind == 'latency' else ('throughput_chars_s', 'resources', 'resource_endpoints')
    facts[key + '.reproduced'] = False
    instrumented = ' Latency-session throughput and resources are instrumented; figures withheld.' if kind == 'latency' else ''
    reasons = []
    for name, group in zip(('first', 'second'), groups):
        kept_n = len(group['kept'])
        scheduled = group['scheduled']
        if group['blocked'] or scheduled != TYPING_PUBLICATION_SESSIONS or kept_n < TYPING_PUBLICATION_MIN_KEPT:
            progress = _typing_progress_text(_typing_progress_for_table(group['progress']))
            suffix = f"; {progress}" if progress else ""
            if not group['blocked'] and scheduled != TYPING_PUBLICATION_SESSIONS:
                reasons.append(
                    f"{name}: wrong schedule (n = {kept_n} of {scheduled}; "
                    f"this campaign schedules {TYPING_PUBLICATION_SESSIONS} sessions){suffix}"
                )
            else:
                reasons.append(
                    f"{name}: not enough sessions or run blocked (n = {kept_n} of {scheduled}; "
                    f"{group['block_reason'] or _refusal_tally_text(group['refusals'])}){suffix}"
                )
    if reasons:
        return label + ': ' + '; '.join(reasons) + instrumented
    builds = [group.get('build_pin') for group in groups]
    if builds[0] is None or builds[1] is None or builds[0] != builds[1]:
        facts[key + '.reproduced'] = False
        return label + ': the two seeds measured different editor builds' + instrumented
    try:
        check_roots_comparable(roots)
    except ValueError as exc:
        facts[key + '.primary'] = _typing_facts_group(groups[0], fields)
        facts[key + '.reproduction'] = _typing_facts_group(groups[1], fields)
        return label + ': ' + str(exc) + instrumented
    # Fixture identity is part of the experiment, including across seeds.
    if len({(row['fixture_sha256'], row['typed_text_sha256'], row.get('fixture_docx_sha256'))
            for group in groups for row in group['kept']}) != 1:
        facts[key + '.primary'] = _typing_facts_group(groups[0], fields)
        facts[key + '.reproduction'] = _typing_facts_group(groups[1], fields)
        return label + ': fixture mismatch' + instrumented
    values = []
    for group in groups:
        metrics = {}
        for row in group['kept']:
            pairs = [('throughput_chars_s', row['throughput_chars_s'])] if kind == 'throughput' else [
                ('load_ms', row['load_ms']), ('key_to_paint.median_ms', row['key_to_paint']['median_ms']),
                ('key_to_paint.p90_ms', row['key_to_paint']['p90_ms'])]
            if kind == 'throughput':
                for field in ('resources', 'resource_endpoints'):
                    pairs.extend(resource_values(row.get(field, {}), field))
            for name, value in pairs:
                metrics.setdefault(name, []).append(value)
        values.append(metrics)
    header = (
        label
        + f"; first n = {len(groups[0]['kept'])} of {TYPING_PUBLICATION_SESSIONS}; "
        + f"second n = {len(groups[1]['kept'])} of {TYPING_PUBLICATION_SESSIONS}."
        + instrumented
    )
    all_reproduced = True
    table_lines: list[str] = []
    for name in sorted(set(values[0]) | set(values[1])):
        series = [v.get(name, []) for v in values]
        numeric = [[x for x in items if e2_cells._number(x)] for items in series]
        unit = 'chars/s' if name == 'throughput_chars_s' else 'ms' if name.endswith('_ms') else 'bytes' if name.endswith('_bytes') else 'count' if name.endswith('_count') else ''
        if all(len(items) >= TYPING_PUBLICATION_MIN_KEPT for items in numeric):
            medians = [e2_cells.percentile(items, 50) for items in numeric]
            agrees = reproduced(*medians, rel_tol=REL_TOL, abs_tol=0)
            all_reproduced &= agrees
            if agrees:
                text = []
                for median, items in zip(medians, numeric):
                    # Same rule as the other lanes: a percentile of a short kept set is not stable.
                    figure = fmt_resource(median, unit)
                    if len(items) < PUBLICATION_REPETITIONS:
                        figure += f'; range {min(items):.1f} to {max(items):.1f} {unit}'
                    text.append(figure + f' (n = {len(items)})')
            else:
                text = ['not reproduced', 'not reproduced']
        else:
            text = ['; '.join(sorted({fmt_resource(x, unit) for x in items if not e2_cells._number(x)})) or 'not enough samples' for items in series]
        for i, items in enumerate(series):
            markers = sorted({fmt_resource(x, unit) for x in items if not e2_cells._number(x)})
            if len(numeric[i]) >= TYPING_PUBLICATION_MIN_KEPT and markers:
                text[i] += '; ' + '; '.join(markers)
        table_lines.append('| ' + name + ' | ' + ' | '.join(text) + ' |')
    if kind == 'latency' and all_reproduced:
        for name, group in zip(('first', 'second'), groups):
            accepted = sum(row['key_to_paint']['n_accepted'] for row in group['kept'])
            refused = sum(row['key_to_paint']['n_refused'] for row in group['kept'])
            # A blank line first: each is a paragraph, and the first one ends the table (#214).
            table_lines.extend(['', f'{name}: accepted {accepted}; refused {refused} key witnesses.'])
    facts[key + '.reproduced'] = all_reproduced
    published = all_reproduced
    facts[key + '.primary'] = _typing_facts_group(groups[0], fields, published=published)
    facts[key + '.reproduction'] = _typing_facts_group(groups[1], fields, published=published)
    if not all_reproduced:
        return header + ' One or more measures did not reproduce, so no figure is printed.'
    # Markdown reads a table only after a blank line (#214).
    lines = [header, '', '| Measure | First seed | Second seed |', '|---|---|---|', *table_lines]
    return '\n'.join(lines)


def facts_from_campaigns(roots):
    """Inventory all shards; selecting paired publication runs remains explicit."""
    from perf.analysis.e2_campaigns import campaign_provenance
    records = campaign_provenance(roots)
    lines = []
    for campaign in records:
        affinity = '; '.join(campaign['cpu_affinity_pinned']) or 'not recorded'
        lines.append(f"- Space **{campaign['space']}**, campaign `{Path(campaign['campaign']).name}`: {affinity}.")
        for job in campaign['jobs']:
            lines.append(f"  - Space **{job['space']}**, {job['runner']}, job `{job['run_id']}`, seed {job['seed']}: {job['status']}. Stolen CPU: {_steal(job)}. Throttle: {_throttle(job)}.")
    return {'perf.e2.campaigns': records, 'perf.e2.provenance': '\n'.join(lines) or 'No campaign roots supplied.'}
