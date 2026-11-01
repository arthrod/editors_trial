"""The release rule: newest version at least COOLDOWN days old, never older than the current pin."""
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pin_versions as P  # noqa: E402


def _git(repo, *args, when=None):
    env = dict(os.environ)
    if when:
        env.update(GIT_AUTHOR_DATE=when, GIT_COMMITTER_DATE=when)
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True,
                          text=True, env=env).stdout.strip()


class CutoffTest(unittest.TestCase):
    def test_cutoff_is_five_days_before_release(self):
        self.assertEqual(P.cutoff(date(2026, 11, 1)), date(2026, 10, 27))


class GitPinTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        _git(self.repo, "init", "-q", "-b", "main")
        _git(self.repo, "config", "user.email", "t@t")
        _git(self.repo, "config", "user.name", "t")
        self.commits = {}
        for day in ("2026-10-20", "2026-10-25", "2026-10-27", "2026-10-30"):
            (self.repo / "f").write_text(day)
            _git(self.repo, "add", "f")
            _git(self.repo, "commit", "-q", "-m", day, when=f"{day}T12:00:00")
            self.commits[day] = _git(self.repo, "rev-parse", "HEAD")

    def tearDown(self):
        self.tmp.cleanup()

    def test_newest_commit_on_or_before_the_cutoff(self):
        got = P.git_pin(self.repo, "main", date(2026, 10, 27), current=self.commits["2026-10-20"])
        self.assertEqual(got, self.commits["2026-10-27"])

    def test_never_goes_back_behind_the_current_pin(self):
        got = P.git_pin(self.repo, "main", date(2026, 10, 27), current=self.commits["2026-10-30"])
        self.assertEqual(got, self.commits["2026-10-30"])

    def test_no_current_pin(self):
        got = P.git_pin(self.repo, "main", date(2026, 10, 26), current=None)
        self.assertEqual(got, self.commits["2026-10-25"])


class NpmPinTest(unittest.TestCase):
    TIMES = {
        "created": "2026-01-01T00:00:00.000Z",
        "modified": "2026-11-01T00:00:00.000Z",
        "2.25.0-next.14": "2026-10-20T10:00:00.000Z",
        "2.26.0-next.3": "2026-10-26T10:00:00.000Z",
        "2.26.0-next.9": "2026-10-27T23:00:00.000Z",
        "2.26.0-next.16": "2026-10-31T10:00:00.000Z",
        "2.25.0": "2026-10-25T10:00:00.000Z",
        "2.26.0": "2026-10-31T09:00:00.000Z",
    }

    def test_next_channel_newest_before_cutoff(self):
        self.assertEqual(P.npm_pin(self.TIMES, date(2026, 10, 27), "next", current="2.25.0-next.14"),
                         "2.26.0-next.9")

    def test_latest_channel_ignores_prereleases(self):
        self.assertEqual(P.npm_pin(self.TIMES, date(2026, 10, 27), "latest", current=None), "2.25.0")

    def test_never_goes_back_behind_the_current_pin(self):
        self.assertEqual(P.npm_pin(self.TIMES, date(2026, 10, 27), "next", current="2.26.0-next.16"),
                         "2.26.0-next.16")


if __name__ == "__main__":
    unittest.main()
