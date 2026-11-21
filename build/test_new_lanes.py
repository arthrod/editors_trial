"""The lanes added on 2026-11-21 (react-docx, OpenDoc, BetterOffice, OnlyOffice's converter)
and Univer's probe: each is pinned exactly, and each lane is in every runner."""
import json
import re
import unittest
from pathlib import Path

BUILD = Path(__file__).resolve().parent
ROOT = BUILD.parent
LANES = ("reactdocx", "opendoc", "betteroffice", "onlyoffice")
# harness folder -> the packages whose exact version is the pin
NPM_PINS = {
    "reactdocx": ("@extend-ai/react-docx",),
    "betteroffice": ("@betteroffice/docx",),
    "univer": ("@univerjs/presets", "@univerjs/preset-docs-core"),
}
EXACT = re.compile(r"^\d+\.\d+\.\d+(-[0-9A-Za-z.]+)?$")


class Pins(unittest.TestCase):
    def test_every_npm_pin_is_an_exact_version_with_a_lockfile_and_the_cooldown(self):
        for folder, packages in NPM_PINS.items():
            d = ROOT / "harness" / folder
            deps = json.loads((d / "package.json").read_text())["dependencies"]
            for name in packages:
                self.assertRegex(deps[name], EXACT, f"{folder}: {name}")
            self.assertTrue((d / "pnpm-lock.yaml").is_file(), folder)
            # AGENTS.md section 1: nothing younger than 5 days is installed
            self.assertIn("minimumReleaseAge: 7200", (d / "pnpm-workspace.yaml").read_text(), folder)

    def test_the_release_archive_is_pinned_by_tag_and_hash(self):
        pin = json.loads((ROOT / "harness/onlyoffice/pin.json").read_text())["x2t"]
        self.assertRegex(pin["sha512"], r"^[0-9a-f]{128}$")
        self.assertIn(pin["tag"].replace("+", "%2B"), pin["url"])
        self.assertRegex(pin["published"], r"^\d{4}-\d{2}-\d{2}T")
        # the driver checks the hash before it unpacks anything
        fetch = (ROOT / "harness/onlyoffice/fetch.mjs").read_text()
        self.assertLess(fetch.index("SHA-512 mismatch"), fetch.index("execFileSync('unzip'"))

    def test_the_opendoc_harness_builds_against_the_checkout_and_its_toolchain(self):
        d = ROOT / "harness/opendoc"
        self.assertIn('path = "../../repos/opendoc/crates/opendoc"', (d / "Cargo.toml").read_text())
        self.assertTrue((d / "Cargo.lock").is_file())
        self.assertIn("channel", (d / "rust-toolchain.toml").read_text())


