"""Report E's facts: the headless speed tables, from the runner's own files.

``facts_from_runs(primary, repro)`` reads two ``perf/runner/speed_headless.py``
publication runs (``dedicated_publish``, different seeds) and returns the
``perf.e.*`` facts the Report E template binds. A figure is published only if

- the primary run measured it with a publishable distribution (n >= 10, no
  excluded sample, quiet machine, AC power, pins attested), and
- the reproduction run measured the same cell and its median agrees
  (``reproduced``).

Otherwise the cell says why instead of a figure (a cell that did not
reproduce shows both medians, labelled "not reproduced"). Rows are in
alphabetical order: a table is not a ranking.

The round trip is computed per sample (that sample's load + that sample's
save, from one process), then summarised; it is not the sum of two medians.

Two checks run before any figure is read (codex review of #103):

- ``load_run`` reconciles the summary with the sample files: every row's n
  and median must be what its samples give, every sample must belong to the
  run, and no repetition may be missing.
- ``check_comparable`` refuses a "reproduction" that is the same run, has the
  same seed, or differs in documents, host, versions, timer boundaries, the
  runner's code or the lanes' files.
"""

from __future__ import annotations

import json
import math
import sys
from datetime import datetime
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from perf.analysis.summarize import summarize
from perf.runner.speed_headless import _sample_failure

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
    """Two medians agree if they differ by at most 10 % of the larger one, or
    by at most 2 ms. Symmetric: the order of the runs does not pick the verdict."""
    return abs(a - b) <= max(abs_tol, rel_tol * max(abs(a), abs(b)))


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
            recs = []
            for p in sorted(editor_dir.glob("r*.json")):
                rec = json.loads(p.read_text(encoding="utf-8"))
                if rec.get("run_id") != summary["run_id"]:
                    raise ValueError("%s belongs to another run (%s, not %s)" % (p, rec.get("run_id"), summary["run_id"]))
                recs.append(rec)
            run.records[wl, editor_dir.name] = recs
    _reconcile(run)
    return run


_MARK = {"C02": "model_ready_ms", "C16": "save_ms"}


def _reconcile(run: Run) -> None:
    """Fail closed unless the summary's rows are what the sample files give."""
    s = run.summary
    editors_rows = {(wl, e) for (wl, e, _) in run.rows}
    if editors_rows != set(run.records):
        raise ValueError("%s: summary rows and sample directories name different cells: %s" % (
            run.path, sorted(editors_rows ^ set(run.records))))
    starts = [r.get("started_at") for recs in run.records.values() for r in recs]
    if len(set(starts)) != len(starts) or None in starts:
        raise ValueError("%s: two sample files have the same start time (a copied sample), or one has none" % run.path)
    for (wl, editor), recs in run.records.items():
        reps = sorted(r.get("repetition") for r in recs)
        stopped = _stopped(run, wl, editor)
        if reps != list(range(1, len(reps) + 1)) or (len(reps) != s["repetitions"] and not stopped):
            raise ValueError("%s %s: sample files for repetitions %s, the run had %d" % (editor, wl, reps, s["repetitions"]))
        good = [r for r in recs if _good(r)]
        for crit, mark in _MARK.items():
            row = run.rows.get((wl, editor, crit))
            if row is None or row["outcome"] == "not_run":
                continue
            if row["outcome"] != "measured":
                if good and mark in good[0].get("marks", {}):
                    raise ValueError("%s %s %s: summary says %s, but %d samples are good" % (editor, wl, crit, row["outcome"], len(good)))
                continue
            values = [r["marks"][mark] for r in good]
            if len(values) != row["n"]:
                raise ValueError("%s %s %s: %d good samples, the summary says n=%s" % (editor, wl, crit, len(values), row["n"]))
            median = _stats(values, "process_cold_fs_warm")["median"]
            if abs(median - row["median_ms"]) > 1e-6 * max(1.0, abs(median)):
                raise ValueError("%s %s %s: median of the samples is %r, the summary says %r" % (editor, wl, crit, median, row["median_ms"]))


