"""Round-3 blockers for the browser resource lane (#142, #115).

The probes live in e2-logs/b8-fix3. Each one must fail on fbf05fc and pass
after the fix. A publishable short group, a born process omitted from the
phase, a complete zero from a malformed network payload, or a preexisting
B8 string counted as this burst is the failure.
"""

import asyncio
import json
import os
import shutil
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace

from perf.runner.benchmark_resources import (
    EDIT_BURST,
    QUIESCENCE,
    SESSION,
    _Bridge,
    _BridgeCdp,
    _BridgePage,
    collect_phases,
    publication_from_run,
)
from perf.runner.browser_hosts import StaticHost
from perf.runner.resources import (
    NOT_AVAILABLE,
    AsyncResourceSampler,
    ResourceSampler,
    WallClock,
    account_network,
    phase_totals,
)
from perf.tests.test_resources import FakeCdp, FakePage, FakeRun, ManualClock, World

MiB = 1024 * 1024
REPO = Path(__file__).resolve().parents[2]


def _cell(editor, workload, outcome, *, fixture_sha="ab"):
    return {
        "editor_id": editor,
        "workload_id": workload,
        "outcome": outcome,
        "fixture_sha256": fixture_sha,
    }


def _write_run(root, cells, *, seed, hosts):
    for index, cell in enumerate(cells):
        path = root / "cells" / str(index) / "resource.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cell))
    (root / "summary.json").write_text(json.dumps({
        "seed": seed,
        "execution_profile": "dedicated_publish",
        "host_class": "dedicated",
        "hosts": hosts,
    }))


def _publish(root, primary_name="a"):
    hosts = {"plate": {"tree_sha256": "tree"}}
    return publication_from_run(SimpleNamespace(
        directory=root / primary_name,
        seed=1,
        companion_summary=str(root / "b" / "summary.json"),
        execution_profile="dedicated_publish",
        host_class="dedicated",
        hosts=hosts,
    ))


def _proc(pid, cpu):
    return {
        "pid": pid,
        "start_time": 1,
        "role": "renderer",
        "cpu_ms": cpu,
        "io_read_bytes": cpu,
        "io_write_bytes": cpu,
    }


