"""s2typing (B9 shakedown): bridge transport, frame interval, early session stop."""

import asyncio
import json
import sys
from pathlib import Path

import pytest

from perf.runner.benchmark_typing import Bridge, classify_bridge_error, read_bridge_line


class ChunkedStdout:
    def __init__(self, payload: bytes):
        self._payload = payload
        self._offset = 0
        self.limit = 2**16

    async def read(self, n):
        if self._offset >= len(self._payload):
            return b""
        chunk = self._payload[self._offset : self._offset + n]
        self._offset += len(chunk)
        return chunk


def test_bridge_read_line_accepts_json_over_64k():
    big = "x" * 70000
    line = (json.dumps({"result": {"text": big}}) + "\n").encode()
    assert len(line) > 2**16
    stdout = ChunkedStdout(line)

    async def check():
        raw = await read_bridge_line(stdout)
        assert json.loads(raw)["result"]["text"] == big

    asyncio.run(check())


def test_classify_bridge_transport_separates_adapter():
    assert classify_bridge_error(RuntimeError("Separator is found, but chunk is longer than limit")) == (
        "witness_bridge_transport",
        "harness_error",
    )
    assert classify_bridge_error(RuntimeError("browser witness bridge exited")) == (
        "witness_bridge_transport",
        "harness_error",
    )
    assert classify_bridge_error(ValueError("dom read failed")) is None


def test_bridge_request_uses_unlimited_reader():
    payload = {"result": {"ok": True, "text": "z" * 70000}}
    line = (json.dumps(payload) + "\n").encode()

    async def run():
        incoming = ChunkedStdout(line)
        outgoing = type("Out", (), {"written": b"", "write": lambda s, v: setattr(s, "written", s.written + v), "drain": staticmethod(lambda: asyncio.sleep(0))})()
        bridge = Bridge(type("P", (), {"stdin": outgoing, "stdout": incoming})())
        got = await bridge.request(op="read_document")
        assert got["text"] == payload["result"]["text"]

    asyncio.run(run())


