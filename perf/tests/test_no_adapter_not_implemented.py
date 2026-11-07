import json
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


class NoAdapterNotImplemented(unittest.TestCase):
    def test_unblocked_summary_still_has_adapter_gaps(self):
        summary = REPO / "perf/out/unblocked_2026_11_07b/summary.json"
        if not summary.is_file():
            self.skipTest("fixture output missing")
        payload = json.loads(summary.read_text(encoding="utf-8"))
        reasons = [r.get("failure_reason") or "" for r in payload.get("editors", [])]
        self.assertTrue(any("adapter-not-implemented" in r for r in reasons))

    def test_full_browser_root_when_present_has_no_adapter_for_browser_editors(self):
        attempt_dir = REPO / "perf/out/full_browser_2026_11_07/ci_broad/attempts"
        if not attempt_dir.is_dir():
            self.skipTest("full_browser output not produced yet")
        for path in attempt_dir.glob("*.json"):
            text = path.read_text(encoding="utf-8")
            data = json.loads(text)
            if data.get("editor_id") in ("plate", "docxodus", "superdoc", "genoffice", "canvas"):
                self.assertNotIn("adapter-not-implemented", text)


if __name__ == "__main__":
    unittest.main()