def _stopped(run: Run, wl: str, editor: str) -> bool:
    """The runner stopped this cell early: a failed row that says so. Only
    then may it have fewer sample files than repetitions."""
    return any(run.rows[wl, editor, c].get("outcome") == "failed"
               and "stopped after" in (run.rows[wl, editor, c].get("failure_reason") or "")
               for c in _MARK if (wl, editor, c) in run.rows)


_SAME_HOST = ("cpu_model", "cpu_cores_logical", "ram_bytes", "os", "os_version", "arch", "container", "cpu_quota",
              "memory_limit_bytes")


def check_comparable(primary: Run, repro: Run) -> None:
    """A reproduction is a second run of the same measurement, nothing else."""
    a, b = primary.summary, repro.summary
    if a["run_id"] == b["run_id"]:
        raise ValueError("the reproduction is the same run (%s)" % a["run_id"])
    if a["seed"] == b["seed"]:
        raise ValueError("the reproduction used the same seed (%s); its order would be the same" % a["seed"])
    wa = {w: m["sha256"] for w, m in a["workloads"].items()}
    wb = {w: m["sha256"] for w, m in b["workloads"].items()}
    if wa != wb:
        raise ValueError("the reproduction measured other workload documents: %s" % sorted(set(wa.items()) ^ set(wb.items())))
    ha, hb = ({k: x["host"].get(k) for k in _SAME_HOST} for x in (a, b))
    if ha != hb:
        raise ValueError("the reproduction ran on another host: %s vs %s" % (ha, hb))
    if a.get("versions") != b.get("versions"):
        raise ValueError("the reproduction attested other versions")
    if a.get("lanes") != b.get("lanes"):
        raise ValueError("the reproduction's lanes have other timer boundaries")
    pa, pb = a.get("provenance"), b.get("provenance")
    if not pa or not pb:
        raise ValueError("a run has no provenance; it predates the reviewed runner")
    for key in ("runner_sha256", "code", "lanes"):
        if pa.get(key) != pb.get(key):
            raise ValueError("the reproduction ran other code (provenance %s differs)" % key)
    if a.get("publication_rules") != b.get("publication_rules"):
        raise ValueError("the reproduction used other publication rules")
    for key in ("timeout_s", "warmup"):
        if a.get(key) != b.get(key):
            raise ValueError("the reproduction used another %s (%s, not %s)" % (key, b.get(key), a.get(key)))
    ta, tb = _window(primary), _window(repro)
    if not (ta[1] < tb[0] or tb[1] < ta[0]):
        raise ValueError("the two runs' samples overlap in time (%s to %s, %s to %s): a reproduction is measured after its primary"
                         % tuple(t.isoformat() for t in ta + tb))


def _instant(stamp: str) -> datetime:
    when = datetime.fromisoformat(stamp)
    if when.tzinfo is None:
        raise ValueError("sample start %r has no time zone" % stamp)
    return when


def _window(run: Run) -> tuple[datetime, datetime]:
    starts = sorted(_instant(r["started_at"]) for recs in run.records.values() for r in recs)
    return starts[0], starts[-1]


def _good(record: dict) -> bool:
    """The runner's own rule (one source of truth): no timeout, exit 0, every
    required mark exactly once, and a saved file that holds the document.
    A record without its mark counts cannot show the marks were each printed
    once, so it is not good (#119)."""
    return isinstance(record.get("mark_counts"), dict) and _sample_failure(record) is None  # null counts too (#120)


