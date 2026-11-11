#!/usr/bin/env python3
"""C04 / C07 / C08 / C09 across every browser host.

One page load per editor measures deferred work (C04), hit testing (C07),
undo (C09) and bulk insert (C08). The Playwright probe emits a JSON payload;
`perf.runner.criteria_input_io` turns it into immutable attempts, refusing a
payload that could produce a dishonest trial.

    PYTHONPATH=. python3 perf/runner/benchmark_input.py --list-support
    PYTHONPATH=. python3 perf/runner/benchmark_input.py --editors plate superdoc
    PYTHONPATH=. python3 perf/runner/benchmark_input.py            # every host
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from perf.runner import criteria_input_io
from perf.runner.criteria_input_io import write_support_matrix
from perf.runner.docx_plaintext import docx_body_text
from perf.runner.benchmark_warm_cold import (  # noqa: E402
    BROWSER_TARGETS,
    PROBE,
    UI,
    _start_server,
    _stop_server,
)
from perf.runner.benchmark_ci_contract import _host_base  # noqa: E402
from perf.runner.browser_run import run_cli, fixture_path as run_fixture, write_json, record_process
from perf.runner.artifacts import write_attempt  # noqa: E402
from perf.schema import validate_trial  # noqa: E402
from perf.runner.benchmark_document import (  # noqa: E402
    content_gate_record,
    content_meta_for_workload,
    gate_length_check_for,
)

CRITERIA = ("C04", "C07", "C09", "C08")
PROBE_TIMEOUT_S = 300


def _fixture(editor_id: str, workload_id: str = "micro-paragraphs") -> tuple[Path, str, int]:
    """The same generated micro workload the warm/cold suite uses.

    ``docx_zip_bytes`` stamps a fresh timestamp on every call, so the file is
    built once and the *bytes on disk* are what the probe is served and what
    the trial hashes — never a second, differently-stamped build.
    """
    import hashlib

    from perf.fixtures.generate import build_workload, correctness_fixtures, docx_zip_bytes
    from perf.fixtures.profiles import size_ladder

    row = next(w for w in size_ladder() if w["workload_id"] == workload_id)
    variant = None
    if row['shape'] in ('prose', 'corpus'):
        from perf.fixtures.docx_workload import workload_for_lane
        built = workload_for_lane(workload_id, "input")
        data = built["docx"]
        variant = built
    else:
        body = build_workload(row)["body"] + b"\n" + correctness_fixtures()["unicode"]
        data = docx_zip_bytes(body)
    from perf.runner.browser_run import ACTIVE
    run = ACTIVE.get()
    path = run_fixture(row["workload_id"], data,
                       (run.directory if run else REPO / "perf/out") / "fixture.docx")
    served = dict(row)
    if variant and variant.get("fixture_variant"):
        served["fixture_variant"] = variant["fixture_variant"]
        served["fixture_source_sha256"] = variant["fixture_source_sha256"]
    return path, hashlib.sha256(data).hexdigest(), len(data), served


# Hosts that paint into a canvas and expose no document text at this pin.
# `canvas` left this set when the input lane learned its command.getText()
# model reader (perf/runner/edit_surface.mjs, READ_SURFACE_STATE).
CANVAS_HOSTS = frozenset({"apryse"})


def _correctness_adapter(editor_id: str, target: dict) -> str | None:
    declared = target.get("correctness_adapter")
    if declared is False or declared == "none":
        return None
    if isinstance(declared, str) and declared:
        return declared
    if editor_id in CANVAS_HOSTS:
        return None
    return "dom_innerText"


def _probe_command(editor_id: str, target: dict, fixture: Path) -> list[str]:
    cmd = [
        "node", str(PROBE),
        "--driver", target.get("driver", "playwright"),
        "--editor", editor_id,
        "--criteria", ",".join(CRITERIA),
        "--url", target["url"],
        "--corpus", str(fixture),
        "--corpus-route", target.get("corpus_route", "/corpus.docx"),
        "--ready-selector", target.get("ready_selector", ""),
        "--edit-selector", target.get("edit_selector", ""),
    ]
    if target.get("ready_js"):
        cmd += ["--ready-js", target["ready_js"]]
    if target.get("error_js"):
        cmd += ["--error-js", target["error_js"]]
    if target.get("wait_after_ready"):
        cmd += ["--wait-after-ready", str(target["wait_after_ready"])]
    return cmd


def _probe_env(editor_id: str, target: dict, fixture: Path, *, workload_id: str,
               workload_row: dict | None = None) -> dict:
    env = dict(os.environ)
    env.pop("PERF_EXPECTED_BODY_B64", None)
    env.pop("PERF_EXPECTED_BODY_PATH", None)
    env.pop("PERF_EXPECTED_OPENING_TEXT", None)
    if workload_id == "complex-corpus":
        from perf.runner.benchmark_document import corpus_opening_text

        opening = corpus_opening_text(fixture)
        if opening:
            env["PERF_EXPECTED_OPENING_TEXT"] = opening
        else:
            env["PERF_INPUT_OPENING_REQUIRED"] = "1"
    else:
        body = docx_body_text(fixture)
        body_path = fixture.with_name(fixture.stem + ".expected-body.txt")
        try:
            # Written once per fixture; a later launch reads the same text.
            with open(body_path, "x", encoding="utf-8") as handle:
                handle.write(body)
        except FileExistsError:
            pass
        env["PERF_EXPECTED_BODY_PATH"] = str(body_path.resolve())
    adapter = _correctness_adapter(editor_id, target)
    if adapter:
        env["PERF_CORRECTNESS_ADAPTER"] = adapter
    else:
        env.pop("PERF_CORRECTNESS_ADAPTER", None)
        env["PERF_CORRECTNESS_ADAPTER"] = ""
    if adapter:
        target.setdefault("correctness_adapter", adapter)
    else:
        target["correctness_adapter"] = None
    if workload_row and workload_row.get("fixture_variant"):
        env["PERF_FIXTURE_VARIANT"] = workload_row["fixture_variant"]
        env["PERF_FIXTURE_SOURCE_SHA256"] = workload_row["fixture_source_sha256"]
    else:
        env.pop("PERF_FIXTURE_VARIANT", None)
        env.pop("PERF_FIXTURE_SOURCE_SHA256", None)
    return env


def _write_criteria_refusals(attempt_dir: Path, editor_id: str, workload_row: dict,
                             fixture_sha: str, fixture_size: int, *,
                             failure_reason: str, refusal_code: str) -> None:
    """One refused trial per scheduled criterion for a launch that produced no payload."""
    from perf.runner.benchmark_ci_contract import _trial_dict
    catalog = criteria_input_io._catalog()
    for cid in CRITERIA:
        if list(attempt_dir.glob("%s-*.json" % cid.lower())):
            continue
        env = criteria_input_io.env_for(
            editor_id, editor_id, fixture_sha, workload_row, fixture_size, "warm_steady")
        meta = content_meta_for_workload(workload_row.get("workload_id") or "micro-paragraphs")
        gate = gate_length_check_for(editor_id, meta)
        trial = _trial_dict(
            criterion_id=cid,
            layer=catalog[cid]["layer"],
            boundary=catalog[cid]["boundary"],
            outcome="failed",
            env=env,
            samples_ms=[],
            failure_reason=failure_reason,
            editor_id=editor_id,
            diagnostic={
                "suite": "criteria_input",
                "refusal_origin": "launch",
                **content_gate_record(meta, gate),
            },
        )
        trial["refusal_code"] = refusal_code
        trial["refusal_detail"] = failure_reason
        write_attempt(
            attempt_dir,
            "%s-%s-%s" % (cid.lower(), editor_id, uuid.uuid4().hex[:10]),
            trial,
        )


def _refuse_run(editor_id: str, attempt_dir: Path, workload_row: dict,
                fixture_sha: str, fixture_size: int, *,
                reason: str, refusal_code: str, t0: float | None = None) -> dict:
    _write_criteria_refusals(
        attempt_dir, editor_id, workload_row, fixture_sha, fixture_size,
        failure_reason=reason, refusal_code=refusal_code)
    row = {"editor_id": editor_id, "outcome": "failed", "failure_reason": reason}
    if t0 is not None:
        row["wall_s"] = round(time.time() - t0, 1)
    return row


def run_editor(editor_id: str, attempt_dir: Path, workload_id: str = "micro-paragraphs") -> dict:
    target = BROWSER_TARGETS[editor_id]
    fixture, fixture_sha, fixture_size, workload_row = _fixture(editor_id, workload_id)
    from perf.runner.browser_hosts import select_fixture
    try:
        select_fixture(target, fixture)
        started = _start_server(editor_id, target)
    except Exception as exc:
        return _refuse_run(
            editor_id, attempt_dir, workload_row, fixture_sha, fixture_size,
            reason="%s: %s" % (type(exc).__name__, exc), refusal_code="host_build")
    t0 = time.time()
    try:
        try:
            proc = subprocess.run(
                _probe_command(editor_id, target, fixture),
                cwd=str(UI),
                capture_output=True,
                text=True,
                timeout=PROBE_TIMEOUT_S,
                env=_probe_env(editor_id, target, fixture, workload_id=workload_id,
                               workload_row=workload_row),
            )
        except subprocess.TimeoutExpired:
            return _refuse_run(
                editor_id, attempt_dir, workload_row, fixture_sha, fixture_size,
                reason="probe exceeded the %ss timeout" % PROBE_TIMEOUT_S,
                refusal_code="editor_timeout", t0=t0)
        record_process(proc)
        wall = round(time.time() - t0, 1)
        if proc.returncode != 0:
            # The editor's own load error is a named refusal with the editor's
            # message — the same classification the document lane uses
            # (benchmark_document.py), never a bare 'editor_crash' stack.
            err_blob = proc.stderr or proc.stdout or ""
            if "editor_load_failed" in err_blob:
                detail = err_blob.split("editor_load_failed:", 1)[-1].strip()[:400]
                return _refuse_run(
                    editor_id, attempt_dir, workload_row, fixture_sha, fixture_size,
                    reason="editor_load_failed: %s" % detail,
                    refusal_code="editor_load_failed", t0=t0)
            return _refuse_run(
                editor_id, attempt_dir, workload_row, fixture_sha, fixture_size,
                reason=(proc.stderr or "")[-600:], refusal_code="editor_crash", t0=t0)
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError:
            return _refuse_run(
                editor_id, attempt_dir, workload_row, fixture_sha, fixture_size,
                reason="probe output was not the criteria payload JSON",
                refusal_code="harness_error", t0=t0)
        written = criteria_input_io.write_trials_from_payload(
            payload,
            attempt_dir,
            editor_version=editor_id,
            fixture_sha256=fixture_sha,
            workload_row=workload_row,
            docx_size=fixture_size,
        )
        criteria_summary = {}
        for cid in payload["criteria_requested"]:
            row = written[cid]
            entry = payload["criteria"][cid]
            criteria_summary[cid] = criterion_summary(row, entry)
        return {
            "editor_id": editor_id,
            "outcome": "ok",
            "wall_s": wall,
            "criteria": criteria_summary,
        }
    except Exception as exc:
        return _refuse_run(
            editor_id, attempt_dir, workload_row, fixture_sha, fixture_size,
            reason="%s: %s" % (type(exc).__name__, exc), refusal_code="harness_error", t0=t0)
    finally:
        _stop_server(started)


def criterion_summary(row, entry):
    if row["written"]:
        return {
            "outcome": entry["outcome"], "samples_ms": entry["samples_ms"],
            "failure_reason": entry.get("failure_reason"),
            "attempt_file": str(Path(row["path"]).resolve()),
        }
    return {**row, "outcome": "failed", "samples_ms": [], "attempt_file": None}


def _main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--editors", nargs="*", default=list(BROWSER_TARGETS))
    ap.add_argument("--workload", default="micro-paragraphs")
    ap.add_argument("--out-root", default=None)
    ap.add_argument("--list-support", action="store_true")
    args = ap.parse_args()

    if args.list_support:
        for editor_id, target in BROWSER_TARGETS.items():
            print("%-12s lane=%-13s edit=%s" % (editor_id, target.get("lane", "?"),
                                                target.get("edit_selector", "")[:60]))
        return 0

    out_root = Path(args.out_root) if args.out_root else REPO / "perf" / "out" / \
        ("criteria_input_%s" % date.today().isoformat())
    attempt_dir = out_root / "attempts"
    attempt_dir.mkdir(parents=True, exist_ok=True)

    summary = {"suite": "criteria_input", "criteria": list(CRITERIA),
               "publishable": False,
               "publication_block_reason": "ci_coarse cannot publish visible latency",
               "editors": []}
    for editor_id in args.editors:
        if editor_id not in BROWSER_TARGETS:
            print("unknown editor %r" % editor_id, file=sys.stderr)
            continue
        try:
            row = run_editor(editor_id, attempt_dir, args.workload)
        except Exception as exc:  # a host failure is data, not a crash
            row = {"editor_id": editor_id, "outcome": "failed",
                   "failure_reason": "%s: %s" % (type(exc).__name__, exc)}
        summary["editors"].append(row)
        print("%-12s %s" % (editor_id, row["outcome"]), flush=True)
    write_json(out_root / "summary.json", summary)
    write_support_matrix(summary, out_root)
    return 0


def main() -> int:
    return run_cli(_main, 'benchmark_input', BROWSER_TARGETS, count_flag=None, default_count=1, single=False)


if __name__ == "__main__":
    raise SystemExit(main())
