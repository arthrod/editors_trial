import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


class LoadUnloadFixtures(unittest.TestCase):
    def test_generated_dir_gitkeep_or_manifest(self):
        gen = REPO / "perf/fixtures/generated"
        self.assertTrue(gen.exists() or (REPO / "perf/runner/benchmark_load_unload.py").is_file())


if __name__ == "__main__":
    unittest.main()