def _values(records: list[dict], metric: str) -> list[float]:
    good = [r for r in records if _good(r)]
    # a published mark is a time whatever the record's other fields say (#120)
    if metric == "roundtrip":
        return [r["marks"]["model_ready_ms"] + r["marks"]["save_ms"] for r in good
                if _finite_nonnegative(r["marks"].get("model_ready_ms")) and _finite_nonnegative(r["marks"].get("save_ms"))]
    key = METRICS[metric][0]
    if metric in ("load", "save"):
        return [r["marks"][key] for r in good if _finite_nonnegative(r["marks"].get(key))]
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
    # The summary's flag is not trusted on its own: the samples must meet the rule too.
    ok, why = _samples_publishable(run, wl, editor)
    if not ok:
        return "unpublishable", why
    if len(run.records.get((wl, editor), [])) != run.summary["repetitions"]:
        return "unpublishable", "%d samples for %d repetitions" % (len(run.records.get((wl, editor), [])), run.summary["repetitions"])
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
    if reason.startswith("marks: missing"):
        return "harness printed no %s time" % ("load" if "model_ready_ms" in reason else "save" if "save_ms" in reason else "host start")
    if reason.startswith("marks:") and "is not a time" in reason:
        return "harness printed an impossible time"
    if reason.startswith("marks:"):
        return "harness printed a time twice"
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
    if len(recs) != run.summary.get("repetitions"):
        return False, "%d samples for %s repetitions" % (len(recs), run.summary.get("repetitions"))
    noisy = sum(1 for r in recs if _noisy(run, r))
    if noisy / len(recs) > MAX_NOISY:
        return False, "%d of %d samples started above the load limit" % (noisy, len(recs))
    off_ac = sum(1 for r in recs if r.get("power_source") != "ac")
    if off_ac:
        return False, "%d of %d samples ran on battery or unknown power" % (off_ac, len(recs))
    return True, None


def _finite_nonnegative(value) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(value) and value >= 0


def _noisy(run: Run, record: dict) -> bool:
    """Started above the load limit: the runner's flag, or the recorded load
    against the recorded limit (the flag alone is not trusted, #119)."""
    if record.get("noisy"):
        return True
    limit = ((run.summary.get("quiet_machine_check_start") or {}).get("thresholds") or {}).get("load1_max")
    load = record.get("load_before")
    if not _finite_nonnegative(limit) or not load or not _finite_nonnegative(load[0]):
        return True  # nothing valid to judge by (NaN, negative, text): fail closed (#120)
    return load[0] > limit


def _metric_complete(recs: list[dict], metric: str) -> tuple[bool, str | None]:
    """Every good sample has this whole-process figure, and for CPU and memory
    no process of the lane outlived it (its time and memory would be missing)."""
    good = [r for r in recs if _good(r)]
    key = METRICS[metric][0]
    lacking = sum(1 for r in good if not _finite_nonnegative(r.get(key)))
    if lacking:
        return False, "%d of %d samples lack it" % (lacking, len(good))
    if metric in ("cpu", "rss"):
        left = sum(1 for r in good if r.get("resources_complete") is not True)
        if left:
            return False, "%d of %d samples left a process running" % (left, len(good))
    return True, None


def _diagnose(facts: dict, editor: str, wl: str, metric: str, first: str, second: str) -> None:
    """A figure that did not reproduce is not printed as a result. Its two
    medians go to a separate diagnostic table, labelled as such (codex #3)."""
    facts.setdefault("_not_reproduced", []).append((DISPLAY.get(editor, editor), WORKLOAD_LABEL.get(wl, wl), metric, first, second))


def _not_reproduced_table(facts: dict) -> str:
    rows = facts.pop("_not_reproduced", [])
    if not rows:
        return "Every figure that was measured in both runs reproduced."
    lines = ["| Editor | Workload | Figure | First run, median | Second run, median |", "|---|---|---|---|---|"]
    lines += ["| %s | %s | %s | %s | %s |" % r for r in rows]
    return "\n".join(lines)


# Work inside a lane's process that is the harness's, not the editor's (#119).
PROCESS_CAVEATS = {
    "canvas": {"wall": "includes a 500 ms wait in the harness between load and save"},
}


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
        _diagnose(facts, editor, wl, metric, fmt_ms(stats["median"]), fmt_ms(r_stats["median"]))
        return "not reproduced"
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
            r_recs = repro.records.get((wl, editor), [])
            complete = [_metric_complete(recs, metric), _metric_complete(r_recs, metric)]
            if not all(ok for ok, _ in complete):
                why = complete[0][1] or "second run: %s" % complete[1][1]
                cells.append("incomplete (%s)" % why)
                continue
            vals = _values(recs, metric)
            r_vals = _values(r_recs, metric)
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
            fmt = fmt_mib if metric == "rss" else fmt_ms
            if not ok:
                _diagnose(facts, editor, wl, metric, fmt(med), fmt(r_med))
                cells.append("not reproduced")
                continue
            caveat = PROCESS_CAVEATS.get(editor, {}).get(metric)
            cells.append("%s (%s)" % (fmt(med), caveat) if caveat else fmt(med))
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


