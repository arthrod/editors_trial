"""Fast guards for docxodus/superdoc/genoffice browser harness wiring."""

import json
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


class UnblockedBrowserHarness(unittest.TestCase):
    def test_docxodus_vite_serves_raw_dist(self):
        text = (REPO / "harness/ui/docxodus/vite.config.ts").read_text(encoding="utf-8")
        self.assertIn("docxodus-raw-dist", text)
        self.assertIn("docxodus/dist/", text)

    def test_genoffice_stub_uses_corpus_route(self):
        stub = (REPO / "harness/ui/genoffice/desktop-stub.js").read_text(encoding="utf-8")
        self.assertIn("/corpus.docx", stub)
        self.assertNotIn("'/sample.docx'", stub)

    def test_genoffice_ready_uses_selector_not_eval(self):
        runner = (REPO / "perf/runner/benchmark_warm_cold.py").read_text(encoding="utf-8")
        start = runner.index('"genoffice":')
        end = runner.index('"canvas":', start)
        block = runner[start:end]
        self.assertIn('"ready_selector": ".doc-page"', block)
        self.assertNotIn(".doc-page').length", block)

    def test_genoffice_has_local_vite_deps(self):
        pkg = json.loads((REPO / "harness/ui/genoffice/package.json").read_text(encoding="utf-8"))
        self.assertIn("vite", pkg.get("devDependencies", {}))

    def test_superdoc_host_uses_published_package(self):
        runner = (REPO / "perf/runner/benchmark_warm_cold.py").read_text(encoding="utf-8")
        self.assertIn('UI / "superdoc"', runner)
        pkg = json.loads((REPO / "harness/ui/superdoc/package.json").read_text(encoding="utf-8"))
        self.assertIn("superdoc", pkg.get("dependencies", {}))


if __name__ == "__main__":
    unittest.main()