def test_typing_session_refuses_latency_without_frame_interval(tmp_path):
    """Drive the real bridge against a fixture whose rAF never fires."""
    import asyncio
    import socket

    pytest.importorskip("playwright.async_api")
    from perf.runner.benchmark_typing import Bridge
    from perf.runner.browser_hosts import StaticHost

    host = StaticHost(Path(__file__).parent / "fixtures")

    async def run():
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        process = await asyncio.create_subprocess_exec(
            "node",
            str(Path(__file__).parents[1] / "runner/typing_session.mjs"),
            str(port),
            str(tmp_path / "profile"),
            "latency",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        bridge = Bridge(process)
        try:
            await asyncio.wait_for(process.stdout.readline(), 30)
            load = await bridge.request(
                op="load",
                url=host.url + "/typing_no_raf.html",
                selector="#editor",
                ready_selector=".status-ok",
                editor_id="plate",
            )
            assert load.get("frame_interval_ms") is None
            assert load.get("refusal") == "frame_interval_unavailable"
            key = await bridge.request(op="key", char="a", selector="#editor")
            assert key.get("refusal") == "frame_interval_unavailable"
        finally:
            await bridge.request(op="close")
            process.terminate()
            await asyncio.wait_for(process.wait(), 15)

    try:
        asyncio.run(run())
    finally:
        host.stop()


def test_typing_session_load_witness_on_global_ready_fixture(tmp_path):
    """Load usable_ms must be set when ready is only a window global."""
    import asyncio
    import socket

    pytest.importorskip("playwright.async_api")
    from perf.runner.benchmark_typing import Bridge
    from perf.runner.browser_hosts import StaticHost

    host = StaticHost(Path(__file__).parent / "fixtures")
    usable_js = "window.__TYPING_HOST_READY__ === true"

    async def run():
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        process = await asyncio.create_subprocess_exec(
            "node",
            str(Path(__file__).parents[1] / "runner/typing_session.mjs"),
            str(port),
            str(tmp_path / "profile-global"),
            "latency",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        bridge = Bridge(process)
        try:
            await asyncio.wait_for(process.stdout.readline(), 30)
            load = await bridge.request(
                op="load",
                url=host.url + "/typing_global_ready.html",
                selector="#editor",
                ready_js=usable_js,
                usable_js=usable_js,
                editor_id="canvas",
            )
            assert load.get("refusal") != "no_correctness_adapter"
            assert load.get("usable_ms") is not None
            assert isinstance(load.get("frame_interval_ms"), (int, float))
        finally:
            await bridge.request(op="close")
            process.terminate()
            await asyncio.wait_for(process.wait(), 15)

    try:
        asyncio.run(run())
    finally:
        host.stop()


def test_typing_session_load_witness_on_fair_fixture(tmp_path):
    """Load must publish a frame interval on a host with a working rAF loop."""
    import asyncio
    import socket

    pytest.importorskip("playwright.async_api")
    from perf.runner.benchmark_typing import Bridge
    from perf.runner.browser_hosts import StaticHost

    host = StaticHost(Path(__file__).parent / "fixtures")

    async def run():
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        process = await asyncio.create_subprocess_exec(
            "node",
            str(Path(__file__).parents[1] / "runner/typing_session.mjs"),
            str(port),
            str(tmp_path / "profile2"),
            "latency",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        bridge = Bridge(process)
        try:
            await asyncio.wait_for(process.stdout.readline(), 30)
            load = await bridge.request(
                op="load",
                url=host.url + "/typing_fair.html",
                selector="#editor",
                ready_selector=".status-ok",
                editor_id="plate",
            )
            assert isinstance(load.get("frame_interval_ms"), (int, float))
            assert load.get("usable_ms") is not None
            assert load.get("witness")
        finally:
            await bridge.request(op="close")
            process.terminate()
            await asyncio.wait_for(process.wait(), 15)

    try:
        asyncio.run(run())
    finally:
        host.stop()


def test_typing_stops_when_ten_kept_unreachable(tmp_path):
    not_kept = 3
    from functools import partial
    from perf.runner.browser_run import BrowserRun, CELL, run_cli, write_json

    old = sys.argv
    runs = 0

    def cell():
        nonlocal runs
        rep = CELL.get()["repetition"]
        if rep >= not_kept:
            raise AssertionError("cell should not run")
        runs += 1
        write_json(
            Path(sys.argv[sys.argv.index("--out-root") + 1]) / "attempts/typing.json",
            {
                "criterion_id": "TYPING",
                "session_kind": "throughput",
                "outcome": "refused",
                "correctness_oracle": "dom_document_text",
                "throughput_chars_s": None,
                "failure_reason": "budget_exceeded",
            },
        )
        return 0

    try:
        sys.argv = [
            "test",
            "--out-root",
            str(tmp_path),
            "--run-id",
            "s2-early",
            "--editors",
            "plate",
            "--execution-profile",
            "dedicated_publish",
            "--host-class",
            "dedicated",
            "--session-kind",
            "throughput",
        ]
        run_cli(
            cell,
            "benchmark_typing",
            {"plate": {}},
            run_factory=partial(
                BrowserRun,
                snapshot=lambda: {},
                accounting_reader=lambda: {"available": False, "reason": "synthetic unavailable"},
            ),
            facts=(lambda: {}, lambda: {}),
        )
    finally:
        sys.argv = old

    result = json.loads((tmp_path / "benchmark_typing/s2-early/summary.json").read_text())
    assert runs == not_kept
    assert result["typing_sessions_kept"]["plate"]["throughput"] == 0
    not_run = list((tmp_path / "benchmark_typing/s2-early").glob("cells/*/attempts/typing.json"))
    skipped = [json.loads(p.read_text()) for p in not_run if json.loads(p.read_text()).get("outcome") == "not_run"]
    assert len(skipped) == 12 - not_kept
    assert {row.get("failure_reason") for row in skipped} == {"typing_sessions_unreachable"}
    for row in skipped:
        assert row.get("throughput_chars_s") is None
        assert row.get("load_ms") is None
        assert row.get("key_to_paint") is None
