"""Report A's namespace tables are generated from out/ns_map.json, byte for byte."""
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ns_tables  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
REPORT = "reports/Report A - Serialization by Namespace (2026).md"


def published() -> str:
    # The v0.9.1 report: the tables were last laid out by hand there.
    return subprocess.run(["git", "-C", str(ROOT), "show", f"v0.9.1:{REPORT}"],
                          capture_output=True, text=True, check=True).stdout


class V091Columns:
    """The generator, restricted to v0.9.1's columns (Apryse joined in v0.9.2), reproduces v0.9.1's tables."""
    def __enter__(self):
        self.saved = ns_tables.EDITORS
        ns_tables.EDITORS = [e for e in self.saved if e != "apryse"]

    def __exit__(self, *exc):
        ns_tables.EDITORS = self.saved


class ReportTablesTest(unittest.TestCase):
    def run(self, result=None):
        with V091Columns():
            return super().run(result)

    def test_each_group_matrix_matches_the_report(self):
        data, text = ns_tables.load(), published()
        for i in range(len(ns_tables.GROUPS)):
            table = ns_tables.report_matrix(data, i)
            self.assertIn(table, text, ns_tables.GROUPS[i][0])

    def test_partial_table_matches_the_report(self):
        # Two rows of the published table were shortened by hand to
        # "`accent1` … `themeElements` … (+41 more)", which miscounts (49 names
        # are lost). Generated, they list the first eight and "+41 more".
        hand = {"| `a` | Fidus | 11/60 | `accent1` … `themeElements` … (+41 more) |",
                "| `a` | canvas | 11/60 | `accent1` … `themeElements` … (+41 more) |"}
        text = "\n".join(l for l in published().splitlines() if l not in hand)
        gen = "\n".join(l for l in ns_tables.partial(ns_tables.load()).splitlines()
                        if not l.startswith(("| `a` | Fidus | 11/60 |", "| `a` | canvas | 11/60 |")))
        self.assertIn(gen, text)


class CurrentReportTest(unittest.TestCase):
    def test_the_rendered_report_carries_the_generated_tables_with_apryse(self):
        text = (ROOT / REPORT).read_text()
        data = ns_tables.load()
        self.assertIn("apryse", ns_tables.EDITORS)
        for i in range(len(ns_tables.GROUPS)):
            self.assertIn(ns_tables.report_matrix(data, i), text)
        self.assertIn(ns_tables.partial(data), text)


if __name__ == "__main__":
    unittest.main()
