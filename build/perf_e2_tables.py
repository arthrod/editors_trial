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

E2_CRITERIA = [f"C{i:02d}" for i in range(3, 16)]
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


def check_comparable(primary: Run, repro: Run) -> None:
    """A reproduction is a second run of the same measurement, nothing else."""
    if any(e2_cells._run_blocks_publication(run.summary)[0] or (run.summary.get('publishable') is not True and run.summary.get('publication_block_reason') != 'summary is not a trial; trials carry publishability') for run in (primary, repro)):
        return
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

    if _pins(primary.path) != _pins(repro.path):
        raise ValueError("the reproduction attested other editor pins")


def _pins(root: Path) -> dict:
    pins = {}
    for row in e2_cells._iter_trials(root):
        pin = (row.get("environment") or {}).get("editor_version")
        pins.setdefault(row["editor_id"], set()).add(str(pin) if pin is not None else "not recorded")
    return {editor: sorted(values) for editor, values in pins.items()}


def _summary(root: Path) -> dict:
    return json.loads((root / "summary.json").read_text())


def _scheduled(root: Path, editor: str) -> int:
    return sum(1 for _, eid in _summary(root).get("order", []) if eid == editor)


def _editors(primary: Path, repro: Path) -> list[str]:
    ids: set[str] = {eid for root in (primary, repro) for _, eid in _summary(root).get("order", [])}

    def collect(root: Path) -> None:
        for row in _iter_trials(root):
            eid = row.get("editor_id")
            if eid:
                ids.add(eid)

    collect(primary)
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
    collect(repro)
    return E2_CRITERIA


def _iter_trials(run_directory: Path):
    for path, row in e2_cells._read_rows(run_directory / "cells"):
        if e2_cells._diagnostic_trial_path(path) or e2_cells._diagnostic_trial_row(row):
            continue
        if row.get("criterion_id") and row.get("editor_id"):
            yield row


def _format_median(cell: dict, median: float) -> str:
    if cell.get("sample_unit") == "bytes":
        return "%.1f bytes" % median
    frame = cell.get("frame_interval_ms") or 0
    if median < frame:
        return "< 1 frame (%g ms)" % frame
    return "%.1f ms" % median


def _cell_text(facts: dict, primary: Path, repro: Path, editor: str, criterion: str, measure: str = '', workload_id: str | None = None) -> str:
    key = 'perf.e2.%s.%s' % (editor, criterion) + ('.' + measure if measure else '') + ('.' + workload_id if workload_id else '')
    facts[key + '.reproduced'] = False
    cells = [
        e2_cells.build_run_cell(root, editor, criterion, scheduled=_scheduled(root, editor), measure=measure, workload_id=workload_id)
        for root in (primary, repro)
    ]
    facts[key + '.primary'], facts[key + '.reproduction'] = cells
    p_cell, r_cell = cells
    reasons = []
    for label, root, cell in zip(('first', 'second'), (primary, repro), cells):
        summary = _summary(root)
        blocked = e2_cells._run_blocks_publication(summary)[0] or (summary.get('publishable') is not True and summary.get('publication_block_reason') != 'summary is not a trial; trials carry publishability')
        if blocked:
            reasons.append(
                '%s run unpublishable: %s'
                % (
                    label,
                    summary.get('publication_block_reason') or summary.get('failure_reason') or 'publishable not true',
                )
                + ' (blocked)'
            )
        text = e2_cells.publication_text(cell)
        if blocked:
            failures = e2_cells.failure_text(cell)
            if failures:
                reasons.append('%s: %s' % (label, failures))
        elif 'not enough samples' in text:
            reasons.append('%s: %s' % (label, text))
        if not cell['scheduled']:
            reasons.append('%s: scheduled count not recorded' % label)
    if reasons:
        for label, cell in zip(('first', 'second'), cells):
            failures = e2_cells.failure_text(cell)
            if failures and cell['stats'] and cell['stats']['n'] >= 10:
                entry = '%s: %s' % (label, failures)
                if entry not in reasons:
                    reasons.append(entry)
        reason = '; '.join(reasons)
        facts[key + '.reason'] = reason
        facts.setdefault('_not_reproduced', []).append((DISPLAY.get(editor, editor), criterion, reason, '—'))
        return reason
    p_text = e2_cells.publication_text(p_cell)
    frame = max(p_cell.get('frame_interval_ms') or 0, r_cell.get('frame_interval_ms') or 0)

    p_med = p_cell['stats']['median']
    r_med = r_cell['stats']['median']
    key = 'perf.e2.%s.%s' % (editor, criterion) + ('.' + measure if measure else '') + ('.' + workload_id if workload_id else '')
    ok = reproduced(p_med, r_med, rel_tol=REL_TOL, abs_tol=frame)
    if not ok:
        facts[key + '.reason'] = 'medians outside tolerance'
        first = _format_median(p_cell, p_med)
        second = _format_median(r_cell, r_med)
        facts.setdefault('_not_reproduced', []).append((DISPLAY.get(editor, editor), criterion, first, second))
        failures = [
            '%s: %s' % (label, e2_cells.failure_text(cell))
            for label, cell in zip(('first', 'second'), cells)
            if cell.get('refusals')
        ]
        suffix = '; ' + '; '.join(failures) if failures else ''
        return 'not reproduced (first %s; second %s)%s' % (first, second, suffix)
    facts[key + '.reproduced'] = True
    failures = e2_cells.failure_text(r_cell)
    return p_text + ('; second: ' + failures if failures else '')


