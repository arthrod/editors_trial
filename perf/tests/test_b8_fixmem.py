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
from perf.tests.test_memory_criteria import PS_TABLE, _workload_row


class _StaticHostLike:
    """Mirrors StaticHost: serves in-thread, no child server pid."""

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
    (tmp_path / "fixture.docx").write_bytes(b"docx")
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
    )
    captured = {}

    def run_pair(**kwargs):
        captured["server_pid"] = kwargs.get("server_pid")
        return _synthetic_pair()

    with mock.patch.object(memory, "_start_server", return_value=_StaticHostLike()):
        with mock.patch.object(memory, "_stop_server", return_value=None):
            with mock.patch.object(memory, "_run_browser_pair", side_effect=run_pair):
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
    assert captured["server_pid"] is None
    outcomes = [(r["criterion_id"], r["measurement_phase"], r["outcome"]) for r in rows]
    assert ("C17", "ready", "measured") in outcomes
    assert ("C19", None, "measured") in outcomes
    trial = json.loads(next(attempt_dir.glob("c17-ready-*.json")).read_text())
    host = trial["diagnostic"]["memory_host"]
    assert host["counted_in_rss"] is False
    assert host["host_server_pid"] is None
    assert STATIC_SERVER_NOTE in host["static_host_note"]
