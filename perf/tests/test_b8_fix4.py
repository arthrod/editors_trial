"""Phase counter deltas are not endpoint levels.

A phase with one sample has no delta. C17 and C19 keep heap, RSS, storage
and profile size, and do not publish those deltas as zero.
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from perf.runner.benchmark_resources import (
    EDIT_BURST,
    QUIESCENCE,
    collect_phases,
)
from perf.runner.resources import NOT_AVAILABLE, phase_totals
from perf.tests.test_b8_fix3 import (
    _BridgeCdp,
    _BridgePage,
    _SessionBox,
    _playwright_ui,
)
from perf.tests.test_resources import (
    MiB,
    ManualClock,
    PhaseSession,
    World,
    make_sampler,
)

COUNTER_DELTAS = (
    "cpu_ms",
    "renderer_cpu_ms",
    "io_read_bytes",
    "io_write_bytes",
    "network_encoded_bytes",
    "network_request_count",
    "longtask_count",
    "longtask_sum_ms",
    "task_duration_ms",
    "script_duration_ms",
    "layout_duration_ms",
    "recalc_style_duration_ms",
)

SINGLE_SAMPLE = {"marker": NOT_AVAILABLE, "reason": "single_sample_phase"}
NOT_APPLICABLE_ENDPOINT = "not_applicable_endpoint"


def _phase_row(cpu):
    return {
        "js_heap_used_bytes": 1000,
        "js_heap_total_bytes": 2000,
        "js_heap_runtime_used_bytes": 900,
        "rss_bytes": 4096,
        "task_duration_ms": 50,
        "script_duration_ms": 40,
        "layout_duration_ms": 10,
        "recalc_style_duration_ms": 5,
        "longtask_count": 2,
        "longtask_sum_ms": 80,
        "network_encoded_bytes": 500,
        "network_request_count": 3,
        "storage_usage_bytes": 7,
        "storage_indexeddb_bytes": 1,
        "storage_cache_bytes": 1,
        "storage_service_worker_bytes": 1,
        "local_storage_bytes": 2,
        "processes": [
            {
                "pid": 11,
                "start_time": 1,
                "role": "renderer",
                "cpu_ms": cpu,
                "io_read_bytes": 9,
                "io_write_bytes": 8,
            }
        ],
    }


def _trial():
    world = World()
    clock = ManualClock(world, disturb=False)
    sampler = make_sampler(world, clock=clock)
    return collect_phases(
        sampler,
        PhaseSession(world, mode="measure"),
        clock,
        quiescence=QUIESCENCE,
        edit_burst=EDIT_BURST,
        editor_id="plate",
        workload_id="prose-500w",
        workload_meta={"sha256": "a" * 64, "byte_size": 10, "paragraph_count": 1, "word_count": 500},
        execution_profile="ci_broad",
        host_class="ci_coarse",
    )


class SingleSamplePhase(unittest.TestCase):
    def test_one_sample_has_no_counter_delta(self):
        """cpu_phase.py: after_edits is one sample, so every counter delta is unavailable."""
        totals = phase_totals([_phase_row(400)])
        self.assertEqual(totals["sample_count"], 1)
        self.assertEqual(totals["js_heap_used_bytes"], 1000)
        self.assertEqual(totals["rss_bytes"], 4096)
        for key in COUNTER_DELTAS:
            self.assertEqual(totals[key], SINGLE_SAMPLE, key)
            self.assertNotEqual(totals[key], 0, key)
            self.assertNotIsInstance(totals[key], int, key)

    def test_two_samples_keep_a_real_zero_and_a_real_burn(self):
        idle = phase_totals([_phase_row(400), _phase_row(400)])
        burned = phase_totals([_phase_row(400), _phase_row(2400)])
        self.assertEqual(idle["cpu_ms"], 0)
        self.assertEqual(idle["renderer_cpu_ms"], 0)
        self.assertEqual(idle["network_encoded_bytes"], 0)
        self.assertEqual(burned["renderer_cpu_ms"], 2000)
        self.assertEqual(burned["cpu_ms"], 2000)


class EndpointCriteria(unittest.TestCase):
    def test_c17_and_c19_do_not_carry_counter_deltas(self):
        """Published CPU is the load / edit / quiescence phase, not the endpoint."""
        trial = _trial()
        self.assertEqual(trial["outcome"], "measured", trial.get("refusal_code"))
        phases = trial["phases"]
        self.assertGreaterEqual(phases["edit_burst"]["renderer_cpu_ms"], 400)
        self.assertGreaterEqual(trial["edit_cpu_ms"], 400)
        self.assertGreaterEqual(trial["edit_renderer_cpu_ms"], 400)
        self.assertIsInstance(trial["load_cpu_ms"], int)
        self.assertIsInstance(trial["quiescence_cpu_ms"], int)
        self.assertEqual(phases["after_edits"]["sample_count"], 1)
        for key in COUNTER_DELTAS:
            self.assertEqual(phases["after_edits"][key], SINGLE_SAMPLE, key)
            self.assertNotEqual(phases["after_edits"][key], 0, key)
        for name in ("C17", "C19"):
            criterion = trial["criteria"][name]
            self.assertIsInstance(criterion["js_heap_used_bytes"], int)
            self.assertIn("rss_bytes", criterion)
            self.assertIn("pss_bytes", criterion)
            self.assertIn("uss_bytes", criterion)
            self.assertIn("storage_usage_bytes", criterion)
            self.assertIn("profile_directory_bytes", criterion)
            for key in COUNTER_DELTAS:
                self.assertEqual(criterion[key], NOT_APPLICABLE_ENDPOINT, "%s %s" % (name, key))
                self.assertNotIsInstance(criterion[key], int, "%s %s" % (name, key))
                self.assertNotEqual(criterion[key], 0, "%s %s" % (name, key))


@unittest.skipUnless(_playwright_ui(), "harness/ui playwright is required for the live session")
class CpuPhaseLive(unittest.TestCase):
    def test_load_and_edit_burn_and_c19_has_no_numeric_cpu(self):
        """cpu_phase.py: load ≈2000 ms renderer CPU, edit_burst ≈1000 ms, C19 CPU is not 0."""
        root = Path(tempfile.mkdtemp())
        try:
            (root / "corpus.docx").write_bytes(b"fake")
            (root / "index.html").write_text(
                '<div id="editor" contenteditable="true">ready</div>'
                "<script>"
                "window.burn = (ms) => { const end = performance.now() + ms;"
                " while (performance.now() < end) {} };"
                "</script>"
            )
            box = _SessionBox(root)
            try:
                bridge, pid = box.launch("one")
                page = _BridgePage(bridge)
                run = SimpleNamespace(
                    editor_browser_pid=pid,
                    static_server_pid=os.getpid(),
                    profile_dir=root / "one",
                    bundle_path=root,
                )
                from perf.runner.resources import ResourceSampler, WallClock

                sampler = ResourceSampler(run, page, _BridgeCdp(bridge), clock=WallClock())

                class Session:
                    has_save = False

                    def load(self):
                        bridge.request("load", timeout=60)
                        page.evaluate("() => window.burn(2000)")

                    def params(self, burst):
                        return {
                            "selector": "#editor",
                            "text": burst["text"],
                            "repetitions": burst["repetitions"],
                            "witness": {"mode": "dom_text"},
                        }

                    def prepare_edit(self, burst):
                        return bridge.request("edit_prepare", self.params(burst), timeout=60)

                    def type_edit(self, burst):
                        page.evaluate("() => window.burn(1000)")
                        return bridge.request("edit_type", self.params(burst), timeout=60)

                    def verify_edit(self, burst, prepared):
                        return bridge.request(
                            "edit_verify",
                            {**self.params(burst), "prepared": prepared},
                            timeout=60,
                        )

                trial = collect_phases(
                    sampler,
                    Session(),
                    sampler.clock,
                    quiescence=QUIESCENCE,
                    edit_burst=EDIT_BURST,
                    editor_id="fake",
                    workload_id="prose-500w",
                    workload_meta={},
                    execution_profile="ci_broad",
                    host_class="ci_coarse",
                )
                load_cpu = trial["phases"]["load"]["renderer_cpu_ms"]
                edit_cpu = trial["phases"]["edit_burst"]["renderer_cpu_ms"]
                self.assertEqual(trial["outcome"], "measured", trial.get("refusal_code"))
                self.assertIsInstance(load_cpu, int)
                self.assertGreaterEqual(load_cpu, 1500)
                self.assertLess(load_cpu, 4000)
                self.assertIsInstance(edit_cpu, int)
                self.assertGreaterEqual(edit_cpu, 700)
                self.assertLess(edit_cpu, 2500)
                self.assertGreaterEqual(trial["load_renderer_cpu_ms"], 1500)
                self.assertGreaterEqual(trial["edit_renderer_cpu_ms"], 700)
                c19 = trial["criteria"]["C19"]
                for key in ("cpu_ms", "renderer_cpu_ms"):
                    self.assertEqual(c19[key], NOT_APPLICABLE_ENDPOINT, key)
                    self.assertNotIsInstance(c19[key], int, key)
                    self.assertNotEqual(c19[key], 0, key)
            finally:
                box.close()
        finally:
            shutil.rmtree(root, ignore_errors=True)


@unittest.skipUnless(_playwright_ui(), "harness/ui playwright is required for the live session")
class WorkerTargetLive(unittest.TestCase):
    def test_dedicated_worker_fetch_of_one_mib_is_counted(self):
        """A dedicated Worker fetches a local file and posts the length back."""
        root = Path(tempfile.mkdtemp())
        try:
            (root / "corpus.docx").write_bytes(b"fake")
            (root / "blob.bin").write_bytes(b"\2" * MiB)
            (root / "dedicated-worker.js").write_text(
                "self.onmessage = () => {"
                " fetch('/blob.bin').then((response) => response.arrayBuffer())"
                " .then((body) => postMessage(body.byteLength))"
                " .catch((error) => postMessage({ error: String(error) }));"
                "};"
                "postMessage({ ready: true });"
            )
            (root / "index.html").write_text('<div id="editor" contenteditable="true">ready</div>')
            box = _SessionBox(root)
            try:
                bridge, pid = box.launch("one")
                bridge.request("load", timeout=60)
                page = _BridgePage(bridge)
                run = SimpleNamespace(
                    editor_browser_pid=pid,
                    static_server_pid=os.getpid(),
                    profile_dir=root / "one",
                    bundle_path=root,
                )
                from perf.runner.resources import ResourceSampler, WallClock

                sampler = ResourceSampler(run, page, _BridgeCdp(bridge), clock=WallClock())
                sampler.mark("dedicated_worker")
                result = page.evaluate(
                    "() => new Promise((resolve) => {"
                    " const timer = setTimeout(() => resolve({ error: 'timeout' }), 8000);"
                    " const worker = new Worker('/dedicated-worker.js');"
                    " let started = false;"
                    " worker.onmessage = (event) => {"
                    "  if (!started && event.data && event.data.ready) {"
                    "   started = true;"
                    "   setTimeout(() => worker.postMessage('go'), 300);"
                    "   return;"
                    "  }"
                    "  clearTimeout(timer);"
                    "  resolve(event.data);"
                    " };"
                    " worker.onerror = (event) => {"
                    "  clearTimeout(timer);"
                    "  resolve({ error: String(event.message || 'worker error') });"
                    " };"
                    "})"
                )
                after = sampler.sample()
                delta = sampler.totals("dedicated_worker")["network_encoded_bytes"]
                self.assertEqual(result, MiB, result)
                self.assertEqual(after["network_observation"], "ok", after.get("network_observation_reason"))
                self.assertIsInstance(delta, int)
                self.assertGreaterEqual(delta, MiB)
                self.assertLess(delta, MiB + 256 * 1024)
            finally:
                box.close()
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_shared_worker_fetch_of_one_mib_is_counted(self):
        """A SharedWorker fetch of a local file is counted on its own target."""
        root = Path(tempfile.mkdtemp())
        try:
            (root / "corpus.docx").write_bytes(b"fake")
            (root / "blob.bin").write_bytes(b"\3" * MiB)
            (root / "shared-worker.js").write_text(
                "onconnect = (event) => {"
                " const port = event.ports[0];"
                " port.onmessage = () => {"
                "  fetch('/blob.bin').then((response) => response.arrayBuffer())"
                "  .then((body) => port.postMessage(body.byteLength))"
                "  .catch((error) => port.postMessage({ error: String(error) }));"
                " };"
                " port.postMessage({ ready: true });"
                "};"
            )
            (root / "index.html").write_text('<div id="editor" contenteditable="true">ready</div>')
            box = _SessionBox(root)
            try:
                bridge, pid = box.launch("one")
                bridge.request("load", timeout=60)
                page = _BridgePage(bridge)
                run = SimpleNamespace(
                    editor_browser_pid=pid,
                    static_server_pid=os.getpid(),
                    profile_dir=root / "one",
                    bundle_path=root,
                )
                from perf.runner.resources import ResourceSampler, WallClock

                sampler = ResourceSampler(run, page, _BridgeCdp(bridge), clock=WallClock())
                sampler.mark("shared_worker")
                result = page.evaluate(
                    "() => new Promise((resolve) => {"
                    " const timer = setTimeout(() => resolve({ error: 'timeout' }), 8000);"
                    " const worker = new SharedWorker('/shared-worker.js');"
                    " let started = false;"
                    " worker.port.onmessage = (event) => {"
                    "  if (!started && event.data && event.data.ready) {"
                    "   started = true;"
                    "   setTimeout(() => worker.port.postMessage('go'), 400);"
                    "   return;"
                    "  }"
                    "  clearTimeout(timer);"
                    "  resolve(event.data);"
                    " };"
                    " worker.port.start();"
                    "})"
                )
                after = sampler.sample()
                delta = sampler.totals("shared_worker")["network_encoded_bytes"]
                self.assertEqual(result, MiB, result)
                self.assertEqual(after["network_observation"], "ok", after.get("network_observation_reason"))
                self.assertIsInstance(delta, int)
                self.assertGreaterEqual(delta, MiB)
                self.assertLess(delta, MiB + 256 * 1024)
            finally:
                box.close()
        finally:
            shutil.rmtree(root, ignore_errors=True)