class Runners(unittest.TestCase):
    def lines(self, script, verb):
        text = (BUILD / script).read_text().replace("\\\n", " ")
        return {l.split()[1]: l for l in text.splitlines() if l.startswith(verb + " ")}

    def test_every_new_lane_is_in_the_round_trip_the_second_pass_and_the_broken_corpus(self):
        for script, verb in (("run_all.sh", "run"), ("run_second_pass.sh", "second"), ("run_broken.sh", "run")):
            have = self.lines(script, verb)
            for lane in LANES:
                self.assertIn(lane, have, f"{script}: {lane}")
                self.assertIn(f"harness/{lane} ", have[lane], f"{script}: {lane}")

    def test_the_second_pass_feeds_each_new_lane_its_own_output(self):
        have = self.lines("run_second_pass.sh", "second")
        for lane in LANES:
            self.assertIn("'__IN__' '__OUT__'", have[lane], lane)

    def test_the_broken_corpus_run_writes_under_its_output_root(self):
        have = self.lines("run_broken.sh", "run")
        for lane in LANES:
            self.assertIn(f"$IN $OUTROOT/{lane}/complex.docx", have[lane], lane)

    def test_the_editor_session_lane_is_a_lane_not_a_participant(self):
        import sys
        sys.path.insert(0, str(BUILD))
        import facts
        import lanes
        self.assertEqual(lanes.PENDING_SLUGS, list(LANES))
        self.assertEqual(lanes.PENDING_LANES, ["betteroffice-editor"])
        self.assertIn("betteroffice-editor", facts.LANES)
        self.assertIn("betteroffice-editor", self.lines("run_all.sh", "run"))

    def test_a_pending_lane_is_out_of_the_release_s_facts_and_scores_unless_asked(self):
        import sys
        sys.path.insert(0, str(BUILD))
        import facts
        import lanes
        for slug in lanes.PENDING_SLUGS + lanes.PENDING_LANES:
            self.assertNotIn(slug, facts.TOOLS, slug)
            self.assertIn(slug, facts.PENDING_TOOLS, slug)
        # Published lanes (lanes.PUBLISHED_IN) are in every run; before that, only on request.
        self.assertEqual(lanes.requested([]), bool(lanes.PUBLISHED_IN))
        self.assertTrue(lanes.requested(["--pending"]))
        import os
        from unittest import mock
        with mock.patch.dict(os.environ, {"TRIAL_PENDING": "0"}):
            self.assertFalse(lanes.requested(["--pending"]), "TRIAL_PENDING=0 reproduces an earlier release")
        for name in ("score_all.py", "score_extra.py"):
            text = (BUILD / name).read_text()
            self.assertIn("lanes.requested()", text, name)
            for slug in lanes.PENDING_SLUGS:
                self.assertNotIn(f'"{slug}"', text, f"{name} names {slug} outside build/lanes.py")
        # a development summary never overwrites the release's
        self.assertIn('SUMMARY = "summary.pending.json"', (BUILD / "score_all.py").read_text())

    def test_univer_has_no_lane_only_a_probe(self):
        for script, verb in (("run_all.sh", "run"), ("run_second_pass.sh", "second"), ("run_broken.sh", "run")):
            self.assertNotIn("univer", self.lines(script, verb))
        self.assertTrue((ROOT / "harness/univer/probe.mjs").is_file())

    def test_the_round_trip_runs_univer_s_probe_and_keeps_its_result(self):
        text = (BUILD / "run_all.sh").read_text()
        self.assertIn('node probe.mjs "$BASE/out/univer/probe.json"', text)
        import json
        import sys
        import tempfile
        sys.path.insert(0, str(BUILD))
        import facts
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "probe.json"
            p.write_text(json.dumps({"docx_path": "none", "packages_read": 16, "hits": 0, "packages": {}}))
            f: dict = {}
            facts.probe_facts(p, f)
            self.assertEqual(f, {"probe.univer.docx_path": "none", "probe.univer.packages": 16, "probe.univer.hits": 0})
            p.write_text(json.dumps({"docx_path": "maybe", "packages_read": 16, "hits": 0}))
            with self.assertRaises(ValueError):
                facts.probe_facts(p, {})


