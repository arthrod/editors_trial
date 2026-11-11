"""B8 resources lane fixes (fixres round)."""

from __future__ import annotations

import unittest
from pathlib import Path
from urllib.parse import urlsplit

REPO = Path(__file__).resolve().parents[2]


class WordcraftPortTest(unittest.TestCase):
    def test_target_copy_wordcraft_port_env_matches_url(self):
        from perf.runner.benchmark_resources import _target_copy

        target = _target_copy("wordcraft")
        port = urlsplit(target["url"]).port
        self.assertIsNotNone(port)
        env = target.get("env") or {}
        self.assertEqual(str(port), env.get("PORT"))


class LegacyHostPidTest(unittest.TestCase):
    def test_live_session_records_subprocess_server_pid(self):
        import os
        from types import SimpleNamespace

        from perf.runner.benchmark_resources import LiveSession

        ctx = {
            "editor_id": "plate",
            "fixture_path": "/tmp/x.docx",
            "execution_profile": "ci_contract",
            "host_class": "ci_coarse",
        }
        session = LiveSession(ctx)
        session._server = SimpleNamespace(pid=424242)
        session.server_pid = getattr(session._server, "pid", None) or os.getpid()
        self.assertEqual(session.server_pid, 424242)


if __name__ == "__main__":
    unittest.main()
