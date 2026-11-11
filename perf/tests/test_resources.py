"""Resource sampler and the publishable browser resource lane.

A fake page is the measurer: the sampler must report what that page did,
in byte and millisecond fields, and the lane must refuse a series that
did not actually move or a quiescence condition that never held.
"""

import json
import tempfile
import unittest
from pathlib import Path

from perf.runner.benchmark_resources import (
    EDIT_BURST,
    QUIESCENCE,
    REFUSAL_CODES,
    RESOURCE_WORKLOADS,
    collect_phases,
    measure_editor,
    publication_verdict,
)
from perf.runner.resources import (
    NOT_AVAILABLE,
    ResourceSampler,
    parse_cgroup_text,
    parse_linux_process,
    parse_ps_resource_table,
    parse_ps_time,
    role_of,
)

MiB = 1024 * 1024


class World:
    def __init__(self):
        self.heap_used = 8 * MiB
        self.heap_total = 16 * MiB
        self.runtime_used = 8 * MiB
        self.runtime_total = 16 * MiB
        self.task_s = 0.0
        self.script_s = 0.0
        self.layout_s = 0.0
        self.style_s = 0.0
        self.storage_usage = 0
        self.indexeddb = 0
        self.caches = 0
        self.service_workers = 0
        self.local_storage_bytes = 0
        self.longtask_count = 0
        self.longtask_sum_ms = 0
        self.network = []
        self.processes = [
            _proc(10, 1, "chrome", rss=40 * MiB, cpu_ms=10),
            _proc(11, 10, "chrome --type=renderer", rss=80 * MiB, cpu_ms=20),
            _proc(12, 10, "chrome --type=gpu-process", rss=30 * MiB, cpu_ms=5),
            _proc(50, 1, "chrome --type=renderer", rss=90 * MiB, cpu_ms=99),
            _proc(99, 1, "node vite", rss=15 * MiB, cpu_ms=3),
        ]

    def allocate(self, nbytes):
        self.heap_used += nbytes
        self.heap_total += nbytes
        self.runtime_used += nbytes
        self.runtime_total += nbytes

    def burn_renderer_cpu_ms(self, cpu_ms):
        for row in self.processes:
            if row["pid"] == 11:
                row["cpu_ms"] += cpu_ms

    def write_indexeddb(self, nbytes):
        self.indexeddb += nbytes
        self.storage_usage += nbytes

    def download(self, nbytes):
        self.network.append(nbytes)

    def set_heap(self, nbytes):
        self.heap_used = nbytes
        self.heap_total = nbytes + MiB
        self.runtime_used = nbytes
        self.runtime_total = nbytes + MiB


def _proc(pid, ppid, cmdline, *, rss, cpu_ms):
    return {
        "pid": pid,
        "ppid": ppid,
        "cmdline": cmdline,
        "rss_bytes": rss,
        "cpu_ms": cpu_ms,
        "pss_bytes": 1,
        "uss_bytes": 1,
        "io_read_bytes": 1,
        "io_write_bytes": 1,
    }


class FakePage:
    def __init__(self, world):
        self.world = world

    def evaluate(self, expression):
        if "navigator.storage" not in expression or "longtask" not in expression:
            raise AssertionError("snapshot script is not the resource probe")
        return {
            "usage": self.world.storage_usage,
            "usageDetails": {
                "indexedDB": self.world.indexeddb,
                "caches": self.world.caches,
                "serviceWorkerRegistrations": self.world.service_workers,
            },
            "localStorageBytes": self.world.local_storage_bytes,
            "longtaskCount": self.world.longtask_count,
            "longtaskSumMs": self.world.longtask_sum_ms,
        }


class ProbeCostPage(FakePage):
    """A page whose full resource probe costs renderer CPU."""

    def evaluate(self, expression):
        self.world.burn_renderer_cpu_ms(500)
        return super().evaluate(expression)


