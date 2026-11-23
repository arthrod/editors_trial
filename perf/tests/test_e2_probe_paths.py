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
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not on PATH")
def test_a_probe_resolves_its_imports_from_a_path_with_a_space_and_a_percent(tmp_path):
    """P1: the probe copied under ``a b%c`` loads its imports."""
    root = tmp_path / "a b%c"
    shutil.copytree(REPO / "perf" / "runner", root / "perf" / "runner",
                    ignore=shutil.ignore_patterns("__pycache__", "*.py"))
    (root / "perf" / "tests").mkdir(parents=True)
    probe = root / "perf" / "tests" / "e2_betteroffice_model_probe.mjs"
    shutil.copy(REPO / "perf" / "tests" / "e2_betteroffice_model_probe.mjs", probe)
    proc = subprocess.run([shutil.which("node"), str(probe), "about:blank"],
                          capture_output=True, text=True, timeout=120)
    assert "ERR_MODULE_NOT_FOUND" not in proc.stderr, proc.stderr[-2000:]


def test_no_probe_takes_a_path_from_an_encoded_url():
    """P2: no ``.mjs`` probe under perf/tests reads ``import.meta.url``'s ``.pathname``."""
    bad = re.compile(r"import\.meta\.url\)\.pathname")
    offenders = sorted(p.name for p in (REPO / "perf" / "tests").glob("*.mjs") if bad.search(p.read_text()))
    assert offenders == []
