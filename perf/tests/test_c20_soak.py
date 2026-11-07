import ast
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from perf.runner.schedule import plan_attempts
from perf.scenarios.catalog import scenarios

REPO = Path(__file__).resolve().parents[2]
SOAK_MODULE = REPO / "perf" / "runner" / "benchmark_c20_soak.py"
NOT_RUN_REASON = (
    "playwright soak probe not implemented; headless round-trip soak is in run_c20_soak_loop.py"
)


class C20SoakHonesty(unittest.TestCase):
    def test_soak_module_does_not_append_sleep_loop_samples(self):
        tree = ast.parse(SOAK_MODULE.read_text(encoding="utf-8"))

        def _names(call: ast.Call) -> list[str]:
            if isinstance(call.func, ast.Attribute):
                base = (
                    call.func.value.id
                    if isinstance(call.func.value, ast.Name)
                    else call.func.value.attr
                )
                return [base, call.func.attr]
            if isinstance(call.func, ast.Name):
                return [call.func.id]
            return []

        offenders: list[str] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.While):
                continue
            has_sleep = False
            has_sample_append = False
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    names = _names(child)
                    if names == ["time", "sleep"]:
                        has_sleep = True
                    if len(names) == 2 and names[0] == "samples" and names[1] == "append":
                        has_sample_append = True
            if has_sleep and has_sample_append:
                offenders.append("while loop records samples during time.sleep")
        self.assertEqual(
            offenders,
            [],
            "benchmark_c20_soak.py must not append timing samples in a sleep-driven loop",
        )

    def test_benchmark_c20_soak_emits_not_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            proc = subprocess.run(
                [
                    sys.executable,
                    str(SOAK_MODULE),
                    "--seconds",
                    "5",
                    "--out-root",
                    str(out),
                ],
                cwd=str(REPO),
                env={**os.environ, "PYTHONPATH": "."},
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["outcome"], "not_run")
            self.assertEqual(summary["failure_reason"], NOT_RUN_REASON)
            attempts = list((out / "attempts").glob("*.json"))
            self.assertEqual(len(attempts), 1)
            trial = json.loads(attempts[0].read_text(encoding="utf-8"))
            self.assertEqual(trial["outcome"], "not_run")
            self.assertEqual(trial["failure_reason"], NOT_RUN_REASON)
            self.assertEqual(trial["samples_ms"], [])


class C20SoakSchedule(unittest.TestCase):
    def test_c20_runs_on_laboratory_dedicated_publish(self):
        c20 = next(r for r in scenarios() if r["id"] == "C20")
        env = {
            "execution_profile": "dedicated_publish",
            "host_class": "laboratory",
            "workload_id": "short-paragraphs",
            "repetition_unit": "fresh_process",
        }
        plan = plan_attempts(c20, env, "plate", "editor")
        self.assertTrue(plan["run"])


if __name__ == "__main__":
    unittest.main()