class SchedulingPerGroup(unittest.TestCase):
    def test_ten_cells_per_group_are_refused(self):
        """extra.py: three groups of ten scheduled cells must not publish."""
        hosts = {"plate": {"tree_sha256": "tree"}}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, seed in (("a", 1), ("b", 2)):
                cells = [
                    _cell("plate", "w%d" % (index // 10), "measured", fixture_sha="fixture%d" % (index // 10))
                    for index in range(30)
                ]
                _write_run(root / name, cells, seed=seed, hosts=hosts)
            verdict = _publish(root)
        self.assertFalse(verdict["publishable"], verdict)
        self.assertIn("scheduled_below_30", verdict["publication_block_reasons"])
        self.assertNotIn("kept_below_10", verdict["publication_block_reasons"])

    def test_thirty_scheduled_and_ten_measured_per_group_can_publish(self):
        hosts = {"plate": {"tree_sha256": "tree"}}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, seed in (("a", 1), ("b", 2)):
                cells = []
                for workload in ("prose-500w", "prose-50kw"):
                    for index in range(30):
                        outcome = "measured" if index < 10 else "failed"
                        cells.append(_cell("plate", workload, outcome, fixture_sha=workload))
                _write_run(root / name, cells, seed=seed, hosts=hosts)
            verdict = _publish(root)
        self.assertTrue(verdict["publishable"], verdict)
        self.assertEqual(verdict["scheduled"], 30)


class ProcessBirth(unittest.TestCase):
    def test_renderer_born_during_the_phase_counts_full_counters(self):
        """extra.py: a renderer that appears at 5000 ms is work done in the phase."""
        totals = phase_totals([
            {"processes": [_proc(1, 100)]},
            {"processes": [_proc(1, 110), _proc(2, 5000)]},
        ])
        self.assertEqual(totals["process_accounting"], "complete")
        self.assertEqual(totals["cpu_ms"], 5010)
        self.assertEqual(totals["renderer_cpu_ms"], 5010)
        self.assertEqual(totals["io_read_bytes"], 5010)
        self.assertEqual(totals["io_write_bytes"], 5010)


class MalformedNetwork(unittest.TestCase):
    def test_missing_observation_events_or_wire_length_is_incomplete(self):
        """extra.py: a malformed payload is never a complete zero."""
        payloads = (
            {},
            {"worker_observation": "ok", "events": None},
            {"worker_observation": "ok", "events": [{"requestId": "a"}]},
        )
        for payload in payloads:
            accounted = account_network(payload)
            self.assertEqual(accounted["network_observation"], "incomplete", payload)
            self.assertEqual(accounted["network_encoded_bytes"], NOT_AVAILABLE, payload)
            self.assertNotEqual(accounted["network_encoded_bytes"], 0, payload)
            self.assertNotEqual(accounted["network_request_count"], 1, payload)

    def test_explicit_empty_observation_stays_a_complete_zero(self):
        accounted = account_network({"worker_observation": "ok", "events": []})
        self.assertEqual(accounted["network_observation"], "ok")
        self.assertEqual(accounted["network_encoded_bytes"], 0)
        self.assertEqual(accounted["network_request_count"], 0)

    def test_explicit_zero_wire_length_is_a_real_zero(self):
        accounted = account_network({
            "worker_observation": "ok",
            "events": [{"requestId": "cache", "encodedDataLength": 0, "decodedBodyBytes": 4}],
        })
        self.assertEqual(accounted["network_observation"], "ok")
        self.assertEqual(accounted["network_encoded_bytes"], 0)
        self.assertEqual(accounted["network_request_count"], 1)


class _TextSession:
    def __init__(self, world, before, after, *, applied=True):
        self.world = world
        self.page = FakePage(world)
        self.cdp = FakeCdp(world)
        self.has_save = False
        self.before = before
        self.after = after
        self.applied = applied

    def load(self):
        self.world.set_heap(12 * MiB)

    def edit(self, burst):
        self.world.set_heap(14 * MiB)
        return {"applied": self.applied, "beforeText": self.before, "editorText": self.after}


class EditWitness(unittest.TestCase):
    def _trial(self, before, after, *, applied=True):
        world = World()
        clock = ManualClock(world, disturb=False)
        directory = tempfile.mkdtemp()
        sampler = ResourceSampler(
            FakeRun(directory),
            FakePage(world),
            FakeCdp(world),
            process_reader=lambda: [dict(row) for row in world.processes],
            platform_name="darwin",
            clock=clock,
        )
        return collect_phases(
            sampler,
            _TextSession(world, before, after, applied=applied),
            clock,
            quiescence=QUIESCENCE,
            edit_burst=EDIT_BURST,
            editor_id="fake",
            workload_id="prose-500w",
            workload_meta={"sha256": "a" * 64, "byte_size": 8, "paragraph_count": 1, "word_count": 8},
            execution_profile="ci_broad",
            host_class="ci_coarse",
        )

    def test_preexisting_eight_b8_is_refused(self):
        """preexisting.py: a read-only node that already contains 8×B8 is not this burst."""
        text = "B8" * 8
        trial = self._trial(text, text)
        self.assertEqual(trial["outcome"], "refused")
        self.assertEqual(trial["refusal_code"], "edit_not_applied")
        self.assertNotIn("C19", trial["criteria"])

    def test_delta_of_eight_is_this_burst(self):
        """The text delta is the witness. A false applied flag does not refuse it."""
        trial = self._trial("ready", "ready" + ("B8" * 8), applied=False)
        self.assertEqual(trial.get("outcome"), "measured", trial.get("refusal_code"))
        self.assertIn("C19", trial["criteria"])

    def test_host_check_uses_before_and_after(self):
        world = World()
        clock = ManualClock(world, disturb=False)
        directory = tempfile.mkdtemp()
        sampler = ResourceSampler(
            FakeRun(directory),
            FakePage(world),
            FakeCdp(world),
            process_reader=lambda: [dict(row) for row in world.processes],
            platform_name="darwin",
            clock=clock,
        )

        class Session(_TextSession):
            def edit_check(self):
                return {"before": "B8" * 8, "after": "B8" * 8}

            def edit(self, burst):
                self.world.set_heap(14 * MiB)
                return {"applied": True, "editorText": "B8" * 8}

        trial = collect_phases(
            sampler,
            Session(world, "", ""),
            clock,
            quiescence=QUIESCENCE,
            edit_burst=EDIT_BURST,
            editor_id="fake",
            workload_id="prose-500w",
            workload_meta={"sha256": "b" * 64, "byte_size": 8, "paragraph_count": 1, "word_count": 8},
            execution_profile="ci_broad",
            host_class="ci_coarse",
        )
        self.assertEqual(trial["refusal_code"], "edit_not_applied")


class _NativeCdp:
    """Playwright's Python CDPSession: send and on, no events()."""

    def __init__(self, world=None, *, flatten_required=False):
        self.world = world
        self.flatten_required = flatten_required
        self.handlers = {}
        self.inner = FakeCdp(world) if world is not None else None

    def on(self, method, handler):
        self.handlers.setdefault(method, []).append(handler)

    def emit(self, method, params):
        for handler in self.handlers.get(method, []):
            handler(params)

    async def send(self, method, params=None):
        if method == "Target.setAutoAttach":
            if self.flatten_required and not (params or {}).get("flatten"):
                raise RuntimeError("Only flatten protocol is supported with browser level auto-attach")
            return {}
        if self.inner is None:
            return {}
        return self.inner.send(method, params)


class _AsyncPage:
    def __init__(self, world, browser_cdp):
        self.world = world
        self.inner = FakePage(world)
        self.handlers = {}
        self.context = SimpleNamespace(
            browser=SimpleNamespace(new_browser_cdp_session=self._browser),
            on=self._on_context,
            service_workers=lambda: [],
        )
        self._browser_cdp = browser_cdp
        self._context_handlers = {}

    async def _browser(self):
        return self._browser_cdp

    def _on_context(self, event, handler):
        self._context_handlers.setdefault(event, []).append(handler)

    def on(self, event, handler):
        self.handlers.setdefault(event, []).append(handler)

    async def evaluate(self, expression):
        return self.inner.evaluate(expression)


class NativeAsyncTransport(unittest.TestCase):
    def test_page_bytes_and_a_worker_request_without_events_method(self):
        """async_live.py: CDPSession has no events(); the adapter must still count."""
        world = World()
        clock = ManualClock(world, disturb=False)
        page_cdp = _NativeCdp(world)
        browser_cdp = _NativeCdp(flatten_required=True)
        page = _AsyncPage(world, browser_cdp)
        directory = tempfile.mkdtemp()
        sampler = AsyncResourceSampler(
            FakeRun(directory),
            page,
            page_cdp,
            process_reader=lambda: [dict(row) for row in world.processes],
            platform_name="darwin",
            clock=clock,
        )

        class WorkerRequest:
            service_worker = object()
            frame = None
            _guid = "worker-1"

            async def sizes(self):
                return {"responseHeadersSize": 81, "responseBodySize": 5 * MiB}

        async def run():
            await sampler.install()
            page_cdp.emit("Network.loadingFinished", {
                "requestId": "page-1",
                "encodedDataLength": 1000,
            })
            for handler in page._context_handlers.get("requestfinished", []):
                handler(WorkerRequest())
            return await sampler.sample()

        sample = asyncio.run(run())
        self.assertFalse(hasattr(page_cdp, "events"))
        self.assertEqual(sample["network_observation"], "ok", sample.get("network_observation_reason"))
        self.assertGreaterEqual(sample["network_encoded_bytes"], 5 * MiB + 1000)
        self.assertLess(sample["network_encoded_bytes"], 5 * MiB + 1000 + 4096)

    def test_no_worker_subscription_is_a_complete_numeric_total(self):
        world = World()
        clock = ManualClock(world, disturb=False)
        page_cdp = _NativeCdp(world)
        page = _AsyncPage(world, _NativeCdp(flatten_required=True))
        sampler = AsyncResourceSampler(
            FakeRun(tempfile.mkdtemp()),
            page,
            page_cdp,
            process_reader=lambda: [dict(row) for row in world.processes],
            platform_name="darwin",
            clock=clock,
        )

        async def run():
            await sampler.install()
            return await sampler.sample()

        sample = asyncio.run(run())
        self.assertEqual(sample["network_observation"], "ok", sample.get("network_observation_reason"))
        self.assertIsInstance(sample["network_encoded_bytes"], int)
        self.assertEqual(sample["network_encoded_bytes"], 0)


def _playwright_ui():
    candidate = REPO / "harness" / "ui" / "node_modules" / "playwright" / "index.mjs"
    if candidate.is_file() and shutil.which("node"):
        return candidate
    return None


class _SessionBox:
    def __init__(self, root):
        self.root = root
        self.host = StaticHost(root)
        self.sessions = []
        self.errors = []

    def launch(self, name):
        proc = subprocess.Popen(
            ["node", str(SESSION)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        threading.Thread(target=lambda: self.errors.extend(proc.stderr.readlines()), daemon=True).start()
        bridge = _Bridge(proc, self.errors)
        self.sessions.append((proc, bridge))
        result = bridge.request("launch", {
            "url": self.host.url + "/index.html",
            "profileDir": str(self.root / name),
            "corpusPath": str(self.root / "corpus.docx"),
            "readySelector": "#editor",
            "editSelector": "#editor",
        })
        return bridge, result["browserPid"]

    def close(self):
        for proc, bridge in self.sessions:
            if proc.poll() is None:
                try:
                    bridge.request("close", timeout=15)
                except Exception:
                    pass
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
        self.host.stop()


@unittest.skipUnless(_playwright_ui(), "harness/ui playwright is required for the live session")
class LiveSessionProbes(unittest.TestCase):
    def test_no_worker_page_and_worker_download(self):
        """live4.py: a page with no workers is complete, and the worker fetch counts."""
        root = Path(tempfile.mkdtemp())
        try:
            (root / "corpus.docx").write_bytes(b"fake")
            (root / "asset.bin").write_bytes(b"\0" * (5 * MiB))
            (root / "worker.bin").write_bytes(b"\1" * (5 * MiB))
            (root / "sw.js").write_text(
                "self.addEventListener('install', e => self.skipWaiting());"
                "self.addEventListener('activate', e => e.waitUntil(clients.claim()));"
                "self.addEventListener('message', e => e.waitUntil("
                "fetch('/worker.bin').then(r => r.arrayBuffer()).then(b => e.ports[0].postMessage(b.byteLength))));"
            )
            (root / "index.html").write_text(
                '<div id="editor">ready</div>'
                '<script>window.__asset = fetch("/asset.bin").then(r => r.arrayBuffer()).then(b => b.byteLength);</script>'
            )
            box = _SessionBox(root)
            try:
                bridge, pid = box.launch("one")
                bridge.request("load", timeout=60)
                page = _BridgePage(bridge)
                self.assertEqual(page.evaluate("() => window.__asset"), 5 * MiB)
                run = SimpleNamespace(
                    editor_browser_pid=pid,
                    static_server_pid=os.getpid(),
                    profile_dir=root / "one",
                    bundle_path=root,
                )
                sampler = ResourceSampler(run, page, _BridgeCdp(bridge), clock=WallClock())
                loaded = sampler.sample()
                self.assertEqual(loaded["network_observation"], "ok", loaded.get("network_observation_reason"))
                self.assertIsInstance(loaded["network_encoded_bytes"], int)
                self.assertGreaterEqual(loaded["network_encoded_bytes"], 5 * MiB)
                self.assertLess(loaded["network_encoded_bytes"], 6 * MiB)
                page.evaluate(
                    "() => navigator.serviceWorker.register('/sw.js').then(() => navigator.serviceWorker.ready)"
                )
                sampler.mark("worker_download")
                count = page.evaluate(
                    "() => navigator.serviceWorker.ready.then(r => new Promise(resolve => {"
                    " const c = new MessageChannel();"
                    " c.port1.onmessage = e => resolve(e.data);"
                    " r.active.postMessage('fetch', [c.port2]);"
                    " }))"
                )
                after = sampler.sample()
                delta = sampler.totals("worker_download")["network_encoded_bytes"]
                self.assertEqual(count, 5 * MiB)
                self.assertEqual(after["network_observation"], "ok", after.get("network_observation_reason"))
                self.assertIsInstance(delta, int)
                self.assertGreaterEqual(delta, 5 * MiB)
                self.assertLess(delta, 5 * MiB + MiB)
            finally:
                box.close()
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_preexisting_text_refuses_edit_not_applied(self):
        """preexisting.py: the production driver must refuse a node that already says B8×8."""
        root = Path(tempfile.mkdtemp())
        try:
            (root / "corpus.docx").write_bytes(b"fake")
            (root / "index.html").write_text('<div id="editor">B8B8B8B8B8B8B8B8</div>')
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
                sampler = ResourceSampler(run, page, _BridgeCdp(bridge), clock=WallClock())

                class Session:
                    has_save = False

                    def load(self):
                        bridge.request("load", timeout=60)

                    def edit(self, burst):
                        return bridge.request("edit", {
                            "selector": "#editor",
                            "text": burst["text"],
                            "repetitions": burst["repetitions"],
                        }, timeout=60)

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
                text = page.evaluate('() => document.querySelector("#editor").textContent')
                self.assertEqual(text, "B8" * 8)
                self.assertEqual(trial["outcome"], "refused")
                self.assertEqual(trial["refusal_code"], "edit_not_applied")
                self.assertNotIn("C19", trial["criteria"])
            finally:
                box.close()
        finally:
            shutil.rmtree(root, ignore_errors=True)


def _chromium_shell():
    root = Path.home() / "Library" / "Caches" / "ms-playwright"
    found = sorted(root.glob("chromium_headless_shell-*/chrome-headless-shell-*/chrome-headless-shell"))
    return found[-1] if found else None


def _python_playwright_ready():
    if _chromium_shell() is None:
        return False
    try:
        import importlib.util
        return importlib.util.find_spec("playwright") is not None
    except (ImportError, ValueError):
        return False


@unittest.skipUnless(
    _python_playwright_ready(),
    "python playwright and the cached headless shell are required for the native transport",
)
class NativeAsyncLive(unittest.TestCase):
    def test_page_download_worker_download_and_no_worker_complete(self):
        """async_live.py: a real CDPSession has no events(); load and worker bytes still count."""
        from playwright.async_api import async_playwright

        root = Path(tempfile.mkdtemp())
        host = None
        try:
            (root / "asset.bin").write_bytes(b"\0" * (5 * MiB))
            (root / "worker.bin").write_bytes(b"\1" * (5 * MiB))
            (root / "sw.js").write_text(
                "self.addEventListener('install', (event) => self.skipWaiting());"
                "self.addEventListener('activate', (event) => event.waitUntil(clients.claim()));"
                "self.addEventListener('message', (event) => event.waitUntil("
                "fetch('/worker.bin').then((response) => response.arrayBuffer())"
                ".then((body) => event.ports[0].postMessage(body.byteLength))));"
            )
            (root / "index.html").write_text(
                "<div id=\"editor\">ready</div>"
                "<script>window.__asset = fetch('/asset.bin').then((response) => response.arrayBuffer())"
                ".then((body) => body.byteLength);</script>"
            )
            host = StaticHost(root)
            shell = _chromium_shell()

            async def run():
                async with async_playwright() as pw:
                    browser = await pw.chromium.launch(executable_path=str(shell), headless=True)
                    try:
                        page = await browser.new_page()
                        cdp = await page.context.new_cdp_session(page)
                        self.assertFalse(hasattr(cdp, "events"))
                        sampler = AsyncResourceSampler(
                            SimpleNamespace(editor_browser_pid=None, static_server_pid=os.getpid(), profile_dir=None, bundle_bytes=0),
                            page,
                            cdp,
                            clock=WallClock(),
                        )
                        await sampler.install()
                        quiet = await sampler.sample()
                        await page.goto(host.url + "/index.html", wait_until="domcontentloaded")
                        asset = await page.evaluate("window.__asset")
                        loaded = await sampler.sample()
                        await sampler.mark("worker_download")
                        await page.evaluate(
                            "navigator.serviceWorker.register('/sw.js').then(() => navigator.serviceWorker.ready)"
                        )
                        count = await page.evaluate(
                            "navigator.serviceWorker.ready.then((registration) => new Promise((resolve) => {"
                            " const channel = new MessageChannel();"
                            " channel.port1.onmessage = (event) => resolve(event.data);"
                            " registration.active.postMessage('fetch', [channel.port2]);"
                            " }))"
                        )
                        after = await sampler.sample()
                        delta = sampler.totals("worker_download")["network_encoded_bytes"]
                        return quiet, loaded, after, count, delta, asset
                    finally:
                        await browser.close()

            quiet, loaded, after, count, delta, asset = asyncio.run(run())
            self.assertEqual(asset, 5 * MiB)
            self.assertEqual(quiet["network_observation"], "ok", quiet.get("network_observation_reason"))
            self.assertEqual(quiet["network_encoded_bytes"], 0)
            self.assertEqual(loaded["network_observation"], "ok", loaded.get("network_observation_reason"))
            self.assertIsInstance(loaded["network_encoded_bytes"], int)
            self.assertGreaterEqual(loaded["network_encoded_bytes"], 5 * MiB)
            self.assertLess(loaded["network_encoded_bytes"], 6 * MiB)
            self.assertEqual(count, 5 * MiB)
            self.assertEqual(after["network_observation"], "ok", after.get("network_observation_reason"))
            self.assertIsInstance(delta, int)
            self.assertGreaterEqual(delta, 5 * MiB)
            self.assertLess(delta, 5 * MiB + MiB)
        finally:
            if host is not None:
                host.stop()
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
