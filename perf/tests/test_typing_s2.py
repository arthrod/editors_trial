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


def test_typing_session_refuses_key_without_frame_interval():
    source = (Path(__file__).parents[1] / "runner/typing_session.mjs").read_text()
    key = source[source.index("command.op === 'key'") : source.index("command.op === 'enter_edit_mode'")]
    assert "frame_interval_unavailable" in key
    assert "interval?.median_ms" in key or "typeof interval?.median_ms" in key or "interval &&" in key


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