def _cpus(h: dict) -> str:
    """The CPUs the process may use, against those its kernel reports. A quota is
    a ceiling on CPU time, not a reservation (#120): nothing here says "to itself"."""
    quota, n = h.get("cpu_quota"), h["cpu_cores_logical"]
    if quota is None:
        return "%d CPUs, no CPU quota" % n
    if quota >= n:
        return "all %d CPUs its kernel reports" % n
    return "a CPU quota of %g of the %d CPUs its kernel reports" % (quota, n)


def _ram(h: dict) -> str:
    limit, ram = h.get("memory_limit_bytes"), h.get("ram_bytes")
    if limit and (not ram or limit < ram):
        return "%d GiB RAM limit" % round(limit / 2**30)
    return "%d GiB RAM" % round(ram / 2**30)  # a limit above the RAM limits nothing


def _vm(h: dict) -> str:
    """The machine as its own firmware (DMI) and CPU flags named it."""
    vendor, product = h.get("machine_vendor"), h.get("machine_product")
    if vendor and h.get("hypervisor"):
        return "an %s virtual machine" % " ".join(v for v in (vendor, product) if v) if vendor[0] in "AEIOU" else \
            "a %s virtual machine" % " ".join(v for v in (vendor, product) if v)
    if h.get("hypervisor"):
        return "a virtual machine"
    return "a machine the run could not identify"


def _host(summary: dict) -> str:
    h = summary["host"]
    if h.get("container") or h.get("cpu_quota") or h.get("memory_limit_bytes"):
        return "%s, %s, %s, Linux %s, %s power" % (
            h["cpu_model"], _cpus(h), _ram(h), h["os_version"], h["power_source"].upper())
    system = "macOS %s" % h["os_version"] if h.get("os") == "darwin" else "%s %s" % (h.get("os", "?").capitalize(), h["os_version"])
    return "%s, %d cores, %d GiB RAM, %s, %s power" % (
        h["cpu_model"], h["cpu_cores_logical"], round(h["ram_bytes"] / 2**30), system, h["power_source"].upper())


def _machine(summary: dict) -> str:
    h = summary["host"]
    if h.get("container"):
        return "one Linux container on %s" % _vm(h)
    if h.get("cpu_quota") or h.get("memory_limit_bytes"):
        return "one cgroup-limited Linux process on %s" % _vm(h)
    return "one Mac" if h.get("os") == "darwin" else "one %s machine" % h.get("os", "?").capitalize()


def _steal_pct(summary: dict) -> float | None:
    """Share of CPU time the hypervisor withheld between the run's two quiet
    checks (``/proc/stat`` steal over all ticks); None without valid counters."""
    a = (summary.get("quiet_machine_check_start") or {}).get("cpu_ticks") or {}
    b = (summary.get("quiet_machine_check_end") or {}).get("cpu_ticks") or {}
    vals = [a.get("steal"), a.get("total"), b.get("steal"), b.get("total")]
    if not all(_finite_nonnegative(v) for v in vals):
        return None
    steal, total = vals[2] - vals[0], vals[3] - vals[1]
    if total <= 0 or steal < 0:
        return None
    return steal / total * 100


