"""Headless speed runner for Report E (editors_trial#103).

``benchmark_ci_contract.py`` checks the trial's contract on CI. This runner
produces the headless speed distributions the report publishes, and it fixes
what an audit found wrong with timing through the contract runner:

- **one process, every metric.** Each sample is one fresh process running the
  editor's own import and export. Its ``PERF model_ready_ms`` (C02), its
  ``PERF save_ms`` (C16), its wall time and its reaped CPU time all come from
  that one process, so a load and a save can be paired.
- **interleaved.** Each repetition runs every editor once, in an order
  reshuffled per repetition from a recorded seed, so a slow minute on the
  host is spread over every editor instead of landing on one.
- **warm file system, cold process.** One discarded warm-up sample per editor
  and workload brings the editor's code and the fixture into the page cache;
  every kept sample is then ``process_cold_fs_warm`` for the load and
  ``warm_steady`` for the save, which follows the load in the same process.
- **every sample kept and checked.** Each sample is an immutable record with
  its command, environment keys, exit status, marks, output tails, the output
  hash, and a namespace-aware check that the saved file still holds the whole
  document. A sample whose output lost the document is excluded and counted,
  never written as a zero; a crash keeps the samples before it.
- **controlled environment.** Lanes get an allowlisted environment plus
  ``PERF_ONLY=1``; ``EDITOR_CONFIG``, ``OUT_DIR`` and the like do not leak in.
- **quiet machine.** ``dedicated_publish`` refuses to start unless
  ``quiet_machine_check()`` passes (AGENTS.md §3); the 1-minute load average
  is recorded before and after every sample.

Usage::

    PYTHONPATH=. python3 -I perf/runner/speed_headless.py \\
        --execution-profile dedicated_publish --repetitions 30 \\
        --workloads prose-500w prose-5kw prose-50kw prose-250kw complex-corpus
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import random
import signal
import subprocess
import sys
import threading
import time
import uuid
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from perf.analysis.publication_gate import trial_publishable_flags
from perf.analysis.summarize import summarize
from perf.fixtures.docx_workload import workload_docx
from perf.fixtures.profiles import assert_workload_allowed
from perf.runner.host import LOAD_FRACTION, host_record, quiet_machine_check
from perf.runner.load_timing import parse_perf_lines
from perf.schema import sample_budget_for_profile, validate_environment, validate_trial

INTERPRETATION_CONDITIONS = ["I%02d" % n for n in range(1, 13)]
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
ENV_ALLOW = ("PATH", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "TMPDIR", "SHELL", "TERM")
# Publication rules this runner adds on top of perf/analysis/publication_gate.
MIN_PUBLISH_N = 10
MAX_NOISY_FRACTION = 0.10
CRITERIA = (
    # criterion, mark, cache state, boundary, layer
    ("C02", "model_ready_ms", "process_cold_fs_warm", "model_ready", "model"),
    ("C16", "save_ms", "warm_steady", "serialization_complete", "model"),
)


class NotQuiet(RuntimeError):
    """The machine failed the AGENTS.md §3 quiet check, or runs on battery."""


class PinMismatch(RuntimeError):
    """A checkout on disk is not the commit the trial pins."""


def pin_label(editor_id: str) -> str:
    from perf.runner.benchmark_ci_contract import pin_label as _pin

    return _pin(editor_id)


# ---------------------------------------------------------- attestation ----
# What each lane actually runs, read from disk at run time: the checkouts it
# imports, the published packages it loads, the binaries it executes.
ATTEST = {
    "plate": {"checkouts": ["repos/plate"]},
    "folio": {"checkouts": ["repos/folio"]},
    "superdoc": {"checkouts": ["repos/superdoc"], "packages": {"@superdoc/sdk": "harness/superdoc-sdk"}},
    "office-open": {"checkouts": ["repos/office-open"]},
    "eigenpal": {"checkouts": ["repos/eigenpal-docx-editor"]},
    "docen": {"checkouts": ["repos/docen"]},
    "genoffice": {"checkouts": ["repos/genoffice"]},
    "fidus": {"checkouts": ["repos/fiduswriter-document-ts", "repos/fiduswriter"]},
    "docsplus": {"checkouts": ["repos/docs-plus"]},
    "canvas": {"checkouts": ["repos/canvas-editor", "repos/canvas-editor-plugin"]},
    "wordcraft": {"checkouts": ["repos/wordcraft"], "binaries": {"wc-harness": "harness/wordcraft/target/release/wc-harness"}},
    "docxodus": {"checkouts": ["repos/docxodus"], "packages": {"docxodus": "harness/ui/docxodus"}},
    "libreoffice": {"command": ["soffice", "--version"]},
}
TOOLS = {"node": ["node", "--version"], "bun": ["bun", "--version"]}


def _capture(cmd: list[str], cwd: Path | None = None) -> str | None:
    try:
        out = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 and out.stdout.strip() else None


def _git_head(path: Path) -> str | None:
    return _capture(["git", "-C", str(path), "rev-parse", "--short=9", "HEAD"])


def _package_version(root: Path, name: str) -> str | None:
    try:
        return json.loads((root / "node_modules" / name / "package.json").read_text(encoding="utf-8"))["version"]
    except (OSError, ValueError, KeyError):
        return None


def attest_versions(editors: list[str]) -> dict:
    tools = {name: _capture(cmd) for name, cmd in TOOLS.items()}
    tools["python"] = sys.version.split()[0]
    out = {}
    for editor_id in editors:
        spec = ATTEST.get(editor_id, {})
        try:
            pin = pin_label(editor_id)
        except KeyError:
            pin = None
        record: dict = {"pin": pin, "checkouts": {}, "packages": {}, "binaries": {}}
        for rel in spec.get("checkouts", []):
            record["checkouts"][rel] = _git_head(REPO / rel)
        for name, rel in spec.get("packages", {}).items():
            record["packages"][name] = _package_version(REPO / rel, name)
        for name, rel in spec.get("binaries", {}).items():
            path = REPO / rel
            record["binaries"][name] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        if "command" in spec:
            record["version"] = _capture(spec["command"])
        heads = list(record["checkouts"].values())
        record["matches_pin"] = bool(pin) and all(h and h in pin for h in heads) if heads else None
        out[editor_id] = record
    return {"tools": tools, "editors": out}


# ---------------------------------------------------------------- lanes ----

def _node_lane(cmd, cwd, env=None, boundary=""):
    return {"cmd": cmd, "cwd": cwd, "env": env or {}, "marks": ("model_ready_ms", "save_ms"), "boundary": boundary}


def default_lanes() -> dict:
    """The thirteen headless lanes: the fidelity trial's own entry points."""
    r, h = REPO / "repos", REPO / "harness"
    lanes = {
        "plate": _node_lane(
            lambda i, o, w: ["bun", "--preload", "./aliases.ts", "roundtrip.ts", str(i), str(o)],
            h / "plate",
            boundary="importDocx(lossPolicy allow, 45 plugins) + createEditor | exportDocx",
        ),
        "folio": _node_lane(
            lambda i, o, w: ["bun", str(h / "folio.ts"), str(i), str(o), "model"],
            r / "folio",
            boundary="parseDocx(preloadFonts false) | repackDocx",
        ),
        "superdoc": _node_lane(
            lambda i, o, w: ["node", str(h / "superdoc.mjs"), str(i), str(o)],
            REPO,
            boundary="client.open(path) after client.connect() | doc.save(path)",
        ),
        "office-open": _node_lane(
            lambda i, o, w: [
                str(r / "office-open" / "node_modules" / ".bin" / "tsx"),
                "--tsconfig",
                str(r / "office-open" / "packages" / "docx" / "tsconfig.json"),
                str(h / "officeopen" / "roundtrip.mts"),
                str(i),
                str(o),
            ],
            r / "office-open",
            boundary="parseDocument | generateDocument",
        ),
        "eigenpal": _node_lane(
            lambda i, o, w: ["bun", str(h / "eigenpal.ts"), str(i), str(o), "store"],
            r / "eigenpal-docx-editor",
            boundary="readOoxmlPackage | writeOoxmlPackage (store lane)",
        ),
        "docen": _node_lane(
            lambda i, o, w: [str(r / "docen" / "node_modules" / ".bin" / "tsx"), str(h / "docen" / "roundtrip.mts"), str(i), str(o)],
            r / "docen",
            boundary="parseDOCX | generateDOCX",
        ),
        "genoffice": _node_lane(
            lambda i, o, w: ["node", str(h / "genoffice.cts"), str(i), str(o)],
            r / "genoffice",
            env={
                "NODE_OPTIONS": "--import %s --import %s"
                % (h / "css-stub.mjs", r / "genoffice" / "node_modules" / "tsx" / "dist" / "loader.mjs"),
                "NODE_PATH": str(r / "genoffice" / "node_modules"),
            },
            boundary="parseDocx + Tiptap setContent | getJSON + pmDocToSavePlan + saveDocx",
        ),
        "fidus": _node_lane(
            lambda i, o, w: [str(r / "fiduswriter-document-ts" / "node_modules" / ".bin" / "tsx"), "--no-cache", str(h / "fidus" / "roundtrip.mts")],
            r / "fiduswriter-document-ts",
            env={"TEMPLATE": "generated", "NODE_PATH": str(r / "fiduswriter-document-ts" / "node_modules")},
            boundary="JSZip.loadAsync + DocxConvert.init | DOCXExporter.init (template and CSL prepared before)",
        ),
        "docsplus": _node_lane(
            lambda i, o, w: ["bun", str(h / "docsplus" / "roundtrip.ts"), str(i), str(o)],
            h / "docsplus" / "repo-copy",
            boundary="importDocx (mammoth) | exportDocx",
        ),
        "canvas": _node_lane(
            lambda i, o, w: [str(r / "canvas-editor" / "node_modules" / ".bin" / "vitest"), "run", "--root", str(h / "canvas")],
            r / "canvas-editor",
            env={"NODE_PATH": str(r / "canvas-editor" / "node_modules")},
            boundary="executeImportDocx | executeExportDocx (jsdom; canvas and workers mocked)",
        ),
        "wordcraft": _node_lane(
            lambda i, o, w: [str(h / "wordcraft" / "target" / "release" / "wc-harness"), str(i), str(o)],
            h / "wordcraft",
            boundary="wordcraft_docx::read | wordcraft_docx::write (native release build)",
        ),
        "docxodus": _node_lane(
            lambda i, o, w: ["node", str(h / "ui" / "docxodus" / "roundtrip.mjs"), str(i), str(o)],
            h / "ui" / "docxodus",
            boundary="openDocxSession | session.save (WASM initialised before the timer)",
        ),
        "libreoffice": {
            "cmd": lambda i, o, w: [
                "soffice",
                "-env:UserInstallation=%s" % (w / "lo-profile").as_uri(),
                "--headless",
                "--norestore",
                "--convert-to",
                "docx",
                "--outdir",
                str(o.parent / "lo"),
                str(i),
            ],
            "cwd": REPO,
            "env": {},
            "marks": (),
            "boundary": "soffice --convert-to docx: whole conversion, no load/save split",
            "relocate_output": "lo",
        },
    }
    # canvas reads its paths from the environment, not argv
    lanes["canvas"]["env_paths"] = ("VITEST_DOCX_INPUT", "VITEST_DOCX_OUTPUT")
    lanes["fidus"]["env_paths"] = ("IN_DOCX", "OUT_DOCX")
    return lanes


