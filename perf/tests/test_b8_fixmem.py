"""B8 memory lane: static production hosts have no server pid to sample."""

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from perf.runner import benchmark_memory as memory
from perf.runner.memory_tree import sample_process_tree
from perf.runner.resources import STATIC_SERVER_NOTE
from perf.tests.test_memory_criteria import PS_TABLE, _workload_row, gate_fixture_docx


class _StaticHostLike:
    """Mirrors StaticHost: serves in-thread, no child server pid."""

    def stop(self):
        pass


class _LegacyHostLike:
    """Mirrors wordcraft legacy_start: node static server with a child pid."""

    pid = 4242

    def stop(self):
        pass


def _synthetic_pair():
    ps = lambda: PS_TABLE
    ready = sample_process_tree(101, ps_reader=ps, platform_name="darwin")
    edited = dict(ready, rss_bytes=ready["rss_bytes"] + 10 * 1024)
    quiescent = dict(ready, rss_bytes=ready["rss_bytes"] + 12 * 1024)
    reopened = dict(ready, rss_bytes=ready["rss_bytes"] + 40 * 1024)
    retention = [
        {"after_close_ms": 1000.0, "rss_bytes": 600 * 1024, "process_count": 2, "pids": [101, 102]},
        {"after_close_ms": 5000.0, "rss_bytes": 600 * 1024, "process_count": 2, "pids": [101, 102]},
    ]
    return {
        "index": 0,
        "roots": [200],
        "ready": {"sample": ready, "probe": {"ready_ms": 10}},
        "edited": {
            "sample": edited,
            "probe": {
                "edit_effective": True,
                "text_length_before": 10,
                "text_length_after": 20,
                "typed_chars": 120,
                "edit_error": None,
            },
        },
        "quiescent": {"sample": quiescent, "probe": {"idle_ms": 2000}},
        "closed": {"probe": {"context_closed": True}, "retention": retention},
        "reopened": {"sample": reopened, "probe": {"reopen_ready_ms": 30, "reopen_error": None}},
        "result": {"ready_ms": 10},
        "retention": retention,
    }


@pytest.fixture
def attempt_dir(tmp_path):
    attempt_dir = tmp_path / "attempts"
    attempt_dir.mkdir()
    (tmp_path / "fixture.docx").write_bytes(gate_fixture_docx())
    return tmp_path, attempt_dir


def test_host_memory_root_static_host_is_none():
    assert memory._host_memory_root(_StaticHostLike()) is None
    assert memory._host_memory_root(SimpleNamespace(pid=101)) == 101


def test_browser_rows_static_host_measures_without_server_pid(attempt_dir):
    tmp_path, attempt_dir = attempt_dir
    args = SimpleNamespace(
        execution_profile="ci_contract",
        pairs=1,
        burst=12,
        quiescence_ms=2000,
        retain_seconds=(1.0, 5.0),
        probe_timeout=30.0,
        # lax layer (owner 2026-11-11): _run_browser_pair takes the workload
        # for its load-timeout env.
        workload="micro-paragraphs",
    )
    with mock.patch.object(memory, "_start_server", return_value=_StaticHostLike()):
        with mock.patch.object(memory, "_stop_server", return_value=None):
            with mock.patch.object(memory, "_run_browser_pair", return_value=_synthetic_pair()):
                with mock.patch.object(memory, "_port_is_free", return_value=True):
                    rows = memory._browser_rows(
                        editor_id="plate",
                        lane="browser_slate",
                        target={"url": "http://127.0.0.1:5299/", "corpus_route": "/corpus.docx"},
                        attempt_dir=attempt_dir,
                        args=args,
                        fixture_path=tmp_path / "fixture.docx",
                        fixture_sha="a" * 64,
                        docx_size=4096,
                        workload_row=_workload_row(),
                    )
    outcomes = [(r["criterion_id"], r["measurement_phase"], r["outcome"]) for r in rows]
    assert ("C17", "ready", "measured") in outcomes
    assert ("C19", None, "measured") in outcomes
    trial = json.loads(next(attempt_dir.glob("c17-ready-*.json")).read_text())
    host = trial["diagnostic"]["memory_host"]
    assert host["host_server_counted_in_rss"] is False
    assert host["host_server_pid_first_pair"] is None
    assert STATIC_SERVER_NOTE in host["static_host_note"]
    # The row measured memory only after reading this fixture's gate.
    assert trial["diagnostic"]["content_length_check"] == "coarse"
    assert "tracked revisions" in trial["diagnostic"]["content_length_check_reason"]


