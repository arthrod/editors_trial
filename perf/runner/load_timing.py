"""Parse ``PERF key=value`` lines from harness stdout (adapter boundary timing)."""

from __future__ import annotations

import re

_PERF = re.compile(r"^PERF\s+(\w+)=(\S+)\s*$")


def parse_perf_lines(stderr: str, stdout: str) -> dict[str, float]:
    combined = (stderr or "") + "\n" + (stdout or "")
    out: dict[str, float] = {}
    for line in combined.splitlines():
        m = _PERF.match(line.strip())
        if m is None:
            continue
        key, raw = m.group(1), m.group(2)
        try:
            out[key] = float(raw)
        except ValueError:
            continue
    return out
