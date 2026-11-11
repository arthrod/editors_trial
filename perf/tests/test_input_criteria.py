"""Criteria C04/C07/C08/C09 payload contract and honesty guardrails.

`perf/runner/criteria_input.mjs` (driven by
`perf/runner/warm_cold_browser.mjs --criteria ...`) emits one JSON payload per
page load. This module is the reference Python writer for it: it turns each
criterion entry into one immutable attempt with the same helpers the warm/cold
suite uses, and it refuses a payload that could produce a dishonest trial.

The runner that owns the hosts (`benchmark_warm_cold.py`) can lift
`trials_from_payload` as is; until then the tests below are the executable
contract. The smoke test runs only when a captured payload is pointed at:

    export PATH="$HOME/.local/bin:$HOME/Library/pnpm/bin:$HOME/.bun/bin:/opt/homebrew/bin:$HOME/.cargo/bin:$PATH"
    PERF_CRITERIA_SMOKE_PAYLOAD=perf/out/criteria_smoke/plate.json \
    PERF_CRITERIA_SMOKE_FIXTURE=perf/out/criteria_smoke/micro-paragraphs.docx \
      PYTHONPATH=. /opt/homebrew/bin/python3.13 -m unittest \
      perf.tests.test_input_criteria -v
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import unittest
import uuid
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from perf.analysis.publication_gate import trial_publishable_flags  # noqa: E402
from perf.analysis.summarize import summarize  # noqa: E402
from perf.fixtures.generate import (  # noqa: E402
    build_workload,
    correctness_fixtures,
    docx_zip_bytes,
)
from perf.fixtures.profiles import size_ladder  # noqa: E402
from perf.runner.artifacts import write_attempt  # noqa: E402
from perf.runner.benchmark_ci_contract import (  # noqa: E402
    INTERPRETATION_CONDITIONS,
    _finalize_publishable,
    _host_base,
    _trial_dict,
)
from perf.scenarios.catalog import scenarios  # noqa: E402
from perf.schema import OUTCOMES, load_trial, validate_environment, validate_trial  # noqa: E402

PROBE = REPO / "perf" / "runner" / "criteria_input.mjs"


from perf.tests.witness_records import publishable_witness_record
from perf.runner.criteria_input_io import (  # noqa: E402
    PAINT_MECHANISM,
    PROBE_SCHEMA,
    SUITE,
    _catalog,
    assert_distinct_samples,
    assert_payload_shape,
    env_for,
    trial_from_entry,
    trials_from_payload,
    write_trials_from_payload,
)


def fixture_identity():
    workload_row = next(w for w in size_ladder() if w["workload_id"] == "micro-paragraphs")
    built = build_workload(workload_row)
    cfs = correctness_fixtures()
    body = built["body"] + b"\n" + cfs["unicode"]
    docx_body = docx_zip_bytes(body)
    return workload_row, hashlib.sha256(docx_body).hexdigest(), len(docx_body)


def served_fixture_identity():
    """Identity of the bytes the probe actually served.

    `docx_zip_bytes` stamps each entry with the current time, so the same
    workload is a different file on every call. A smoke trial must name the
    hash of the file on disk, not of a fresh rebuild.
    """
    path = os.environ.get("PERF_CRITERIA_SMOKE_FIXTURE")
    if not path:
        return fixture_identity()
    data = Path(path).read_bytes()
    workload_row = next(w for w in size_ladder() if w["workload_id"] == "micro-paragraphs")
    return workload_row, hashlib.sha256(data).hexdigest(), len(data)


# --------------------------------------------------------------------- tests


def _entry(cid="C07", **overrides):
    catalog = _catalog()
    row = catalog[cid]
    entry = {
        "criterion_id": cid,
        "layer": row["layer"],
        "boundary": row["boundary"],
        "evidence": row["evidence"],
        "outcome": "measured",
        "samples_ms": [18.5, 21.25, 19.0],
        "failure_reason": None,
        "assertion": {"name": "x", "passed": True, "scope": "s", "checks": {}, "failures": []},
        "trial_hints": {"cache_state": "warm_steady", "repetition_unit": "fresh_process"},
        "observations": [
            {
                "frame_ms": 118.5,
                "sample_ms": 18.5,
                "witness": publishable_witness_record(118.5, 100.0),
            },
            {
                "frame_ms": 221.25,
                "sample_ms": 21.25,
                "witness": publishable_witness_record(221.25, 200.0),
            },
            {
                "frame_ms": 319.0,
                "sample_ms": 19.0,
                "witness": publishable_witness_record(319.0, 300.0),
            },
        ],
        "notes": [],
    }
    entry.update(overrides)
    if "observations" not in overrides:
        # Keep all three click observations, including when only one is retained.
        # Explicit/invalid evidence stays untouched for the refusal tests.
        for sample, observation in zip(entry["samples_ms"], entry["observations"]):
            if isinstance(sample, bool) or not isinstance(sample, (int, float)) or not math.isfinite(sample) or sample <= 0:
                continue
            arm = observation["witness"]["after_page_ms"]
            observation.update(
                frame_ms=arm + sample, sample_ms=sample,
                witness=publishable_witness_record(arm + sample, arm),
            )
    for index, observation in enumerate(entry["observations"]):
        observation.setdefault("observation_id", f"observation-{index}")
        if isinstance(observation.get("witness"), dict):
            observation.setdefault("input_ms", observation["witness"].get("after_page_ms"))
    if cid == "C07" and "observations" not in overrides:
        # The r3c07b contract: every retained click sample carries the
        # quiet-window proof (on the observation and inside its witness), a
        # fresh/untouched state, distinct coordinates, and the caret on its
        # clicked line — the same shape criteria_input.mjs emits.
        for index, observation in enumerate(entry["observations"]):
            y = 200.0 + index * 250.0
            quiet = {
                "required_ms": 1000, "budget_ms": 8000, "proven": True,
                "observed_ms": 1240.5, "start_page_ms": 2100.0,
                "end_page_ms": 3340.5, "changes_seen": 0, "events": [],
                "exhausted": False, "violated": False,
            }
            observation.setdefault("x", 640.0)
            observation.setdefault("y", y)
            observation.setdefault("line", {"top": y - 10, "bottom": y + 10})
            observation.setdefault("scope", "quiet_box_first_paint")
            observation.setdefault("anchor_inside", True)
            observation.setdefault("caret_on_clicked_line", True)
            observation.setdefault("quiet_window", dict(quiet))
            observation.setdefault("fresh_state", {"state": "untouched_verified"})
            if isinstance(observation.get("witness"), dict):
                observation["witness"].setdefault("quiet_window", dict(quiet))
    entry.setdefault("sample_observation_ids", [
        observation["observation_id"]
        for observation in entry["observations"][:len(entry["samples_ms"])]]
    )
    return entry


def _payload(entries, witness=None):
    return {
        "probe": "criteria_input",
        "schema": PROBE_SCHEMA,
        "criteria_requested": list(entries),
        "criteria": entries,
        "paint_witness": witness
        or {
            "mechanism": PAINT_MECHANISM,
            "frames_seen": 12,
            "timeout_ms": 2000,
            "frame_interval_ms": 16.667,
        },
    }


class CriteriaPayloadHonesty(unittest.TestCase):
    def test_measured_entry_without_samples_is_rejected(self):
        with self.assertRaises(ValueError):
            assert_payload_shape(_payload({"C07": _entry(samples_ms=[])}))

    def test_failed_action_never_carries_a_number(self):
        entry = _entry(outcome="failed", failure_reason="caret_not_on_clicked_line")
        with self.assertRaises(ValueError):
            assert_payload_shape(_payload({"C07": entry}))

    def test_measured_entry_whose_assertion_failed_is_rejected(self):
        entry = _entry(assertion={"name": "x", "passed": False, "checks": {}, "failures": ["y"]})
        with self.assertRaises(ValueError):
            assert_payload_shape(_payload({"C07": entry}))

    def test_refusal_needs_a_reason(self):
        entry = _entry(cid="C08", outcome="unsupported", samples_ms=[], failure_reason=None)
        with self.assertRaises(ValueError):
            assert_payload_shape(_payload({"C08": entry}))
        blank = _entry(cid="C08", outcome="unsupported", samples_ms=[], failure_reason="   ")
        with self.assertRaises(ValueError):
            assert_payload_shape(_payload({"C08": blank}))

    def test_refusal_with_reason_is_accepted(self):
        entry = _entry(
            cid="C08",
            outcome="unsupported",
            samples_ms=[],
            failure_reason="surface_not_dom_editable",
            observations=[],
        )
        entries = assert_payload_shape(_payload({"C08": entry}))
        self.assertEqual(entries["C08"]["outcome"], "unsupported")

    def test_zero_and_negative_samples_are_rejected(self):
        for bad in (0, 0.0, -1.5):
            with self.assertRaises(ValueError):
                assert_payload_shape(_payload({"C07": _entry(samples_ms=[bad])}))
        # C04 may legitimately be zero: nothing was deferred past ready.
        c04 = _entry(
            cid="C04",
            samples_ms=[0.0],
            trial_hints={"cache_state": "process_cold_fs_warm"},
            observations=[{"quiescent": True, "elapsed_from_ready_ms": 0.0}],
        )
        assert_payload_shape(_payload({"C04": c04}))
        with self.assertRaises(ValueError):
            assert_payload_shape(_payload({"C04": _entry(cid="C04", samples_ms=[-0.5])}))

    def test_copied_sample_vectors_are_rejected(self):
        shared_witness = publishable_witness_record(21.0, 1.0)
        shared_obs = {"input_ms": 1.0, "frame_ms": 21.0, "sample_ms": 20.0, "witness": shared_witness}
        entries = {
            "C07": _entry(cid="C07", samples_ms=[20.0, 20.0]),
            "C09": _entry(
                cid="C09",
                samples_ms=[20.0, 20.0],
                observations=[dict(shared_obs), dict(shared_obs)],
            ),
        }
        assert_payload_shape(_payload(entries))
        with self.assertRaises(ValueError):
            assert_distinct_samples(entries)
        distinct = {
            "C07": _entry(cid="C07", samples_ms=[20.0]),
            "C09": _entry(
                cid="C09",
                samples_ms=[21.0],
                observations=[
                    {"frame_ms": 22.0, "sample_ms": 21.0, "witness": publishable_witness_record(22.0, 1.0)},
                ],
            ),
        }
        assert_distinct_samples(distinct)

    def test_raf_callback_cannot_be_the_paint_witness(self):
        entry = _entry(observations=[{"raf_ms": 16.0}, {"raf_ms": 16.0}, {"raf_ms": 16.0}])
        payload = _payload({"C07": entry}, witness={"mechanism": "raf_callback", "frames_seen": 99})
        with self.assertRaises(ValueError):
            assert_payload_shape(payload)

    def test_measured_visible_entry_needs_a_frame_timestamp_per_sample(self):
        entry = _entry(observations=[{"frame_ms": 1.0}])
        with self.assertRaises(ValueError):
            assert_payload_shape(_payload({"C07": entry}))

    def test_measured_c07_needs_caret_evidence(self):
        observations = [
            {
                "frame_ms": 1.0,
                "point": "page_centre",
                "line": None,
                "scope": "dom_caret_on_clicked_line",
                "anchor_inside": True,
            },
            {
                "frame_ms": 2.0,
                "point": "first_text_line",
                "line": {"top": 1.0, "bottom": 2.0},
                "scope": "dom_caret_on_clicked_line",
                "caret_on_clicked_line": False,
            },
            {
                "frame_ms": 3.0,
                "point": "last_text_line",
                "line": {"top": 1.0, "bottom": 2.0},
                "scope": "dom_caret_on_clicked_line",
                "caret_on_clicked_line": True,
            },
        ]
        for index, obs in enumerate(observations):
            frame = float(obs["frame_ms"])
            obs["input_ms"] = frame
            obs["frame_ms"] = frame + 18.5
            obs["sample_ms"] = 18.5
            obs["witness"] = publishable_witness_record(frame + 18.5, frame)
            y = 200.0 + index * 250.0
            quiet = {
                "required_ms": 1000, "budget_ms": 8000, "proven": True,
                "observed_ms": 1240.5, "start_page_ms": 2100.0,
                "end_page_ms": 3340.5, "changes_seen": 0, "events": [],
                "exhausted": False, "violated": False,
            }
            obs["x"] = 640.0
            obs["y"] = y
            obs["quiet_window"] = dict(quiet)
            obs["witness"]["quiet_window"] = dict(quiet)
            obs["fresh_state"] = {"state": "untouched_verified"}
        with self.assertRaisesRegex(ValueError, "caret not on the clicked line"):
            assert_payload_shape(_payload({"C07": _entry(
                observations=observations, samples_ms=[18.5, 18.5, 18.5],
            )}))
        observations[1]["caret_on_clicked_line"] = True
        assert_payload_shape(
            _payload({"C07": _entry(observations=observations, samples_ms=[18.5, 18.5, 18.5])})
        )

    def test_layer_and_boundary_must_match_the_catalog(self):
        entry = _entry(cid="C07", boundary="presented_frame")
        with self.assertRaises(ValueError):
            assert_payload_shape(_payload({"C07": entry}))
        entry = _entry(cid="C04", layer="browser_visible", boundary="deferred_quiescence")
        with self.assertRaises(ValueError):
            assert_payload_shape(_payload({"C04": entry}))

    def test_unrequested_entry_is_rejected(self):
        entries = {"C07": _entry(), "C09": _entry(cid="C09")}
        payload = _payload({"C07": entries["C07"]})
        payload["criteria"]["C09"] = entries["C09"]
        with self.assertRaises(ValueError):
            assert_payload_shape(payload)

    def test_refusal_becomes_a_valid_trial(self):
        workload_row, sha, size = fixture_identity()
        entry = _entry(
            cid="C09",
            outcome="unsupported",
            samples_ms=[],
            failure_reason="surface_not_dom_editable",
            observations=[],
        )
        payload = _payload({"C09": entry})
        payload["editor_id"] = "wordcraft"
        trials = trials_from_payload(
            payload,
            editor_version="test",
            fixture_sha256=sha,
            workload_row=workload_row,
            docx_size=size,
        )
        trial = trials["C09"]
        self.assertEqual(trial["outcome"], "unsupported")
        self.assertEqual(trial["samples_ms"], [])
        self.assertEqual(trial["failure_reason"], "surface_not_dom_editable")
        validate_trial(trial)

    def test_measured_entry_becomes_a_blocked_valid_trial(self):
        workload_row, sha, size = fixture_identity()
        payload = _payload({"C07": _entry()})
        payload["editor_id"] = "plate"
        trials = trials_from_payload(
            payload,
            editor_version="test",
            fixture_sha256=sha,
            workload_row=workload_row,
            docx_size=size,
        )
        trial = trials["C07"]
        self.assertEqual(trial["outcome"], "measured")
        self.assertEqual(trial["samples_ms"], [19.0])
        self.assertEqual(trial["summary_stats"]["n"], 1)
        self.assertEqual(trial["environment"]["repetition_unit"], "fresh_process")
        validate_trial(trial)

    def test_probe_module_names_the_catalog_boundaries(self):
        source = PROBE.read_text(encoding="utf-8")
        catalog = _catalog()
        for cid in SUITE:
            row = catalog[cid]
            for key in ("layer", "boundary", "evidence"):
                self.assertIn(
                    "%s: '%s'" % (key, row[key]),
                    source,
                    "%s %s missing from criteria_input.mjs" % (cid, key),
                )
        self.assertIn(PAINT_MECHANISM, source)
        self.assertNotIn("raf_callback", source)


SMOKE_PAYLOAD = os.environ.get("PERF_CRITERIA_SMOKE_PAYLOAD")


class CriteriaSmoke(unittest.TestCase):
    @unittest.skipUnless(
        SMOKE_PAYLOAD,
        "set PERF_CRITERIA_SMOKE_PAYLOAD=<captured probe json> to write real attempts",
    )
    def test_smoke_payload_writes_valid_attempts(self):
        payload = json.loads(Path(SMOKE_PAYLOAD).read_text(encoding="utf-8"))
        workload_row, sha, size = served_fixture_identity()
        day = date.today().isoformat().replace("-", "_")
        attempt_dir = REPO / "perf" / "out" / ("criteria_smoke_%s" % day) / "attempts"
        written = write_trials_from_payload(
            payload,
            attempt_dir,
            editor_version="smoke",
            fixture_sha256=sha,
            workload_row=workload_row,
            docx_size=size,
        )
        self.assertEqual(len(written), len(payload["criteria_requested"]))
        for row in written.values():
            self.assertTrue(row["written"], row.get("failure_reason"))
        for row in written.values():
            trial = load_trial(row["path"].read_text(encoding="utf-8"))
            validate_trial(trial)
        observed = {}
        for cid, row in written.items():
            if row["written"]:
                trial = load_trial(row["path"].read_text(encoding="utf-8"))
                observed[trial["criterion_id"]] = trial["outcome"]
        self.assertTrue(observed, "no attempt written")


if __name__ == "__main__":
    unittest.main()


def test_default_observations_match_requested_samples():
    from perf.runner.witness import validate_witness

    for samples in ([8.5], [8.5, 20.0, 30.0]):
        entry = _entry(samples_ms=samples)
        assert len(entry["observations"]) == 3
        for sample, observation in zip(samples, entry["observations"]):
            witness = observation["witness"]
            assert validate_witness(witness)["ok"]
            assert observation["sample_ms"] == sample
            assert round(witness["frame_page_ms"] - witness["after_page_ms"], 3) == sample

    explicit = [{"deliberately": "invalid"}]
    assert _entry(samples_ms=[20.0], observations=explicit)["observations"] is explicit
    for sample in (0, -1, float("inf")):
        assert _entry(samples_ms=[sample])["samples_ms"][0] == sample
