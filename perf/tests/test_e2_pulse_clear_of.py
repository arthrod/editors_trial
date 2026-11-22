"""The edit's frame pulse keeps clear of react-docx's pages, and of nothing else new.

On Linux the screencast delivers frames only when the page changes, so the warm/cold
edit starts a small blinking pulse in a window corner outside the document. react-docx's
edit selector is its root, which fills the window: no corner was free, no pulse ran,
and C05/C06 refused witness_sparse on the e2-publish shakedown (2026-11-22, median frame
interval 383 ms). PULSE_CLEAR_OF names, per editor, the elements the pulse must avoid
instead of the edit selector's first match. It must never name a published editor, whose
figures were taken with the edit selector's box.
"""
import re
import unittest
from pathlib import Path

from perf.container.policy import E2_CAMPAIGN_EDITORS, LATER_CAMPAIGN_EDITORS

SOURCE = Path(__file__).resolve().parents[1] / "runner" / "warm_cold_browser.mjs"


def pulse_clear_of():
    text = SOURCE.read_text()
    found = re.search(r"const PULSE_CLEAR_OF = Object\.freeze\(\{(.*?)\}\);", text, re.S)
    if not found:
        return None
    return dict(re.findall(r"(\w+):\s*'([^']+)'", found.group(1)))


class PulseClearOf(unittest.TestCase):
    def test_react_docx_pulse_avoids_its_pages(self):
        self.assertEqual(pulse_clear_of(), {"reactdocx": "[data-docx-page-wrapper]"})

    def test_no_published_editor_is_named(self):
        names = set(pulse_clear_of() or {})
        self.assertFalse(names & set(E2_CAMPAIGN_EDITORS))
        self.assertTrue(names <= set(LATER_CAMPAIGN_EDITORS))

    def test_the_pulse_reads_the_gate_and_checks_every_avoided_box(self):
        text = SOURCE.read_text()
        self.assertIn("[selector, PULSE_CLEAR_OF[editorId] || null]", text)
        self.assertIn("boxes.every(box =>", text)
        # Without a gate the pulse avoids the edit selector's first match, as before.
        self.assertIn("(documentElement ? [documentElement] : [])", text)


if __name__ == "__main__":
    unittest.main()
