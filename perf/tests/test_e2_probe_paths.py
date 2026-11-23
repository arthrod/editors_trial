"""The test probes find the repository from a checkout path with a space or a %.

``new URL('../..', import.meta.url).pathname`` keeps the URL's percent
encoding: a checkout at ``/tmp/a b`` gives ``/tmp/a%20b``, and
``pathToFileURL`` encodes that again (``a%2520b``), so the probe's imports
miss (CodeRabbit and CodeAnt on #283, 2026-11-23). ``fileURLToPath`` decodes.

P1  The BetterOffice model probe, copied under a folder named ``a b%c``,
    resolves its imports (it may fail later, without a browser; it must not
    fail with ERR_MODULE_NOT_FOUND).
P2  No probe under perf/tests takes a file path from ``.pathname`` of an
    ``import.meta.url`` URL.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


class ProbePathTests(unittest.TestCase):
    def test_a_probe_resolves_its_imports_from_a_path_with_a_space_and_a_percent(self):
        node = shutil.which("node")
        if node is None:
            raise unittest.SkipTest("node is not on PATH")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "a b%c"
            shutil.copytree(REPO / "perf" / "runner", root / "perf" / "runner",
                            ignore=shutil.ignore_patterns("__pycache__", "*.py"))
            (root / "perf" / "tests").mkdir(parents=True)
            probe = root / "perf" / "tests" / "e2_betteroffice_model_probe.mjs"
            shutil.copy(REPO / "perf" / "tests" / "e2_betteroffice_model_probe.mjs", probe)
            proc = subprocess.run([node, str(probe), "about:blank"], capture_output=True, text=True, timeout=120)
            self.assertNotIn("ERR_MODULE_NOT_FOUND", proc.stderr, proc.stderr[-2000:])

    def test_no_probe_takes_a_path_from_an_encoded_url(self):
        bad = re.compile(r"import\.meta\.url\)\.pathname")
        offenders = sorted(p.name for p in (REPO / "perf" / "tests").glob("*.mjs") if bad.search(p.read_text()))
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