class FakeCdp:
    def __init__(self, world):
        self.world = world

    def send(self, method, params=None):
        if method in ("Performance.enable", "Network.enable"):
            return {}
        if method == "Performance.getMetrics":
            return {
                "metrics": [
                    {"name": "JSHeapUsedSize", "value": self.world.heap_used},
                    {"name": "JSHeapTotalSize", "value": self.world.heap_total},
                    {"name": "TaskDuration", "value": self.world.task_s},
                    {"name": "ScriptDuration", "value": self.world.script_s},
                    {"name": "LayoutDuration", "value": self.world.layout_s},
                    {"name": "RecalcStyleDuration", "value": self.world.style_s},
                ]
            }
        if method == "Runtime.getHeapUsage":
            return {"usedSize": self.world.runtime_used, "totalSize": self.world.runtime_total}
        raise AssertionError(method)

    def events(self, method):
        if method != "Network.loadingFinished":
            return []
        return [
            {"requestId": "req-%d" % index, "encodedDataLength": size}
            for index, size in enumerate(self.world.network)
        ]


class FakeRun:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.editor_browser_pid = 10
        self.static_server_pid = 99
        self.profile_dir = None
        self.bundle_bytes = 4096
        self.seed = 7
        self.out_root = self.directory

    def fixture(self, workload, data):
        path = self.directory / "fixtures" / ("%s.docx" % workload)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_bytes(data)
        return path


