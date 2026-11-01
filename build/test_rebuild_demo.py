#!/usr/bin/env python3
"""build/rebuild_demo.sh copies each demo's own files (demos/<slug>/) into the
build tree. A local `pnpm install` in demos/<slug>/ (to update its lockfile)
leaves a node_modules there; copying it over the build tree's own install
links the demo against the wrong packages."""
import re
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "rebuild_demo.sh"


class RsyncFromDemos(unittest.TestCase):
    def test_every_copy_of_a_demo_skips_node_modules(self):
        lines = [l for l in SCRIPT.read_text().splitlines()
                 if re.search(r'rsync .*"\$ROOT/demos/', l)]
        self.assertTrue(lines)
        for l in lines:
            self.assertIn("--exclude node_modules", l, l.strip())


if __name__ == "__main__":
    unittest.main()