class HostilePackages(unittest.TestCase):
    """Report D: the sandbox runs each new lane through the same entry the round trip uses."""
    def setUp(self):
        import sys
        sys.path.insert(0, str(BUILD))
        import run_bomb_sandbox
        self.sb = run_bomb_sandbox
        self.tools = {t[0]: t for t in run_bomb_sandbox._tools(Path("/w/B1.docx"), Path("/w/out"), pending=True)}
        self.published = {t[0] for t in run_bomb_sandbox._tools(Path("/w/B1.docx"), Path("/w/out"), pending=False)}

    def test_every_new_lane_is_in_the_sandbox_with_its_round_trip_entry(self):
        for lane in LANES + ("betteroffice-editor",):
            self.assertIn(lane, self.tools, lane)
        for lane in ("reactdocx", "betteroffice", "betteroffice-editor", "onlyoffice"):
            _, cwd, cmd, _ = self.tools[lane]
            self.assertEqual(cwd, ROOT / "harness" / lane.replace("-editor", ""), lane)
            self.assertEqual(cmd[1:4], ["roundtrip.mjs", "/w/B1.docx", "/w/out/out.docx"], lane)
        self.assertEqual(self.tools["betteroffice"][2][4], "model")
        self.assertEqual(self.tools["betteroffice-editor"][2][4], "editor")
        self.assertEqual(self.tools["opendoc"][2], [self.sb.OD, "/w/B1.docx", "/w/out/out.docx"])
        self.assertTrue(self.sb.OD.endswith("harness/opendoc/target/release/opendoc-harness"))

    def test_the_browser_lane_is_contained_as_apryse_is(self):
        env = self.tools["reactdocx"][3]
        self.assertEqual(env["REACTDOCX_NO_CHROME_SANDBOX"], "1")
        self.assertEqual(env["REACTDOCX_VITE_CACHE"], "/w/out/vite-cache")
        self.assertIn("PLAYWRIGHT_BROWSERS_PATH", env)
        self.assertEqual(self.sb.PROFILE_EXTRA["reactdocx"], self.sb.PROFILE_EXTRA["apryse"])
        # the harness reads exactly those two switches
        text = (ROOT / "harness/reactdocx/roundtrip.mjs").read_text() + (ROOT / "harness/reactdocx/vite.config.mjs").read_text()
        for name in ("REACTDOCX_NO_CHROME_SANDBOX", "REACTDOCX_VITE_CACHE"):
            self.assertIn(name, text)

    def test_the_sandbox_s_clock_not_the_harness_s_calls_a_stalled_converter_a_hang(self):
        # The lane's own watchdog exits 1, which the sandbox would label an error exit.
        # Inside the sandbox it is set past the wall clock, so a stall is killed and labelled a hang.
        self.assertGreater(int(self.tools["onlyoffice"][3]["X2T_TIMEOUT_S"]), self.sb.WALL)

    def test_the_converter_is_fetched_before_the_sandbox_not_inside_it(self):
        # No network inside: the sandbox entry must not be the one that downloads.
        self.assertNotIn("fetch.mjs", " ".join(self.tools["onlyoffice"][2]))

    def test_the_labels_cover_every_sandboxed_tool(self):
        text = (BUILD / "label_protection.py").read_text()
        order = re.search(r"order = \[(.*?)\]", text, re.S).group(1)
        labelled = set(re.findall(r'"([^"]+)"', order))
        self.assertEqual(labelled - {"libreoffice"}, self.published)
        self.assertIn("order += lanes.PENDING_SLUGS + lanes.PENDING_LANES", text)
        import lanes
        self.assertEqual(set(self.tools) - self.published, set(lanes.PENDING_SLUGS + lanes.PENDING_LANES))


class Speed(unittest.TestCase):
    """Report E: the headless speed runner times the same entries, and can name their pins."""
    def test_every_headless_lane_prints_the_two_marks_the_runner_reads(self):
        for path in ("harness/opendoc/src/main.rs", "harness/betteroffice/roundtrip.mjs", "harness/onlyoffice/roundtrip.mjs"):
            text = (ROOT / path).read_text()
            for mark in ("PERF model_ready_ms=", "PERF save_ms="):
                self.assertIn(mark, text, f"{path}: {mark}")

    def test_the_runner_has_a_lane_provenance_and_pin_for_each(self):
        import sys
        sys.path.insert(0, str(ROOT))
        from perf import pins
        from perf.runner import speed_headless as sh
        lanes = sh.default_lanes()
        for lane in ("opendoc", "betteroffice", "onlyoffice"):
            self.assertIn(lane, lanes, lane)
            self.assertIn(lane, sh.ATTEST, lane)
            self.assertIn(lane, pins._FACTS_KEYS, lane)
        self.assertEqual(sh.BUILD_STEPS["opendoc"][1], "harness/opendoc")
        self.assertIn("host_start_ms", lanes["onlyoffice"]["marks"])
        # react-docx has no headless entry (harness/reactdocx/headless.mjs shows why): it is not timed here.
        self.assertNotIn("reactdocx", lanes)
        self.assertEqual(pins._FACTS_KEYS["opendoc"], ("ver.opendoc.commit",))
        self.assertEqual(pins._FACTS_KEYS["betteroffice"], ("ver.npm.betteroffice",))
        self.assertEqual(pins._FACTS_KEYS["onlyoffice"], ("ver.release.onlyoffice_x2t.tag",))


