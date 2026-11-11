#!/usr/bin/env python3
"""C17 memory footprint, C19 disposal/reopen and C22 feature/extension overhead.

What this runner can measure, and on which lane:

* **C17 (memory footprint)** -- every editor that starts a process.  A browser
  lane (``harness/ui`` host) is sampled at three declared phases: ready, after
  a fixed edit burst, and at quiescence.  A one-shot headless lane has no
  ready/edit/quiescence boundary, so it is sampled while it runs and the cell
  is labelled ``peak_during_run`` instead of pretending to be a phase series.
* **C19 (disposal/reopen)** -- browser lanes only: close the context, sample
  retained RSS, reopen the same fixture in a fresh context, and record the
  delta.  A one-shot CLI exits before anything could be closed, so it is
  ``not_applicable`` rather than a structural zero.
* **C22 (feature/extension overhead)** -- only a host with a P0-P3 feature
  switch could produce it.  No host here has one, so every editor is
  ``not_applicable`` with the inspection that established it.

Sampling method on this host: ``ps -Ao pid=,ppid=,rss=`` summed over the process
tree (``perf/runner/memory_tree.py``).  Darwin has no ``/proc``, no
``smaps_rollup`` and no cgroup v2, so PSS, USS and the cgroup fields are null in
every sample and every attempt's ``evidence`` field says so.  RSS counts a
shared page once per process, which over-counts a browser tree.

Every attempt is written once, immutably, through ``perf.runner.artifacts``.
A ``ci_coarse`` host never publishes: every measured cell carries
``publishable: false`` and an explicit ``publication_block_reason``.

Field-name note: ``perf/schema.py`` names the sample series ``samples_ms`` and
requires it non-empty for a measured trial.  For C17/C19 the series is bytes,
not milliseconds, so every measured attempt here also carries
``sample_unit: "bytes"``, the summary repeats it, and the ``evidence`` block
says how the bytes were read.  Read the median as a byte count, never as a
duration; a schema field named for the unit does not exist.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import select
import shutil
import signal
import socket
import subprocess
import sys
import time
import uuid
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from perf.adapters.capabilities import default_lane, pin_label  # noqa: E402
from perf.analysis.publication_gate import trial_publishable_flags  # noqa: E402
from perf.analysis.summarize import summarize  # noqa: E402
from perf.fixtures.generate import build_workload, docx_zip_bytes  # noqa: E402
from perf.fixtures.profiles import assert_workload_allowed, size_ladder  # noqa: E402
from perf.runner.artifacts import write_attempt  # noqa: E402
from perf.runner.benchmark_ci_contract import (  # noqa: E402
    INTERPRETATION_CONDITIONS,
    _finalize_publishable,
    _host_base,
    _trial_dict,
)
from perf.runner.benchmark_warm_cold import (  # noqa: E402
    BROWSER_TARGETS,
    _apryse_key_present,
    _start_server,
    _stop_server,
)
from perf.runner.harness_ui_versions import browser_harness_editor_version  # noqa: E402
from perf.runner.resources import STATIC_SERVER_NOTE  # noqa: E402
from perf.runner.memory_tree import (  # noqa: E402
    PS_COMMAND,
    assert_phases_not_copied,
    load_average,
    peak_process_tree,
    sample_process_trees,
    validate_tree_sample,
)
from perf.scenarios.catalog import scenarios  # noqa: E402
from perf.schema import (  # noqa: E402
    sample_budget_for_profile,
    validate_environment,
    validate_sample_budget,
    validate_trial,
)

UI = REPO / "harness" / "ui"
PROBE = REPO / "perf" / "runner" / "memory_probe.mjs"

PHASES = ("ready", "after_edit_burst", "quiescent")
PROCESS_PHASE = "peak_during_run"

BURST_ITERATIONS = 12
BURST_TEXT = "abcdefghij"
QUIESCENCE_MS = 2000
RETAIN_SECONDS = (1.0, 5.0)
PROBE_TIMEOUT_S = 300.0
PEAK_INTERVAL_S = 0.05

# Features of the P0-P3 profiles (perf/fixtures/profiles.py).  A host exposes a
# feature switch only if a URL parameter, flag or environment variable toggles
# one of these; a flag that does something else is not a profile switch.
PROFILE_FEATURES = ("collaboration", "ai_panel", "proofing", "style_display", "busy_panel")

# What was inspected for C22, per editor.  Written after grepping each host for
# `location.search', `URLSearchParams' and feature flags, and reading the
# published command lines.  `params` lists every switch the host actually has.
FEATURE_SWITCH_PROBE = {
    "plate": ("harness/ui/plate", "reads no location.search/URLSearchParams and the vite command has no flag", ()),
    "docxodus": ("harness/ui/docxodus", "reads no location.search/URLSearchParams and the vite command has no flag", ()),
    "superdoc": ("harness/ui/superdoc", "reads no location.search/URLSearchParams and the vite command has no flag", ()),
    "genoffice": ("harness/ui/genoffice", "reads no location.search/URLSearchParams and the vite command has no feature flag", ()),
    "canvas": ("harness/ui/canvas", "reads only ?src= (fixture path)", ("src",)),
    "docsplus": ("harness/ui/docsplus/host", "reads only ?perf=0 (disables the perf bridge)", ("perf",)),
    "docen": ("harness/ui/docen-host", "reads only ?src= (fixture path)", ("src",)),
    "fidus": ("harness/ui/fidus-host", "proxy.mjs takes no feature parameter", ()),
    "wordcraft": ("harness/ui/wordcraft-host", "server.mjs takes no feature parameter", ()),
    "apryse": ("harness/apryse", "vite.perf.config.mjs has no feature flag", ()),
    "eigenpal": (
        "repos/eigenpal-docx-editor/examples/vite",
        "reads ?perfE2e=1&fixture=&reviewRail=0 (e2e mode, fixture path, review rail off)",
        ("perfE2e", "fixture", "reviewRail"),
    ),
    "folio": ("repos/folio/packages/playground", "reads only ?file= (fixture path)", ("file",)),
    "office-open": ("harness/officeopen", "headless round-trip CLI, no feature flags", ()),
    "libreoffice": ("system soffice", "headless --convert-to command line, no feature flags", ()),
}


# ---------------------------------------------------------------------------
# Headless process lanes: mirrors perf/runner/benchmark_ci_contract._RUNNERS.
# Each builder returns (cwd, argv, extra_env).  Drift between the two tables is
# a harness bug: perf/tests/test_memory_criteria.py pins the editor set.
# ---------------------------------------------------------------------------


def _cmd_plate(indocx: Path, outdocx: Path):
    return REPO / "harness" / "plate", ["bun", "--preload", "./aliases.ts", "roundtrip.ts", str(indocx), str(outdocx)], {}


def _cmd_folio(indocx: Path, outdocx: Path):
    return REPO / "repos" / "folio", ["bun", str(REPO / "harness" / "folio.ts"), str(indocx), str(outdocx), "model"], {}


def _cmd_superdoc(indocx: Path, outdocx: Path):
    return REPO, ["node", str(REPO / "harness" / "superdoc.mjs"), str(indocx), str(outdocx)], {}


def _cmd_office_open(indocx: Path, outdocx: Path):
    tsx = REPO / "repos" / "office-open" / "node_modules" / ".bin" / "tsx"
    argv = [
        str(tsx),
        "--tsconfig",
        str(REPO / "repos" / "office-open" / "packages" / "docx" / "tsconfig.json"),
        str(REPO / "harness" / "officeopen" / "roundtrip.mts"),
        str(indocx),
        str(outdocx),
    ]
    return REPO / "repos" / "office-open", argv, {}


def _cmd_eigenpal(indocx: Path, outdocx: Path):
    argv = ["bun", str(REPO / "harness" / "eigenpal.ts"), str(indocx), str(outdocx), "store"]
    return REPO / "repos" / "eigenpal-docx-editor", argv, {}


def _cmd_docen(indocx: Path, outdocx: Path):
    tsx = REPO / "repos" / "docen" / "node_modules" / ".bin" / "tsx"
    argv = [str(tsx), str(REPO / "harness" / "docen" / "roundtrip.mts"), str(indocx), str(outdocx)]
    return REPO / "repos" / "docen", argv, {}


def _cmd_genoffice(indocx: Path, outdocx: Path):
    env = {
        "NODE_OPTIONS": "--import %s --import %s"
        % (
            REPO / "harness" / "css-stub.mjs",
            REPO / "repos" / "genoffice" / "node_modules" / "tsx" / "dist" / "loader.mjs",
        ),
        "NODE_PATH": str(REPO / "repos" / "genoffice" / "node_modules"),
    }
    argv = ["node", str(REPO / "harness" / "genoffice.cts"), str(indocx), str(outdocx)]
    return REPO / "repos" / "genoffice", argv, env


def _cmd_fidus(indocx: Path, outdocx: Path):
    env = {
        "IN_DOCX": str(indocx),
        "OUT_DOCX": str(outdocx),
        "TEMPLATE": "generated",
        "NODE_PATH": str(REPO / "repos" / "fiduswriter-document-ts" / "node_modules"),
    }
    tsx = REPO / "repos" / "fiduswriter-document-ts" / "node_modules" / ".bin" / "tsx"
    argv = [str(tsx), "--no-cache", str(REPO / "harness" / "fidus" / "roundtrip.mts")]
    return REPO / "repos" / "fiduswriter-document-ts", argv, env


def _cmd_docsplus(indocx: Path, outdocx: Path):
    argv = ["bun", str(REPO / "harness" / "docsplus" / "roundtrip.ts"), str(indocx), str(outdocx)]
    return REPO / "harness" / "docsplus" / "repo-copy", argv, {}


def _cmd_canvas(indocx: Path, outdocx: Path):
    env = {
        "VITEST_DOCX_INPUT": str(indocx),
        "VITEST_DOCX_OUTPUT": str(outdocx),
        "NODE_PATH": str(REPO / "repos" / "canvas-editor" / "node_modules"),
    }
    argv = [
        str(REPO / "repos" / "canvas-editor" / "node_modules" / ".bin" / "vitest"),
        "run",
        "--root",
        str(REPO / "harness" / "canvas"),
    ]
    return REPO / "repos" / "canvas-editor", argv, env


def _cmd_wordcraft(indocx: Path, outdocx: Path):
    binary = REPO / "harness" / "wordcraft" / "target" / "release" / "wc-harness"
    return REPO / "harness" / "wordcraft", [str(binary), str(indocx), str(outdocx)], {}


def _cmd_docxodus(indocx: Path, outdocx: Path):
    argv = ["node", str(UI / "docxodus" / "roundtrip.mjs"), str(indocx), str(outdocx)]
    return UI / "docxodus", argv, {}


def _cmd_libreoffice(indocx: Path, outdocx: Path):
    # soffice names its output after the input basename, so converting into the
    # input's own directory overwrites the input mid-run (SfxBaseModel::impl_store
    # error). Convert into a dedicated subdir instead: the output lands at
    # <outdir>/micro-paragraphs-in.docx, never on top of the input.
    outdir = outdocx.parent / "lo-converted"
    argv = ["soffice", "--headless", "--norestore", "--convert-to", "docx", "--outdir", str(outdir), str(indocx)]
    return outdocx.parent, argv, {}


PROCESS_TARGETS = {
    "plate": _cmd_plate,
    "docxodus": _cmd_docxodus,
    "superdoc": _cmd_superdoc,
    "folio": _cmd_folio,
    "genoffice": _cmd_genoffice,
    "eigenpal": _cmd_eigenpal,
    "office-open": _cmd_office_open,
    "docen": _cmd_docen,
    "wordcraft": _cmd_wordcraft,
    "fidus": _cmd_fidus,
    "canvas": _cmd_canvas,
    "docsplus": _cmd_docsplus,
    "libreoffice": _cmd_libreoffice,
}


def _scenario(criterion_id: str) -> dict:
    for row in scenarios():
        if row["id"] == criterion_id:
            return row
    raise ValueError("unknown criterion %r" % (criterion_id,))


def _browser_target(editor_id: str):
    target = BROWSER_TARGETS.get(editor_id)
    if target and target.get("enabled") is False:
        return None
    return target


def _port_of(url: str) -> tuple[str, int]:
    parts = urlsplit(url)
    host = parts.hostname or "127.0.0.1"
    port = parts.port or (443 if parts.scheme == "https" else 80)
    return host, port


def _port_is_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def _retarget_port(target: dict, port: int) -> dict:
    """Copy a browser target onto another port (never squat on a used one)."""
    command = list(target["command"])
    if "--port" not in command:
        raise ValueError("target command has no --port flag to override")
    index = command.index("--port")
    if index + 1 >= len(command):
        raise ValueError("--port without a value")
    command[index + 1] = str(port)
    parts = urlsplit(target["url"])
    netloc = "%s:%d" % (parts.hostname or "127.0.0.1", port)
    updated = dict(target)
    updated["command"] = command
    updated["url"] = urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
    return updated


def _attempt_id(criterion: str, phase: str | None, editor_id: str) -> str:
    slug = criterion.lower()
    if phase:
        slug += "-" + phase.replace("_", "")
    return "%s-%s-%s" % (slug, editor_id, uuid.uuid4().hex[:10])


def _attempt_ref(path: Path) -> str:
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return path.name


def _env_for(*, editor_id, editor_version, fixture_sha, docx_size, workload_row, cache_state, execution_profile):
    env = _host_base(
        editor_id=editor_id,
        editor_version=editor_version,
        execution_profile=execution_profile,
        fixture_sha256=fixture_sha,
        workload_row=workload_row,
        docx_size=docx_size,
        cache_state=cache_state,
        repetition_unit="fresh_process",
        run_kind="timing",
        feature_profile_name="P0",
    )
    env["interpretation_conditions"] = list(INTERPRETATION_CONDITIONS)
    return env


def _method_descriptor():
    """The sampling method without taking a live sample."""
    return {
        "method": "ps_rss_sum",
        "platform": platform.system().lower(),
        "ps_command": " ".join(PS_COMMAND),
        "roots": [],
    }


def _evidence(*, phase, method_sample, phases, extra=None):
    """How this cell was sampled, in the terms the host can actually support."""
    evidence = {
        "method": method_sample["method"],
        "platform": method_sample["platform"],
        "sample_unit": "bytes",
        "ps_command": method_sample["ps_command"],
        "tree_roots": "the Chromium process tree rooted at the browser process this run launched",
        "phases_sampled": list(phases),
        "phase": phase,
        "pss_bytes": None,
        "uss_bytes": None,
        "cgroup_current_bytes": None,
        "cgroup_peak_bytes": None,
        "smaps_rollup": "not read: darwin has no /proc and no smaps_rollup",
        "cgroup": "not used: no editor is launched inside a cgroup on this host",
        "shared_pages": "RSS counts a shared page once per process, so a tree total over-counts; "
        "PSS would correct it and is unavailable on darwin",
        "gpu_memory": "outside RSS on darwin; not sampled",
    }
    if extra:
        evidence.update(extra)
    return evidence


def _write_measured(
    *,
    attempt_dir: Path,
    criterion_id: str,
    phase: str | None,
    editor_id: str,
    lane: str,
    env: dict,
    samples_bytes: list,
    evidence: dict,
    diagnostic: dict,
) -> Path:
    scenario = _scenario(criterion_id)
    if not samples_bytes:
        raise ValueError("measured trial needs samples")
    for sample in samples_bytes:
        if isinstance(sample, bool) or not isinstance(sample, int) or sample < 0:
            raise ValueError("memory samples must be non-negative ints")
    stats = summarize(samples_bytes, env["cache_state"], env["repetition_unit"], seed=0)
    validate_sample_budget(env, len(samples_bytes))
    # #136: fresh_process gives one value per launch; n is enforced per cell (e2_cells).
    publishable, reason = trial_publishable_flags(
        env, scenario["layer"], None if env["repetition_unit"] == "fresh_process" else stats["n"])
    publishable, reason = _finalize_publishable(publishable, reason, env)
    trial = _trial_dict(
        criterion_id=criterion_id,
        layer=scenario["layer"],
        boundary=scenario["boundary"],
        outcome="measured",
        env=env,
        samples_ms=samples_bytes,
        editor_id=editor_id,
        lane=lane,
        summary_stats=stats,
        publishable=publishable,
        publication_block_reason=reason,
        diagnostic=diagnostic,
    )
    trial["sample_unit"] = "bytes"
    if phase:
        trial["measurement_phase"] = phase
    trial["evidence"] = evidence
    validate_trial(trial)
    return write_attempt(attempt_dir, _attempt_id(criterion_id, phase, editor_id), trial)


def _write_outcome(
    *,
    attempt_dir: Path,
    criterion_id: str,
    phase: str | None,
    editor_id: str,
    lane: str,
    env: dict,
    outcome: str,
    failure_reason: str,
    evidence: dict,
    diagnostic: dict | None = None,
    refusal_code: str | None = None,
) -> Path:
    if not failure_reason or not failure_reason.strip():
        raise ValueError("a non-measured cell needs a failure_reason")
    scenario = _scenario(criterion_id)
    trial = _trial_dict(
        criterion_id=criterion_id,
        layer=scenario["layer"],
        boundary=scenario["boundary"],
        outcome=outcome,
        env=env,
        samples_ms=[],
        failure_reason=failure_reason,
        editor_id=editor_id,
        lane=lane,
        diagnostic=diagnostic,
    )
    trial["evidence"] = evidence
    trial["refusal_detail"] = failure_reason
    if refusal_code is not None:
        trial["refusal_code"] = refusal_code
    if phase:
        trial["measurement_phase"] = phase
    validate_environment(env)
    validate_trial(trial)
    return write_attempt(attempt_dir, _attempt_id(criterion_id, phase, editor_id), trial)


# ---------------------------------------------------------------------------
# Browser lane
# ---------------------------------------------------------------------------


def _probe_command(
    target: dict,
    corpus_path: Path,
    *,
    burst: int,
    quiescence_ms: int,
    reopen: bool,
    editor_id: str = "",
) -> list[str]:
    node = shutil.which("node") or "node"
    command = [
        node,
        str(PROBE),
        "--url",
        target["url"],
        "--corpus",
        str(corpus_path.resolve()),
        "--corpus-route",
        target["corpus_route"],
        "--ready-selector",
        target.get("ready_selector", ""),
        "--edit-selector",
        target.get("edit_selector", ""),
        "--burst",
        str(burst),
        "--burst-text",
        BURST_TEXT,
        "--quiescence-ms",
        str(quiescence_ms),
        "--reopen",
        "true" if reopen else "false",
    ]
    if target.get("ready_js"):
        command.extend(["--ready-js", target["ready_js"]])
    if target.get("error_js"):
        command.extend(["--error-js", target["error_js"]])
    if target.get("wait_after_ready"):
        command.extend(["--wait-after-ready", str(target["wait_after_ready"])])
    if editor_id:
        command.extend(["--editor", editor_id])
    command.extend(["--poll-bound-ms", "90000"])
    return command


def _probe_failure(reason: str, family: str) -> RuntimeError:
    exc = RuntimeError(reason)
    exc.refusal_family = family
    return exc


def _read_probe_line(proc: subprocess.Popen, deadline: float) -> str:
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("probe produced no line before the timeout")
        ready, _, _ = select.select([proc.stdout], [], [], min(remaining, 1.0))
        if not ready:
            if proc.poll() is not None:
                raise _probe_failure("probe exited (%s) without a RESULT" % (proc.returncode,), "editor_crash")
            continue
        line = proc.stdout.readline()
        if not line:
            raise _probe_failure("probe closed stdout without a RESULT", "editor_crash")
        line = line.strip()
        if line:
            return line


def _stop_process_group(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except ProcessLookupError:
        proc.terminate()
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except ProcessLookupError:
            proc.kill()
        proc.wait(timeout=10)


def _pair_error_family(exc) -> str:
    if "out of memory" in str(exc).lower():
        return "out_of_memory"
    family = getattr(exc, "refusal_family", None)
    if family:
        return family
    if isinstance(exc, TimeoutError):
        return "editor_timeout"
    if isinstance(exc, (ValueError, OSError, subprocess.SubprocessError)):
        return "harness_error"
    return "crash"


def _host_memory_root(server) -> int | None:
    """RSS root for a browser host process, if it is a separate editor server."""
    pid = getattr(server, "pid", None)
    if isinstance(pid, int) and pid > 0:
        return pid
    return None


def _memory_host_diagnostic(server) -> dict:
    return {
        "memory_roots": "editor_browser_tree_only",
        "host_server_pid_first_pair": _host_memory_root(server),
        "host_server_counted_in_rss": False,
        "static_host_note": STATIC_SERVER_NOTE,
    }


def _sample_roots(roots: list[int]) -> dict:
    sample = sample_process_trees([pid for pid in roots if pid])
    validate_tree_sample(sample)
    return sample


def _retention_series(roots: list[int], seconds) -> list[dict]:
    """Sample retained RSS at the declared intervals after the context closes."""
    started = time.monotonic()
    series = []
    for target in sorted(seconds):
        remaining = target - (time.monotonic() - started)
        if remaining > 0:
            time.sleep(remaining)
        sample = _sample_roots(roots)
        series.append(
            {
                "after_close_ms": (time.monotonic() - started) * 1000.0,
                "rss_bytes": sample["rss_bytes"],
                "process_count": sample["process_count"],
                "pids": sample["pids"],
            }
        )
    return series


def _run_browser_pair(
    *,
    target: dict,
    corpus_path: Path,
    burst: int,
    quiescence_ms: int,
    retain_seconds,
    probe_timeout_s: float,
    editor_id: str = "",
    workload: str = "micro-paragraphs",
) -> dict:
    from perf.runner.load_timeouts import load_timeout_env, load_timeout_ms

    # Lax layer (owner 2026-11-11): the probe may wait minutes for a big
    # document to load; our own wall clock stays above that wait so the
    # probe's ready timeout governs, never this deadline.
    load_timeout_s = load_timeout_ms(workload) / 1000.0
    probe_timeout_s = max(probe_timeout_s, load_timeout_s + 120.0)
    command = _probe_command(
        target,
        corpus_path,
        burst=burst,
        quiescence_ms=quiescence_ms,
        reopen=True,
        editor_id=editor_id,
    )
    proc = subprocess.Popen(
        command,
        cwd=str(UI),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        start_new_session=True,
        env={**os.environ, **load_timeout_env(workload)},
    )
    roots: list[int] = []
    deadline = time.monotonic() + probe_timeout_s
    record = {
        "phases": {},
        "ready": None,
        "edited": None,
        "quiescent": None,
        "closed": None,
        "reopened": None,
        "result": None,
        "retention": [],
        "roots": roots,
    }
    try:
        while True:
            line = _read_probe_line(proc, deadline)
            if line.startswith("PHASE "):
                _, name, payload = line.split(" ", 2)
                details = json.loads(payload)
                if name in ("ready", "edited", "quiescent", "reopened"):
                    browser_pid = details.get("browser_pid")
                    if isinstance(browser_pid, int) and browser_pid > 0 and not roots:
                        roots = [browser_pid]
                    if not roots:
                        raise _probe_failure("probe did not report browser_pid", "harness_error")
                    sample = _sample_roots(roots)
                    record["phases"][name] = {"sample": sample, "probe": details}
                    record[name] = record["phases"][name]
                elif name == "closed":
                    if not roots:
                        browser_pid = details.get("browser_pid")
                        if isinstance(browser_pid, int) and browser_pid > 0:
                            roots = [browser_pid]
                    if not roots:
                        raise _probe_failure("probe did not report browser_pid before close", "harness_error")
                    record["retention"] = _retention_series(roots, retain_seconds)
                    record["closed"] = {"probe": details, "retention": record["retention"]}
                else:
                    raise _probe_failure("probe announced an unknown phase %r" % (name,), "harness_error")
                proc.stdin.write("go\n")
                proc.stdin.flush()
            elif line.startswith("RESULT "):
                record["result"] = json.loads(line[len("RESULT ") :])
                break
            elif line.startswith("ERROR "):
                raise _probe_failure(line[len("ERROR ") :], "editor_crash")
            else:
                raise _probe_failure("probe said %r" % (line[:200],), "harness_error")
    finally:
        try:
            if proc.stdin and not proc.stdin.closed:
                proc.stdin.close()
        except OSError:
            pass
        _stop_process_group(proc)
    record["roots"] = roots
    record["probe_exit"] = proc.returncode
    return record


def _browser_rows(
    *,
    editor_id: str,
    lane: str,
    target: dict,
    attempt_dir: Path,
    args,
    fixture_path: Path,
    fixture_sha: str,
    docx_size: int,
    workload_row: dict,
) -> list[dict]:
    rows: list[dict] = []
    pairs: list[dict] = []
    editor_version, harness_meta = browser_harness_editor_version(editor_id, pin_label(editor_id))

    host, port = _port_of(target["url"])
    if not _port_is_free(host, port):
        reason = (
            "%s: port %d is already in use by another session; this runner does not kill "
            "another session's server and will not measure on a shared port" % (editor_id, port)
        )
        for criterion, phase in (("C17", "ready"), ("C19", None)):
            env = _env_for(
                editor_id=editor_id,
                editor_version=editor_version,
                fixture_sha=fixture_sha,
                docx_size=docx_size,
                workload_row=workload_row,
                cache_state="process_cold_fs_warm",
                execution_profile=args.execution_profile,
            )
            path = _write_outcome(
                attempt_dir=attempt_dir,
                criterion_id=criterion,
                phase=phase,
                editor_id=editor_id,
                lane=lane,
                env=env,
                outcome="not_run",
                failure_reason=reason,
                evidence={"state": "host_not_started", "reason": reason},
            )
            rows.append(_row(criterion, phase, editor_id, "not_run", reason, path))
        return rows

    memory_host = None
    for index in range(args.pairs):
        server = None
        try:
            server = _start_server(editor_id, target)
            if memory_host is None:
                memory_host = _memory_host_diagnostic(server)
            pair = _run_browser_pair(
                target=target,
                corpus_path=fixture_path,
                burst=args.burst,
                quiescence_ms=args.quiescence_ms,
                retain_seconds=args.retain_seconds,
                probe_timeout_s=args.probe_timeout,
                editor_id=editor_id,
                workload=args.workload,
            )
            pair["index"] = index
            pairs.append(pair)
        except Exception as exc:  # noqa: BLE001 - the reason is the payload
            family = "host_build" if server is None else _pair_error_family(exc)
            pairs.append({"index": index, "error": str(exc)[:800], "error_family": family})
        finally:
            if server is not None:
                _stop_server(server)

    failures = [pair for pair in pairs if pair.get("error")]
    from perf.runner.browser_run import host_class

    from perf.runner.benchmark_document import (
        content_gate_record,
        content_meta_for_workload,
        gate_length_check_for,
    )

    workload_id = workload_row.get("workload_id") or "prose-500w"
    content_meta = content_meta_for_workload(workload_id, fixture_path)
    diagnostics = {
        "pairs": [_pair_diagnostic(pair) for pair in pairs],
        "harness": harness_meta,
        "burst": {"iterations": args.burst, "text": BURST_TEXT, "method": "keyboard.type"},
        "quiescence_ms": args.quiescence_ms,
        "retain_seconds": list(args.retain_seconds),
        "load_average": load_average(),
        "host_class": host_class(),
        "memory_host": memory_host
        or {"memory_roots": "unknown", "host_server_counted_in_rss": None},
        **content_gate_record(content_meta, gate_length_check_for(editor_id, content_meta)),
    }

    def env_for(cache_state):
        return _env_for(
            editor_id=editor_id,
            editor_version=editor_version,
            fixture_sha=fixture_sha,
            docx_size=docx_size,
            workload_row=workload_row,
            cache_state=cache_state,
            execution_profile=args.execution_profile,
        )

    def sample_of(pair, phase):
        entry = pair.get(phase)
        if not entry:
            return None
        return entry["sample"]

    for phase, cache_state, outcome_name in (
        ("ready", "process_cold_fs_warm", "ready"),
        ("after_edit_burst", "warm_steady", "edited"),
        ("quiescent", "warm_steady", "quiescent"),
    ):
        env = env_for(cache_state)
        samples = [sample_of(pair, outcome_name) for pair in pairs]
        if failures or any(sample is None for sample in samples):
            reason = "browser memory probe failed: %s" % (
                failures[0]["error"] if failures else "a phase was never announced",
            )
            path = _write_outcome(
                attempt_dir=attempt_dir,
                criterion_id="C17",
                phase=phase,
                editor_id=editor_id,
                lane=lane,
                env=env,
                outcome="failed",
                failure_reason=reason,
                evidence={"state": "probe_failed", "phase": phase},
                diagnostic=diagnostics,
                refusal_code=failures[0].get("error_family") if failures else "witness_unavailable",
            )
            rows.append(_row("C17", phase, editor_id, "failed", reason, path))
            continue
        if phase == "after_edit_burst" and not all(
            (pair.get("edited") or {}).get("probe", {}).get("edit_effective") for pair in pairs
        ):
            details = [
                {
                    "text_length_before": (pair.get("edited") or {}).get("probe", {}).get("text_length_before"),
                    "text_length_after": (pair.get("edited") or {}).get("probe", {}).get("text_length_after"),
                    "typed_chars": (pair.get("edited") or {}).get("probe", {}).get("typed_chars"),
                    "edit_error": (pair.get("edited") or {}).get("probe", {}).get("edit_error"),
                }
                for pair in pairs
            ]
            reason = (
                "host accepted no text: document text length did not grow after %d keyboard.type of %r "
                "(%s); no post-edit memory sample exists for this host"
                % (args.burst, BURST_TEXT, json.dumps(details, sort_keys=True))
            )
            path = _write_outcome(
                attempt_dir=attempt_dir,
                criterion_id="C17",
                phase=phase,
                editor_id=editor_id,
                lane=lane,
                env=env,
                outcome="not_applicable",
                failure_reason=reason,
                evidence=_evidence(
                    phase=phase,
                    method_sample=samples[0],
                    phases=PHASES,
                    extra={"edit_effective": False, "burst": diagnostics["burst"]},
                ),
                diagnostic=diagnostics,
            )
            rows.append(_row("C17", phase, editor_id, "not_applicable", reason, path))
            continue
        series = [sample["rss_bytes"] for sample in samples]
        copied = False
        phase_series = {}
        for name in ("ready", "edited", "quiescent"):
            values = [sample_of(pair, name) for pair in pairs]
            if any(value is None for value in values):
                phase_series = {}
                break
            phase_series[name] = [value["rss_bytes"] for value in values]
        if phase_series:
            try:
                assert_phases_not_copied(phase_series)
            except ValueError:
                copied = True
        attempt_diagnostic = dict(diagnostics)
        attempt_diagnostic["phase_series_identical"] = copied
        path = _write_measured(
            attempt_dir=attempt_dir,
            criterion_id="C17",
            phase=phase,
            editor_id=editor_id,
            lane=lane,
            env=env,
            samples_bytes=series,
            evidence=_evidence(
                phase=phase,
                method_sample=samples[0],
                phases=PHASES,
                extra={
                    "burst": diagnostics["burst"],
                    "quiescence_ms": args.quiescence_ms if phase == "quiescent" else None,
                    "probe_ready_ms": [(pair.get("result") or {}).get("ready_ms") for pair in pairs]
                    if phase == "ready"
                    else None,
                },
            ),
            diagnostic=attempt_diagnostic,
        )
        rows.append(_row("C17", phase, editor_id, "measured", None, path))

    # C19: retained RSS after the context closed, then the reopen delta.
    env = env_for("process_cold_fs_warm")
    method_sample = sample_of(pairs[0], "ready") if pairs else None
    if method_sample is None:
        method_sample = _method_descriptor()
    retained = []
    reopen_details = []
    for pair in pairs:
        closed = pair.get("closed")
        if not closed or not closed.get("retention"):
            continue
        last = closed["retention"][-1]
        reopened = sample_of(pair, "reopened")
        reopen_details.append(
            {
                "index": pair.get("index"),
                "retained_after_close_ms": last["after_close_ms"],
                "retained_bytes": last["rss_bytes"],
                "retained_process_count": last["process_count"],
                "reopened_bytes": reopened["rss_bytes"] if reopened else None,
                "reattach_delta_bytes": (reopened["rss_bytes"] - last["rss_bytes"]) if reopened else None,
                "reopen_ready_ms": (pair.get("reopened") or {}).get("probe", {}).get("reopen_ready_ms"),
                "reopen_error": (pair.get("reopened") or {}).get("probe", {}).get("reopen_error"),
            }
        )
        retained.append(last["rss_bytes"])
    reopen_failed = [
        d for d in reopen_details if d["reopened_bytes"] is None or d["reopen_error"]
    ]
    c19_diagnostic = dict(diagnostics)
    c19_diagnostic["retention"] = reopen_details
    if failures or not retained:
        reason = "browser memory probe failed: %s" % (
            failures[0]["error"] if failures else "the context never closed",
        )
        path = _write_outcome(
            attempt_dir=attempt_dir,
            criterion_id="C19",
            phase=None,
            editor_id=editor_id,
            lane=lane,
            env=env,
            outcome="failed",
            failure_reason=reason,
            evidence={"state": "probe_failed"},
            diagnostic=c19_diagnostic,
            refusal_code=failures[0].get("error_family") if failures else "witness_unavailable",
        )
        rows.append(_row("C19", None, editor_id, "failed", reason, path))
    elif reopen_failed:
        reason = "context closed but the reopen failed: %s" % (
            reopen_failed[0]["reopen_error"] or "no reopened sample",
        )
        path = _write_outcome(
            attempt_dir=attempt_dir,
            criterion_id="C19",
            phase=None,
            editor_id=editor_id,
            lane=lane,
            env=env,
            outcome="failed",
            failure_reason=reason,
            evidence={"state": "reopen_failed", "retained_samples": retained},
            diagnostic=c19_diagnostic,
            refusal_code="editor_crash",
        )
        rows.append(_row("C19", None, editor_id, "failed", reason, path))
    else:
        path = _write_measured(
            attempt_dir=attempt_dir,
            criterion_id="C19",
            phase=None,
            editor_id=editor_id,
            lane=lane,
            env=env,
            samples_bytes=retained,
            evidence=_evidence(
                phase="retained_after_close",
                method_sample=method_sample,
                phases=("ready", "after_edit_burst", "quiescent", "closed", "reopened"),
                extra={
                    "retain_seconds": list(args.retain_seconds),
                    "reopen": "a new browser context loads the same fixture; the delta is the re-attach cost",
                    "wasm_memory": "WASM linear memory is not sampled: no host here exposes memory.buffer to this probe",
                },
            ),
            diagnostic=c19_diagnostic,
        )
        rows.append(_row("C19", None, editor_id, "measured", None, path))
    return rows


def _pair_diagnostic(pair: dict) -> dict:
    if pair.get("error"):
        return {"index": pair.get("index"), "error": pair["error"]}
    diagnostic = {"index": pair.get("index"), "roots": pair.get("roots"), "probe": pair.get("result")}
    for phase in ("ready", "edited", "quiescent", "reopened"):
        entry = pair.get(phase)
        if entry:
            diagnostic[phase] = {
                "rss_bytes": entry["sample"]["rss_bytes"],
                "process_count": entry["sample"]["process_count"],
                "sampled_at_unix_ms": entry["sample"]["sampled_at_unix_ms"],
                "probe": entry["probe"],
            }
    if pair.get("retention"):
        diagnostic["retention"] = pair["retention"]
    return diagnostic


def _row(criterion, phase, editor_id, outcome, reason, path) -> dict:
    return {
        "criterion_id": criterion,
        "measurement_phase": phase,
        "editor_id": editor_id,
        "outcome": outcome,
        "failure_reason": reason,
        "attempt_file": _attempt_ref(path),
    }


# ---------------------------------------------------------------------------
# Headless process lane
# ---------------------------------------------------------------------------


def _process_rows(
    *,
    editor_id: str,
    lane: str,
    attempt_dir: Path,
    args,
    indocx: Path,
    outdocx: Path,
    fixture_sha: str,
    docx_size: int,
    workload_row: dict,
) -> list[dict]:
    rows: list[dict] = []
    editor_version = pin_label(editor_id)
    if not indocx.is_absolute() or not indocx.is_file():
        # A relative fixture path resolves against the editor's own cwd and the
        # child then fails with ENOENT.  That is a harness bug, never an editor
        # failure, so it raises instead of being written as a failed cell.
        raise ValueError("fixture path must be absolute and exist: %s" % (indocx,))
    if not outdocx.is_absolute():
        raise ValueError("output path must be absolute: %s" % (outdocx,))
    builder = PROCESS_TARGETS[editor_id]
    cwd, argv, extra_env = builder(indocx, outdocx)
    if not Path(argv[0]).exists() and shutil.which(argv[0]) is None:
        reason = "%s: %s is not installed on this host" % (editor_id, argv[0])
        env = _env_for(
            editor_id=editor_id,
            editor_version=editor_version,
            fixture_sha=fixture_sha,
            docx_size=docx_size,
            workload_row=workload_row,
            cache_state="process_cold_fs_warm",
            execution_profile=args.execution_profile,
        )
        path = _write_outcome(
            attempt_dir=attempt_dir,
            criterion_id="C17",
            phase=PROCESS_PHASE,
            editor_id=editor_id,
            lane=lane,
            env=env,
            outcome="not_run",
            failure_reason=reason,
            evidence={"state": "toolchain_missing", "argv0": argv[0]},
        )
        rows.append(_row("C17", PROCESS_PHASE, editor_id, "not_run", reason, path))
        c19_reason = "%s; the lane never ran, so there is no process to close and no reopen to time" % (reason,)
        c19_path = _write_outcome(
            attempt_dir=attempt_dir,
            criterion_id="C19",
            phase=None,
            editor_id=editor_id,
            lane=lane,
            env=env,
            outcome="not_run",
            failure_reason=c19_reason,
            evidence={"state": "toolchain_missing", "argv0": argv[0]},
        )
        rows.append(_row("C19", None, editor_id, "not_run", c19_reason, c19_path))
        return rows

    env = _env_for(
        editor_id=editor_id,
        editor_version=editor_version,
        fixture_sha=fixture_sha,
        docx_size=docx_size,
        workload_row=workload_row,
        cache_state="process_cold_fs_warm",
        execution_profile=args.execution_profile,
    )
    runs = []
    for index in range(args.pairs):
        err_path = attempt_dir.parent / ("%s-run%d.stderr.log" % (editor_id, index))
        run_env = os.environ.copy()
        run_env.update(extra_env)
        run_env.setdefault("NODE_OPTIONS", "--no-deprecation")
        with open(err_path, "wb") as err_handle:
            proc = subprocess.Popen(
                argv,
                cwd=str(cwd),
                env=run_env,
                stdout=subprocess.DEVNULL,
                stderr=err_handle,
                start_new_session=True,
            )
            try:
                peak = peak_process_tree(proc, interval_s=PEAK_INTERVAL_S, timeout_s=args.probe_timeout)
            except Exception as exc:  # noqa: BLE001
                proc.kill()
                proc.wait()
                runs.append({"index": index, "error": str(exc)[:400]})
                continue
        tail = ""
        try:
            tail = err_path.read_text(encoding="utf-8", errors="replace")[-600:]
        except OSError:
            pass
        peak["index"] = index
        peak["stderr_tail"] = tail
        runs.append(peak)

    failures = [run for run in runs if run.get("error") or run.get("exit_code") not in (0,)]
    diagnostics = {
        "runs": [
            {
                "index": run.get("index"),
                "exit_code": run.get("exit_code"),
                "observed_peak_rss_bytes": run.get("observed_peak_rss_bytes"),
                "process_count_max": run.get("process_count_max"),
                "interval_ms": run.get("interval_ms"),
                "duration_ms": run.get("duration_ms"),
                "error": run.get("error"),
            }
            for run in runs
        ],
        "command": argv,
        "cwd": str(cwd),
        "load_average": load_average(),
        "one_shot": True,
    }
    if failures:
        first = failures[0]
        reason = "%s exited %s: %s" % (
            editor_id,
            first.get("exit_code"),
            (first.get("stderr_tail") or first.get("error") or "").strip()[:400],
        )
        path = _write_outcome(
            attempt_dir=attempt_dir,
            criterion_id="C17",
            phase=PROCESS_PHASE,
            editor_id=editor_id,
            lane=lane,
            env=env,
            outcome="failed",
            failure_reason=reason,
            evidence={"state": "process_failed", "argv": argv},
            diagnostic=diagnostics,
            refusal_code="editor_crash",
        )
        rows.append(_row("C17", PROCESS_PHASE, editor_id, "failed", reason, path))
    else:
        series = [run["observed_peak_rss_bytes"] for run in runs]
        if any(value is None for value in series):
            reason = "%s: no resident sample was taken before the process exited" % (editor_id,)
            path = _write_outcome(
                attempt_dir=attempt_dir,
                criterion_id="C17",
                phase=PROCESS_PHASE,
                editor_id=editor_id,
                lane=lane,
                env=env,
                outcome="failed",
                failure_reason=reason,
                evidence={"state": "no_sample"},
                diagnostic=diagnostics,
                refusal_code="witness_unavailable",
            )
            rows.append(_row("C17", PROCESS_PHASE, editor_id, "failed", reason, path))
        else:
            path = _write_measured(
                attempt_dir=attempt_dir,
                criterion_id="C17",
                phase=PROCESS_PHASE,
                editor_id=editor_id,
                lane=lane,
                env=env,
                samples_bytes=series,
                evidence=_evidence(
                    phase=PROCESS_PHASE,
                    method_sample=_method_descriptor(),
                    phases=(PROCESS_PHASE,),
                    extra={
                        "one_shot": "the lane is a one-shot CLI: there is no ready, edit or quiescent phase, "
                        "so this cell is the observed peak during the run and is not comparable to a "
                        "browser-context phase cell",
                        "interval_ms": int(PEAK_INTERVAL_S * 1000),
                        "peak_is_sampled": "the maximum over polls every %d ms; a shorter spike between polls is unseen"
                        % (int(PEAK_INTERVAL_S * 1000),),
                    },
                ),
                diagnostic=diagnostics,
            )
            rows.append(_row("C17", PROCESS_PHASE, editor_id, "measured", None, path))

    reason = (
        "one-shot headless lane: %s runs once and exits, so there is no live context to close, "
        "sample and reopen; a retained figure here would be a structural zero, not a disposal "
        "measurement" % (editor_id,)
    )
    path = _write_outcome(
        attempt_dir=attempt_dir,
        criterion_id="C19",
        phase=None,
        editor_id=editor_id,
        lane=lane,
        env=env,
        outcome="not_applicable",
        failure_reason=reason,
        evidence={"state": "no_live_context", "lane": "one_shot_process"},
    )
    rows.append(_row("C19", None, editor_id, "not_applicable", reason, path))
    return rows


# ---------------------------------------------------------------------------
# C22: no host exposes a P0-P3 switch
# ---------------------------------------------------------------------------


def _feature_switch_reason(editor_id: str, execution_profile: str) -> str:
    host, inspected, params = FEATURE_SWITCH_PROBE[editor_id]
    detail = "" if params else " The host has no query parameter or flag at all."
    reason = (
        "%s (%s) exposes no P0-P3 feature profile: %s.%s A P0-P3 comparison would need a switch "
        "for one of %s; none of the five is toggleable here, and a matrix built from an unrelated "
        "flag would not be a feature-profile measurement"
        % (editor_id, host, inspected, detail, ", ".join(PROFILE_FEATURES))
    )
    if execution_profile not in ("ci_broad", "dedicated_publish"):
        reason += " (also below C22's min_execution_profile ci_broad: %s)" % (execution_profile,)
    return reason


def _c22_row(*, editor_id, lane, attempt_dir, args, fixture_sha, docx_size, workload_row, editor_version) -> dict:
    env = _env_for(
        editor_id=editor_id,
        editor_version=editor_version,
        fixture_sha=fixture_sha,
        docx_size=docx_size,
        workload_row=workload_row,
        cache_state="process_cold_fs_warm",
        execution_profile=args.execution_profile,
    )
    reason = _feature_switch_reason(editor_id, args.execution_profile)
    host, inspected, params = FEATURE_SWITCH_PROBE[editor_id]
    path = _write_outcome(
        attempt_dir=attempt_dir,
        criterion_id="C22",
        phase=None,
        editor_id=editor_id,
        lane=lane,
        env=env,
        outcome="not_applicable",
        failure_reason=reason,
        evidence={
            "state": "no_feature_profile_switch",
            "inspected": inspected,
            "host": host,
            "switches_found": list(params),
            "features_required": list(PROFILE_FEATURES),
        },
    )
    return _row("C22", None, editor_id, "not_applicable", reason, path)


# ---------------------------------------------------------------------------
# Support table and CLI
# ---------------------------------------------------------------------------


def support_table() -> list[dict]:
    rows = []
    for editor_id in sorted(set(BROWSER_TARGETS) | set(PROCESS_TARGETS) | set(FEATURE_SWITCH_PROBE)):
        browser = _browser_target(editor_id)
        process = editor_id in PROCESS_TARGETS
        # Docxodus's default #pages surface is rendered HTML; its editor mode
        # requires an explicit UI transition. C06 registration alone does not
        # establish an editable surface. Keep the runtime text-growth check.
        typing_surface = bool(browser and "C06" in (browser.get("criteria") or {}) and editor_id != "docxodus")
        cwd = None
        if browser:
            try:
                cwd = str(Path(browser["cwd"]).relative_to(REPO))
            except ValueError:
                cwd = str(browser["cwd"])
        rows.append(
            {
                "editor_id": editor_id,
                "browser_host": cwd,
                "headless_process_lane": process,
                "typing_surface": typing_surface,
                "c17": (
                    "ready + after_edit_burst + quiescent"
                    if typing_surface
                    else (
                        "ready + quiescent (no verified typing surface)"
                        if browser
                        else ("peak_during_run (one-shot)" if process else "not_run")
                    )
                ),
                "c19": "retained_after_close + reopen delta" if browser else ("not_applicable (one-shot)" if process else "not_run"),
                "c22": "not_applicable: no P0-P3 switch",
            }
        )
    return rows


def _print_support() -> None:
    print("| editor | lane | C17 | C19 | C22 |")
    print("|---|---|---|---|---|")
    for row in support_table():
        lane = "browser: %s" % row["browser_host"] if row["browser_host"] else ("process" if row["headless_process_lane"] else "none")
        print("| %s | %s | %s | %s | %s |" % (row["editor_id"], lane, row["c17"], row["c19"], row["c22"]))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--editor", action="append", default=None, help="editor id; repeat for several (sequential)")
    parser.add_argument("--editors", nargs="+", dest="editor")
    parser.add_argument("--workload", default="micro-paragraphs")
    parser.add_argument("--execution-profile", default="ci_contract", choices=("ci_contract", "ci_broad"))
    parser.add_argument("--pairs", type=int, default=1, help="fresh hosts per editor (bounded by the profile budget)")
    parser.add_argument("--out-root", type=Path, default=None)
    parser.add_argument("--burst", type=int, default=BURST_ITERATIONS)
    parser.add_argument("--quiescence-ms", type=int, default=QUIESCENCE_MS)
    parser.add_argument("--retain-seconds", default="1,5", help="seconds after close at which retained RSS is sampled")
    parser.add_argument("--port", type=int, default=None, help="run one browser editor on this free port instead of its default")
    parser.add_argument("--probe-timeout", type=float, default=PROBE_TIMEOUT_S, help="seconds one probe run may take")
    parser.add_argument("--list-support", action="store_true")
    return parser


def _main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if args.list_support:
        _print_support()
        return 0
    if not args.editor:
        parser.error("--editor is required (or use --list-support)")
    if args.port is not None and len(args.editor) > 1:
        parser.error("--port applies to a single --editor run")
    if args.burst < 0:
        parser.error("--burst must be >= 0")
    if args.quiescence_ms < 0:
        parser.error("--quiescence-ms must be >= 0")

    try:
        retain_seconds = tuple(float(part) for part in str(args.retain_seconds).split(",") if part.strip())
    except ValueError:
        parser.error("--retain-seconds must be comma-separated numbers")
    if not retain_seconds or any(value <= 0 for value in retain_seconds):
        parser.error("--retain-seconds must be positive")
    args.retain_seconds = retain_seconds

    from perf.runner.browser_run import execution_profile
    args.execution_profile = execution_profile(args.execution_profile)
    assert_workload_allowed(args.execution_profile, args.workload)
    workload_row = next(row for row in size_ladder() if row["workload_id"] == args.workload)
    if workload_row['shape'] in ('prose', 'corpus'):
        from perf.fixtures.docx_workload import workload_for_lane

        docx_body = workload_for_lane(args.workload, "memory", REPO)['docx']
    else:
        built = build_workload(workload_row)
        docx_body = docx_zip_bytes(built["body"])
    fixture_sha = hashlib.sha256(docx_body).hexdigest()
    docx_size = len(docx_body)

    budget = sample_budget_for_profile(args.execution_profile, "fresh_process")
    if args.pairs < 1 or args.pairs > budget:
        parser.error("--pairs must be between 1 and %d for %s" % (budget, args.execution_profile))

    run_day = date.today().isoformat().replace("-", "_")
    out_root = (args.out_root or (REPO / "perf" / "out" / ("memory_%s" % run_day))).resolve()
    if (out_root / "summary.json").exists():
        parser.error("%s already has a summary.json; attempts are immutable, so pick a new --out-root" % (out_root,))
    attempt_dir = out_root / "attempts"
    attempt_dir.mkdir(parents=True, exist_ok=True)
    fixture_path = out_root / ("%s.docx" % args.workload)
    if not fixture_path.is_file():
        fixture_path.write_bytes(docx_body)
    indocx = out_root / ("%s-in.docx" % args.workload)
    if not indocx.is_file():
        indocx.write_bytes(docx_body)

    rows: list[dict] = []
    for editor_id in args.editor:
        if editor_id not in FEATURE_SWITCH_PROBE:
            parser.error("unknown editor %r" % (editor_id,))
        lane = default_lane(editor_id)
        target = _browser_target(editor_id)
        if target is not None and args.port is not None:
            try:
                target = _retarget_port(target, args.port)
            except ValueError as exc:
                parser.error("--port: %s" % (exc,))
        error = None
        if editor_id == "apryse" and not _apryse_key_present():
            error = "apryse: trial key not present in environment; the WebViewer host cannot start"
        if error is not None:
            editor_version = pin_label(editor_id)
            env = _env_for(
                editor_id=editor_id,
                editor_version=editor_version,
                fixture_sha=fixture_sha,
                docx_size=docx_size,
                workload_row=workload_row,
                cache_state="process_cold_fs_warm",
                execution_profile=args.execution_profile,
            )
            for criterion in ("C17", "C19"):
                path = _write_outcome(
                    attempt_dir=attempt_dir,
                    criterion_id=criterion,
                    phase=PROCESS_PHASE if criterion == "C17" else None,
                    editor_id=editor_id,
                    lane=lane,
                    env=env,
                    outcome="not_run",
                    failure_reason=error,
                    evidence={"state": "host_not_started", "reason": error},
                )
                rows.append(_row(criterion, PROCESS_PHASE if criterion == "C17" else None, editor_id, "not_run", error, path))
        elif target is not None:
            rows.extend(
                _browser_rows(
                    editor_id=editor_id,
                    lane=lane,
                    target=target,
                    attempt_dir=attempt_dir,
                    args=args,
                    fixture_path=fixture_path,
                    fixture_sha=fixture_sha,
                    docx_size=docx_size,
                    workload_row=workload_row,
                )
            )
            editor_version, _meta = browser_harness_editor_version(editor_id, pin_label(editor_id))
        elif editor_id in PROCESS_TARGETS:
            outdocx = (out_root / ("%s-out.docx" % editor_id)).resolve()
            rows.extend(
                _process_rows(
                    editor_id=editor_id,
                    lane=lane,
                    attempt_dir=attempt_dir,
                    args=args,
                    indocx=indocx,
                    outdocx=outdocx,
                    fixture_sha=fixture_sha,
                    docx_size=docx_size,
                    workload_row=workload_row,
                )
            )
            editor_version = pin_label(editor_id)
        else:
            editor_version = pin_label(editor_id)
            env = _env_for(
                editor_id=editor_id,
                editor_version=editor_version,
                fixture_sha=fixture_sha,
                docx_size=docx_size,
                workload_row=workload_row,
                cache_state="process_cold_fs_warm",
                execution_profile=args.execution_profile,
            )
            reason = "%s: no browser host and no headless lane configured for memory sampling" % (editor_id,)
            for criterion in ("C17", "C19"):
                path = _write_outcome(
                    attempt_dir=attempt_dir,
                    criterion_id=criterion,
                    phase=PROCESS_PHASE if criterion == "C17" else None,
                    editor_id=editor_id,
                    lane=lane,
                    env=env,
                    outcome="not_run",
                    failure_reason=reason,
                    evidence={"state": "no_lane"},
                )
                rows.append(_row(criterion, PROCESS_PHASE if criterion == "C17" else None, editor_id, "not_run", reason, path))
        rows.append(
            _c22_row(
                editor_id=editor_id,
                lane=lane,
                attempt_dir=attempt_dir,
                args=args,
                fixture_sha=fixture_sha,
                docx_size=docx_size,
                workload_row=workload_row,
                editor_version=editor_version,
            )
        )
        print("%s done: %d attempts" % (editor_id, len([row for row in rows if row["editor_id"] == editor_id])))

    from perf.runner.browser_run import host_class as lane_host_class

    lane_host = lane_host_class()
    summary = {
        "runner": "perf/runner/benchmark_memory.py",
        "criterion_ids": ["C17", "C19", "C22"],
        "host_class": lane_host,
        "execution_profile": args.execution_profile,
        "pairs": args.pairs,
        "sample_unit": "bytes (C17/C19); the harness series field is named samples_ms",
        "sampling_method": "ps -Ao pid=,ppid=,rss= summed over the process tree",
        "pss_uss_cgroup": None,
        "publishable": False,
        "publication_block_reason": (
            "ci_coarse host_class blocks headline publication"
            if lane_host == "ci_coarse"
            else "summary is not a trial; trials carry publishability"
        ),
        "rows": rows,
        "support": support_table(),
        "environment": {
            "os": platform.system().lower(),
            "arch": platform.machine(),
            "python": platform.python_version(),
            "load_average": load_average(),
            "quiet_host_check": "uptime/ps were read; the figures carry the load average observed",
        },
        "workload": workload_row["workload_id"],
        "fixture_sha256": fixture_sha,
        "fixture_byte_size": docx_size,
    }
    summary_path = out_root / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print("summary: %s" % (_attempt_ref(summary_path),))
    return 0


def main() -> int:
    # Container invocations use B1 bookkeeping; retain the standalone CLI.
    if any(arg.split('=', 1)[0] in ('--run-id', '--seed', '--host-class') for arg in sys.argv[1:]):
        from perf.runner.browser_run import run_cli
        return run_cli(_main, "benchmark_memory", BROWSER_TARGETS, count_flag="--pairs")
    return _main()


if __name__ == "__main__":
    raise SystemExit(main())
