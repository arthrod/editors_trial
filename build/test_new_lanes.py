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

    def test_the_editor_session_lane_is_scored_as_a_lane_not_a_participant(self):
        import sys
        sys.path.insert(0, str(BUILD))
        import facts
        self.assertIn("betteroffice-editor", facts.LANES)
        self.assertIn("betteroffice-editor", self.lines("run_all.sh", "run"))
        for lane in LANES:
            self.assertIn(lane, facts.TOOLS)

    def test_univer_has_no_lane_only_a_probe(self):
        for script, verb in (("run_all.sh", "run"), ("run_second_pass.sh", "second"), ("run_broken.sh", "run")):
            self.assertNotIn("univer", self.lines(script, verb))
        self.assertTrue((ROOT / "harness/univer/probe.mjs").is_file())


if __name__ == "__main__":
    unittest.main()