def _host_note(summary: dict, second: dict | None = None) -> str:
    """What the quiet check could and could not see, from what the run recorded."""
    h = summary["host"]
    if not h.get("container"):
        return ""
    n = h["cpu_cores_logical"]
    quota = h.get("cpu_quota")
    may = ("The container may use all %d CPUs its kernel reports." % n if quota is None or quota >= n
           else "The container may use %g of the %d CPUs its kernel reports." % (quota, n))
    parts = [may, "The load average counts every process on that kernel, in this container or any other, and was "
                  "judged against all %d CPUs; the process check cannot see processes outside the container." % n]
    steal = [v for v in (_steal_pct(summary), _steal_pct(second) if second else None) if v is not None]
    if steal and h.get("hypervisor"):
        runs = "%.2f%% during the run" % steal[0] + (" and %.2f%% during the second run" % steal[1] if len(steal) > 1 else "")
        parts.append("Work elsewhere on the physical server shows only as steal time: the hypervisor withheld %s." % runs)
    if h.get("power_supplies") == []:
        vendor = h.get("machine_vendor")
        parts.append("The container sees no power supply; AC power is inferred from the machine's vendor (%s)." % vendor
                     if vendor and h.get("power_source") == "ac" else "The container sees no power supply.")
    return " ".join(parts)


def _libreoffice_table(facts: dict, primary: Run, repro: Run) -> str | None:
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
        if r_med is None:
            lines.append("| %s | not reproduced (second run has no samples) | |" % WORKLOAD_LABEL.get(wl, wl))
        elif not reproduced(med, r_med):
            _diagnose(facts, "libreoffice", wl, "conversion", fmt_ms(med), fmt_ms(r_med))
            lines.append("| %s | not reproduced | |" % WORKLOAD_LABEL.get(wl, wl))
        else:
            lines.append("| %s | %s | agrees (%s) |" % (WORKLOAD_LABEL.get(wl, wl), fmt_ms(med), fmt_ms(r_med)))
    return "\n".join(lines) if found else None


def facts_from_runs(primary_dir: Path, repro_dir: Path) -> dict:
    primary, repro = load_run(primary_dir), load_run(repro_dir)
    check_comparable(primary, repro)
    s = primary.summary
    facts: dict = {
        "perf.e.run_id": s["run_id"],
        "perf.e.repro_run_id": repro.summary["run_id"],
        "perf.e.n": s["repetitions"],
        "perf.e.repro_n": repro.summary["repetitions"],
        "perf.e.seed": s["seed"],
        "perf.e.repro_seed": repro.summary["seed"],
        "perf.e.host": _host(s),
        "perf.e.machine": _machine(s),
        "perf.e.host_note": _host_note(s, repro.summary),
        "perf.e.date": s["quiet_machine_check_start"].get("date") or _date(primary),
        "perf.e.rel_tol_pct": round(REL_TOL * 100),
        "perf.e.abs_tol_ms": ABS_TOL_MS,
        "perf.e.workloads": _workload_table(primary),
        "perf.e.editors": len([e for e in _editors(primary) if e != "libreoffice"]),
        "perf.e.context.load": "layer model, boundary model_ready, cache state process_cold_fs_warm (fresh process, file system cache warm)",
        "perf.e.context.save": "layer model, boundary serialization_complete, cache state warm_steady (same process, right after load)",
        "perf.e.context.roundtrip": "the load clock plus the save clock of the same sample, summed per sample (layer model; "
                                    "the load starts process cold with the file system cache warm, the save follows in the same process); "
                                    "work outside the two clocks, such as starting the runtime, is in the process figures",
    }
    for metric in TIMED:
        facts["perf.e.table.%s" % metric] = _table(facts, primary, repro, metric)
    facts["perf.e.table.process"] = _process_table(facts, primary, repro)
    facts["perf.e.appendix"] = _appendix(facts, primary)
    lo = _libreoffice_table(facts, primary, repro)
    facts["perf.e.table.libreoffice"] = lo or "LibreOffice was not in these runs."
    facts["perf.e.summary"] = _summary(facts, primary)
    facts["perf.e.lanes"] = _lanes(primary)
    facts["perf.e.versions"] = _versions(primary)
    facts["perf.e.passthrough"] = _passthrough(primary)
    facts["perf.e.exceptions"] = _exceptions(facts, primary, repro)
    facts["perf.e.correctness_lost"] = _correctness_lost(primary)
    _host_start_facts(facts, primary, repro)
    facts["perf.e.prepared_export"] = _prepared_export(facts, _editors(primary))
    facts["perf.e.host_start"] = _host_start(facts, primary)
    facts["perf.e.save_notes"] = _save_notes(facts)
    facts["perf.e.check"] = _check_text(s)
    facts["perf.e.end_check"] = " ".join(t for t in (_end_check(s), _end_check(repro.summary).replace(
        "When the last sample had finished", "After the second run")) if t)
    facts["perf.e.not_reproduced"] = _not_reproduced_table(facts)
    facts["perf.e.dirty_allowed"] = _dirty_allowed(s)
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


