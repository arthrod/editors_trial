"""The test commands the docs give must collect the pytest-style tests.

perf/tests and build hold pytest functions as well as unittest classes;
`python3 -m unittest discover` silently skips the functions, so a reader who
follows the docs would never run them (CodeRabbit on #287).
"""

import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCS = [
    "README.md",
    "perf/README.md",
    "RELEASING.md",
    ".github/ISSUE_TEMPLATE/release.md",
    "perf/runner/benchmark_warm_cold.py",
]


def test_no_doc_tells_the_reader_to_run_the_suites_with_unittest_discover():
    """Every documented suite command runs pytest, which collects both styles."""
    offenders = [
        f"{doc}:{n}"
        for doc in DOCS
        for n, line in enumerate((ROOT / doc).read_text().splitlines(), 1)
        if "unittest discover" in line
    ]
    assert offenders == []


def test_the_documented_commands_name_pytest_for_both_suites():
    """The perf and build suites each have a pytest command somewhere in the docs."""
    text = "\n".join((ROOT / doc).read_text() for doc in DOCS)
    assert "python -m pytest -q perf/tests" in text
    assert "python -m pytest -q build" in text
