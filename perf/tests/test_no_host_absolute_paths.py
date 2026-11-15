"""Harness sources must not hardcode a host-absolute editor path.

The canvas vitest lane once mocked ``WorkerManager`` by an absolute path from
the CI agent's checkout (``/agent/repos/...``); on any other host the mock
silently stopped intercepting and the lane failed on the inline worker import.
Relative literals resolve on every host, so forbid host-absolute editor paths
in harness TypeScript/JavaScript sources (vendored copies excluded).
"""

import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SKIP_DIRS = {"node_modules", "repo-copy", ".vite-cache", "target", "dist", "evidence"}
FORBIDDEN = ("/agent/repos/",)


class NoHostAbsoluteEditorPaths(unittest.TestCase):
    def test_harness_sources_have_no_host_absolute_paths(self):
        offenders = []
        for path in (REPO / "harness").rglob("*"):
            if not path.is_file() or path.suffix not in {".ts", ".mts", ".mjs", ".js"}:
                continue
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for marker in FORBIDDEN:
                for line in text.splitlines():
                    if marker in line and "SKIP-ABSOLUTE-PATH-AUDIT" not in line:
                        offenders.append("%s: %s" % (path.relative_to(REPO), line.strip()[:120]))
                        break
        self.assertEqual(offenders, [], "host-absolute paths found:\n%s" % "\n".join(offenders))


if __name__ == "__main__":
    unittest.main()
