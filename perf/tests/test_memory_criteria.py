"""Honesty rules for the C17/C19/C22 memory runner.

Pinned here:

* a sample that claims smaps/PSS/USS/cgroup numbers on this darwin host raises;
* an empty process tree is only a sample when it was explicitly reclaimed;
* a phase series copied into every phase raises;
* a refusal is an attempt with a non-empty ``failure_reason``;
* a measured memory cell is blocked on ``ci_coarse`` and names its byte unit;
* C22 is never measured where the host has no P0-P3 switch.
"""

import json
import tempfile
import unittest
from pathlib import Path

from perf.fixtures.profiles import size_ladder
from perf.runner.benchmark_ci_contract import EDITORS, _RUNNERS
from perf.runner.benchmark_memory import (
    BROWSER_TARGETS,
    FEATURE_SWITCH_PROBE,
    PROCESS_TARGETS,
    PROFILE_FEATURES,
    _c22_row,
    _env_for,
    _evidence,
    _feature_switch_reason,
    _row,
    _write_measured,
    _write_outcome,
    support_table,
)
from perf.runner.memory_tree import (
    assert_phases_not_copied,
    parse_ps,
    peak_process_tree,
    sample_process_tree,
    sample_process_trees,
    tree_pids,
    validate_tree_sample,
)
from perf.schema import validate_trial

PS_TABLE = """\
  100     1  1000
  101   100  2000
  102   101  3000
  200     1  4000
  201   200  5000
"""


def _workload_row():
    return next(row for row in size_ladder() if row["workload_id"] == "micro-paragraphs")


def _env(cache_state="process_cold_fs_warm", execution_profile="ci_contract"):
    return _env_for(
        editor_id="plate",
        editor_version="test-pin",
        fixture_sha="a" * 64,
        docx_size=4096,
        workload_row=_workload_row(),
        cache_state=cache_state,
        execution_profile=execution_profile,
    )


class TreeSampleHonesty(unittest.TestCase):
    def _sample(self, **overrides):
        sample = sample_process_tree(101, ps_reader=lambda: PS_TABLE, platform_name="darwin", now_ms=1_700_000_000_000)
        sample.update(overrides)
        return sample

    def test_darwin_sample_states_its_method_and_leaves_smaps_fields_null(self):
        sample = self._sample()
        validate_tree_sample(sample)
        self.assertEqual(sample["method"], "ps_rss_sum")
        self.assertEqual(sample["platform"], "darwin")
        self.assertEqual(sample["ps_command"], "ps -Ao pid=,ppid=,rss=")
        for key in ("pss_bytes", "uss_bytes", "cgroup_current_bytes", "cgroup_peak_bytes"):
            self.assertIsNone(sample[key], key)
        self.assertEqual(sample["rss_bytes"], (2000 + 3000) * 1024)
        self.assertEqual(sample["process_count"], 2)

    def test_fabricated_pss_on_darwin_raises(self):
        with self.assertRaises(ValueError):
            validate_tree_sample(self._sample(pss_bytes=4096))

    def test_fabricated_uss_on_darwin_raises(self):
        with self.assertRaises(ValueError):
            validate_tree_sample(self._sample(uss_bytes=4096))

    def test_fabricated_cgroup_on_darwin_raises(self):
        with self.assertRaises(ValueError):
            validate_tree_sample(self._sample(cgroup_current_bytes=4096))

    def test_smaps_method_is_refused_on_darwin(self):
        with self.assertRaises(ValueError):
            validate_tree_sample(self._sample(method="smaps_and_cgroup"))

    def test_sub_block_precision_raises(self):
        with self.assertRaises(ValueError):
            validate_tree_sample(self._sample(rss_bytes=5001))

    def test_live_tree_with_zero_rss_raises(self):
        with self.assertRaises(ValueError):
            validate_tree_sample(self._sample(rss_bytes=0))

    def test_empty_process_count_without_reclaim_raises(self):
        with self.assertRaises(ValueError):
            validate_tree_sample(self._sample(process_count=0, rss_bytes=0))

    def test_a_gone_process_is_not_a_zero_sample(self):
        with self.assertRaises(ValueError):
            sample_process_tree(999, ps_reader=lambda: PS_TABLE, platform_name="darwin")

    def test_reclaimed_process_must_be_declared(self):
        sample = sample_process_tree(999, ps_reader=lambda: PS_TABLE, platform_name="darwin", allow_empty=True)
        validate_tree_sample(sample)
        self.assertTrue(sample["empty_tree"])
        self.assertEqual(sample["rss_bytes"], 0)
        self.assertEqual(sample["process_count"], 0)

    def test_two_roots_count_a_shared_child_once(self):
        sample = sample_process_trees([100, 101], ps_reader=lambda: PS_TABLE, platform_name="darwin")
        validate_tree_sample(sample)
        self.assertEqual(sample["pids"], [100, 101, 102])
        self.assertEqual(sample["rss_bytes"], (1000 + 2000 + 3000) * 1024)
        self.assertEqual(sample["roots"], [100, 101])

    def test_missing_second_root_is_recorded_not_ignored(self):
        with self.assertRaises(ValueError):
            sample_process_trees([100, 999], ps_reader=lambda: PS_TABLE, platform_name="darwin")
        sample = sample_process_trees([100, 999], ps_reader=lambda: PS_TABLE, platform_name="darwin", allow_empty=True)
        self.assertEqual(sample["missing_roots"], [999])

    def test_walk_ignores_cycles_and_unparsable_rows(self):
        rows = parse_ps("header line\n 5 4 100\n 4 5 200\nnonsense\n")
        self.assertEqual([row["pid"] for row in rows], [5, 4])
        self.assertEqual(tree_pids(rows, 5), [4, 5])
        self.assertEqual(tree_pids(rows, 77), [])

    def test_peak_sampler_returns_the_observed_maximum(self):
        class FakeProc:
            def __init__(self):
                self.pid = 101
                self.reads = 0

            def poll(self):
                self.reads += 1
                return None if self.reads < 3 else 0

            def wait(self, timeout=None):
                return 0

        peak = peak_process_tree(FakeProc(), interval_s=0.001, ps_reader=lambda: PS_TABLE, platform_name="darwin")
        self.assertEqual(peak["observed_peak_rss_bytes"], 5000 * 1024)
        self.assertEqual(peak["exit_code"], 0)
        self.assertGreaterEqual(len(peak["samples"]), 1)


