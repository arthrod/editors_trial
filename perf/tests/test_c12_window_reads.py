"""C12 window membership counts a frame's own read on the frame clock (#175).

``c12WindowReads`` lives in a ``page.evaluate`` callback. This slices that
callback out of ``document_probe.mjs`` and runs it in Chromium, which is how
the probe itself runs it. Cooked counts through ``c12_measured_sample`` are a
different test: that gate already refuses ``reads < frames``.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PROBE = REPO / "perf" / "runner" / "document_probe.mjs"
WITNESS = REPO / "perf" / "runner" / "witness.mjs"

# Window from the issue: frame at 100, stamp at 180, bound at 166.
_START = 90
_BOUND = 166

# The witness path must not be argv[1]: witness.mjs treats that as its CLI and
# prints a witness_run onto the same stdout. The callback and cases travel in
# the environment for the same reason.
_NODE = r"""
import { pathToFileURL } from 'node:url';
const witness = await import(pathToFileURL(process.env.C12_WITNESS).href);
const fn = (0, eval)(process.env.C12_PREDICATE);
if (typeof fn !== 'function') throw new Error('c12WindowReads callback is not a function');
const cases = JSON.parse(process.env.C12_CASES);
const { chromium } = await witness.loadPlaywright();
const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage();
  await page.setContent('<!doctype html><title>c12</title>');
  const out = {};
  for (const c of cases) {
    await page.evaluate((payload) => {
      window.__c12ProbeReadLog = payload.log;
      window.__c12FrameLog = payload.frames;
    }, { log: c.log, frames: c.frames });
    out[c.name] = await page.evaluate(fn, { start: c.start, bound: c.bound });
  }
  process.stdout.write(JSON.stringify(out));
} finally {
  await browser.close();
}
"""


def _node():
    return shutil.which("node")


def _playwright_ready() -> bool:
    if os.environ.get("WITNESS_PLAYWRIGHT"):
        return True
    for candidate in (
        REPO / "harness" / "ui" / "plate" / "node_modules" / "playwright",
        REPO / "harness" / "ui" / "node_modules" / "playwright",
        REPO / "harness" / "ui" / "node_modules" / "playwright-core",
    ):
        if candidate.is_dir():
            return True
    return False


def _predicate_source() -> str:
    source = PROBE.read_text(encoding="utf-8")
    marker = "const c12WindowReads = (startMs, boundMs) =>"
    at = source.index(marker)
    start = source.index("({ start, bound }) =>", at)
    end = source.index("}, { start: startMs, bound: boundMs });", start)
    return source[start : end + 1]


def _cases():
    frame = [{"t": 100}]
    return [
        {
            "name": "paired",
            "log": [{"t": 180, "ms": 2, "frameT": 100}],
            "frames": frame,
            "start": _START,
            "bound": _BOUND,
        },
        {
            "name": "orphan",
            "log": [{"t": 180, "ms": 4}],
            "frames": frame,
            "start": _START,
            "bound": _BOUND,
        },
        {
            "name": "census",
            "log": [{"t": 120, "ms": 3}, {"t": 200, "ms": 9}],
            "frames": frame,
            "start": _START,
            "bound": _BOUND,
        },
        {
            "name": "unpaired_frame",
            "log": [{"t": 180, "ms": 2, "frameT": 100}],
            "frames": [{"t": 100}, {"t": 140}],
            "start": _START,
            "bound": _BOUND,
        },
        {
            "name": "frame_time_outside",
            "log": [{"t": 180, "ms": 2, "frameT": 50}],
            "frames": frame,
            "start": _START,
            "bound": _BOUND,
        },
    ]


def _run() -> dict:
    scratch = REPO / ".scratch" / "tmp"
    scratch.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["TMPDIR"] = str(scratch)
    env["C12_WITNESS"] = str(WITNESS)
    env["C12_PREDICATE"] = _predicate_source()
    env["C12_CASES"] = json.dumps(_cases())
    proc = subprocess.run(
        [_node(), "--input-type=module", "-e", _NODE],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    if proc.returncode != 0:
        raise AssertionError(
            "window predicate driver failed (rc=%s)\nstdout:\n%s\nstderr:\n%s"
            % (proc.returncode, proc.stdout, proc.stderr)
        )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            "window predicate driver did not print JSON (%s)\nstdout:\n%s\nstderr:\n%s"
            % (exc, proc.stdout, proc.stderr)
        ) from exc


@unittest.skipUnless(_node() and _playwright_ready(), "node+playwright required")
class C12WindowPredicate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.got = _run()

    def test_paired_read_counts_on_its_frame_time(self):
        # Stamp is past the bound. The frame time is inside. That read counts.
        self.assertEqual(
            self.got["paired"],
            {"reads": 1, "read_ms": 2, "total": 1, "frames": 1},
        )

    def test_orphan_read_without_frame_time_stays_outside(self):
        # No frameT: the stamp is the only clock. A late orphan stays out.
        self.assertEqual(
            self.got["orphan"],
            {"reads": 0, "read_ms": 0, "total": 1, "frames": 1},
        )

    def test_census_rect_uses_its_own_timestamp(self):
        # Census rects carry no frameT. The one inside [90, 166] counts; the
        # one at t=200 does not, and its duration is not in read_ms.
        self.assertEqual(
            self.got["census"],
            {"reads": 1, "read_ms": 3, "total": 2, "frames": 1},
        )

    def test_frame_without_a_paired_read_stays_short(self):
        # One paired read does not cover a second in-window frame.
        self.assertEqual(
            self.got["unpaired_frame"],
            {"reads": 1, "read_ms": 2, "total": 1, "frames": 2},
        )

    def test_frame_time_outside_the_window_does_not_count(self):
        self.assertEqual(
            self.got["frame_time_outside"],
            {"reads": 0, "read_ms": 0, "total": 1, "frames": 1},
        )