def controlled_env(extra: dict) -> dict:
    env = {k: os.environ[k] for k in ENV_ALLOW if k in os.environ}
    env.update(extra)
    env["PERF_ONLY"] = "1"
    return env


def plan_order(editors: list[str], repetitions: int, seed: int) -> list[tuple[int, list[str]]]:
    plan = []
    for rep in range(1, repetitions + 1):
        order = list(editors)
        random.Random("%d:%d" % (seed, rep)).shuffle(order)
        plan.append((rep, order))
    return plan


# --------------------------------------------------------------- checks ----

def _paragraph_texts(document: bytes) -> list[str]:
    root = ET.fromstring(document)
    return ["".join(t.text or "" for t in p.iter("{%s}t" % W_NS)) for p in root.iter("{%s}p" % W_NS)]


def check_output(path: Path, expect: dict) -> dict:
    """Does the saved file still hold the whole document? Never raises."""
    result = {"parse_ok": False, "sentinel": None, "word_ratio": None, "correctness": {}, "complete": False, "text_head": ""}
    try:
        with zipfile.ZipFile(path) as zf:
            document = zf.read("word/document.xml")
        texts = _paragraph_texts(document)
    except Exception as exc:
        result["error"] = "%s: %s" % (type(exc).__name__, exc)
        return result
    text = "\n".join(texts)
    result["parse_ok"] = True
    result["text_head"] = text[:200]
    expected_words = expect.get("expected_words") or expect.get("word_count") or 1
    result["word_ratio"] = round(len(text.split()) / float(expected_words), 4)
    sentinel = expect.get("sentinel")
    if sentinel:
        result["sentinel"] = sentinel in text
    for name, value in (expect.get("correctness") or {}).items():
        result["correctness"][name] = value in text
    if expect.get("shape") == "corpus":
        result["complete"] = result["word_ratio"] >= 0.5
    else:
        result["complete"] = bool(result["sentinel"]) and result["word_ratio"] >= 0.98
    return result