def test_memory_host_diagnostic_legacy_host_pid_not_counted():
    host = memory._memory_host_diagnostic(_LegacyHostLike())
    assert host["memory_roots"] == "editor_browser_tree_only"
    assert host["host_server_pid_first_pair"] == 4242
    assert host["host_server_counted_in_rss"] is False
    assert STATIC_SERVER_NOTE in host["static_host_note"]


PROBE_BROWSER_TABLE = """\
  500     1  100000
  501   500  200000
  502   501  300000
"""


def test_chromium_tree_sample_excludes_node_probe_driver():
    """Sampling at the launched browser must not count the node probe parent."""
    sample = sample_process_tree(501, ps_reader=lambda: PROBE_BROWSER_TABLE, platform_name="darwin")
    assert 500 not in sample["pids"]
    assert sample["pids"] == [501, 502]


def test_run_browser_pair_roots_are_launched_browser_not_probe(tmp_path):
    fake_proc = mock.MagicMock()
    fake_proc.pid = 501
    fake_proc.stdin = mock.MagicMock()
    fake_proc.stdin.closed = False
    fake_proc.returncode = 0
    fixture = tmp_path / "fixture.docx"
    fixture.write_bytes(b"docx")
    phase_ready = 'PHASE ready {"ready_ms": 10, "browser_pid": 601}'
    lines = iter([phase_ready, "RESULT {}"])

    def read_line(proc, deadline):
        return next(lines)

    with mock.patch.object(memory.subprocess, "Popen", return_value=fake_proc):
        with mock.patch.object(memory, "_read_probe_line", side_effect=read_line):
            with mock.patch.object(memory, "_stop_process_group"):
                with mock.patch.object(memory, "_sample_roots") as sample_roots:
                    sample_roots.return_value = {
                        "rss_bytes": 1,
                        "process_count": 1,
                        "pids": [601],
                        "method": "ps_rss_sum",
                        "platform": "darwin",
                        "ps_command": "ps",
                        "roots": [601],
                    }
                    record = memory._run_browser_pair(
                    target={"url": "http://127.0.0.1:1/", "corpus_route": "/x"},
                    corpus_path=fixture,
                    burst=0,
                    quiescence_ms=0,
                    retain_seconds=[],
                    probe_timeout_s=5.0,
                )
    assert record["roots"] == [601]
    assert 501 not in record["roots"]
    sample_roots.assert_called()
    assert sample_roots.call_args[0][0] == [601]


def test_browser_rows_legacy_host_does_not_sample_server_pid(attempt_dir):
    tmp_path, attempt_dir = attempt_dir
    args = SimpleNamespace(
        execution_profile="ci_contract",
        pairs=1,
        burst=12,
        quiescence_ms=2000,
        retain_seconds=(1.0, 5.0),
        probe_timeout=30.0,
    )
    with mock.patch.object(memory, "_start_server", return_value=_LegacyHostLike()):
        with mock.patch.object(memory, "_stop_server", return_value=None):
            with mock.patch.object(memory, "_run_browser_pair", return_value=_synthetic_pair()):
                with mock.patch.object(memory, "_port_is_free", return_value=True):
                    memory._browser_rows(
                        editor_id="wordcraft",
                        lane="browser_wordcraft",
                        target={"url": "http://127.0.0.1:5299/", "corpus_route": "/corpus.docx"},
                        attempt_dir=attempt_dir,
                        args=args,
                        fixture_path=tmp_path / "fixture.docx",
                        fixture_sha="a" * 64,
                        docx_size=4096,
                        workload_row=_workload_row(),
                    )
    trial = json.loads(next(attempt_dir.glob("c17-ready-*.json")).read_text())
    host = trial["diagnostic"]["memory_host"]
    assert host["host_server_pid_first_pair"] == 4242
    assert host["host_server_counted_in_rss"] is False
    # Wordcraft runs no length gate. The coarse reason still proves the fixture was opened.
    assert trial["diagnostic"]["content_length_check"] == "not_run"
    assert "tracked revisions" in trial["diagnostic"]["content_length_check_reason"]
