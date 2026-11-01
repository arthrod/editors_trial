#!/usr/bin/env python3
"""The "Release" issue template carries RELEASING.md's checklist, word for word."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ReleaseTemplate(unittest.TestCase):
    def test_issue_template_body_is_releasing_md(self):
        template = (ROOT / ".github/ISSUE_TEMPLATE/release.md").read_text()
        self.assertTrue(template.startswith("---\n"), "the template needs GitHub's front matter")
        body = template.split("\n---\n", 1)[1].lstrip("\n")
        self.assertEqual(body, (ROOT / "RELEASING.md").read_text())


if __name__ == "__main__":
    unittest.main()
