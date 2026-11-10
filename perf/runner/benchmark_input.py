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
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from perf.runner import criteria_input_io
from perf.runner.benchmark_warm_cold import (  # noqa: E402
    BROWSER_TARGETS,
    PROBE,
    UI,
    _start_server,
    _stop_server,
)
from perf.runner.benchmark_ci_contract import _host_base  # noqa: E402
from perf.runner.artifacts import write_attempt  # noqa: E402
from perf.schema import validate_trial  # noqa: E402

CRITERIA = ("C04", "C07", "C09", "C08")
PROBE_TIMEOUT_S = 300


def _fixture(editor_id: str) -> tuple[Path, str, int]:
    """The same generated micro workload the warm/cold suite uses.

    ``docx_zip_bytes`` stamps a fresh timestamp on every call, so the file is
    built once and the *bytes on disk* are what the probe is served and what
    the trial hashes — never a second, differently-stamped build.
    """
    import hashlib

    from perf.fixtures.generate import build_workload, correctness_fixtures, docx_zip_bytes
    from perf.fixtures.profiles import size_ladder

    row = next(w for w in size_ladder() if w["workload_id"] == "micro-paragraphs")
    path = REPO / "perf" / "out" / "_fixtures" / "micro-paragraphs.docx"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        body = build_workload(row)["body"] + b"\n" + correctness_fixtures()["unicode"]
        path.write_bytes(docx_zip_bytes(body))
    data = path.read_bytes()
    return path, hashlib.sha256(data).hexdigest(), len(data), row


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
    if target.get("wait_after_ready"):
        cmd += ["--wait-after-ready", str(target["wait_after_ready"])]
    return cmd


def run_editor(editor_id: str, attempt_dir: Path) -> dict:
    target = BROWSER_TARGETS[editor_id]
    fixture, fixture_sha, fixture_size, workload_row = _fixture(editor_id)
    started = _start_server(editor_id, target)
    t0 = time.time()
    try:
        proc = subprocess.run(
            _probe_command(editor_id, target, fixture),
            cwd=str(UI),
            capture_output=True,
            text=True,
            timeout=PROBE_TIMEOUT_S,
        )
        wall = round(time.time() - t0, 1)
        if proc.returncode != 0:
            return {"editor_id": editor_id, "outcome": "failed", "wall_s": wall,
                    "failure_reason": (proc.stderr or "")[-600:]}
        payload = json.loads(proc.stdout)
        written = criteria_input_io.write_trials_from_payload(
            payload,
            attempt_dir,
            editor_version=editor_id,
            fixture_sha256=fixture_sha,
            workload_row=workload_row,
            docx_size=fixture_size,
        )
        return {
            "editor_id": editor_id,
            "outcome": "ok",
            "wall_s": wall,
            "criteria": {
                cid: {
                    "outcome": payload["criteria"][cid]["outcome"],
                    "samples_ms": payload["criteria"][cid]["samples_ms"],
                    "failure_reason": payload["criteria"][cid].get("failure_reason"),
                    "attempt_file": str(Path(path).resolve().relative_to(REPO.resolve())),
                }
                for cid, path in zip(
                    payload["criteria_requested"],
                    [Path(p) for p in written],
                )
            },
        }
    finally:
        _stop_server(started)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--editors", nargs="*", default=list(BROWSER_TARGETS))
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
            row = run_editor(editor_id, attempt_dir)
        except Exception as exc:  # a host failure is data, not a crash
            row = {"editor_id": editor_id, "outcome": "failed",
                   "failure_reason": "%s: %s" % (type(exc).__name__, exc)}
        summary["editors"].append(row)
        print("%-12s %s" % (editor_id, row["outcome"]), flush=True)
        (out_root / "summary.json").write_text(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