class OtherRegistries(unittest.TestCase):
    def test_word_is_offered_every_new_output_that_exists(self):
        import sys
        sys.path.insert(0, str(BUILD))
        text = (BUILD / "word_verdicts.py").read_text()
        self.assertIn("TOOLS = lanes.join(TOOLS, lambda name, slug, key: slug)", text)
        self.assertIn("TOOLS[-1:-1] = lanes.PENDING_LANES", text)

    def test_the_preserved_matrix_takes_pending_lanes_only_when_asked(self):
        text = (BUILD / "preserved_matrix.py").read_text()
        self.assertIn("if lanes.requested():", text)
        import sys
        sys.path.insert(0, str(BUILD))
        import preserved_matrix
        import lanes
        last = ("BetterOffice", "betteroffice") if lanes.requested() else ("Apryse", "apryse")
        self.assertEqual(preserved_matrix.TOOLS[-1], last)

    def test_the_namespace_map_reads_every_new_output(self):
        self.assertIn("TARGETS = lanes.join(TARGETS", (BUILD / "ns_map.py").read_text())

    def test_the_speed_runner_times_a_pending_lane_only_when_named_or_asked(self):
        text = (ROOT / "perf/runner/speed_headless.py").read_text()
        self.assertIn('if not args.editors and os.environ.get("TRIAL_PENDING") != "1":', text)


class Join(unittest.TestCase):
    """lanes.join: how every list of participants takes the pending lanes."""
    def setUp(self):
        import sys
        sys.path.insert(0, str(BUILD))
        import lanes
        self.lanes = lanes

    def test_nothing_moves_unless_asked(self):
        items = ["apryse", "libreoffice"]
        self.assertIs(self.lanes.join(items, on=False), items)
        import os
        from unittest import mock
        with mock.patch.dict(os.environ, {"TRIAL_PENDING": "0"}):
            self.assertEqual(self.lanes.names([]), {})
        if self.lanes.PUBLISHED_IN:
            self.assertEqual(set(self.lanes.names([])), set(self.lanes.KEYS.values()))

    def test_pending_lanes_go_before_the_baseline_in_the_list_s_own_shape(self):
        j = lambda items, make=None: self.lanes.join(items, make, on=True)
        with_out = [s for s in self.lanes.PENDING_SLUGS if self.lanes.has_output(s)]
        keys = [self.lanes.KEYS[s] for s in with_out]
        self.assertEqual(j(["apryse", "libreoffice"]), ["apryse"] + keys + ["libreoffice"])
        got = j([("Apryse", "out/apryse/complex.docx"), ("LibreOffice (baseline)", "out/lo_baseline/complex.docx")],
                lambda name, slug, key: (name, "out/%s/complex.docx" % slug))
        self.assertEqual(got[-1][0], "LibreOffice (baseline)")
        self.assertEqual([p for _, p in got[1:-1]], ["out/%s/complex.docx" % s for s in with_out])
        self.assertIsInstance(j((("a", 1),), lambda name, slug, key: (slug, 2)), tuple)
        self.assertEqual(j([("Apryse", "apryse")], lambda name, slug, key: (name, slug))[1:],
                         [(n, s) for n, s in self.lanes.PENDING if s in with_out])

    def test_a_lane_that_recorded_no_output_is_not_audited(self):
        import json
        import tempfile
        old = self.lanes.ROOT
        with tempfile.TemporaryDirectory() as tmp:
            self.lanes.ROOT = Path(tmp)
            try:
                d = Path(tmp) / "out" / "onlyoffice"
                d.mkdir(parents=True)
                (d / "no_output.json").write_text(json.dumps({"outcome": "did-not-return"}))
                self.assertFalse(self.lanes.has_output("onlyoffice"))
                self.assertTrue(self.lanes.has_output("opendoc"))
                self.assertNotIn("onlyoffice", self.lanes.join(["apryse"], on=True))
                (d / "complex.docx").write_bytes(b"PK")
                self.assertTrue(self.lanes.has_output("onlyoffice"))
            finally:
                self.lanes.ROOT = old



if __name__ == "__main__":
    unittest.main()
