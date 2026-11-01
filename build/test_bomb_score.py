"""The safety label the bomb scorer gives a run from its exit status."""
import signal
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bomb_score  # noqa: E402


class SafetyTest(unittest.TestCase):
    def test_wall_timeout_is_a_hang(self):
        self.assertEqual(bomb_score.safety(1, True, False), "hang")

    def test_cpu_limit_kill_is_a_hang_not_a_crash(self):
        # RLIMIT_CPU ends the run with SIGXCPU: the sandbox's budget ran out
        # before the editor finished. That is the run not finishing, as a
        # wall-clock timeout is, not the editor dying on its own.
        self.assertEqual(bomb_score.safety(-signal.SIGXCPU, False, False), "hang")
        self.assertEqual(bomb_score.safety(128 + signal.SIGXCPU, False, False), "hang")

    def test_other_signals_are_crashes(self):
        self.assertEqual(bomb_score.safety(-signal.SIGSEGV, False, False), "crash")
        self.assertEqual(bomb_score.safety(-signal.SIGKILL, False, False), "crash")

    def test_clean_and_rejecting_runs(self):
        self.assertEqual(bomb_score.safety(0, False, False), "ok")
        self.assertEqual(bomb_score.safety(1, False, False), "bounded-reject")


if __name__ == "__main__":
    unittest.main()
