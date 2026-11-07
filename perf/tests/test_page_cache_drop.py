import unittest
from unittest.mock import patch

from perf.runner.benchmark_full_browser import drop_page_cache
from pathlib import Path


class PageCacheDrop(unittest.TestCase):
    def test_runner_records_drop_failure_without_page_cache_dropped(self):
        with patch("perf.runner.benchmark_full_browser.subprocess.run") as run:
            run.return_value.returncode = 1
            run.return_value.stderr = "sudo: a password is required"
            meta = drop_page_cache(Path("/tmp"))
        self.assertFalse(meta["page_cache_dropped"])
        self.assertIn("drop_caches", meta["cache_drop_command"])


if __name__ == "__main__":
    unittest.main()