def _covers(good: list[dict], mark: str) -> bool:
    """Every good sample printed ``mark`` exactly once, as a time (and there is
    at least one sample). An optional mark is not checked by the runner (#120)."""
    return bool(good) and all(
        (r.get("mark_counts") or {}).get(mark) == 1 and _finite_nonnegative((r.get("marks") or {}).get(mark))
        for r in good)


def _end_check(summary: dict) -> str:
    """The quiet check repeated after the last sample. If it was not quiet, the report says why (#119)."""
    end = summary.get("quiet_machine_check_end") or {}
    if end.get("quiet"):
        return ""
    reasons = "; ".join(end.get("reasons") or ["no end-of-run check was recorded"])
    return "When the last sample had finished, the quiet check was no longer clean: %s." % reasons


def _host_start_facts(facts: dict, primary: Run, repro: Run) -> None:
    """A host start time is printed under the same rules as a table figure:
    publishable samples in both runs, and the two medians agree."""
    for (wl, editor), recs in sorted(primary.records.items()):
        good = [r for r in recs if _good(r)]
        if not _covers(good, "host_start_ms"):
            continue  # a host start is published only if every sample reported it
        starts = [r["marks"]["host_start_ms"] for r in good]
        r_good = [r for r in repro.records.get((wl, editor), []) if _good(r)]
        if not _covers(r_good, "host_start_ms"):
            continue  # and every good sample of the second run (#119)
        r_starts = [r["marks"]["host_start_ms"] for r in r_good]
        if _status(primary, wl, editor, "load")[0] != "measured" or _status(repro, wl, editor, "load")[0] != "measured":
            continue
        if not (_samples_publishable(primary, wl, editor)[0] and _samples_publishable(repro, wl, editor)[0]) or not r_starts:
            continue
        med = _stats(starts, "process_cold_fs_warm")["median"]
        r_med = _stats(r_starts, "process_cold_fs_warm")["median"]
        if reproduced(med, r_med):
            facts["perf.e.%s.%s.host_start.median" % (editor, wl)] = round(med, 3)


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


def _check_text(summary: dict) -> str:
    """The content check the run applied, in words, from its own publication rules."""
    limits = summary["publication_rules"]["check_limits"]
    keep, longer = limits["default"]
    text = "keep at least %d percent of the input's words, counted word by word, be at most %d percent longer, and end with the sentinel" % (
        round(keep * 100), round((longer - 1) * 100))
    if "corpus" in limits:
        c_keep, c_longer = limits["corpus"]
        text += " (`complex.docx`, which is mostly tables, images and fields: keep %d percent, at most %s times as long, no sentinel)" % (
            round(c_keep * 100), ("%.2f" % c_longer).rstrip("0").rstrip("."))
    return text


def _dirty_allowed(summary: dict) -> str:
    """Changed tracked files the run accepted, each with the reason it recorded."""
    out = []
    for editor, rec in sorted((summary.get("versions") or {}).get("editors", {}).items()):
        for _, why in sorted((rec.get("dirty_allowed") or {}).items()):
            out.append("%s: %s" % (DISPLAY.get(editor, editor), why))
    return "; ".join(out) if out else "none"


def _date(run: Run) -> str:
    starts = [r["started_at"] for recs in run.records.values() for r in recs if r.get("started_at")]
    return min(starts)[:10] if starts else ""
