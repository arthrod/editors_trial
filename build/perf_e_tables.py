"""Report E's facts: the headless speed tables, from the runner's own files.

``facts_from_runs(primary, repro)`` reads two ``perf/runner/speed_headless.py``
publication runs (``dedicated_publish``, different seeds) and returns the
``perf.e.*`` facts the Report E template binds. A figure is published only if

- the primary run measured it with a publishable distribution (n >= 10, no
  excluded sample, quiet machine, AC power, pins attested), and
- the reproduction run measured the same cell and its median agrees
  (``reproduced``).

Otherwise the cell says why, never a number. Rows are in alphabetical order:
a table is not a ranking.

The round trip is computed per sample (that sample's load + that sample's
save, from one process), then summarised; it is not the sum of two medians.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from perf.analysis.summarize import summarize

DISPLAY = {
    "canvas": "canvas-editor + plugin",
    "docen": "Docen",
    "docsplus": "docs.plus",
    "docxodus": "Docxodus",
    "eigenpal": "eigenpal",
    "fidus": "Fidus Writer",
    "folio": "Folio",
    "genoffice": "GenOffice",
    "libreoffice": "LibreOffice (baseline)",
    "office-open": "office-open",
    "plate": "Plate.js",
    "superdoc": "SuperDoc",
    "wordcraft": "WordCraft",
}
LADDER = ["prose-500w", "prose-5kw", "prose-50kw", "prose-250kw", "complex-corpus"]
WORKLOAD_LABEL = {
    "prose-500w": "500 words",
    "prose-5kw": "5,000 words",
    "prose-50kw": "50,000 words",
    "prose-250kw": "250,000 words",
    "complex-corpus": "complex.docx",
}
# metric -> (how to read one sample, cache state of the clock, unit)
METRICS = {
    "load": ("model_ready_ms", "process_cold_fs_warm"),
    "save": ("save_ms", "warm_steady"),
    "roundtrip": (None, "process_cold_fs_warm"),  # load (process cold) then save (warm) in one process
    "wall": ("wall_ms", "process_cold_fs_warm"),
    "cpu": ("cpu_ms", "process_cold_fs_warm"),
    "rss": ("max_rss_bytes", "process_cold_fs_warm"),
}
TIMED = ("load", "save", "roundtrip")
REL_TOL = 0.10
ABS_TOL_MS = 2.0
PROCESS_WORKLOAD = "prose-50kw"


def reproduced(a: float, b: float, rel_tol: float = REL_TOL, abs_tol: float = ABS_TOL_MS) -> bool:
    """Two medians agree if they differ by at most 10 %, or by at most 2 ms."""
    return abs(a - b) <= max(abs_tol, rel_tol * abs(a))


@dataclass
class Run:
    path: Path
    summary: dict
    records: dict = field(default_factory=dict)  # (workload, editor) -> kept records
    rows: dict = field(default_factory=dict)  # (workload, editor, criterion) -> summary row


def load_run(path: Path) -> Run:
    summary = json.loads((Path(path) / "summary.json").read_text(encoding="utf-8"))
    if summary.get("execution_profile") != "dedicated_publish":
        raise ValueError("%s is a %s run; Report E publishes dedicated_publish runs only" % (path, summary.get("execution_profile")))
    run = Run(Path(path), summary)
    for row in summary["rows"]:
        run.rows[row["workload_id"], row["editor_id"], row["criterion_id"]] = row
    for wl in summary["workloads"]:
        for editor_dir in sorted((Path(path) / "samples" / wl).glob("*")):
            recs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(editor_dir.glob("r*.json"))]
            run.records[wl, editor_dir.name] = [r for r in recs if r.get("run_id") == summary["run_id"]]
    return run


def _good(record: dict) -> bool:
    return (
        not record.get("timed_out")
        and record.get("returncode") == 0
        and bool(record.get("check", {}).get("complete"))
    )


def _values(records: list[dict], metric: str) -> list[float]:
    good = [r for r in records if _good(r)]
    if metric == "roundtrip":
        return [r["marks"]["model_ready_ms"] + r["marks"]["save_ms"] for r in good if {"model_ready_ms", "save_ms"} <= set(r["marks"])]
    key = METRICS[metric][0]
    if metric in ("load", "save"):
        return [r["marks"][key] for r in good if key in r["marks"]]
    return [r[key] for r in good if r.get(key) is not None]


def _criterion(metric: str) -> str:
    return "C16" if metric == "save" else "C02"


def _status(run: Run, wl: str, editor: str, metric: str) -> tuple[str, str | None]:
    """('measured' | 'failed' | 'not_run' | 'unpublishable', reason)."""
    criteria = ("C02", "C16") if metric == "roundtrip" else (_criterion(metric),)
    for crit in criteria:
        row = run.rows.get((wl, editor, crit))
        if row is None:
            return "not_run", "not in this run"
        if row["outcome"] != "measured":
            return row["outcome"], row.get("failure_reason")
        if not row.get("publishable"):
            return "unpublishable", row.get("publication_block_reason")
    return "measured", None


def _stats(values: list[float], cache: str) -> dict:
    return summarize(values, cache, "fresh_process", seed=0)


def _short(reason: str | None) -> str:
    if not reason:
        return "no samples"
    if "stopped after" in reason:
        last = reason.split("(last: ", 1)[1].rstrip(")") if "(last: " in reason else ""
        return "stopped after repeated failures" + (", last %s" % _short(last) if last else "")
    if "timeout" in reason:
        return "timed out"
    if "correctness" in reason:
        return "lost content"
    if "rc=" in reason:
        code = reason.split("rc=", 1)[1].split(";")[0].split(" ")[0]
        return "crashed (exit %s)" % code
    if "no model_ready_ms mark" in reason or "no save_ms mark" in reason:
        return "no load/save split"
    return reason[:60]


def fmt_ms(value: float) -> str:
    if value < 10:
        return "%.1f" % value
    return "{:,.0f}".format(value)


def fmt_mib(value: float) -> str:
    return "{:,.0f}".format(value / (1024 * 1024))


MIN_N = 10
MAX_NOISY = 0.10


def _samples_publishable(run: Run, wl: str, editor: str) -> tuple[bool, str | None]:
    """The runner's publication rule, for figures that have no criterion row
    (whole-process wall, CPU, memory; LibreOffice's conversion)."""
    recs = run.records.get((wl, editor), [])
    good = [r for r in recs if _good(r)]
    if len(recs) != len(good):
        return False, "%d of %d samples excluded" % (len(recs) - len(good), len(recs))
    if len(good) < MIN_N:
        return False, "n=%d below %d" % (len(good), MIN_N)
    noisy = sum(1 for r in recs if r.get("noisy"))
    if noisy / len(recs) > MAX_NOISY:
        return False, "%d of %d samples started above the load limit" % (noisy, len(recs))
    return True, None


def _cell(facts: dict, primary: Run, repro: Run, wl: str, editor: str, metric: str) -> str:
    state, reason = _status(primary, wl, editor, metric)
    if state == "not_run" and editor == "libreoffice":
        return "n/a"
    if state == "not_run":
        return "not run"
    if state != "measured":
        return ("failed: %s" % _short(reason)) if state == "failed" else "not publishable"
    cache = METRICS[metric][1]
    stats = _stats(_values(primary.records[wl, editor], metric), cache)
    r_state, _ = _status(repro, wl, editor, metric)
    r_vals = _values(repro.records.get((wl, editor), []), metric)
    prefix = "perf.e.%s.%s.%s" % (editor, wl, metric)
    if r_state != "measured" or not r_vals:
        facts[prefix + ".reproduced"] = False
        return "not reproduced (second run: %s)" % r_state
    r_stats = _stats(r_vals, cache)
    ok = reproduced(stats["median"], r_stats["median"])
    facts[prefix + ".reproduced"] = ok
    facts[prefix + ".repro_median"] = round(r_stats["median"], 3)
    if not ok:
        return "not reproduced (%s vs %s)" % (fmt_ms(stats["median"]), fmt_ms(r_stats["median"]))
    for k in ("n", "median", "p90", "p95", "p99", "mad", "ci95_low", "ci95_high", "minimum", "maximum"):
        facts["%s.%s" % (prefix, k)] = stats[k] if k == "n" else round(stats[k], 3)
    return "%s (p90 %s)" % (fmt_ms(stats["median"]), fmt_ms(stats["p90"]))


def _editors(primary: Run) -> list[str]:
    ids = {e for (_, e) in primary.records}
    return sorted(ids, key=lambda e: DISPLAY.get(e, e).casefold())


def _workloads(primary: Run) -> list[str]:
    present = list(primary.summary["workloads"])
    return [w for w in LADDER if w in present] + [w for w in present if w not in LADDER]


def _table(facts: dict, primary: Run, repro: Run, metric: str) -> str:
    wls = _workloads(primary)
    head = "| Editor | " + " | ".join(WORKLOAD_LABEL.get(w, w) for w in wls) + " |"
    sep = "|---|" + "---|" * len(wls)
    lines = [head, sep]
    for editor in _editors(primary):
        cells = [_cell(facts, primary, repro, wl, editor, metric) for wl in wls]
        lines.append("| %s | %s |" % (DISPLAY.get(editor, editor), " | ".join(cells)))
    return "\n".join(lines)


def _process_table(facts: dict, primary: Run, repro: Run) -> str:
    wl = PROCESS_WORKLOAD if PROCESS_WORKLOAD in primary.summary["workloads"] else _workloads(primary)[0]
    lines = [
        "| Editor | Whole process, wall (ms) | CPU time (ms) | Peak resident memory (MiB) |",
        "|---|---|---|---|",
    ]
    for editor in _editors(primary):
        recs = primary.records.get((wl, editor), [])
        if not [r for r in recs if _good(r)]:
            _, reason = _status(primary, wl, editor, "load")
            lines.append("| %s | failed: %s | | |" % (DISPLAY.get(editor, editor), _short(reason)))
            continue
        ok_a, why_a = _samples_publishable(primary, wl, editor)
        ok_b, why_b = _samples_publishable(repro, wl, editor)
        if not (ok_a and ok_b):
            lines.append("| %s | not publishable (%s) | | |" % (DISPLAY.get(editor, editor), why_a or "second run: %s" % why_b))
            continue
        cells = []
        for metric in ("wall", "cpu", "rss"):
            vals = _values(recs, metric)
            r_vals = _values(repro.records.get((wl, editor), []), metric)
            if not vals or not r_vals:
                cells.append("not reproduced")
                continue
            med, r_med = _stats(vals, "process_cold_fs_warm")["median"], _stats(r_vals, "process_cold_fs_warm")["median"]
            tol = (0.10, 2.0) if metric != "rss" else (0.10, 8 * 1024 * 1024)
            ok = reproduced(med, r_med, *tol)
            key = "perf.e.%s.%s.%s" % (editor, wl, metric)
            facts[key + ".reproduced"] = ok
            if ok:
                facts[key + ".median"] = round(med, 3)
            text = fmt_mib(med) if metric == "rss" else fmt_ms(med)
            cells.append(text if ok else "not reproduced (%s vs %s)" % (text, fmt_mib(r_med) if metric == "rss" else fmt_ms(r_med)))
        lines.append("| %s | %s |" % (DISPLAY.get(editor, editor), " | ".join(cells)))
    facts["perf.e.process_workload"] = WORKLOAD_LABEL.get(wl, wl)
    return "\n".join(lines)


def _appendix(facts: dict, primary: Run) -> str:
    out = []
    for wl in _workloads(primary):
        out.append("**%s, round trip (ms)**\n" % WORKLOAD_LABEL.get(wl, wl))
        out.append("| Editor | n | median | p90 | p95 | p99 | MAD | 95% CI | min | max |")
        out.append("|---|---|---|---|---|---|---|---|---|---|")
        for editor in _editors(primary):
            state, reason = _status(primary, wl, editor, "roundtrip")
            name = DISPLAY.get(editor, editor)
            if state != "measured":
                out.append("| %s | %s | | | | | | | | |" % (name, "n/a" if editor == "libreoffice" else _short(reason) if state == "failed" else state.replace("_", " ")))
                continue
            if not facts.get("perf.e.%s.%s.roundtrip.reproduced" % (editor, wl)):
                out.append("| %s | not reproduced | | | | | | | | |" % name)
                continue
            s = _stats(_values(primary.records[wl, editor], "roundtrip"), METRICS["roundtrip"][1])
            out.append("| %s | %d | %s | %s | %s | %s | %s | %s to %s | %s | %s |" % (
                name, s["n"], fmt_ms(s["median"]), fmt_ms(s["p90"]), fmt_ms(s["p95"]), fmt_ms(s["p99"]),
                fmt_ms(s["mad"]), fmt_ms(s["ci95_low"]), fmt_ms(s["ci95_high"]), fmt_ms(s["minimum"]), fmt_ms(s["maximum"])))
        out.append("")
    return "\n".join(out).rstrip("\n")


def _workload_table(primary: Run) -> str:
    lines = ["| Workload | Words | Paragraphs | File size | Shape |", "|---|---|---|---|---|"]
    for wl in _workloads(primary):
        m = primary.summary["workloads"][wl]
        lines.append("| %s | %s | %s | %s KB | %s |" % (
            WORKLOAD_LABEL.get(wl, wl), "{:,}".format(m["word_count"]), "{:,}".format(m["paragraph_count"]),
            "{:,.0f}".format(m["byte_size"] / 1000), m["shape"]))
    return "\n".join(lines)


def _host(summary: dict) -> str:
    h = summary["host"]
    return "%s, %d cores, %d GiB RAM, macOS %s, %s power" % (
        h["cpu_model"], h["cpu_cores_logical"], round(h["ram_bytes"] / 2**30), h["os_version"], h["power_source"].upper())


def _libreoffice_table(primary: Run, repro: Run) -> str | None:
    lines = ["| Workload | Whole conversion, wall (ms) | Second run |", "|---|---|---|"]
    found = False
    for wl in _workloads(primary):
        vals = _values(primary.records.get((wl, "libreoffice"), []), "wall")
        r_vals = _values(repro.records.get((wl, "libreoffice"), []), "wall")
        if not vals:
            continue
        found = True
        ok_a, why_a = _samples_publishable(primary, wl, "libreoffice")
        ok_b, why_b = _samples_publishable(repro, wl, "libreoffice")
        if not (ok_a and ok_b):
            lines.append("| %s | not publishable (%s) | |" % (WORKLOAD_LABEL.get(wl, wl), why_a or "second run: %s" % why_b))
            continue
        med = _stats(vals, "process_cold_fs_warm")["median"]
        r_med = _stats(r_vals, "process_cold_fs_warm")["median"] if r_vals else None
        lines.append("| %s | %s | %s |" % (
            WORKLOAD_LABEL.get(wl, wl), fmt_ms(med),
            ("agrees (%s)" % fmt_ms(r_med)) if r_med is not None and reproduced(med, r_med) else "not reproduced"))
    return "\n".join(lines) if found else None


def facts_from_runs(primary_dir: Path, repro_dir: Path) -> dict:
    primary, repro = load_run(primary_dir), load_run(repro_dir)
    s = primary.summary
    facts: dict = {
        "perf.e.run_id": s["run_id"],
        "perf.e.repro_run_id": repro.summary["run_id"],
        "perf.e.n": s["repetitions"],
        "perf.e.repro_n": repro.summary["repetitions"],
        "perf.e.seed": s["seed"],
        "perf.e.repro_seed": repro.summary["seed"],
        "perf.e.host": _host(s),
        "perf.e.date": s["quiet_machine_check_start"].get("date") or _date(primary),
        "perf.e.rel_tol_pct": round(REL_TOL * 100),
        "perf.e.abs_tol_ms": ABS_TOL_MS,
        "perf.e.workloads": _workload_table(primary),
        "perf.e.editors": len([e for e in _editors(primary) if e != "libreoffice"]),
        "perf.e.context.load": "layer model, boundary model_ready, cache state process_cold_fs_warm (fresh process, file system cache warm)",
        "perf.e.context.save": "layer model, boundary serialization_complete, cache state warm_steady (same process, right after load)",
        "perf.e.context.roundtrip": "layer model, from a fresh process (file system cache warm) to the saved file; load and save of the same sample summed",
    }
    for metric in TIMED:
        facts["perf.e.table.%s" % metric] = _table(facts, primary, repro, metric)
    facts["perf.e.table.process"] = _process_table(facts, primary, repro)
    facts["perf.e.appendix"] = _appendix(facts, primary)
    lo = _libreoffice_table(primary, repro)
    facts["perf.e.table.libreoffice"] = lo or "LibreOffice was not in these runs."
    facts["perf.e.summary"] = _summary(facts, primary)
    facts["perf.e.lanes"] = _lanes(primary)
    facts["perf.e.versions"] = _versions(primary)
    facts["perf.e.passthrough"] = _passthrough(primary)
    facts["perf.e.exceptions"] = _exceptions(facts, primary, repro)
    facts["perf.e.correctness_lost"] = _correctness_lost(primary)
    for (wl, editor), recs in primary.records.items():
        starts = [r["marks"]["host_start_ms"] for r in recs if _good(r) and "host_start_ms" in r["marks"]]
        if starts:
            facts["perf.e.%s.%s.host_start.median" % (editor, wl)] = round(_stats(starts, "process_cold_fs_warm")["median"], 3)
    facts["perf.e.prepared_export"] = _prepared_export(facts, _editors(primary))
    facts["perf.e.host_start"] = _host_start(facts, primary)
    facts["perf.e.save_notes"] = _save_notes(facts)
    published = [k for k in facts if k.endswith(".reproduced")]
    facts["perf.e.cells_checked"] = len(published)
    facts["perf.e.cells_reproduced"] = sum(1 for k in published if facts[k])
    return facts


def _seconds_or_ms(value: float) -> str:
    return ("%.1f s" % (value / 1000.0)) if value >= 1000 else ("%s ms" % fmt_ms(value))


def _summary(facts: dict, primary: Run) -> str:
    """One bullet per editor: its own round trip at each workload, from published cells only."""
    bullets = []
    for editor in _editors(primary):
        if editor == "libreoffice":
            continue
        parts, gaps = [], []
        for wl in _workloads(primary):
            key = "perf.e.%s.%s.roundtrip.median" % (editor, wl)
            label = WORKLOAD_LABEL.get(wl, wl)
            if key in facts:
                parts.append("%s at %s" % (_seconds_or_ms(facts[key]), label))
                continue
            state, reason = _status(primary, wl, editor, "roundtrip")
            if state == "failed":
                gaps.append("%s: %s" % (label, _short(reason)))
            else:
                gaps.append("%s: not published (%s)" % (
                    label, "not reproduced" if state == "measured" else state.replace("_", " ")))
        text = "- **%s.** " % DISPLAY.get(editor, editor)
        if parts:
            text += "Round trip " + ", ".join(parts) + "."
        a = "perf.e.%s.prose-5kw.roundtrip.median" % editor
        b = "perf.e.%s.prose-250kw.roundtrip.median" % editor
        if a in facts and b in facts and facts[a] > 0:
            text += " From 5,000 to 250,000 words (50 times the text) it grew %.0f times." % (facts[b] / facts[a])
        if gaps:
            text += (" " if parts else "") + "; ".join(gaps) + "."
        bullets.append(text.rstrip())
    return "\n".join(bullets)


def _lanes(primary: Run) -> str:
    lines = ["| Editor | Load timer ends at / save timer covers |", "|---|---|"]
    lines.extend("| %s | %s |" % (DISPLAY.get(e, e), primary.summary["lanes"].get(e, "")) for e in _editors(primary))
    return "\n".join(lines)


def _versions(primary: Run) -> str:
    v = primary.summary.get("versions", {})
    lines = ["| Editor | Pin | Checkouts on disk | Packages and binaries |", "|---|---|---|---|"]
    for editor in _editors(primary):
        rec = v.get("editors", {}).get(editor, {})
        checkouts = ", ".join("%s %s" % (k.split("/", 1)[-1], h) for k, h in (rec.get("checkouts") or {}).items()) or "—"
        extra = ["%s %s" % (k, val) for k, val in (rec.get("packages") or {}).items()]
        extra += ["%s sha256 %s" % (k, (val or "")[:12]) for k, val in (rec.get("binaries") or {}).items()]
        if rec.get("version"):
            extra.append(rec["version"])
        lines.append("| %s | %s | %s | %s |" % (DISPLAY.get(editor, editor), rec.get("pin") or "—", checkouts, "; ".join(extra) or "—"))
    tools = v.get("tools", {})
    lines.append("")
    lines.append("Runtimes: " + ", ".join("%s %s" % (k, tools[k]) for k in sorted(tools)) + ".")
    return "\n".join(lines)


def _prepared_export(facts: dict, editors: list[str]) -> str:
    """Editors whose save barely moves from 5,000 to 250,000 words while their
    load grows: the export work happens during load. Published cells only."""
    out = []
    for editor in editors:
        k = "perf.e.%s.%s.%s.median"
        need = [k % (editor, wl, m) for wl in ("prose-5kw", "prose-250kw") for m in ("save", "load")]
        if not all(n in facts for n in need):
            continue
        s5, l5, s250, l250 = (facts[n] for n in need)
        if s5 > 0 and l5 > 0 and s250 / s5 < 2 and l250 / l5 > 5:
            out.append("%s's save took %s ms at 5,000 words and %s ms at 250,000 words, while its load grew %.0f times" % (
                DISPLAY.get(editor, editor), fmt_ms(s5), fmt_ms(s250), l250 / l5))
    return "; ".join(out)


def _host_start(facts: dict, primary: Run) -> str:
    parts = []
    for editor in _editors(primary):
        for wl in _workloads(primary):
            key = "perf.e.%s.%s.host_start.median" % (editor, wl)
            if key in facts:
                parts.append("%s's native host starts before the load timer, in %s ms (median at %s); that start is in the process figures, not in load" % (
                    DISPLAY.get(editor, editor), fmt_ms(facts[key]), WORKLOAD_LABEL.get(wl, wl)))
                break
    return "; ".join(parts)


def _save_notes(facts: dict) -> str:
    notes = []
    if facts.get("perf.e.passthrough", "none") != "none":
        notes.append("- **The file is the input.** These editors wrote back the exact bytes they were given, on every sample: %s. "
                     "With nothing edited, they keep the original package; their save time is the time to decide that and hand the bytes back." % facts["perf.e.passthrough"])
    if facts.get("perf.e.prepared_export"):
        notes.append("- **The export is prepared during load.** %s. Their saved file is a new serialisation, not the input, "
                     "so the work is done before the save timer starts; the round trip counts it." % facts["perf.e.prepared_export"])
    if facts.get("perf.e.host_start"):
        notes.append("- **A host process.** %s." % facts["perf.e.host_start"])
    return "\n".join(notes) if notes else "- none"


def _names(editors) -> str:
    names = sorted({DISPLAY.get(e, e) for e in editors}, key=str.casefold)
    return ", ".join(names) if names else "none"


def _passthrough(primary: Run) -> str:
    """Editors whose saved file is byte-identical to the input it was given (every good sample)."""
    same = set()
    for (wl, editor), recs in primary.records.items():
        good = [r for r in recs if _good(r)]
        if good and all(r.get("output_sha256") == primary.summary["workloads"][wl]["sha256"] for r in good):
            same.add(editor)
    return _names(same)


def _correctness_lost(primary: Run) -> str:
    lost: dict[str, set] = {}
    for (_, editor), recs in primary.records.items():
        for r in recs:
            for name, ok in (r.get("check", {}).get("correctness") or {}).items():
                if not ok:
                    lost.setdefault(editor, set()).add(name)
    if not lost:
        return "none"
    return "; ".join("%s: %s" % (DISPLAY.get(e, e), ", ".join(sorted(v))) for e, v in sorted(lost.items(), key=lambda kv: DISPLAY.get(kv[0], kv[0]).casefold()))


def _exceptions(facts: dict, primary: Run, repro: Run) -> str:
    """One bullet per cell that is not a published figure, with the reason."""
    out = []
    for editor in _editors(primary):
        if editor == "libreoffice":
            continue
        for wl in _workloads(primary):
            for metric in TIMED:
                state, reason = _status(primary, wl, editor, metric)
                label = "%s, %s, %s" % (DISPLAY.get(editor, editor), WORKLOAD_LABEL.get(wl, wl), metric.replace("roundtrip", "round trip"))
                if state == "failed":
                    out.append("- %s: failed, %s." % (label, _short(reason)))
                elif state != "measured":
                    out.append("- %s: %s (%s)." % (label, state.replace("_", " "), reason or "no reason recorded"))
                elif facts.get("perf.e.%s.%s.%s.reproduced" % (editor, wl, metric)) is False:
                    out.append("- %s: not reproduced (second run median %s ms)." % (
                        label, fmt_ms(facts.get("perf.e.%s.%s.%s.repro_median" % (editor, wl, metric), float("nan")))))
    return "\n".join(out) if out else "- none"


def _date(run: Run) -> str:
    starts = [r["started_at"] for recs in run.records.values() for r in recs if r.get("started_at")]
    return min(starts)[:10] if starts else ""
