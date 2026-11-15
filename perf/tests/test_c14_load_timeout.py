"""C14 waits 1000 s for each document load (#184, owner decision 2026-11-13).

C14's probe target carries no workload id, so the 600 s rule for prose-250kw
never reached it: every rung got the 300 s default, and the subprocess
watchdog killed Plate's 250,000-word load at 330 s. C14 now has its own
timeout, set on every rung, recorded on every trial, and disclosed.
"""

from __future__ import annotations

import unittest
from unittest import mock

import perf.runner.benchmark_document as bd
from perf.runner import lax_bounds
import re

from perf.runner.load_timeouts import C14_COPY_WAIT_MS, C14_LOAD_STAGES, C14_LOAD_TIMEOUT_MS


class _Stop(Exception):
    pass


class C14LoadTimeout(unittest.TestCase):
    TARGET = {"url": "http://127.0.0.1:1/", "corpus_route": "/corpus.docx"}
    CFG = {"doc_selector": ".p", "page_model": "page", "edit_selector": ".p"}

    def test_the_value_is_1000_seconds(self):
        self.assertEqual(C14_LOAD_TIMEOUT_MS, 1_000_000)

    def _scale_cmd(self, target):
        seen = {}

        def fake_run(cmd, *, editor_id, env=None):
            seen["cmd"] = list(cmd)
            raise _Stop()

        with mock.patch.object(bd, "_run_probe", fake_run), \
                mock.patch("perf.runner.browser_hosts.select_fixture", lambda *a, **k: None), \
                self.assertRaises(_Stop):
            bd._run_scale_samples(editor_id="plate", target=target, cfg=self.CFG,
                                  fixture_path=bd.REPO / "x.docx", count=1)
        return seen["cmd"]

    def test_every_rung_probe_waits_1000_seconds(self):
        for target in (self.TARGET, {**self.TARGET, "workload_id": "prose-500w"},
                       {**self.TARGET, "workload_id": "prose-250kw"}):
            cmd = self._scale_cmd(target)
            self.assertEqual(cmd[cmd.index("--timeout-ms") + 1], str(C14_LOAD_TIMEOUT_MS), target)

    def test_the_watchdog_covers_the_load_and_the_whole_text_read(self):
        cmd = self._scale_cmd(self.TARGET)
        self.assertEqual(cmd[cmd.index("--c14-copy-wait-ms") + 1], str(C14_COPY_WAIT_MS))
        # Navigation, the ready signal and the document surface each get the full wait, one after another
        # (review of e0c237de, H1): the watchdog must outlast all three plus the copy.
        self.assertEqual(C14_LOAD_STAGES, 3)
        self.assertEqual(bd._subprocess_timeout_s(cmd),
                         (C14_LOAD_STAGES * C14_LOAD_TIMEOUT_MS + C14_COPY_WAIT_MS) / 1000 + 30)

    def test_a_canvas_host_gets_the_load_event_wait_too(self):
        # Review of f97f74e0, H1: screencast_ink hosts (Docen, WordCraft) wait for the load event first.
        cmd = ["--mode", "scale", "--timeout-ms", "1000000", "--usable-signal", "screencast_ink",
               "--c14-copy-wait-ms", "120000"]
        self.assertEqual(bd._subprocess_timeout_s(cmd), (4 * C14_LOAD_TIMEOUT_MS + C14_COPY_WAIT_MS) / 1000 + 30)

    def test_the_c14_watchdog_follows_the_scale_mode_not_the_copy_flag(self):
        # Review of f97f74e0, L4.
        cmd = ["--mode", "scale", "--timeout-ms", "1000000"]
        self.assertEqual(bd._subprocess_timeout_s(cmd), 3 * C14_LOAD_TIMEOUT_MS / 1000 + 30)

    def test_other_probes_outlast_every_load_stage_and_their_own_work(self):
        # #195: one load timeout for the whole probe cut Plate's prose-250kw C11 and C12.
        self.assertEqual(bd._subprocess_timeout_s(["--timeout-ms", "300000"]), 4 * 300 + 30.0)

    FIXTURE = {"sha256": "0", "workload_row": {}, "byte_size": 1, "paragraph_count": 1}

    def test_every_c14_trial_records_the_timeout(self):
        with mock.patch.object(bd, "_host_base", lambda **k: {"load_timeout_ms": 300_000}):
            env = bd._c14_env_for(editor_id="plate", editor_version="v", fixture=self.FIXTURE, cache_state="cold")
        self.assertEqual(env["load_timeout_ms"], C14_LOAD_TIMEOUT_MS)

    def test_a_refused_c14_cell_records_the_c14_timeout_too(self):
        # Review of e0c237de, M1: the refusal path built its environment with the per-workload rule.
        with mock.patch.object(bd, "_host_base", lambda **k: {"load_timeout_ms": 300_000}):
            c14 = bd._criterion_env_for("C14", editor_id="plate", editor_version="v", fixture=self.FIXTURE,
                                        cache_state="cold")
            c11 = bd._criterion_env_for("C11", editor_id="plate", editor_version="v", fixture=self.FIXTURE,
                                        cache_state="cold")
        self.assertEqual(c14["load_timeout_ms"], C14_LOAD_TIMEOUT_MS)
        self.assertEqual(c11["load_timeout_ms"], 300_000)

    def test_the_copy_wait_matches_the_probe(self):
        source = (bd.REPO / "perf" / "runner" / "c14_whole_text.mjs").read_text()
        found = re.search(r"export const C14_COPY_WAIT_MS = ([\d_]+);", source)
        self.assertIsNotNone(found)
        self.assertEqual(int(found.group(1).replace("_", "")), C14_COPY_WAIT_MS)

    def test_the_report_discloses_it(self):
        self.assertIn("C14 (large-document scaling) gives each wait of a load (navigation, the editor's ready "
                      "signal, the page's load event for the canvas editors Docen and WordCraft, the painted "
                      "document) up to 1000 s", lax_bounds.relaxed_bounds_paragraph())


if __name__ == "__main__":
    unittest.main()
