#!/usr/bin/env python3
"""Write corpus.docx next to this host: the warm_cold micro-paragraphs fixture.

Run from the host directory:

    PYTHONPATH=. /opt/homebrew/bin/python3.13 make_corpus.py

It uses the same bytes as perf/runner/benchmark_warm_cold.py (micro-paragraphs
body + the Unicode correctness fixture), so a human opening the host sees the
document the perf suite measures. The driver still intercepts /corpus.docx and
serves the runner's own fixture; this file only makes the host self-contained.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))

from perf.fixtures.generate import (  # noqa: E402
    build_workload,
    correctness_fixtures,
    docx_zip_bytes,
)
from perf.fixtures.profiles import size_ladder  # noqa: E402


def main() -> int:
    row = next(w for w in size_ladder() if w["workload_id"] == "micro-paragraphs")
    body = build_workload(row)["body"] + b"\n" + correctness_fixtures()["unicode"]
    out = HERE / "corpus.docx"
    out.write_bytes(docx_zip_bytes(body))
    print("wrote %s (%d bytes)" % (out, out.stat().st_size))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
