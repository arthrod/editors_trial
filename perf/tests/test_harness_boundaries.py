"""Where each harness starts and stops its PERF clocks under PERF_ONLY=1.

The speed report says the save clock runs "from the start of the editor's
export call until the DOCX bytes exist". Work the export needs from the
loaded model (a citation style, a template, the exporter itself) belongs
inside that clock; work done only to print evidence does not.

These tests read the harness source: the order of statements is the
boundary. A probe that timed the phases (2026-11-09, prose-50kw) found the
Fidus export spending about 53 ms outside its save clock (citation style
40 ms, template 5 ms, exporter construction 8 ms) against a save of 305 ms.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIDUS = ROOT / "harness" / "fidus" / "roundtrip.mts"


def _line_of(src: str, pattern: str) -> int:
    hits = [n for n, line in enumerate(src.splitlines(), 1) if re.search(pattern, line)]
    if len(hits) != 1:
        raise AssertionError(f"{pattern!r} matched lines {hits}, expected exactly one")
    return hits[0]


@unittest.skipUnless(FIDUS.exists(), "harness/fidus is not checked out")
class FidusSaveClock(unittest.TestCase):
    def setUp(self):
        self.src = FIDUS.read_text(encoding="utf-8")
        # The clock that PERF save_ms is measured from, under PERF_ONLY.
        self.start = _line_of(self.src, r"const perfSaveStart = process\.env\.PERF_ONLY === \"1\"")
        self.stop = _line_of(self.src, r"const tSave1 = performance\.now\(\)")

    def test_save_clock_uses_the_perf_only_start(self):
        _line_of(self.src, r"const tSave0 = perfSaveStart \?\? performance\.now\(\)")

    def test_export_preparation_is_inside_the_save_clock(self):
        for step in (
            r"catalog\.getStyles\(\)",
            r"await generateDocxTemplate\(",
            r"new CapturingDocxExporter\(",
            r"await exporter\.init\(\)",
        ):
            with self.subTest(step=step):
                line = _line_of(self.src, step)
                self.assertTrue(self.start < line < self.stop, f"{step} at {line} is outside {self.start}..{self.stop}")

    def test_load_clock_stops_before_the_save_clock_starts(self):
        load_stop = _line_of(self.src, r"const t1 = performance\.now\(\)")
        self.assertLess(load_stop, self.start)

    def test_nothing_is_printed_inside_the_save_clock_under_perf_only(self):
        lines = self.src.splitlines()[self.start : self.stop - 1]
        for n, line in enumerate(lines, self.start + 1):
            if "console.log(" in line:
                with self.subTest(line=n):
                    self.assertRegex(line, r"perfSaveStart === undefined", f"line {n} prints inside the clock: {line.strip()}")


CANVAS = ROOT / "harness" / "canvas" / "roundtrip.test.ts"


@unittest.skipUnless(CANVAS.exists(), "harness/canvas is not checked out")
class CanvasImportFailure(unittest.TestCase):
    """A thrown import is the editor refusing the file. Under PERF_ONLY the
    harness must fail the sample, not export the half-loaded editor and print
    a save time for it (found on complex.docx, 2026-11-09)."""

    def test_perf_only_rethrows_the_import_error(self):
        src = CANVAS.read_text(encoding="utf-8")
        rethrow = _line_of(src, r"throw importError")
        guard = src.splitlines()[rethrow - 2]
        self.assertRegex(guard, r"PERF_ONLY")
        self.assertLess(rethrow, _line_of(src, r"const tSave0 = performance\.now\(\)"))


if __name__ == "__main__":
    unittest.main()