def _criterion_table(facts: dict, primary: Path, repro: Path, criterion: str, editors: list[str]) -> str:
    groups = sorted({(e2_cells.trial_workload(row), e2_cells.trial_measure(row))
                     for root in (primary, repro) for row in e2_cells._iter_trials(root)
                     if row['criterion_id'] == criterion}) or [('', '')]
    has_workload = any(workload for workload, _ in groups)
    distinct = criterion in ('C14', 'C15') or any(measure for _, measure in groups)
    columns = ['Editor'] + (['Workload'] if has_workload else []) + (['Measure'] if distinct else []) + [criterion]
    lines = ['| ' + ' | '.join(columns) + ' |', '|' + '---|' * len(columns)]
    for workload, measure in groups:
        for editor in editors:
            text = _cell_text(facts, primary, repro, editor, criterion, measure, workload)
            row = [DISPLAY.get(editor, editor)] + ([workload or 'unspecified'] if has_workload else [])
            row += ([measure or 'unspecified'] if distinct else []) + [text]
            lines.append('| ' + ' | '.join(row) + ' |')
    return "\n".join(lines)


def _not_reproduced_table(facts: dict) -> str:
    rows = facts.pop("_not_reproduced", [])
    if not rows:
        return "Every figure that was measured in both runs reproduced."
    lines = [
        "| Editor | Criterion | First run / reason | Second run, median |",
        "|---|---|---|---|",
    ]
    lines += ["| %s | %s | %s | %s |" % r for r in rows]
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


def _host_note(summary: dict) -> str:
    playwright, chromium, renderer = _rendering(summary)
    return ("Host class: %s. %s. Playwright %s; Chromium %s; renderer %s; headless %s. "
            "Stolen CPU time: %s. Throttle: %s. Editor pins: %s." % (
                _machine(summary), _host_block(summary), playwright, chromium, renderer,
                (summary.get("rendering") or {}).get("headless", "not recorded"),
                _steal(summary), _throttle(summary), summary.get("trial_pins", "not recorded")))


def _steal(summary: dict) -> str:
    v = summary.get("cpu_steal_percent")
    if v is None:
        acct = summary.get("cpu_accounting") or {}
        v = acct.get("steal_percent")
    if v is None:
        return "not recorded"
    return _pct(v)


def _throttle(summary: dict) -> str:
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
            p = e2_cells.build_run_cell(primary, editor, criterion, scheduled=_scheduled(primary, editor))
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
        "perf.e2.scheduled": SCHEDULED,
    }
    for cid in E2_CRITERIA:
        facts["perf.e2.criterion.%s" % cid] = blurbs.get(cid, cid)
        facts["perf.e2.table.%s" % cid] = "not yet measured"
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
    primary, repro = load_run(primary_dir), load_run(repro_dir)
    check_comparable(primary, repro)
    editors = _editors(primary.path, repro.path)
    criteria = _criteria_present(primary.path, repro.path)
    s = primary.summary
    playwright, chromium, renderer = _rendering(s)
    facts: dict = {
        "perf.e2.word_verification": "Word verification not recorded for this generated twin.",
        "perf.e2.measured": "measured",
        "perf.e2.status": "",
        "perf.e2.run_id": s["run_id"],
        "perf.e2.repro_run_id": repro.summary["run_id"],
        "perf.e2.seed": s["seed"],
        "perf.e2.repro_seed": repro.summary["seed"],
        "perf.e2.date": _date(s),
        "perf.e2.repro_date": _date(repro.summary),
        "perf.e2.machine": _machine(s),
        "perf.e2.host": _host_block(s),
        "perf.e2.host_class": s.get("host_class", "?"),
        "perf.e2.host_note": "First run: " + _host_note({**s, "trial_pins": _pins(primary.path)}) + "\n\nSecond run: " + _host_note({**repro.summary, "trial_pins": _pins(repro.path)}),
        "perf.e2.steal": _steal(s),
        "perf.e2.throttle": _throttle(s),
        "perf.e2.renderer": renderer,
        "perf.e2.playwright": playwright,
        "perf.e2.chromium": chromium,
        "perf.e2.scheduled": {"primary": {e: _scheduled(primary.path, e) for e in editors}, "reproduction": {e: _scheduled(repro.path, e) for e in editors}},
        "perf.e2.rel_tol_pct": REL_TOL_PCT,
        "perf.e2.rule": (
            "Each launch contributes the median of its own samples; n counts kept launches. "
            "Scheduled counts come from each run's order. Both runs must be publishable and keep at least 10 launches. "
            "The medians must agree within 10 percent of the larger median or the larger witnessed frame interval. "
            "Samples require complete boolean flags checked against a witnessed interval. Sub-frame medians are buckets; "
            "p90 is over launch medians. C14 rungs and C15 steps are separate measures."
        ),
        "perf.e2.reproduce": "See perf/container/README.md.",
    }
    blurbs = _criterion_blurbs()
    for cid in E2_CRITERIA:
        facts["perf.e2.criterion.%s" % cid] = blurbs.get(cid, cid)
    for cid in criteria:
        facts["perf.e2.table.%s" % cid] = _criterion_table(facts, primary.path, repro.path, cid, editors)
    for cid in E2_CRITERIA:
        facts.setdefault("perf.e2.table.%s" % cid, "not in these runs.")
    facts["perf.e2.not_run"] = _not_run_editors(primary.path, repro.path, editors)
    facts["perf.e2.not_reproduced"] = _not_reproduced_table(facts)
    published = [k for k in facts if k.endswith(".reproduced")]
    facts["perf.e2.cells_checked"] = len(published)
    facts["perf.e2.cells_reproduced"] = sum(1 for k in published if facts[k])
    facts["perf.e2.intro"] = "%d of %d scheduled editor/criterion/measure cells reproduced between the two runs. Dates: first %s; second %s." % (
        facts["perf.e2.cells_reproduced"], facts["perf.e2.cells_checked"], _date(s), _date(repro.summary))
    return facts
