"""Review blockers for the browser resource lane (#142, #115).

These reproduce the executed probes under /tmp/review-b8-1. A zero, a negative
phase delta, or a publishable verdict is the failure.
"""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from perf.runner.benchmark_resources import (
    EDIT_BURST,
    QUIESCENCE,
    collect_phases,
    publication_from_run,
    publication_verdict,
)
from perf.runner.resources import (
    NOT_AVAILABLE,
    FIELD_SOURCES,
    ResourceSampler,
    phase_totals,
)
from perf.tests.test_resources import FakeCdp, FakePage, ManualClock, World, make_sampler

MiB = 1024 * 1024


def _cell(editor, workload, outcome, *, fixture_sha=None):
    row = {"editor_id": editor, "workload_id": workload, "outcome": outcome}
    if fixture_sha is not None:
        row["fixture_sha256"] = fixture_sha
    return row


def _write_run(root, cells):
    for index, cell in enumerate(cells):
        path = root / "cells" / str(index) / "resource.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cell))


class PublicationGate(unittest.TestCase):
    def test_empty_companion_is_refused(self):
        """publication.py: 10 measured cells plus an empty unsuccessful companion."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            primary = root / "primary"
            cells = [
                _cell("plate", "prose-500w", "measured" if i < 10 else "failed")
                for i in range(30)
            ]
            _write_run(primary, cells)
            companion = root / "empty-companion" / "summary.json"
            companion.parent.mkdir(parents=True, exist_ok=True)
            companion.write_text(json.dumps({
                "seed": 2,
                "publishable": False,
                "failure_reason": "no measurements",
                "execution_profile": "ci_contract",
            }))
            verdict = publication_from_run(SimpleNamespace(
                directory=primary,
                seed=1,
                companion_summary=str(companion),
                execution_profile="dedicated_publish",
                host_class="dedicated",
                hosts={},
            ))
        self.assertFalse(verdict["publishable"])
        self.assertTrue(verdict["publication_block_reasons"])

    def test_failed_group_does_not_disappear(self):
        """probes.py: 10 Plate measurements must not hide 20 failures of another editor."""
        kept = [_cell("plate", "prose-500w", "measured") for _ in range(10)]
        failed = [_cell("other", "prose-500w", "failed") for _ in range(20)]
        verdict = publication_verdict(
            kept + failed,
            seeds=[1, 2],
            scheduled=30,
            execution_profile="dedicated_publish",
            host_class="dedicated",
        )
        self.assertFalse(verdict["publishable"])
        self.assertIn("kept_below_10", verdict["publication_block_reasons"])

    def test_companion_provenance_must_match(self):
        sha = "a" * 64
        hosts_ok = {"plate": {"tree_sha256": "build-a", "host_build": "production"}}
        hosts_other = {"plate": {"tree_sha256": "build-b", "host_build": "production"}}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            primary = root / "primary"
            other_dir = root / "companion"
            cells = [
                _cell("plate", "prose-500w", "measured" if i < 10 else "failed", fixture_sha=sha)
                for i in range(30)
            ]
            _write_run(primary, cells)
            _write_run(other_dir, cells)
            summary = other_dir / "summary.json"
            summary.write_text(json.dumps({
                "seed": 2,
                "publishable": False,
                "execution_profile": "dedicated_publish",
                "host_class": "dedicated",
                "hosts": hosts_other,
            }))
            verdict = publication_from_run(SimpleNamespace(
                directory=primary,
                seed=1,
                companion_summary=str(summary),
                execution_profile="dedicated_publish",
                host_class="dedicated",
                hosts=hosts_ok,
            ))
        self.assertFalse(verdict["publishable"])
        self.assertIn("companion_provenance_mismatch", verdict["publication_block_reasons"])

    def test_matching_second_seed_can_publish(self):
        sha = "b" * 64
        hosts = {"plate": {"tree_sha256": "build-same", "host_build": "production"}}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            primary = root / "primary"
            other_dir = root / "companion"
            cells = [
                _cell("plate", "prose-500w", "measured" if i < 10 else "failed", fixture_sha=sha)
                for i in range(30)
            ]
            _write_run(primary, cells)
            _write_run(other_dir, cells)
            summary = other_dir / "summary.json"
            summary.write_text(json.dumps({
                "seed": 2,
                "execution_profile": "dedicated_publish",
                "host_class": "dedicated",
                "hosts": hosts,
            }))
            verdict = publication_from_run(SimpleNamespace(
                directory=primary,
                seed=1,
                companion_summary=str(summary),
                execution_profile="dedicated_publish",
                host_class="dedicated",
                hosts=hosts,
            ))
        self.assertTrue(verdict["publishable"], verdict)
        self.assertEqual(verdict["publication_block_reasons"], [])
        self.assertEqual(sorted(verdict["seeds"]), [1, 2])


class AllocClock:
    """Advances a 3-second post-load allocation (1 MiB every 100 ms, 30 times)."""

    def __init__(self, world):
        self.t = 0.0
        self.world = world
        self.t0 = None
        self.applied_steps = 0

    def start(self):
        self.t0 = self.t
        self.applied_steps = 0

    def monotonic(self):
        self._apply()
        return self.t

    def sleep(self, seconds):
        self.t += seconds
        self._apply()

    def _apply(self):
        if self.t0 is None:
            return
        steps = min(30, int((self.t - self.t0) / 0.1))
        delta_steps = steps - self.applied_steps
        if delta_steps:
            self.world.allocate(delta_steps * MiB)
            self.applied_steps = steps


class DelayedSession:
    def __init__(self, world, clock):
        self.world = world
        self.clock = clock
        self.page = FakePage(world)
        self.cdp = FakeCdp(world)
        self.has_save = False
        self.editor = "ready"

    def load(self):
        self.clock.start()

    def edit(self, burst):
        self.world.allocate(MiB)
        self.editor = burst["text"] * burst["repetitions"]
        return {"applied": True, "editorText": self.editor}

    def editor_text(self):
        return self.editor


class ReadOnlySession:
    def __init__(self, world):
        self.world = world
        self.page = FakePage(world)
        self.cdp = FakeCdp(world)
        self.has_save = False

    def load(self):
        self.world.set_heap(12 * MiB)

    def edit(self, burst):
        return {"applied": False, "editorText": "ready"}

    def editor_text(self):
        return "ready"


class GcCdp(FakeCdp):
    def __init__(self, world):
        super().__init__(world)
        self.collections = 0

    def send(self, method, params=None):
        if method == "HeapProfiler.collectGarbage":
            self.collections += 1
            self.world.allocate(-2 * MiB)
            return {}
        return super().send(method, params)


class EndpointProtocol(unittest.TestCase):
    def test_delayed_allocation_stays_out_of_edit_growth(self):
        """live3.py: three seconds of post-load allocation must settle before C17."""
        world = World()
        clock = AllocClock(world)
        sampler = make_sampler(world, clock=clock)
        session = DelayedSession(world, clock)
        trial = collect_phases(
            sampler, session, clock,
            quiescence=QUIESCENCE,
            edit_burst=EDIT_BURST,
            editor_id="fake",
            workload_id="prose-500w",
            workload_meta={"sha256": "c" * 64, "byte_size": 10, "paragraph_count": 1, "word_count": 500},
            execution_profile="ci_broad",
            host_class="ci_coarse",
        )
        self.assertEqual(trial.get("outcome"), "measured", trial.get("refusal_code"))
        c17 = trial.get("criteria", {}).get("C17", {})
        c19 = trial.get("criteria", {}).get("C19", {})
        growth = c19.get("growth_js_heap_used_bytes")
        self.assertIsInstance(growth, int)
        self.assertLess(growth, 2 * MiB)
        self.assertGreaterEqual(c17.get("js_heap_used_bytes") or 0, 30 * MiB)

    def test_post_gc_endpoints_are_labelled_and_do_not_replace_natural_heap(self):
        world = World()
        clock = ManualClock(world, disturb=False)
        directory = tempfile.mkdtemp()
        from perf.tests.test_resources import FakeRun
        run = FakeRun(directory)
        page = FakePage(world)
        cdp = GcCdp(world)
        sampler = ResourceSampler(
            run, page, cdp,
            process_reader=lambda: [dict(row) for row in world.processes],
            platform_name="darwin",
            clock=clock,
        )

        class Session(DelayedSession):
            def __init__(self):
                self.world = world
                self.page = page
                self.cdp = cdp
                self.has_save = False
                self.editor = "ready"

            def load(self):
                world.set_heap(20 * MiB)

            def edit(self, burst):
                world.set_heap(24 * MiB)
                self.editor = burst["text"] * burst["repetitions"]
                return {"applied": True, "editorText": self.editor}

        trial = collect_phases(
            sampler, Session(), clock,
            quiescence=QUIESCENCE,
            edit_burst=EDIT_BURST,
            editor_id="fake",
            workload_id="prose-500w",
            workload_meta={"sha256": "d" * 64, "byte_size": 10, "paragraph_count": 1, "word_count": 500},
            execution_profile="ci_broad",
            host_class="ci_coarse",
        )
        c17 = trial["criteria"]["C17"]
        c19 = trial["criteria"]["C19"]
        self.assertIn("js_heap_used_bytes_after_gc", c17)
        self.assertIn("js_heap_used_bytes_after_gc", c19)
        self.assertIn("retained_growth_js_heap_bytes", c19)
        self.assertIsNone(c19["retained_growth_refusal"])
        self.assertEqual(
            c19["retained_growth_js_heap_bytes"],
            c19["js_heap_used_bytes_after_gc"] - c17["js_heap_used_bytes_after_gc"],
        )
        self.assertNotEqual(c17["js_heap_used_bytes"], c17["js_heap_used_bytes_after_gc"])
        self.assertEqual(c19["growth_js_heap_used_bytes"], c19["js_heap_used_bytes"] - c17["js_heap_used_bytes"])

    def test_failed_gc_refuses_only_the_retained_field(self):
        world = World()
        clock = ManualClock(world, disturb=False)
        sampler = make_sampler(world, clock=clock)

        class Session:
            def __init__(self):
                self.page = FakePage(world)
                self.cdp = FakeCdp(world)
                self.has_save = False

            def load(self):
                world.set_heap(20 * MiB)

            def edit(self, burst):
                world.set_heap(22 * MiB)
                return {"applied": True, "editorText": burst["text"] * burst["repetitions"]}

        trial = collect_phases(
            sampler, Session(), clock,
            quiescence=QUIESCENCE,
            edit_burst=EDIT_BURST,
            editor_id="fake",
            workload_id="prose-500w",
            workload_meta={"sha256": "e" * 64, "byte_size": 8, "paragraph_count": 1, "word_count": 8},
            execution_profile="ci_broad",
            host_class="ci_coarse",
        )
        self.assertEqual(trial.get("outcome"), "measured", trial.get("refusal_code"))
        c19 = trial.get("criteria", {}).get("C19", {})
        self.assertEqual(c19.get("retained_growth_js_heap_bytes"), NOT_AVAILABLE)
        self.assertEqual(c19.get("retained_growth_refusal"), "gc_unsupported")
        self.assertIsInstance(c19.get("growth_js_heap_used_bytes"), int)

    def test_readonly_edit_is_refused_and_has_no_c19(self):
        """live4.py: a non-editable target must not produce a measured C19."""
        world = World()
        clock = ManualClock(world, disturb=False)
        sampler = make_sampler(world, clock=clock)
        trial = collect_phases(
            sampler, ReadOnlySession(world), clock,
            quiescence=QUIESCENCE,
            edit_burst=EDIT_BURST,
            editor_id="fake",
            workload_id="prose-500w",
            workload_meta={"sha256": "f" * 64, "byte_size": 8, "paragraph_count": 1, "word_count": 8},
            execution_profile="ci_broad",
            host_class="ci_coarse",
        )
        self.assertEqual(trial["outcome"], "refused")
        self.assertEqual(trial["refusal_code"], "edit_not_applied")
        self.assertNotIn("C19", trial["criteria"])


class UnavailableIsNeverZero(unittest.TestCase):
    def test_missing_snapshot_storage_and_network_and_renderer_are_not_zero(self):
        """probes.py MISSING_STORAGE / MISSING_NETWORK / MISSING_RENDERER."""
        world = World()
        clock = ManualClock(world, disturb=False)
        sampler = make_sampler(world, clock=clock)
        sampler.page = SimpleNamespace(evaluate=lambda expression: {})
        sampler.cdp = SimpleNamespace(
            send=lambda method, params=None: {},
            events=lambda method: (_ for _ in ()).throw(RuntimeError("unsupported events")),
        )
        storage = sampler._storage()
        network = sampler._network()
        for key in (
            "storage_usage_bytes",
            "storage_indexeddb_bytes",
            "storage_cache_bytes",
            "storage_service_worker_bytes",
            "longtask_count",
            "longtask_sum_ms",
        ):
            self.assertEqual(storage[key], NOT_AVAILABLE, key)
            self.assertNotEqual(storage[key], 0, key)
        self.assertNotEqual(network, (0, 0))
        self.assertEqual(network[0], NOT_AVAILABLE)
        renderer = phase_totals([{"processes": []}, {"processes": []}])["renderer_cpu_ms"]
        self.assertEqual(renderer, NOT_AVAILABLE)
        self.assertNotEqual(renderer, 0)

    def test_missing_usage_detail_member_is_not_zero(self):
        world = World()
        sampler = make_sampler(world)
        sampler.page = SimpleNamespace(evaluate=lambda expression: {
            "usage": 10,
            "usageDetails": {"caches": 4},
            "localStorageBytes": 0,
            "longtaskCount": 0,
            "longtaskSumMs": 0,
        })
        storage = sampler._storage()
        self.assertEqual(storage["storage_usage_bytes"], 10)
        self.assertEqual(storage["storage_cache_bytes"], 4)
        self.assertEqual(storage["storage_indexeddb_bytes"], NOT_AVAILABLE)
        self.assertEqual(storage["local_storage_bytes"], 0)

    def test_unknown_longtask_cannot_prove_quiescence(self):
        world = World()
        clock = ManualClock(world, disturb=False)
        sampler = make_sampler(world, clock=clock)
        sampler.page = SimpleNamespace(evaluate=lambda expression: {
            "usage": 10,
            "usageDetails": {"indexedDB": 0, "caches": 0, "serviceWorkerRegistrations": 0},
            "localStorageBytes": 0,
            "longtaskCount": None,
            "longtaskSumMs": None,
            "longtaskReason": "longtask_observer_failed",
        })
        from perf.runner.resources import drive_quiescence
        reached = drive_quiescence(sampler, clock, {
            "no_longtask_s": 2.0,
            "heap_band_percent": 5.0,
            "max_wait_s": 15.0,
            "poll_s": 1.0,
        })
        self.assertFalse(reached)
        self.assertEqual(sampler.series()[-1]["longtask_count"], NOT_AVAILABLE)
        self.assertLess(clock.t, 15.0)

    def test_genuine_zero_storage_stays_zero(self):
        world = World()
        sample = make_sampler(world).sample()
        self.assertEqual(sample["storage_usage_bytes"], 0)
        self.assertEqual(sample["longtask_count"], 0)


class ProcessIdentity(unittest.TestCase):
    def test_exited_renderer_is_not_a_negative_delta(self):
        """probes.py EXITED_RENDERER: dropping pid 11 must not subtract its lifetime CPU."""
        world = World()
        clock = ManualClock(world, disturb=False)
        sampler = make_sampler(world, clock=clock)
        sampler.mark("edit")
        clock.t = 1
        world.processes = [row for row in world.processes if row["pid"] != 11]
        sample = sampler.sample()
        totals = sampler.totals("edit")
        self.assertNotEqual(totals.get("renderer_cpu_ms"), -20)
        self.assertNotEqual(totals.get("cpu_ms"), -20)
        self.assertNotEqual(sample.get("cpu_percent"), -2.0)
        self.assertEqual(totals.get("renderer_cpu_ms"), NOT_AVAILABLE)
        self.assertEqual(totals.get("cpu_ms"), NOT_AVAILABLE)
        self.assertEqual(totals.get("process_accounting"), "incomplete")
        self.assertIsNone(sample.get("cpu_percent"))

    def test_per_process_and_per_role_cpu_percent(self):
        world = World()
        clock = ManualClock(world, disturb=False)
        sampler = make_sampler(world, clock=clock)
        sampler.mark("burn")
        clock.t = 1
        world.burn_renderer_cpu_ms(2500)
        sample = sampler.sample()
        renderer = next(row for row in sample["processes"] if row["pid"] == 11)
        self.assertEqual(renderer.get("cpu_percent"), 250.0)
        by_role = sample.get("cpu_percent_by_role") or {}
        self.assertGreaterEqual(by_role.get("renderer") or 0, 250.0)
        self.assertIn("summed over cores", FIELD_SOURCES["cpu_percent"])
        self.assertIn("2.5", FIELD_SOURCES["cpu_percent"])

    def test_same_identity_cpu_is_counted_when_the_process_survives(self):
        world = World()
        clock = ManualClock(world, disturb=False)
        sampler = make_sampler(world, clock=clock)
        sampler.mark("burn")
        clock.t = 1
        world.burn_renderer_cpu_ms(2000)
        sampler.sample()
        self.assertGreaterEqual(sampler.totals("burn")["renderer_cpu_ms"], 1800)
        self.assertEqual(sampler.totals("burn")["process_accounting"], "complete")


class NetworkAccounting(unittest.TestCase):
    def test_worker_bytes_are_counted_and_cache_is_separate(self):
        world = World()
        sampler = make_sampler(world)
        sampler.cdp = SimpleNamespace(
            send=lambda method, params=None: {},
            events=lambda method: {
                "events": [
                    {
                        "requestId": "page-1",
                        "encodedDataLength": 100,
                        "decodedBodyBytes": 80,
                        "fromDiskCache": False,
                        "fromServiceWorker": False,
                        "targetType": "page",
                    },
                    {
                        "requestId": "worker-1",
                        "encodedDataLength": 5 * MiB,
                        "decodedBodyBytes": 5 * MiB,
                        "fromDiskCache": False,
                        "fromServiceWorker": False,
                        "targetType": "service_worker",
                    },
                    {
                        "requestId": "cache-1",
                        "encodedDataLength": 0,
                        "decodedBodyBytes": 4096,
                        "fromDiskCache": True,
                        "fromServiceWorker": False,
                        "targetType": "page",
                    },
                ],
                "worker_observation": "ok",
            },
        )
        sample = sampler.sample()
        self.assertGreaterEqual(sample["network_encoded_bytes"], 5 * MiB)
        self.assertEqual(sample["network_decoded_body_bytes"], 80 + 5 * MiB + 4096)
        self.assertEqual(sample["network_from_disk_cache_bytes"], 4096)
        self.assertNotEqual(sample["network_encoded_bytes"], sample["network_from_disk_cache_bytes"])
        self.assertEqual(sample["network_observation"], "ok")

    def test_unobserved_worker_marks_network_incomplete(self):
        world = World()
        sampler = make_sampler(world)
        sampler.cdp = SimpleNamespace(
            send=lambda method, params=None: {},
            events=lambda method: {
                "events": [{"requestId": "page-1", "encodedDataLength": 5 * MiB, "decodedBodyBytes": 5 * MiB}],
                "worker_observation": "failed",
                "worker_observation_reason": "worker_targets_unobserved",
            },
        )
        sample = sampler.sample()
        self.assertEqual(sample.get("network_encoded_bytes"), NOT_AVAILABLE)
        self.assertNotEqual(sample.get("network_encoded_bytes"), 0)
        self.assertEqual(sample.get("network_observation"), "incomplete")
        self.assertEqual(sample.get("network_observation_reason"), "worker_targets_unobserved")


class SharedCore(unittest.TestCase):
    def test_async_sampler_uses_the_same_phase_contract(self):
        import asyncio
        from perf.runner import resources as resources_module

        self.assertTrue(hasattr(resources_module, "AsyncResourceSampler"), "AsyncResourceSampler")
        self.assertIn(NOT_AVAILABLE, resources_module.__doc__)
        self.assertIn("js_heap_used_bytes", resources_module.__doc__)
        self.assertIn("retained_growth_js_heap_bytes", resources_module.__doc__)

        world = World()
        clock = ManualClock(world, disturb=False)

        class AsyncPage:
            def __init__(self):
                self.inner = FakePage(world)

            async def evaluate(self, expression):
                return self.inner.evaluate(expression)

        class AsyncCdp:
            def __init__(self):
                self.inner = FakeCdp(world)

            async def send(self, method, params=None):
                return self.inner.send(method, params)

            async def events(self, method):
                return self.inner.events(method)

        sampler = resources_module.AsyncResourceSampler(
            SimpleNamespace(editor_browser_pid=10, static_server_pid=99, profile_dir=None, bundle_bytes=4096),
            AsyncPage(),
            AsyncCdp(),
            process_reader=lambda: [dict(row) for row in world.processes],
            platform_name="darwin",
            clock=clock,
        )

        async def run():
            await sampler.mark("load")
            clock.t = 1
            world.allocate(MiB)
            await sampler.sample()
            return sampler.totals("load")

        totals = asyncio.run(run())
        self.assertEqual(totals["sample_count"], 2)
        self.assertGreaterEqual(totals["js_heap_used_bytes"], world.heap_used - MiB)
        with self.assertRaises(TypeError):
            sampler.totals()

    def test_profile_growth_names_the_before_load_baseline(self):
        world = World()
        clock = ManualClock(world, disturb=False)
        sampler = make_sampler(world, clock=clock)
        sampler.run.profile_dir = None

        class Session:
            def __init__(self):
                self.page = FakePage(world)
                self.cdp = FakeCdp(world)
                self.has_save = False

            def load(self):
                world.set_heap(18 * MiB)

            def edit(self, burst):
                world.set_heap(19 * MiB)
                return {"applied": True, "editorText": burst["text"] * burst["repetitions"]}

        trial = collect_phases(
            sampler, Session(), clock,
            quiescence=QUIESCENCE,
            edit_burst=EDIT_BURST,
            editor_id="fake",
            workload_id="prose-500w",
            workload_meta={"sha256": "1" * 64, "byte_size": 4, "paragraph_count": 1, "word_count": 4},
            execution_profile="ci_broad",
            host_class="ci_coarse",
        )
        self.assertEqual(trial.get("profile_directory_baseline"), "before_load")
        self.assertIn("profile_directory_growth_bytes", trial)
        self.assertIn("on-disk", FIELD_SOURCES["bundle_bytes"])
        self.assertIn("not bytes served", FIELD_SOURCES["bundle_bytes"])


if __name__ == "__main__":
    unittest.main()