class ManualClock:
    def __init__(self, world, *, disturb):
        self.t = 0.0
        self.world = world
        self.disturb = disturb

    def monotonic(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds
        if self.disturb:
            self.world.longtask_count += 1
            self.world.longtask_sum_ms += 80
            self.world.heap_used += 8 * MiB
            self.world.runtime_used = self.world.heap_used


class PhaseSession:
    """In-process stand-in for one browser launch. No Chromium, no server."""

    def __init__(self, world, *, mode):
        self.world = world
        self.mode = mode
        self.page = FakePage(world)
        self.cdp = FakeCdp(world)
        self.browser_pid = 10
        self.server_pid = 99
        self.profile_dir = None
        self.bundle_bytes = 4096
        self.has_save = False
        self.edited = None

    def process_reader(self):
        return [dict(row) for row in self.world.processes]

    def load(self):
        if self.mode == "measure":
            self.world.set_heap(40 * MiB)
            self.world.download(6 * MiB)

    def after_load(self):
        if self.mode == "measure":
            self.world.set_heap(42 * MiB)

    def prepare_edit(self, burst):
        return {"beforeText": "", "pre_type_settle_ms": 300}

    def type_edit(self, burst):
        self.edited = dict(burst)
        text = str(burst.get("text") or "")
        repetitions = int(burst.get("repetitions") or 0)
        if self.mode == "measure":
            self.world.set_heap(48 * MiB)
            self.world.burn_renderer_cpu_ms(400)
            self._editor_text = text * repetitions
        else:
            self._editor_text = "ready"
        return {"typed": True, "typing_duration_ms": 1.0}

    def verify_edit(self, burst, prepared):
        verified = self.mode == "measure"
        return {
            "applied": verified,
            "beforeText": prepared.get("beforeText", ""),
            "editorText": getattr(self, "_editor_text", "ready"),
            "kind": "keyboard.type",
            "oracle": {
                "mode": "dom_text",
                "witness_mode": "dom_text",
                "status": "verified" if verified else "edit_not_applied",
                "reason": None if verified else "text_delta_mismatch",
                "model_hook": False,
                "trusted_keys": 16 if verified else 0,
                "expected_text_delta": int(burst.get("repetitions") or 0),
                "text_delta": int(burst.get("repetitions") or 0) if verified else 0,
            },
        }

    def edit(self, burst):
        self.edited = dict(burst)
        text = str(burst.get("text") or "")
        repetitions = int(burst.get("repetitions") or 0)
        if self.mode == "measure":
            self.world.set_heap(48 * MiB)
            self.world.burn_renderer_cpu_ms(400)
            self._editor_text = text * repetitions
            return {"applied": True, "editorText": self._editor_text}
        self._editor_text = "ready"
        return {"applied": False, "editorText": "ready"}

    def editor_text(self):
        return getattr(self, "_editor_text", "")

    def after_edits(self):
        if self.mode == "measure":
            self.world.set_heap(49 * MiB)

    def save(self):
        raise AssertionError("this host has no save")

    def close(self):
        return None


def make_sampler(world, *, clock=None, platform_name="darwin", browser_pid=10, page=None):
    directory = tempfile.mkdtemp()
    run = FakeRun(directory)
    run.editor_browser_pid = browser_pid
    page = page or FakePage(world)
    cdp = FakeCdp(world)
    return ResourceSampler(
        run,
        page,
        cdp,
        process_reader=lambda: [dict(row) for row in world.processes],
        platform_name=platform_name,
        clock=clock or ManualClock(world, disturb=False),
    )


SHORT_QUIESCENCE = {
    "no_longtask_s": 2.0,
    "heap_band_percent": 5.0,
    "max_wait_s": 6.0,
    "poll_s": 1.0,
}


class SamplerMeasurements(unittest.TestCase):
    def test_allocating_200_mib_reports_at_least_that_much_js_heap(self):
        world = World()
        sampler = make_sampler(world)
        world.allocate(200 * MiB)
        sample = sampler.sample()
        self.assertGreaterEqual(sample["js_heap_used_bytes"], 200 * MiB)
        self.assertGreaterEqual(sample["js_heap_runtime_used_bytes"], 200 * MiB)
        self.assertNotIn("samples_ms", sample)
        self.assertNotIn("samples_ms", sampler.series()[0])

    def test_burning_cpu_for_two_seconds_records_renderer_cpu_ms(self):
        world = World()
        sampler = make_sampler(world)
        sampler.mark("burn")
        world.burn_renderer_cpu_ms(2000)
        sampler.sample()
        self.assertGreaterEqual(sampler.totals("burn")["renderer_cpu_ms"], 1800)

    def test_indexeddb_write_of_50_mib_is_storage_usage(self):
        world = World()
        sampler = make_sampler(world)
        world.write_indexeddb(50 * MiB)
        sample = sampler.sample()
        self.assertGreaterEqual(sample["storage_usage_bytes"], 50 * MiB)
        self.assertGreaterEqual(sample["storage_indexeddb_bytes"], 50 * MiB)

    def test_downloading_5_mib_records_network_bytes(self):
        world = World()
        sampler = make_sampler(world)
        world.download(5 * MiB)
        sample = sampler.sample()
        self.assertGreaterEqual(sample["network_encoded_bytes"], 5 * MiB)
        self.assertGreaterEqual(sample["network_request_count"], 1)

    def test_three_process_tree_is_recorded_by_role_and_excludes_the_server(self):
        world = World()
        sampler = make_sampler(world)
        sample = sampler.sample()
        roles = sorted(row["role"] for row in sample["processes"])
        self.assertEqual(roles, ["browser", "gpu", "renderer"])
        self.assertEqual(sorted(row["pid"] for row in sample["processes"]), [10, 11, 12])
        self.assertNotIn(50, [row["pid"] for row in sample["processes"]])
        self.assertNotIn(99, [row["pid"] for row in sample["processes"]])
        self.assertEqual(sample["static_server"]["pid"], 99)
        self.assertFalse(sample["static_server"]["counted_as_editor"])
        self.assertIn("The dev/static server is not the editor.", sample["static_server"]["note"])
        for row in sample["processes"]:
            self.assertEqual(row["pss_bytes"], NOT_AVAILABLE)
            self.assertEqual(row["uss_bytes"], NOT_AVAILABLE)
            self.assertEqual(row["io_read_bytes"], NOT_AVAILABLE)
            self.assertEqual(row["io_write_bytes"], NOT_AVAILABLE)
            self.assertNotEqual(row["pss_bytes"], 0)
        self.assertEqual(sample["cgroup_memory_current_bytes"], NOT_AVAILABLE)
        self.assertNotEqual(sample["cgroup_memory_current_bytes"], 0)
        self.assertEqual(sample["cgroup_rss_gap_bytes"], NOT_AVAILABLE)

    def test_missing_launch_pid_does_not_guess_another_browser(self):
        world = World()
        sampler = make_sampler(world, browser_pid=None)
        sample = sampler.sample()
        self.assertEqual(sample["processes"], [])
        self.assertEqual(sample["process_tree_status"], "process_tree_not_launched")
        self.assertEqual(sample["rss_bytes"], NOT_AVAILABLE)

    def test_network_service_is_its_own_role(self):
        self.assertEqual(
            role_of("chrome --type=utility --utility-sub-type=network.mojom.NetworkService"),
            "network_service",
        )

    def test_linux_proc_fields_keep_their_units(self):
        stat = "11 (chrome) R 10 11 11 0 11 0 1 2 3 4 100 50 0 0"
        status = "VmRSS:\t2048 kB\n"
        io = "read_bytes: 4096\nwrite_bytes: 8192\n"
        rollup = "Rss:\t2048 kB\nPss:\t1500 kB\nPrivate_Clean:\t100 kB\nPrivate_Dirty:\t200 kB\n"
        row = parse_linux_process(
            pid=11,
            stat=stat,
            cmdline="chrome --type=renderer",
            status=status,
            io_text=io,
            rollup=rollup,
            hz=100,
        )
        self.assertEqual(row["ppid"], 10)
        self.assertEqual(row["cpu_ms"], 1500)
        self.assertEqual(row["rss_bytes"], 2048 * 1024)
        self.assertEqual(row["pss_bytes"], 1500 * 1024)
        self.assertEqual(row["uss_bytes"], 300 * 1024)
        self.assertEqual(row["io_read_bytes"], 4096)
        self.assertEqual(row["io_write_bytes"], 8192)
        self.assertEqual(row["role"], "renderer")

    def test_cgroup_gap_is_recorded(self):
        parsed = parse_cgroup_text(
            cpu_stat="usage_usec 5000000\nuser_usec 1\nsystem_usec 1\n",
            memory_current="419430400\n",
            memory_peak="524288000\n",
            io_stat="259:0 rbytes=100 wbytes=200 rios=1 wios=1 dbytes=0 dios=0\n",
        )
        self.assertEqual(parsed["cgroup_cpu_usec"], 5000000)
        self.assertEqual(parsed["cgroup_memory_current_bytes"], 400 * MiB)
        self.assertEqual(parsed["cgroup_memory_peak_bytes"], 500 * MiB)
        self.assertEqual(parsed["cgroup_io_read_bytes"], 100)
        self.assertEqual(parsed["cgroup_io_write_bytes"], 200)
        world = World()
        sampler = make_sampler(world, platform_name="linux")
        sampler.cgroup_reader = lambda pid: parsed
        sample = sampler.sample()
        self.assertGreater(sample["cgroup_rss_gap_bytes"], 50 * MiB)
        self.assertTrue(sample["cgroup_gap_large"])
        self.assertNotEqual(sample["cgroup_rss_gap_bytes"], 0)

    def test_macos_ps_time_is_the_dev_cpu_fallback(self):
        self.assertEqual(parse_ps_time("0:02.00"), 2000)
        table = parse_ps_resource_table("  11  10  2048  0:02.00 chrome --type=renderer\n")
        self.assertEqual(table[0]["pid"], 11)
        self.assertEqual(table[0]["ppid"], 10)
        self.assertEqual(table[0]["rss_bytes"], 2048 * 1024)
        self.assertEqual(table[0]["cpu_ms"], 2000)
        self.assertEqual(table[0]["pss_bytes"], NOT_AVAILABLE)
        self.assertEqual(table[0]["io_read_bytes"], NOT_AVAILABLE)


class SplitWindowSession:
    """A session whose oracle work is deliberately much more expensive than typing."""

    def __init__(self, world, *, oracle_status="verified"):
        self.world = world
        self.oracle_status = oracle_status
        self.page = FakePage(world)
        self.cdp = FakeCdp(world)
        self.browser_pid = 10
        self.server_pid = 99
        self.profile_dir = None
        self.bundle_bytes = 4096
        self.has_save = False
        self.events = []
        self._editor_text = ""

    def process_reader(self):
        return [dict(row) for row in self.world.processes]

    def load(self):
        self.world.set_heap(40 * MiB)

    def after_load(self):
        self.world.set_heap(42 * MiB)

    def prepare_edit(self, burst):
        self.events.append("prepare")
        self.world.burn_renderer_cpu_ms(100)
        return {"beforeText": "", "pre_type_settle_ms": 300}

    def type_edit(self, burst):
        self.events.append("type")
        self.world.set_heap(48 * MiB)
        self.world.burn_renderer_cpu_ms(10)
        self._editor_text = str(burst.get("text") or "") * int(burst.get("repetitions") or 0)
        return {"typed": True, "typing_duration_ms": 2.0}

    def verify_edit(self, burst, prepared):
        self.events.append("verify")
        self.world.burn_renderer_cpu_ms(1000)
        verified = self.oracle_status == "verified"
        return {
            "applied": verified,
            "beforeText": "",
            "editorText": self._editor_text,
            "kind": "keyboard.type",
            "oracle": {
                "mode": "dom_text",
                "status": self.oracle_status,
                "model_hook": False,
                "trusted_keys": 16,
                "text_delta": 8 if verified else None,
                "expected_text_delta": 8,
                "poll_attempts": 1,
                "poll_bound_ms": 2000,
            },
        }

    def edit(self, burst):
        """The pre-fix combined path; kept so RED proves the old boundary is wrong."""
        self.events.append("legacy_combined")
        self.world.set_heap(48 * MiB)
        self.world.burn_renderer_cpu_ms(1010)
        self._editor_text = str(burst.get("text") or "") * int(burst.get("repetitions") or 0)
        return {
            "applied": True,
            "beforeText": "",
            "editorText": self._editor_text,
            "kind": "keyboard.type",
            "oracle": {
                "mode": "dom_text",
                "status": "verified",
                "model_hook": False,
                "trusted_keys": 16,
                "text_delta": 8,
                "expected_text_delta": 8,
            },
        }

    def editor_text(self):
        return self._editor_text

    def after_edits(self):
        self.world.set_heap(49 * MiB)

    def close(self):
        return None


class LaneRefusals(unittest.TestCase):
    def test_constant_series_is_refused(self):
        world = World()
        sampler = make_sampler(world)
        sampler.mark("after_load")
        sampler.sample()
        trial = collect_phases(
            sampler,
            PhaseSession(world, mode="idle"),
            ManualClock(world, disturb=False),
            quiescence=SHORT_QUIESCENCE,
            edit_burst=EDIT_BURST,
            editor_id="plate",
            workload_id="prose-500w",
            workload_meta={"sha256": "a" * 64, "byte_size": 10, "paragraph_count": 1, "word_count": 1},
            execution_profile="ci_broad",
            host_class="ci_coarse",
            already_sampled=True,
        )
        self.assertEqual(trial["outcome"], "refused")
        self.assertEqual(trial["refusal_code"], "constant_series")
        self.assertIn(trial["refusal_code"], REFUSAL_CODES)
        self.assertNotIn("samples_ms", trial)
        self.assertNotIn("samples_ms", json.dumps(trial))

    def test_copied_phase_series_is_refused(self):
        world = World()
        clock = ManualClock(world, disturb=False)
        sampler = make_sampler(world, clock=clock)
        world.set_heap(10 * MiB)
        sampler.mark("left")
        world.set_heap(20 * MiB)
        sampler.sample()
        world.set_heap(10 * MiB)
        sampler.mark("right")
        world.set_heap(20 * MiB)
        sampler.sample()
        from perf.runner.resources import classify_series

        self.assertEqual(classify_series(sampler.series(), quiescence_reached=True), "copied_series")

    def test_an_editor_that_never_idles_is_measured_and_flagged(self):
        # Owner decision 2026-11-11 (#155.3): WordCraft repaints forever. Its load
        # and edit counters are real; refusing the cell hid that it never idles.
        world = World()
        clock = ManualClock(world, disturb=True)
        sampler = make_sampler(world, clock=clock)
        session = PhaseSession(world, mode="measure")
        trial = collect_phases(
            sampler,
            session,
            clock,
            quiescence=SHORT_QUIESCENCE,
            edit_burst=EDIT_BURST,
            editor_id="plate",
            workload_id="prose-500w",
            workload_meta={"sha256": "b" * 64, "byte_size": 10, "paragraph_count": 1, "word_count": 1},
            execution_profile="ci_broad",
            host_class="ci_coarse",
        )
        self.assertFalse(trial["quiescence"]["reached"])
        self.assertEqual(trial["settle"], {"after_load": "capped", "after_edit": "capped"})
        self.assertEqual(trial["outcome"], "measured")
        self.assertIsNone(trial["refusal_code"])
        self.assertEqual(session.edited, EDIT_BURST)
        for phase in ("edit_burst", "quiescence", "after_edits"):
            self.assertIn(phase, trial["phases"])
        self.assertEqual(trial["edit_oracle"]["status"], "verified")
        self.assertNotIn("quiescence_not_reached", REFUSAL_CODES)

    def test_work_done_after_the_ready_signal_is_published_as_open_settle(self):
        # SuperDoc says "ready" at 250k words before the document is laid out, and
        # Docxodus opens its editor after its viewer. That work is the cost of opening.
        world = World()
        clock = ManualClock(world, disturb=False)
        sampler = make_sampler(world, clock=clock)

        class LateWork(PhaseSession):
            def after_load(self):
                super().after_load()
                self.world.burn_renderer_cpu_ms(700)

        trial = collect_phases(
            sampler, LateWork(world, mode="measure"), clock,
            quiescence=SHORT_QUIESCENCE, edit_burst=EDIT_BURST, editor_id="plate",
            workload_id="prose-500w",
            workload_meta={"sha256": "b" * 64, "byte_size": 10, "paragraph_count": 1, "word_count": 1},
            execution_profile="ci_broad", host_class="ci_coarse",
        )
        self.assertGreaterEqual(trial["open_settle_cpu_ms"], 700)
        self.assertIn("open_settle_network_encoded_bytes", trial)

    def test_a_settled_editor_says_so(self):
        world = World()
        clock = ManualClock(world, disturb=False)
        sampler = make_sampler(world, clock=clock)
        trial = collect_phases(
            sampler,
            PhaseSession(world, mode="measure"),
            clock,
            quiescence=SHORT_QUIESCENCE,
            edit_burst=EDIT_BURST,
            editor_id="plate",
            workload_id="prose-500w",
            workload_meta={"sha256": "b" * 64, "byte_size": 10, "paragraph_count": 1, "word_count": 1},
            execution_profile="ci_broad",
            host_class="ci_coarse",
        )
        self.assertTrue(trial["quiescence"]["reached"])
        self.assertEqual(trial["settle"], {"after_load": "reached", "after_edit": "reached"})

    def test_workload_prose_50kw_runs_in_a_fake_host(self):
        holder = {}

        def factory(ctx):
            holder["ctx"] = ctx
            world = World()
            return PhaseSession(world, mode="measure")

        with tempfile.TemporaryDirectory() as tmp:
            run = FakeRun(tmp)
            trial = measure_editor(
                editor_id="plate",
                workload_id="prose-50kw",
                run=run,
                execution_profile="dedicated_publish",
                host_class="dedicated",
                session_factory=factory,
                clock=ManualClock(None, disturb=False),
                quiescence=SHORT_QUIESCENCE,
            )
        seen = holder["ctx"]
        self.assertEqual(seen["workload_id"], "prose-50kw")
        self.assertEqual(seen["editor_id"], "plate")
        self.assertGreaterEqual(seen["workload_meta"]["word_count"], 50_000)
        self.assertEqual(trial["workload_id"], "prose-50kw")
        self.assertEqual(trial["editor_id"], "plate")
        self.assertEqual(trial["outcome"], "measured")
        self.assertIsNone(trial["refusal_code"])
        self.assertNotIn("samples_ms", trial)
        self.assertNotIn("samples_ms", json.dumps(trial))
        self.assertIn("prose-50kw", RESOURCE_WORKLOADS)
        self.assertGreaterEqual(trial["criteria"]["C17"]["js_heap_used_bytes"], 1)
        self.assertGreaterEqual(trial["criteria"]["C19"]["js_heap_used_bytes"], 1)
        self.assertIn("growth_js_heap_used_bytes", trial["criteria"]["C19"])
        self.assertGreaterEqual(trial["peak_ram_bytes"], 1)
        self.assertEqual(trial["edit_burst"]["kind"], EDIT_BURST["kind"])
        self.assertEqual(trial["edit_burst"]["repetitions"], EDIT_BURST["repetitions"])
        self.assertTrue(trial["quiescence"]["reached"])
        self.assertIn("no_longtask_s", QUIESCENCE)
        self.assertIn("heap_band_percent", QUIESCENCE)
        self.assertIn("max_wait_s", QUIESCENCE)
        self.assertFalse(trial["static_server"]["counted_as_editor"])
        self.assertEqual(seen["edited"]["text"], EDIT_BURST["text"])
        self.assertEqual(seen["edited"]["repetitions"], EDIT_BURST["repetitions"])
        self.assertGreater(seen["workload_meta"]["byte_size"], 0)

    def test_publication_needs_thirty_scheduled_ten_kept_and_two_seeds(self):
        kept = [
            {"outcome": "measured", "editor_id": "plate", "workload_id": "prose-500w"}
            for _ in range(10)
        ]
        one = publication_verdict(
            kept,
            seeds=[1],
            scheduled=30,
            execution_profile="dedicated_publish",
            host_class="dedicated",
        )
        self.assertFalse(one["publishable"])
        self.assertIn("second_seed_required", one["publication_block_reasons"])
        short = publication_verdict(
            kept[:9],
            seeds=[1, 2],
            scheduled=30,
            execution_profile="dedicated_publish",
            host_class="dedicated",
        )
        self.assertIn("kept_below_10", short["publication_block_reasons"])
        both = publication_verdict(
            kept,
            seeds=[1, 2],
            scheduled=30,
            execution_profile="dedicated_publish",
            host_class="dedicated",
        )
        self.assertTrue(both["publishable"])
        self.assertEqual(both["publication_block_reasons"], [])


class EditWindowAndOracleTest(unittest.TestCase):
    def collect_split_trial(self, editor_id, *, oracle_status="verified"):
        world = World()
        clock = ManualClock(world, disturb=False)
        sampler = make_sampler(world, clock=clock, page=ProbeCostPage(world))
        session = SplitWindowSession(world, oracle_status=oracle_status)
        trial = collect_phases(
            sampler,
            session,
            clock,
            quiescence=SHORT_QUIESCENCE,
            edit_burst=EDIT_BURST,
            editor_id=editor_id,
            workload_id="prose-500w",
            workload_meta={"sha256": "a" * 64, "byte_size": 10, "paragraph_count": 1, "word_count": 500},
            execution_profile="ci_broad",
            host_class="ci_coarse",
        )
        return trial, session

    def test_edit_cpu_window_is_typing_plus_one_fixed_settle_for_every_editor(self):
        measured = []
        for editor_id in ("plate", "canvas"):
            trial, session = self.collect_split_trial(editor_id)
            self.assertEqual(trial["edit_cpu_ms"], 10, trial)
            measurement = trial["edit_measurement"]
            measured.append(measurement["settle_ms"])
            self.assertGreaterEqual(measurement["measured_window_duration_ms"], 500)
            self.assertEqual(measurement["pre_type_settle_ms"], 300)
            self.assertEqual(session.events, ["prepare", "type", "verify"])
        self.assertEqual(measured, [500, 500])

    def test_unverified_paint_edit_withholds_all_edit_cpu_but_keeps_other_metrics(self):
        trial, _ = self.collect_split_trial("superdoc", oracle_status="edit_unverified")
        self.assertEqual(trial["outcome"], "measured")
        self.assertTrue(trial.get("edit_unverified"))
        self.assertEqual(trial["edit_oracle"]["status"], "edit_unverified")
        self.assertNotIn("edit_cpu_ms", trial)
        self.assertNotIn("edit_renderer_cpu_ms", trial)
        self.assertIn("load_cpu_ms", trial)
        self.assertIn("quiescence_cpu_ms", trial)
        self.assertIn("quiescence", trial["phases"])
        self.assertIn("C19", trial["criteria"])

        def numeric_cpu_keys(value):
            found = []
            if isinstance(value, dict):
                for key, child in value.items():
                    if "cpu" in key.lower() and isinstance(child, (int, float)):
                        found.append(key)
                    found.extend(numeric_cpu_keys(child))
            elif isinstance(value, list):
                for child in value:
                    found.extend(numeric_cpu_keys(child))
            return found

        edit_phase = trial["phases"]["edit_burst"]
        edit_rows = [row for row in trial["series"] if row.get("phase") == "edit_burst"]
        self.assertEqual(numeric_cpu_keys(edit_phase), [])
        self.assertEqual(numeric_cpu_keys(edit_rows), [])
        self.assertEqual(edit_phase["cpu_ms"]["marker"], "withheld")
        self.assertEqual(edit_phase["renderer_cpu_ms"]["marker"], "withheld")
        for row in edit_rows:
            self.assertEqual(row["cpu_ms"]["marker"], "withheld")
            self.assertEqual(row["cgroup_cpu_usec"]["marker"], "withheld")
            for process in row["processes"]:
                self.assertEqual(process["cpu_ms"]["marker"], "withheld")

    def test_cell_records_edit_oracle_evidence(self):
        trial, _ = self.collect_split_trial("plate")
        oracle = trial.get("edit_oracle") or {}
        self.assertEqual(oracle.get("mode"), "dom_text")
        self.assertEqual(oracle.get("status"), "verified")
        self.assertEqual(oracle.get("trusted_keys"), 16)
        self.assertEqual(oracle.get("text_delta"), 8)
        self.assertEqual(oracle.get("expected_text_delta"), 8)


if __name__ == "__main__":
    unittest.main()
