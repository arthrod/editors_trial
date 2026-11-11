"""Report E2: browser-lane speed tables from two ``dedicated_publish`` runs.

Reads trial JSON under each run directory (as ``browser_run`` writes) and
returns ``perf.e2.*`` facts for the template. Figures use ``e2_cells``; two
runs must agree (``reproduced``, abs_tol = witnessed frame interval).
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from perf.analysis import e2_cells
from perf.scenarios.catalog import scenarios

from build.perf_e_tables import DISPLAY, REL_TOL, _SAME_HOST, _pct, reproduced

E2_CRITERIA = [f"C{i:02d}" for i in range(3, 16)] + ["C17", "C19"]
SCHEDULED = 30
REL_TOL_PCT = round(REL_TOL * 100)


@dataclass
class Run:
    path: Path
    summary: dict


def load_run(path: Path) -> Run:
    path = Path(path)
    summary = json.loads((path / "summary.json").read_text(encoding="utf-8"))
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


def _pins(root: Path) -> dict:
    """Built-editor identity per editor (#149).

    ``host_provenance.tree_sha256`` — the built editor — is the pin whenever
    present, for every lane; ``environment.editor_version`` counts only when
    it is a real pin, not the editor slug the runner stamps there. A trial
    with neither records "not recorded".
    """
    pins = {}
    for row in e2_cells._iter_trials(root):
        pin = e2_cells.editor_pin(row)
        pins.setdefault(row["editor_id"], set()).add(pin if pin else _PIN_SENTINEL)
    return {editor: sorted("not recorded" if value is _PIN_SENTINEL else value for value in values) for editor, values in pins.items()}


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
    return json.loads((root / "summary.json").read_text())


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
        return "%.1f bytes" % median
    suffix = " — content not verified" if cell.get("criterion_id") == "C11" and cell.get("content_verified") is not True else ""
    frame = cell.get("frame_interval_ms") or 0
    if median < frame:
        return "< 1 frame (%g ms)" % frame + suffix
    return "%.1f ms" % median + suffix


def _cell_text(facts: dict, roots, editor: str, criterion: str, measure: str = '', workload_id: str | None = None) -> str:
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
                    '%s run unpublishable: %s (blocked)' % (label, cell.get('block_reason') or 'run blocked'))
                failures = e2_cells.failure_text(cell)
                if failures:
                    reasons.append('%s: %s' % (label, failures))
            else:
                text = e2_cells.publication_text(cell)
                if 'not enough samples' in text or 'not publishable' in text:
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


def _criterion_table(facts: dict, roots, criterion: str, editors: list[str]) -> str:
    groups = sorted({(e2_cells.trial_workload(row), e2_cells.trial_measure(row))
                     for root in roots for row in e2_cells._iter_trials(root)
                     if row['criterion_id'] == criterion})
    if not groups:
        return 'not in these runs.'
    has_workload = any(workload for workload, _ in groups)
    distinct = criterion in ('C14', 'C15') or any(measure for _, measure in groups)
    columns = ['Editor'] + (['Workload'] if has_workload else []) + (['Measure'] if distinct else []) + [criterion]
    lines = ['| ' + ' | '.join(columns) + ' |', '|' + '---|' * len(columns)]
    for workload, measure in groups:
        for editor in editors:
            text = _cell_text(facts, roots, editor, criterion, measure, workload)
            row = [DISPLAY.get(editor, editor)] + ([workload or 'unspecified'] if has_workload else [])
            row += ([measure or 'unspecified'] if distinct else []) + [text]
            lines.append('| ' + ' | '.join(row) + ' |')
    return "\n".join(lines)


def _not_reproduced_table(facts: dict) -> str:
    rows = facts.pop("_not_reproduced", [])
    if not rows:
        return "Every figure that was measured in both runs reproduced."
    lines = [
        "| Editor | Criterion | Workload | Measure | First run / reason | Second run, median |",
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
    root = Path(root)
    if (root / "runs").is_dir():
        return root.name
    if root.parent.name == "runs":
        return root.parent.parent.name
    return root.name


def _all_job_summaries(roots) -> list[dict]:
    rows = []
    for root in map(Path, roots):
        for job in e2_cells._job_roots(root):
            summary = e2_cells._load_summary(job)
            if summary:
                rows.append({**summary, "space": _space_name(root)})
    return rows


def check_roots_comparable(roots) -> None:
    """Versions and pins must match across every shard; host class must agree."""
    summaries = _all_job_summaries(roots)
    if len(summaries) < 2:
        return
    first = summaries[0]
    for summary in summaries[1:]:
        if summary.get("versions") != first.get("versions"):
            raise ValueError("the reproduction attested other versions")
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


def _host_note_campaign(roots) -> str:
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


def _date(summary: dict) -> str:
    for key in ("started_at", "finished_at"):
        if summary.get(key):
            return str(summary[key])[:10]
    return "not recorded"


def unset_facts() -> dict:
    """Facts when ``report_e2_runs.json`` is absent: the template still renders."""
    blurbs = _criterion_blurbs()
    facts = {
        "perf.e2.provenance": "Per-Space provenance not supplied.",
        "perf.e2.table.TYPING": "not in these runs.",
        "perf.e2.word_verification": "Word verification not recorded for this generated twin.",
        "perf.e2.measured": "not yet measured",
        "perf.e2.status": "This report is not yet measured.",
        "perf.e2.intro": "No browser runs are available; not yet measured.",
        "perf.e2.machine": _machine(),
        "perf.e2.host": "not yet measured",
        "perf.e2.host_class": "not yet measured",
        "perf.e2.host_note": "not yet measured",
        "perf.e2.rule": "not yet measured",
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
        "perf.e2.scheduled": SCHEDULED,
    }
    for cid in E2_CRITERIA:
        facts["perf.e2.criterion.%s" % cid] = blurbs.get(cid, cid)
        facts["perf.e2.table.%s" % cid] = "not yet measured"
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


def facts_from_roots(roots) -> dict:
    roots = _require_campaign_roots(roots)
    classic = len(roots) == 2 and all((root / "summary.json").is_file() for root in roots)
    if classic:
        primary, repro = load_run(roots[0]), load_run(roots[1])
        try:
            check_comparable(primary, repro)
        except ValueError:
            raise
    else:
        check_roots_comparable(roots)
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
    playwright, chromium, renderer = _rendering(s)
    facts: dict = {
        "perf.e2.provenance": "Per-Space provenance not supplied.",
        "perf.e2.table.TYPING": "not in these runs.",
        "perf.e2.word_verification": "Word verification not recorded for this generated twin.",
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
        "perf.e2.host_note": (
            _host_note_campaign(roots)
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
        "perf.e2.rule": (
            "Each launch contributes the median of its own samples; n counts kept launches. "
            "Scheduled counts come from each run's order. Publishability is decided per trial — job "
            "summaries delegate it to their trials — and a cell publishes only from trials that are "
            "publishable and record the built editor's identity (host_provenance.tree_sha256, else a "
            "pinned editor_version); a trial recording neither is refused as pin not recorded, and a "
            "reproduction across different built-editor trees is refused. Both runs must keep at least "
            "10 launches per cell, and a run-level block — a shakedown run, dirty repos, unavailable "
            "CPU accounting or a failed run — refuses the whole run. "
            "The medians must agree within 10 percent of the larger median or the larger witnessed frame interval. "
            "Samples of frame-witnessed criteria require complete boolean flags checked against a witnessed interval; "
            "model-layer clocks such as C04 and byte counts publish without them, and sub-frame medians are buckets; "
            "p90 is over launch medians. C14 rungs and C14 measures (presented_frame, usable_no_damage) and C15 steps "
            "are separate measures; a no-damage C14 sample is the DOM document-surface time, never a compositor frame."
        ),
        "perf.e2.reproduce": "See perf/container/README.md.",
    }
    blurbs = _criterion_blurbs()
    for cid in E2_CRITERIA:
        facts["perf.e2.criterion.%s" % cid] = blurbs.get(cid, cid)
    for cid in criteria:
        facts["perf.e2.table.%s" % cid] = _criterion_table(facts, roots, cid, editors)
    for cid in E2_CRITERIA:
        facts.setdefault("perf.e2.table.%s" % cid, "not in these runs.")
    typing_groups = sorted({(row['editor_id'], row.get('session_kind'))
                            for root in roots for row in _iter_trials(root)
                            if row['criterion_id'] == 'TYPING' and row.get('session_kind') in ('throughput', 'latency')})
    if typing_groups:
        facts['perf.e2.table.TYPING'] = '\n\n'.join(typing_table(facts, roots, editor, kind) for editor, kind in typing_groups)
    facts.update(resource_facts(roots, editors))
    facts["perf.e2.not_run"] = _not_run_editors(roots[0], roots[-1], editors)
    facts["perf.e2.not_reproduced"] = _not_reproduced_table(facts)
    published = [k for k in facts if k.endswith(".reproduced")]
    facts["perf.e2.cells_checked"] = len(published)
    facts["perf.e2.cells_reproduced"] = sum(1 for k in published if facts[k])
    facts["perf.e2.intro"] = "%d of %d scheduled editor/criterion/measure cells reproduced between the two runs. Dates: first %s; second %s." % (
        facts["perf.e2.cells_reproduced"], facts["perf.e2.cells_checked"], _date(s), _date(repro.summary))
    return facts


RESOURCES_BLURB = (
    "**B8 — resources while opening and editing.** One fresh browser per launch opens the document, waits "
    "until the editor is idle, types sixteen characters into a body line on the first screen, and waits "
    "again. CPU is the processor time of the whole browser process tree: to open (from navigation until "
    "idle, including work an editor does after it reports ready), during the edit (the keystrokes plus "
    "half a second), and while settling afterwards. Peak memory is the resident memory of that tree. An "
    "edit counts only when it is verified in the document: the text of the block at the caret, read from "
    "the page or from the editor's model, gained exactly the typed text; WordCraft, which exposes no text, "
    "is verified by its own modified flag. An editor that never goes idle is measured over a 30-second cap "
    "and flagged. The complex document is loaded without its read-only protection, which the editors honour."
)


def resource_facts(roots, editors) -> dict:
    """The B8 section: every seed's launches from every run directory given."""
    from perf.analysis import e2_resources
    facts: dict = {"perf.e2.criterion.B8": RESOURCES_BLURB}
    facts["perf.e2.table.B8"] = e2_resources.resources_tables(facts, roots, editors, DISPLAY)
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


def _typing_group_for_seed(roots, editor, kind, seed):
    from perf.analysis import e2_cells
    from perf.analysis.e2_typing import _sessions_from_jobs

    job_pairs = []
    for root in roots:
        root = Path(root)
        for job in e2_cells._lane_jobs(root, e2_cells._job_roots(root), editor, 'TYPING'):
            summary = e2_cells._load_summary(job) or {}
            if summary.get('seed') not in (None, seed):
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
        if group['blocked'] or group['scheduled'] != 12 or len(group['kept']) < 10:
            progress = _typing_progress_for_table(group['progress'])
            suffix = f"; progress {progress}" if progress else ""
            reasons.append(
                f"{name}: not enough sessions or run blocked (n = {len(group['kept'])} of {group['scheduled']}; "
                f"{group['block_reason'] or group['refusals']}){suffix}"
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
    header = label + f"; first n = {len(groups[0]['kept'])} of 12; second n = {len(groups[1]['kept'])} of 12." + instrumented
    all_reproduced = True
    table_lines: list[str] = []
    for name in sorted(set(values[0]) | set(values[1])):
        series = [v.get(name, []) for v in values]
        numeric = [[x for x in items if e2_cells._number(x)] for items in series]
        unit = 'chars/s' if name == 'throughput_chars_s' else 'ms' if name.endswith('_ms') else 'bytes' if name.endswith('_bytes') else 'count' if name.endswith('_count') else ''
        if all(len(items) >= 10 for items in numeric):
            medians = [e2_cells.percentile(items, 50) for items in numeric]
            agrees = reproduced(*medians, rel_tol=REL_TOL, abs_tol=0)
            all_reproduced &= agrees
            text = [fmt_resource(m, unit) + f' (n = {len(items)})' for m, items in zip(medians, numeric)] if agrees else ['not reproduced', 'not reproduced']
        else:
            text = ['; '.join(sorted({fmt_resource(x, unit) for x in items if not e2_cells._number(x)})) or 'not enough samples' for items in series]
        for i, items in enumerate(series):
            markers = sorted({fmt_resource(x, unit) for x in items if not e2_cells._number(x)})
            if len(numeric[i]) >= 10 and markers:
                text[i] += '; ' + '; '.join(markers)
        table_lines.append('| ' + name + ' | ' + ' | '.join(text) + ' |')
    if kind == 'latency' and all_reproduced:
        for name, group in zip(('first', 'second'), groups):
            accepted = sum(row['key_to_paint']['n_accepted'] for row in group['kept'])
            refused = sum(row['key_to_paint']['n_refused'] for row in group['kept'])
            table_lines.append(f'{name}: accepted {accepted}; refused {refused} key witnesses.')
    facts[key + '.reproduced'] = all_reproduced
    published = all_reproduced
    facts[key + '.primary'] = _typing_facts_group(groups[0], fields, published=published)
    facts[key + '.reproduction'] = _typing_facts_group(groups[1], fields, published=published)
    if not all_reproduced:
        return header + ': one or more measures did not reproduce' + instrumented
    lines = [header, '| Measure | First seed | Second seed |', '|---|---|---|', *table_lines]
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
