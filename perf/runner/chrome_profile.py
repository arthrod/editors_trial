"""Diagnostic Chromium profile attempts for browser lanes."""
from __future__ import annotations

import hashlib
import gzip
import json
import re
from pathlib import Path

_TRACE = re.compile(r"^trace-(.+)\.json\.gz$")


def _trace_metadata(path: Path) -> dict:
    raw = path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    return {"path": str(path.resolve()), "bytes": len(raw), "sha256": sha}


def _criterion_from_name(name: str) -> str:
    match = _TRACE.match(name)
    return match.group(1).upper() if match else "PROFILE"


def record_profile_traces(cell_directory: Path, editor_id: str, default_criterion: str, *, write_fn) -> list[Path]:
    profile = Path(cell_directory) / "profile"
    if not profile.is_dir():
        return []
    attempt_dir = Path(cell_directory) / "attempts"
    attempt_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for path in sorted(profile.glob("trace-*.json.gz")):
        criterion = _criterion_from_name(path.name) or default_criterion
        meta = _trace_metadata(path)
        attempt_id = f"chrome-profile-{criterion.lower()}-{meta['sha256'][:10]}"
        trial = {
            "schema": "perf.chrome_profile/1",
            "criterion_id": criterion if criterion != "PROFILE" else default_criterion,
            "editor_id": editor_id,
            "outcome": "profiled",
            "accounting_scope": "diagnostic",
            "publishable": False,
            "chrome_trace": meta,
        }
        written.append(write_fn(attempt_dir, attempt_id, trial))
    return written


def trace_has_cpu_profile(path: Path) -> bool:
    try:
        data = gzip.decompress(path.read_bytes())
        payload = json.loads(data)
    except (OSError, json.JSONDecodeError, gzip.BadGzipFile):
        return False
    events = payload if isinstance(payload, list) else payload.get("traceEvents") or []
    for event in events:
        if not isinstance(event, dict):
            continue
        name = event.get("name") or ""
        cat = event.get("cat") or ""
        if "CpuProfiler" in name or "cpu_profiler" in cat or name == "Profile":
            return True
    return False
