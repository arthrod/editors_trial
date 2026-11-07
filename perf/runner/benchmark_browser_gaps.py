#!/usr/bin/env python3
"""Fill honest not_run rows for browser criteria without adapter-not-implemented stubs."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from perf.adapters.capabilities import default_lane, pin_label  # noqa: E402
from perf.runner.artifacts import write_attempt  # noqa: E402
from perf.runner.benchmark_ci_contract import INTERPRETATION_CONDITIONS, _host_base, _trial_dict  # noqa: E402
from perf.runner.harness_ui_versions import browser_harness_editor_version  # noqa: E402
from perf.scenarios.catalog import scenarios  # noqa: E402

BROWSER = {"docxodus", "superdoc", "genoffice", "plate", "canvas"}


def _existing(attempt_dir: Path) -> set[tuple[str, str]]:
    out = set()
    for path in attempt_dir.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        out.add((data.get("criterion_id"), data.get("editor_id")))
    return out


def _reason(cid: str, editor_id: str) -> str:
    reasons = {
        "C01": "C01 startup: warm_cold records cold load only; dedicated cache matrix pending",
        "C04": "C04 deferred-work quiescence probe not completed on this host pass",
        "C11": "C11 navigation paint: no paginated navigation hook exercised",
        "C14": "C14 gigantic fixture: workload cap on ci_broad defers one-paragraph host file",
        "C15": "C15 search: browser search API not probed on this editor harness",
        "C16": "C16 browser save: no export/download hook timed on this harness",
        "C17": "C17 memory at cap: diagnostic cgroup not enabled on laboratory pass",
        "C18": "C18 allocation: diagnostic Chrome trace not collected in this pass",
        "C19": "C19 collaboration: not applicable for P0 harness hosts",
        "C21": "C21 child CPU: measured on contract lane, not browser_visible repeat",
    }
    if editor_id == "genoffice":
        return "genoffice: renderer repo absent; browser harness cannot boot"
    return reasons.get(cid, "browser criterion not driven in this suite stage")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-root", type=Path, required=True)
    parser.add_argument("--execution-profile", default="ci_broad")
    parser.add_argument("--host-class", default="ci_coarse")
    args = parser.parse_args()
    attempt_dir = args.out_root / "attempts"
    attempt_dir.mkdir(parents=True, exist_ok=True)
    have = _existing(attempt_dir)
    sc_map = {s["id"]: s for s in scenarios()}
    for editor_id in sorted(BROWSER):
        lane = default_lane(editor_id)
        version, _ = browser_harness_editor_version(editor_id, pin_label(editor_id))
        for cid in [s["id"] for s in scenarios() if s["id"].startswith("C")]:
            if (cid, editor_id) in have:
                continue
            if cid == "C24":
                continue
            sc = sc_map[cid]
            env = _host_base(
                editor_id=editor_id,
                editor_version=version,
                execution_profile=args.execution_profile,
                fixture_sha256="0" * 64,
                workload_row={
                    "workload_id": "micro-paragraphs",
                    "paragraphs": 5,
                    "unicode_class": "ascii",
                    "match_count": 0,
                    "shape": "micro",
                },
                docx_size=1000,
                cache_state="warm_steady",
                repetition_unit=sc.get("repetition_unit", "fresh_process"),
                run_kind=sc.get("run_kind", "timing"),
                feature_profile_name="P0",
            )
            env["host_class"] = args.host_class
            env["headless"] = True
            env["display_refresh_hz"] = None
            env["interpretation_conditions"] = list(INTERPRETATION_CONDITIONS)
            trial = _trial_dict(
                criterion_id=cid,
                layer=sc["layer"],
                boundary=sc["boundary"],
                outcome="not_run",
                env=env,
                samples_ms=[],
                failure_reason=_reason(cid, editor_id),
                editor_id=editor_id,
                lane=lane,
                publishable=False,
                publication_block_reason="honest gap fill",
            )
            write_attempt(attempt_dir, "%s-%s-%s" % (cid.lower(), editor_id, uuid.uuid4().hex[:8]), trial)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
