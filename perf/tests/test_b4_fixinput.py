"""B4 input lane: expected body must not ride MAX_ARG_STRLEN via the probe env."""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from perf.fixtures.profiles import size_ladder  # noqa: E402
from perf.runner.benchmark_warm_cold import BROWSER_TARGETS  # noqa: E402
from perf.runner.benchmark_input import (  # noqa: E402
    _probe_command,
    _probe_env,
    _fixture,
)
from perf.runner.docx_plaintext import docx_body_text  # noqa: E402

# Linux execve(2): ARG_MAX counts the whole vector, but each argv/env *string*
# is capped separately at MAX_ARG_STRLEN (128 KiB on typical HF kernels).
MAX_ARG_STRLEN = 128 * 1024


def _max_exec_string_bytes(cmd: list[str], env: dict[str, str]) -> int:
    lengths = [len(part.encode("utf-8")) for part in cmd]
    lengths += [len(f"{key}={value}".encode("utf-8")) for key, value in env.items()]
    return max(lengths) if lengths else 0


class ProbeLaunchStrings(unittest.TestCase):
    def test_probe_argv_and_env_strings_under_max_arg_strlen_for_ladder(self):
        workloads = [row["workload_id"] for row in size_ladder()]
        offenders: list[str] = []
        for workload_id in workloads:
            fixture, _sha, _size, _row = _fixture("plate", workload_id)
            for editor_id in BROWSER_TARGETS:
                target = dict(BROWSER_TARGETS[editor_id])
                cmd = _probe_command(editor_id, target, fixture)
                env = _probe_env(editor_id, target, fixture, workload_id=workload_id)
                for idx, part in enumerate(cmd):
                    n = len(part.encode("utf-8"))
                    if n >= MAX_ARG_STRLEN:
                        offenders.append(
                            f"argv[{idx}] editor={editor_id} workload={workload_id} len={n}"
                        )
                for key, value in env.items():
                    n = len(value.encode("utf-8"))
                    if n >= MAX_ARG_STRLEN:
                        offenders.append(
                            f"env[{key}] editor={editor_id} workload={workload_id} len={n}"
                        )
                self.assertNotIn(
                    "PERF_EXPECTED_BODY_B64",
                    env,
                    msg=f"{editor_id}/{workload_id} must not pass expected body on env",
                )
        self.assertEqual(offenders, [])

    def test_large_prose_expected_body_via_path_not_inline(self):
        for workload_id in ("prose-50kw", "prose-250kw"):
            fixture, _sha, size, _row = _fixture("superdoc", workload_id)
            self.assertGreaterEqual(size, 144_000 if workload_id == "prose-50kw" else 700_000)
            env = _probe_env("superdoc", dict(BROWSER_TARGETS["superdoc"]), fixture, workload_id=workload_id)
            path = env.get("PERF_EXPECTED_BODY_PATH")
            self.assertIsNotNone(path)
            body_path = Path(path)
            self.assertTrue(body_path.is_file())
            self.assertEqual(body_path.read_text(encoding="utf-8"), docx_body_text(fixture))
            self.assertLess(_max_exec_string_bytes([], env), MAX_ARG_STRLEN)


class ProbeNodeStarts(unittest.TestCase):
    """Node must launch with prose fixtures; editor outcome may still fail."""

    def test_node_accepts_probe_env_for_prose_50kw(self):
        fixture, _sha, _size, _row = _fixture("plate", "prose-50kw")
        env = {**os.environ, **_probe_env("plate", dict(BROWSER_TARGETS["plate"]), fixture, workload_id="prose-50kw")}
        cmd = [
            "node",
            "-e",
            "const fs=require('fs');"
            "const p=process.env.PERF_EXPECTED_BODY_PATH;"
            "if(!p||!fs.existsSync(p)) process.exit(2);"
            "if(fs.statSync(p).size<100000) process.exit(3);"
            "process.exit(0);",
        ]
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr)


if __name__ == "__main__":
    unittest.main()