def _expectation(meta: dict) -> dict:
    from perf.fixtures.generate import correctness_fixtures

    correctness = {}
    if meta["shape"] != "corpus":
        for key, raw in correctness_fixtures().items():
            correctness[key] = raw.decode("utf-8").rstrip("\n")
    return {
        "sentinel": meta.get("sentinel"),
        "expected_words": len(meta["text"].split()),
        "word_count": meta["word_count"],
        "shape": meta["shape"],
        "correctness": correctness,
    }


# --------------------------------------------------------------- sample ----

def _tail(text: str, limit: int = 4000) -> str:
    return text[-limit:] if text else ""


def _spawn_and_reap(cmd: list[str], cwd, env: dict, timeout_s: float) -> dict:
    """Run one lane in its own session and reap it with ``wait4``.

    ``wait4`` returns the resource use of this child and every descendant it
    reaped, so CPU time and peak resident memory are this sample's own (the
    peak is the largest single process in the tree, not a sum). A lane that
    outlives ``timeout_s`` has its whole process group killed.
    """
    result = {"returncode": None, "stdout": "", "stderr": "", "timed_out": False,
              "wall_ms": 0.0, "cpu_ms": None, "max_rss_bytes": None}
    t0 = time.perf_counter()
    try:
        proc = subprocess.Popen(cmd, cwd=str(cwd), env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    except OSError as exc:
        result["stderr"] = "spawn failed: %s" % exc
        return result
    chunks: dict[str, list[bytes]] = {"stdout": [], "stderr": []}

    def _drain(name, pipe):
        for block in iter(lambda: pipe.read(65536), b""):
            chunks[name].append(block)

    readers = [threading.Thread(target=_drain, args=(n, p), daemon=True) for n, p in (("stdout", proc.stdout), ("stderr", proc.stderr))]
    for reader in readers:
        reader.start()

    def _kill():
        result["timed_out"] = True
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass

    timer = threading.Timer(timeout_s, _kill)
    timer.start()
    try:
        _, status, usage = os.wait4(proc.pid, 0)
    finally:
        timer.cancel()
    result["wall_ms"] = (time.perf_counter() - t0) * 1000.0
    proc.returncode = os.waitstatus_to_exitcode(status)  # tell Popen it is reaped
    result["returncode"] = proc.returncode
    try:  # anything the lane left behind in its group (it was not reaped, so it is not counted)
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    for reader in readers:
        reader.join(timeout=10)
    result["stdout"] = b"".join(chunks["stdout"]).decode("utf-8", "replace")
    result["stderr"] = b"".join(chunks["stderr"]).decode("utf-8", "replace")
    result["cpu_ms"] = (usage.ru_utime + usage.ru_stime) * 1000.0
    result["max_rss_bytes"] = usage.ru_maxrss if sys.platform == "darwin" else usage.ru_maxrss * 1024
    return result


def run_sample(lane: dict, editor_id: str, meta: dict, expect: dict, work: Path, timeout_s: float) -> dict:
    work.mkdir(parents=True, exist_ok=True)
    indocx = work / ("in-%s.docx" % meta["workload_id"])
    outdocx = work / ("out-%s.docx" % meta["workload_id"])
    indocx.write_bytes(meta["docx"])
    if outdocx.exists():
        outdocx.unlink()
    env = controlled_env(dict(lane.get("env") or {}))
    for key, value in zip(lane.get("env_paths") or (), (indocx, outdocx)):
        env[key] = str(value)
    cmd = lane["cmd"](indocx, outdocx, work)
    load_before = [round(v, 2) for v in os.getloadavg()]
    started = _dt.datetime.now(_dt.timezone.utc).isoformat()
    run = _spawn_and_reap(cmd, lane["cwd"], env, timeout_s)
    rc, out, err, timed_out = run["returncode"], run["stdout"], run["stderr"], run["timed_out"]
    wall_ms, cpu_ms, max_rss = run["wall_ms"], run["cpu_ms"], run["max_rss_bytes"]
    relocate = lane.get("relocate_output")
    if relocate:
        produced = outdocx.parent / relocate / indocx.with_suffix(".docx").name
        if produced.is_file():
            produced.replace(outdocx)
    marks = parse_perf_lines(err, out)
    check = check_output(outdocx, expect) if outdocx.is_file() else {"parse_ok": False, "complete": False, "error": "no output file"}
    return {
        "editor_id": editor_id,
        "workload_id": meta["workload_id"],
        "command": cmd,
        "cwd": str(lane["cwd"]),
        "env_keys": sorted(env),
        "env_lane": {k: v for k, v in (lane.get("env") or {}).items()},
        "returncode": rc,
        "timed_out": timed_out,
        "marks": marks,
        "wall_ms": round(wall_ms, 6),
        "cpu_ms": round(cpu_ms, 6) if cpu_ms is not None else None,
        "max_rss_bytes": max_rss,
        "stdout_tail": _tail(out),
        "stderr_tail": _tail(err),
        "output_sha256": hashlib.sha256(outdocx.read_bytes()).hexdigest() if outdocx.is_file() else None,
        "output_bytes": outdocx.stat().st_size if outdocx.is_file() else None,
        "check": check,
        "load_before": load_before,
        "load_after": [round(v, 2) for v in os.getloadavg()],
        "started_at": started,
    }


def _sample_failure(record: dict) -> str | None:
    if record["timed_out"]:
        return "timeout"
    if record["returncode"] != 0:
        return "rc=%s" % record["returncode"]
    if not record["check"].get("complete"):
        return "correctness: %s" % (record["check"].get("error") or "output does not hold the whole document")
    return None


def _write_once(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=1, sort_keys=True)
        handle.write("\n")


# ---------------------------------------------------------------- suite ----

def _environment(host: dict, host_class: str, profile: str, editor_id: str, meta: dict, cache_state: str) -> dict:
    env = {
        "host_class": host_class,
        "execution_profile": profile,
        "cpu_model": host["cpu_model"],
        "os": host["os"],
        "os_version": host["os_version"],
        "arch": host["arch"],
        "ram_bytes": host["ram_bytes"],
        "cpu_cores_logical": host["cpu_cores_logical"],
        "power_source": host["power_source"],
        "editor_id": editor_id,
        "editor_version": pin_label(editor_id),
        "fixture_sha256": meta["sha256"],
        "cache_state": cache_state,
        "feature_profile": "P0",
        "workload_id": meta["workload_id"],
        "fixture_byte_size": meta["byte_size"],
        "fixture_paragraph_count": meta["paragraph_count"],
        "fixture_word_count": meta["word_count"],
        "paragraph_shape": meta["shape"],
        "unicode_class": meta["unicode_class"],
        "match_count": meta["match_count"],
        "repetition_unit": "fresh_process",
        "run_kind": "timing",
        "headless": True,
        "display_refresh_hz": None,
        "interpretation_conditions": list(INTERPRETATION_CONDITIONS),
        "feature_fallback": [],
    }
    validate_environment(env)
    return env


def run_suite(
    *,
    lanes: dict,
    workloads: list[str],
    repetitions: int,
    seed: int,
    out_root: Path,
    execution_profile: str,
    timeout_s: float,
    warmup: int = 1,
    wait_quiet_s: float = 0.0,
    max_consecutive_failures: int = 3,
) -> dict:
    quiet = quiet_machine_check()
    deadline = time.monotonic() + wait_quiet_s
    while execution_profile == "dedicated_publish" and not quiet["quiet"] and time.monotonic() < deadline:
        time.sleep(30)
        quiet = quiet_machine_check()
    if execution_profile == "dedicated_publish" and not quiet["quiet"]:
        raise NotQuiet("; ".join(quiet["reasons"]))
    budget = sample_budget_for_profile(execution_profile, "fresh_process")
    if repetitions > budget:
        raise ValueError("%d repetitions exceed the %s budget of %d" % (repetitions, execution_profile, budget))
    host_class = "dedicated" if execution_profile == "dedicated_publish" else "ci_coarse"
    host = host_record()
    if execution_profile == "dedicated_publish" and host["power_source"] != "ac":
        raise NotQuiet("host runs on %s power; a publication run needs AC power" % host["power_source"])
    versions = attest_versions(list(lanes))
    if execution_profile == "dedicated_publish":
        off = sorted(e for e, rec in versions["editors"].items() if rec["matches_pin"] is False)
        if off:
            raise PinMismatch("checkouts off their pins: %s" % ", ".join(
                "%s %s (pin %s)" % (e, versions["editors"][e]["checkouts"], versions["editors"][e]["pin"]) for e in off))
    out_root = Path(out_root)
    samples_dir = out_root / "samples"
    run_id = uuid.uuid4().hex[:12]
    load_limit = LOAD_FRACTION * host["cpu_cores_logical"]
    rows: list[dict] = []
    workload_meta = {}
    editors = list(lanes)
    for workload_id in workloads:
        assert_workload_allowed(execution_profile, workload_id)
        meta = workload_docx(workload_id)
        expect = _expectation(meta)
        workload_meta[workload_id] = {k: meta[k] for k in ("sha256", "byte_size", "paragraph_count", "word_count", "shape", "builder_version")}
        records: dict[str, list[dict]] = {e: [] for e in editors}
        plan = [(0, list(editors))] * warmup + plan_order(editors, repetitions, seed)
        streak = {e: 0 for e in editors}
        stopped: dict[str, str] = {}
        for rep, order in plan:
            for index, editor_id in enumerate(order):
                if editor_id in stopped:
                    continue
                work = out_root / "work" / run_id / workload_id / editor_id
                record = run_sample(lanes[editor_id], editor_id, meta, expect, work, timeout_s)
                record.update({"repetition": rep, "order_index": index, "warmup": rep == 0, "run_id": run_id})
                record["noisy"] = record["load_before"][0] > load_limit
                name = "w%03d-%s.json" % (index, uuid.uuid4().hex[:6]) if rep == 0 else "r%03d.json" % rep
                _write_once(samples_dir / workload_id / editor_id / name, record)
                if rep:
                    records[editor_id].append(record)
                # A lane that keeps failing on this workload is not sampled further
                # (a 250k-word crash costs minutes per attempt); the stop is recorded.
                streak[editor_id] = streak[editor_id] + 1 if _sample_failure(record) else 0
                if max_consecutive_failures and streak[editor_id] >= max_consecutive_failures:
                    stopped[editor_id] = "stopped after %d consecutive failures (last: %s)" % (
                        streak[editor_id], _sample_failure(record))
        for editor_id in editors:
            rows.extend(
                _rows_for(
                    lanes[editor_id], editor_id, meta, records[editor_id], host, host_class, execution_profile, out_root, run_id,
                    stopped=stopped.get(editor_id),
                )
            )
    summary = {
        "suite": "speed_headless",
        "run_id": run_id,
        "execution_profile": execution_profile,
        "host_class": host_class,
        "host": host,
        "versions": versions,
        "quiet_machine_check_start": quiet,
        "quiet_machine_check_end": quiet_machine_check(),
        "repetitions": repetitions,
        "warmup": warmup,
        "seed": seed,
        "timeout_s": timeout_s,
        "workloads": workload_meta,
        "lanes": {e: lanes[e].get("boundary", "") for e in editors},
        "publication_rules": {
            "min_n": MIN_PUBLISH_N,
            "max_noisy_fraction": MAX_NOISY_FRACTION,
            "no_excluded_samples": True,
            "gate": "perf/analysis/publication_gate.trial_publishable_flags",
        },
        "rows": rows,
    }
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def _rows_for(lane, editor_id, meta, records, host, host_class, profile, out_root, run_id, stopped=None) -> list[dict]:
    rows = []
    failures = [(r, _sample_failure(r)) for r in records]
    good = [r for r, why in failures if why is None]
    reasons = sorted({why for _, why in failures if why})
    if stopped:
        reasons.append(stopped)
    noisy = sum(1 for r in records if r.get("noisy"))
    supplementary = {
        "wall_ms_median": _median([r["wall_ms"] for r in good]),
        "cpu_ms_median": _median([r["cpu_ms"] for r in good]),
        "max_rss_bytes_median": _median([r["max_rss_bytes"] for r in good if r.get("max_rss_bytes")]),
        "noisy_samples": noisy,
        "word_ratio_min": min((r["check"].get("word_ratio") or 0 for r in good), default=None),
        "correctness_lost": sorted({k for r in good for k, ok in (r["check"].get("correctness") or {}).items() if not ok}),
    }
    if "host_start_ms" in (good[0]["marks"] if good else {}):
        supplementary["host_start_ms_median"] = _median([r["marks"].get("host_start_ms", 0.0) for r in good])
    for criterion, mark, cache_state, boundary, layer in CRITERIA:
        env = _environment(host, host_class, profile, editor_id, meta, cache_state)
        base = {
            "schema_version": 1,
            "criterion_id": criterion,
            "layer": layer,
            "boundary": boundary,
            "claims": [],
            "latency_ms": None,
            "environment": env,
            "editor_id": editor_id,
            "lane": lane.get("boundary", ""),
            "diagnostic": {"run_id": run_id, "excluded_samples": len(records) - len(good), "reasons": reasons, **supplementary},
        }
        row = {
            "criterion_id": criterion,
            "editor_id": editor_id,
            "workload_id": meta["workload_id"],
            "excluded": len(records) - len(good),
            **supplementary,
        }
        if mark not in lane.get("marks", ()):
            trial = dict(base, outcome="not_run", samples_ms=[], failure_reason="%s: lane has no %s mark" % (editor_id, mark))
            row.update(outcome="not_run", failure_reason=trial["failure_reason"], publishable=False, n=0, median_ms=None)
        elif not good:
            reason = "; ".join(reasons) or "no samples"
            trial = dict(base, outcome="failed", samples_ms=[], failure_reason=reason)
            row.update(outcome="failed", failure_reason=reason, publishable=False, n=0, median_ms=None)
        else:
            missing = [r for r in good if mark not in r["marks"]]
            if missing:
                reason = "harness did not emit PERF %s" % mark
                trial = dict(base, outcome="failed", samples_ms=[], failure_reason=reason)
                row.update(outcome="failed", failure_reason=reason, publishable=False, n=0, median_ms=None)
            else:
                samples = [round(float(r["marks"][mark]), 6) for r in good]
                stats = summarize(samples, cache_state, "fresh_process", seed=0)
                pub, block = trial_publishable_flags(env, layer, len(samples))
                extra = []
                if host_class != "dedicated":
                    extra.append("%s host: not a publication run" % host_class)
                if len(samples) < MIN_PUBLISH_N:
                    extra.append("n=%d below the report's minimum of %d" % (len(samples), MIN_PUBLISH_N))
                if len(records) != len(good):
                    extra.append("%d of %d samples excluded (%s)" % (len(records) - len(good), len(records), "; ".join(reasons)))
                if records and noisy / len(records) > MAX_NOISY_FRACTION:
                    extra.append("%d of %d samples started above the quiet load limit" % (noisy, len(records)))
                if extra:
                    pub, block = False, "; ".join(([block] if block else []) + extra)
                trial = dict(base, outcome="measured", samples_ms=samples, summary_stats=stats, publishable=pub)
                trial["publication_block_reason"] = block if not pub else None
                row.update(
                    outcome="measured",
                    n=stats["n"],
                    median_ms=stats["median"],
                    p90_ms=stats["p90"],
                    p95_ms=stats["p95"],
                    mad_ms=stats["mad"],
                    ci95_ms=[stats["ci95_low"], stats["ci95_high"]],
                    min_ms=stats["minimum"],
                    max_ms=stats["maximum"],
                    publishable=pub,
                    publication_block_reason=trial["publication_block_reason"],
                )
        validate_trial(trial)
        _write_once(out_root / "trials" / ("%s-%s-%s-%s.json" % (criterion.lower(), editor_id, meta["workload_id"], run_id)), trial)
        rows.append(row)
    return rows


def _median(values):
    values = sorted(values)
    if not values:
        return None
    mid = len(values) // 2
    return values[mid] if len(values) % 2 else (values[mid - 1] + values[mid]) / 2.0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--workloads", nargs="+", default=["prose-500w"])
    parser.add_argument("--editors", nargs="+", default=None)
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--seed", type=int, default=20261109)
    parser.add_argument("--execution-profile", choices=("ci_broad", "dedicated_publish"), default="ci_broad")
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("--wait-quiet", type=float, default=0.0, help="seconds to wait for a quiet machine")
    parser.add_argument("--max-consecutive-failures", type=int, default=3, help="stop sampling an editor on a workload after this many failures in a row (0: never)")
    parser.add_argument("--out-root", type=Path, default=None)
    args = parser.parse_args(argv)
    lanes = default_lanes()
    if args.editors:
        unknown = sorted(set(args.editors) - set(lanes))
        if unknown:
            parser.error("unknown editors: %s" % ", ".join(unknown))
        lanes = {e: lanes[e] for e in args.editors}
    out_root = args.out_root or REPO / "perf" / "out" / ("speed_headless_%s_%s" % (args.execution_profile, _dt.date.today().strftime("%Y_%m_%d")))
    try:
        summary = run_suite(
            lanes=lanes,
            workloads=args.workloads,
            repetitions=args.repetitions,
            seed=args.seed,
            out_root=out_root,
            execution_profile=args.execution_profile,
            timeout_s=args.timeout,
            warmup=args.warmup,
            wait_quiet_s=args.wait_quiet,
            max_consecutive_failures=args.max_consecutive_failures,
        )
    except NotQuiet as exc:
        print("NOT QUIET: %s" % exc, file=sys.stderr)
        return 3
    for row in summary["rows"]:
        print(
            "%-8s %-12s %-14s %-9s n=%-3s median=%s %s"
            % (row["criterion_id"], row["editor_id"], row["workload_id"], row["outcome"], row.get("n"), row.get("median_ms"), row.get("failure_reason") or "")
        )
    print("summary: %s" % (out_root / "summary.json"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