class CopiedSampleGuard(unittest.TestCase):
    def test_identical_phase_series_raises(self):
        with self.assertRaises(ValueError):
            assert_phases_not_copied({"ready": [1, 2], "edited": [1, 2], "quiescent": [1, 2]})

    def test_distinct_series_pass(self):
        assert_phases_not_copied({"ready": [1, 2], "edited": [3, 4], "quiescent": [5, 6]})

    def test_one_phase_is_not_a_comparison(self):
        with self.assertRaises(ValueError):
            assert_phases_not_copied({"ready": [1, 2]})

    def test_empty_phase_raises(self):
        with self.assertRaises(ValueError):
            assert_phases_not_copied({"ready": [], "quiescent": [1]})


class AttemptHonesty(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.attempt_dir = Path(self._tmp.name) / "attempts"

    def tearDown(self):
        self._tmp.cleanup()

    def test_measured_memory_cell_is_blocked_on_ci_coarse(self):
        path = _write_measured(
            attempt_dir=self.attempt_dir,
            criterion_id="C17",
            phase="ready",
            editor_id="plate",
            lane="browser_slate",
            env=_env(execution_profile="ci_broad"),
            samples_bytes=[64 * 1024 * 1024, 65 * 1024 * 1024],
            evidence=_evidence(phase="ready", method_sample=sample_process_tree(101, ps_reader=lambda: PS_TABLE, platform_name="darwin"), phases=("ready",)),
            diagnostic={"pairs": []},
        )
        trial = json.loads(path.read_text(encoding="utf-8"))
        validate_trial(trial)
        self.assertEqual(trial["samples_ms"], [64 * 1024 * 1024, 65 * 1024 * 1024])
        self.assertEqual(trial["sample_unit"], "bytes")
        self.assertFalse(trial["publishable"])
        self.assertTrue(trial["publication_block_reason"])
        self.assertEqual(trial["boundary"], "process_tree_sample")
        self.assertEqual(trial["layer"], "native")
        self.assertIsNone(trial["evidence"]["pss_bytes"])
        self.assertNotIn("claimed", trial["evidence"].get("smaps_rollup", ""))

    def test_a_float_byte_sample_is_refused(self):
        with self.assertRaises(ValueError):
            _write_measured(
                attempt_dir=self.attempt_dir,
                criterion_id="C17",
                phase="ready",
                editor_id="plate",
                lane="browser_slate",
                env=_env(),
                samples_bytes=[1.5],
                evidence={},
                diagnostic={},
            )

    def test_a_refusal_needs_a_reason(self):
        with self.assertRaises(ValueError):
            _write_outcome(
                attempt_dir=self.attempt_dir,
                criterion_id="C19",
                phase=None,
                editor_id="plate",
                lane="browser_slate",
                env=_env(),
                outcome="not_applicable",
                failure_reason="   ",
                evidence={},
            )

    def test_a_refusal_carries_no_samples_and_keeps_its_reason(self):
        path = _write_outcome(
            attempt_dir=self.attempt_dir,
            criterion_id="C19",
            phase=None,
            editor_id="libreoffice",
            lane="headless",
            env=_env(),
            outcome="not_applicable",
            failure_reason="one-shot lane has no live context to close",
            evidence={"state": "no_live_context"},
        )
        trial = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(trial["outcome"], "not_applicable")
        self.assertEqual(trial["samples_ms"], [])
        self.assertIsNone(trial["latency_ms"])
        self.assertEqual(trial["failure_reason"], "one-shot lane has no live context to close")

    def test_a_relative_fixture_path_raises_instead_of_failing_the_editor(self):
        from perf.runner.benchmark_memory import _process_rows

        with self.assertRaises(ValueError) as caught:
            _process_rows(
                editor_id="office-open",
                lane="library",
                attempt_dir=self.attempt_dir,
                args=type("Args", (), {"execution_profile": "ci_contract", "pairs": 1, "probe_timeout": 5})(),
                indocx=Path("relative/fixture.docx"),
                outdocx=Path("/tmp/out.docx"),
                fixture_sha="a" * 64,
                docx_size=4096,
                workload_row=_workload_row(),
            )
        self.assertIn("absolute", str(caught.exception))

    def test_attempts_are_written_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            attempt_dir = Path(tmp) / "attempts"
            _write_outcome(
                attempt_dir=attempt_dir,
                criterion_id="C19",
                phase=None,
                editor_id="plate",
                lane="browser_slate",
                env=_env(),
                outcome="not_applicable",
                failure_reason="no live context",
                evidence={},
            )
            self.assertEqual(len(list(attempt_dir.glob("*.json"))), 1)

    def test_evidence_says_how_it_was_sampled(self):
        evidence = _evidence(
            phase="ready",
            method_sample=sample_process_tree(101, ps_reader=lambda: PS_TABLE, platform_name="darwin"),
            phases=("ready", "after_edit_burst", "quiescent"),
        )
        self.assertEqual(evidence["method"], "ps_rss_sum")
        self.assertEqual(evidence["platform"], "darwin")
        self.assertIn("no /proc", evidence["smaps_rollup"])
        self.assertIsNone(evidence["pss_bytes"])
        self.assertIn("over-counts", evidence["shared_pages"])


class FeatureProfileHonesty(unittest.TestCase):
    def test_every_editor_has_an_inspection_record(self):
        self.assertEqual(set(FEATURE_SWITCH_PROBE), set(EDITORS))

    def test_reason_names_the_host_and_the_missing_switch(self):
        for editor_id in FEATURE_SWITCH_PROBE:
            reason = _feature_switch_reason(editor_id, "ci_broad")
            self.assertIn(editor_id, reason)
            self.assertIn("no P0-P3 feature profile", reason)
            for feature in PROFILE_FEATURES:
                self.assertIn(feature, reason)

    def test_no_host_actually_exposes_a_profile_switch(self):
        # If a host ever gains one, this test fails and C22 must be implemented
        # for it instead of being recorded not_applicable.
        for editor_id, (_host, _inspected, params) in FEATURE_SWITCH_PROBE.items():
            self.assertFalse(
                set(PROFILE_FEATURES) & set(params),
                "%s exposes a profile switch; C22 must be measured there" % (editor_id,),
            )

    def test_c22_is_recorded_not_applicable_with_a_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            attempt_dir = Path(tmp) / "attempts"
            args = type("Args", (), {"execution_profile": "ci_broad"})()
            _c22_row(
                editor_id="plate",
                lane="browser_slate",
                attempt_dir=attempt_dir,
                args=args,
                fixture_sha="a" * 64,
                docx_size=4096,
                workload_row=_workload_row(),
                editor_version="test-pin",
            )
            files = list(attempt_dir.glob("*.json"))
            self.assertEqual(len(files), 1)
            trial = json.loads(files[0].read_text(encoding="utf-8"))
            validate_trial(trial)
            self.assertEqual(trial["outcome"], "not_applicable")
            self.assertEqual(trial["criterion_id"], "C22")
            self.assertIn("no P0-P3 feature profile", trial["failure_reason"])
            self.assertEqual(trial["evidence"]["state"], "no_feature_profile_switch")


class BrowserFlowWithFakePairs(unittest.TestCase):
    """Drive _browser_rows end to end with injected pairs (no browser, no server)."""

    def _pair(self, *, edit_effective=True, reopen=True, retained=(700, 600)):
        ready = sample_process_tree(101, ps_reader=lambda: PS_TABLE, platform_name="darwin")
        edited = dict(ready, rss_bytes=ready["rss_bytes"] + 10 * 1024)
        quiescent = dict(ready, rss_bytes=ready["rss_bytes"] + 12 * 1024)
        reopened = dict(ready, rss_bytes=ready["rss_bytes"] + 400 * 1024)
        retention = [
            {"after_close_ms": 1000.0, "rss_bytes": retained[0] * 1024, "process_count": 2, "pids": [101, 102]},
            {"after_close_ms": 5000.0, "rss_bytes": retained[1] * 1024, "process_count": 2, "pids": [101, 102]},
        ]
        return {
            "index": 0,
            "roots": [101, 200],
            "ready": {"sample": ready, "probe": {"ready_ms": 10}},
            "edited": {
                "sample": edited,
                "probe": {
                    "edit_effective": edit_effective,
                    "text_length_before": 10,
                    "text_length_after": 20 if edit_effective else 10,
                    "typed_chars": 120,
                    "edit_error": None,
                },
            },
            "quiescent": {"sample": quiescent, "probe": {"idle_ms": 2000}},
            "closed": {"probe": {"context_closed": True}, "retention": retention},
            "reopened": {
                "sample": reopened,
                "probe": {"reopen_ready_ms": 30, "reopen_error": None if reopen else "context crashed"},
            },
            "result": {"ready_ms": 10},
            "retention": retention,
        }

    def _run(self, pair):
        from unittest import mock

        import perf.runner.benchmark_memory as module

        args = type(
            "Args",
            (),
            {
                "execution_profile": "ci_contract",
                "pairs": 1,
                "burst": 12,
                "quiescence_ms": 2000,
                "retain_seconds": (1.0, 5.0),
                "probe_timeout": 30.0,
            },
        )()
        attempt_dir = Path(self._tmp.name) / "attempts"
        with mock.patch.object(module, "_start_server", return_value=type("P", (), {"pid": 101})()):
            with mock.patch.object(module, "_stop_server", return_value=None):
                with mock.patch.object(module, "_run_browser_pair", return_value=pair):
                    with mock.patch.object(module, "_port_is_free", return_value=True):
                        rows = module._browser_rows(
                            editor_id="plate",
                            lane="browser_slate",
                            target={"url": "http://127.0.0.1:5299/", "corpus_route": "/corpus.docx"},
                            attempt_dir=attempt_dir,
                            args=args,
                            fixture_path=Path(self._tmp.name) / "fixture.docx",
                            fixture_sha="a" * 64,
                            docx_size=4096,
                            workload_row=_workload_row(),
                        )
        return rows, attempt_dir

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        Path(self._tmp.name, "fixture.docx").write_bytes(b"docx")

    def tearDown(self):
        self._tmp.cleanup()

    def test_healthy_pair_measures_three_phases_and_c19(self):
        rows, attempt_dir = self._run(self._pair())
        outcomes = [(row["criterion_id"], row["measurement_phase"], row["outcome"]) for row in rows]
        self.assertEqual(
            outcomes,
            [
                ("C17", "ready", "measured"),
                ("C17", "after_edit_burst", "measured"),
                ("C17", "quiescent", "measured"),
                ("C19", None, "measured"),
            ],
        )
        files = sorted(attempt_dir.glob("*.json"))
        self.assertEqual(len(files), 4)
        for path in files:
            trial = json.loads(path.read_text(encoding="utf-8"))
            validate_trial(trial)
            self.assertEqual(trial["sample_unit"], "bytes")
            self.assertFalse(trial["publishable"])
            self.assertTrue(trial["publication_block_reason"])
            self.assertIsNone(trial["evidence"]["pss_bytes"])
        c19 = next(t for t in (json.loads(p.read_text()) for p in files) if t["criterion_id"] == "C19")
        self.assertEqual(c19["samples_ms"], [600 * 1024])
        retention = c19["diagnostic"]["retention"][0]
        self.assertEqual(retention["retained_bytes"], 600 * 1024)
        self.assertEqual(
            retention["reattach_delta_bytes"],
            retention["reopened_bytes"] - retention["retained_bytes"],
        )
        self.assertEqual(c19["evidence"]["method"], "ps_rss_sum")

    def test_ineffective_burst_is_not_applicable_not_a_measurement(self):
        rows, _attempt_dir = self._run(self._pair(edit_effective=False))
        by_phase = {row["measurement_phase"]: row for row in rows if row["criterion_id"] == "C17"}
        self.assertEqual(by_phase["after_edit_burst"]["outcome"], "not_applicable")
        self.assertIn("accepted no text", by_phase["after_edit_burst"]["failure_reason"])
        self.assertEqual(by_phase["ready"]["outcome"], "measured")

    def test_failed_reopen_keeps_the_retention_evidence_and_fails_c19(self):
        rows, attempt_dir = self._run(self._pair(reopen=False))
        c19 = [row for row in rows if row["criterion_id"] == "C19"][0]
        self.assertEqual(c19["outcome"], "failed")
        self.assertIn("reopen failed", c19["failure_reason"])
        trial = json.loads((attempt_dir / Path(c19["attempt_file"]).name).read_text(encoding="utf-8"))
        self.assertEqual(trial["evidence"]["retained_samples"], [600 * 1024])

    def test_busy_port_is_not_run_and_never_killed(self):
        from unittest import mock

        import perf.runner.benchmark_memory as module

        args = type("Args", (), {"execution_profile": "ci_contract", "pairs": 1, "burst": 12, "quiescence_ms": 10, "retain_seconds": (1.0,), "probe_timeout": 30.0})()
        attempt_dir = Path(self._tmp.name) / "attempts"
        with mock.patch.object(module, "_port_is_free", return_value=False):
            rows = module._browser_rows(
                editor_id="docxodus",
                lane="wasm_editor",
                target={"url": "http://127.0.0.1:5210/", "corpus_route": "/corpus.docx"},
                attempt_dir=attempt_dir,
                args=args,
                fixture_path=Path(self._tmp.name) / "fixture.docx",
                fixture_sha="a" * 64,
                docx_size=4096,
                workload_row=_workload_row(),
            )
        self.assertEqual([row["outcome"] for row in rows], ["not_run", "not_run"])
        self.assertIn("another session", rows[0]["failure_reason"])


class LaneCoverage(unittest.TestCase):
    def test_headless_targets_mirror_the_contract_runner(self):
        self.assertEqual(set(PROCESS_TARGETS), set(_RUNNERS))

    def test_every_editor_has_a_lane(self):
        for editor_id in EDITORS:
            self.assertTrue(
                editor_id in BROWSER_TARGETS or editor_id in PROCESS_TARGETS,
                editor_id,
            )

    def test_support_table_covers_every_editor(self):
        rows = {row["editor_id"]: row for row in support_table()}
        self.assertEqual(set(rows), set(EDITORS))
        for editor_id, row in rows.items():
            self.assertTrue(row["browser_host"] or row["headless_process_lane"], editor_id)

    def test_support_table_distinguishes_typing_surfaces(self):
        rows = {row["editor_id"]: row for row in support_table()}
        self.assertIn("after_edit_burst", rows["plate"]["c17"])
        self.assertNotIn("after_edit_burst", rows["docxodus"]["c17"])

    def test_rows_reference_their_attempt(self):
        row = _row("C17", "ready", "plate", "measured", None, Path("/tmp/x/attempts/c17.json"))
        self.assertEqual(row["criterion_id"], "C17")
        self.assertEqual(row["measurement_phase"], "ready")
        self.assertEqual(row["editor_id"], "plate")

    def test_every_args_attribute_read_by_the_runner_exists(self):
        # A copy-pasted `args.probe_timeout_s' once killed a whole run after the
        # browser had booted.  Read the module source and require every attribute
        # to exist on the parsed namespace.
        import re

        import perf.runner.benchmark_memory as module

        namespace = vars(module._build_parser().parse_args(["--editor", "plate"]))
        source = Path(module.__file__).read_text(encoding="utf-8")
        used = set(re.findall(r"args\.([a-z_]+)", source))
        self.assertTrue(used)
        self.assertEqual(sorted(name for name in used if name not in namespace), [])


if __name__ == "__main__":
    unittest.main()
