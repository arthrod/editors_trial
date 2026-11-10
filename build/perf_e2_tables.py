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

from perf_e_tables import DISPLAY, REL_TOL, _SAME_HOST, _pct, reproduced

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
    if summary.get("execution_profile") != "dedicated_publish":
        raise ValueError(
            "%s is a %s run; Report E2 publishes dedicated_publish runs only"
            % (path, summary.get("execution_profile"))
        )
    return Run(path, summary)


def check_comparable(primary: Run, repro: Run) -> None:
    """A reproduction is a second run of the same measurement, nothing else."""
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
    for key in ("browser_version", "renderer", "headless"):
        if ra.get(key) != rb.get(key):
            raise ValueError("the reproduction used other Playwright or Chromium versions")
    if a.get("host_class") != b.get("host_class"):
        raise ValueError("the reproduction used another host class")
    if a.get("execution_profile") != b.get("execution_profile"):
        raise ValueError("the reproduction used another execution profile")


def _editors(primary: Path, repro: Path) -> list[str]:
    ids: set[str] = set()

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
    return [c for c in E2_CRITERIA if c in present]


def _iter_trials(run_directory: Path):
    for path in sorted(run_directory.rglob("*.json")):
        if path.name == "summary.json":
            continue
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(row, dict) and row.get("criterion_id") and row.get("editor_id"):
            yield row


def _format_median(cell: dict, median: float) -> str:
    frame = cell.get("frame_interval_ms") or 16.7
    if median < frame:
        return "< 1 frame (%g ms)" % frame
    return "%.1f ms" % median


def _cell_text(facts: dict, primary: Path, repro: Path, editor: str, criterion: str) -> str:
    p_cell = e2_cells.build_run_cell(primary, editor, criterion, scheduled=SCHEDULED)
    r_cell = e2_cells.build_run_cell(repro, editor, criterion, scheduled=SCHEDULED)
    p_text = e2_cells.publication_text(p_cell)
    r_text = e2_cells.publication_text(r_cell)
    if "not enough samples" in p_text:
        return p_text
    if "not enough samples" in r_text:
        return r_text
    frame = p_cell.get("frame_interval_ms") or r_cell.get("frame_interval_ms") or 16.7
    p_med = p_cell["stats"]["median"]
    r_med = r_cell["stats"]["median"]
    key = "perf.e2.%s.%s" % (editor, criterion)
    ok = reproduced(p_med, r_med, rel_tol=REL_TOL, abs_tol=frame)
    if not ok:
        facts[key + ".reproduced"] = False
        first = _format_median(p_cell, p_med)
        second = _format_median(r_cell, r_med)
        facts.setdefault("_not_reproduced", []).append(
            (DISPLAY.get(editor, editor), criterion, first, second)
        )
        return "not reproduced (first %s; second %s)" % (first, second)
    facts[key + ".reproduced"] = True
    return p_text


def _criterion_table(facts: dict, primary: Path, repro: Path, criterion: str, editors: list[str]) -> str:
    lines = ["| Editor | %s |" % criterion, "|---|---|"]
    for editor in editors:
        text = _cell_text(facts, primary, repro, editor, criterion)
        lines.append("| %s | %s |" % (DISPLAY.get(editor, editor), text))
    return "\n".join(lines)


def _not_reproduced_table(facts: dict) -> str:
    rows = facts.pop("_not_reproduced", [])
    if not rows:
        return "Every figure that was measured in both runs reproduced."
    lines = [
        "| Editor | Criterion | First run, median | Second run, median |",
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
    quota = h.get("cpu_quota")
    n = h.get("cpu_cores_logical") or "?"
    cpus = "all %s CPUs its kernel reports" % n if quota is None or (isinstance(quota, (int, float)) and quota >= n) else (
        "a CPU quota of %g on %s logical CPUs" % (quota, n)
    )
    return "%s, %s, Linux %s, AC power" % (h.get("cpu_model", "?"), cpus, h.get("os_version", "?"))


def _machine() -> str:
    return "one Hugging Face cpu-upgrade Space (shared EC2, not dedicated CPUs)"


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
    if refused is None:
        return "not recorded"
    if total is not None:
        return "%d of %d samples refused for cgroup CPU throttling" % (refused, total)
    return "%d samples refused for cgroup CPU throttling" % refused


def _rendering(summary: dict) -> tuple[str, str, str]:
    r = summary.get("rendering") or {}
    tools = (summary.get("versions") or {}).get("tools") or {}
    playwright = tools.get("playwright") or "not recorded"
    chromium = r.get("browser_version") or "not recorded"
    renderer = r.get("renderer") or "not recorded"
    return playwright, chromium, renderer


def _not_run_editors(primary: Path, repro: Path, editors: list[str]) -> str:
    lines = []
    for editor in editors:
        for criterion in E2_CRITERIA:
            p = e2_cells.build_run_cell(primary, editor, criterion, scheduled=SCHEDULED)
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
    return ""


def unset_facts() -> dict:
    """Facts when ``report_e2_runs.json`` is absent: the template still renders."""
    blurbs = _criterion_blurbs()
    facts = {
        "perf.e2.measured": "not yet measured",
        "perf.e2.status": "This report has not been measured yet.",
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


def facts_from_runs(primary_dir: Path, repro_dir: Path) -> dict:
    primary, repro = load_run(primary_dir), load_run(repro_dir)
    check_comparable(primary, repro)
    editors = _editors(primary.path, repro.path)
    criteria = _criteria_present(primary.path, repro.path)
    s = primary.summary
    playwright, chromium, renderer = _rendering(s)
    facts: dict = {
        "perf.e2.measured": "measured",
        "perf.e2.status": "",
        "perf.e2.run_id": s["run_id"],
        "perf.e2.repro_run_id": repro.summary["run_id"],
        "perf.e2.seed": s["seed"],
        "perf.e2.repro_seed": repro.summary["seed"],
        "perf.e2.date": _date(s),
        "perf.e2.repro_date": _date(repro.summary),
        "perf.e2.machine": _machine(),
        "perf.e2.host": _host_block(s),
        "perf.e2.host_class": s.get("host_class", "?"),
        "perf.e2.host_note": (
            "The host is a shared EC2 instance with an 8-CPU cgroup quota (not dedicated cores). "
            "Rendering used headless Chromium with software rasterization (%s). "
            "Stolen CPU time during the run was %s. %s. "
            "Other tenants could use the same machine; the load average counted every process on the kernel."
            % (renderer, _steal(s), _throttle(s))
        ),
        "perf.e2.steal": _steal(s),
        "perf.e2.throttle": _throttle(s),
        "perf.e2.renderer": renderer,
        "perf.e2.playwright": playwright,
        "perf.e2.chromium": chromium,
        "perf.e2.scheduled": SCHEDULED,
        "perf.e2.rel_tol_pct": REL_TOL_PCT,
        "perf.e2.rule": (
            "Each cell is the median of up to %d repetitions per editor, in fresh browser contexts. "
            "A figure is printed only when both runs kept at least 10 samples and the two medians agree "
            "within %d percent of the larger median or within one witnessed frame interval, whichever is larger. "
            "Medians below one frame are written as sub-frame buckets with the share of sub-frame samples and the p90."
            % (SCHEDULED, REL_TOL_PCT)
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
    return facts
