#!/usr/bin/env python3
"""B5 — the C10 scroll criterion: scroll a real container, witness the frame.

The defect this runner fixes (#106): the C10 probe published a *measured*
scroll latency for hosts where nothing scrolled. The old probe looked for a
scroll container, and when it found none it skipped the scroll, timed two
``requestAnimationFrame`` callbacks and published the elapsed time anyway
(apryse 14 ms, docxodus 16 ms, docen 31 ms — one frame of nothing). It never
looked inside an open shadow root, so the hosts that scroll in one (apryse,
docen) were never found at all, and it ran on the 5-paragraph micro fixture,
where most hosts have nothing to scroll.

What this runner does instead:

* it runs on **prose-50kw** (the #100 size ladder), the workload that makes a
  document taller than the viewport;
* the **execution profile** and the **host class** belong to the *run*
  (``perf/runner/browser_run.py::run_cli`` owns them since #132); this lane
  reads them, refuses a profile whose workload cap does not admit prose-50kw,
  and records the schema's own verdict on the environment;
* every sample records the **container selector** it scrolled, the shadow host
  chain it lives under, the **`scrollTop` delta** it produced and the
  **movement of the document's content** — a frame that changed is not
  evidence that the document scrolled;
* the frame is **witnessed** by B1c's shared module (``witness.mjs``): the
  first presented frame at or after the scroll whose pixels really changed
  **inside the container's own box**, in the page's own clock, with the run's
  clock check (the pixel anchor's evidence) carried in the record;
* a sample with no container, an unmoved ``scrollTop``, an unmoved document, a
  witness that is not document-scoped or a clock skew above the bound is
  **refused with a reason** — ``not_applicable`` or ``failed``, never
  ``measured``;
* the trial's **publishability follows the policy**
  (``perf/analysis/publication_gate.py``): a ``ci_coarse`` host cannot publish
  visible latency and a distribution needs two independent samples; the lane
  never hardcodes the answer.

The Python side is the authority: every witness record is re-validated with
B1c's reader (``perf/runner/witness.py``) before a sample may become a
number, and a sample without a container selector or with a ``scrollTop``
delta of zero or less is refused even if the browser said it was fine.

Usage (production host)::

    python3 perf/runner/adversarial_c10_scroll.py --editor plate --out-root out/c10

Usage (the fake hosts of the acceptance measurers)::

    python3 perf/runner/adversarial_c10_scroll.py --fake-host \\
        perf/tests/fixtures/hosts/b5_scroll --fake-page prose.html --out-root out/c10 \\
        --execution-profile dedicated_publish
"""

from __future__ import annotations

import argparse
import contextlib
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2].resolve()
sys.path.insert(0, str(REPO))

from perf.adapters.capabilities import default_lane, pin_label  # noqa: E402
from perf.analysis.publication_gate import trial_publishable_flags  # noqa: E402
from perf.analysis.summarize import summarize  # noqa: E402
from perf.fixtures.docx_workload import workload_docx  # noqa: E402
from perf.fixtures.profiles import allowed_workloads, assert_workload_allowed, size_ladder  # noqa: E402
from perf.layers.classify import assert_visible_evidence  # noqa: E402
from perf.runner.artifacts import write_attempt  # noqa: E402
from perf.runner.browser_run import (  # noqa: E402
    ACTIVE,
    execution_profile as run_profile,
    fixture_path as run_fixture,
    host_class as run_host_class,
    record_process,
    run_cli,
    write_json,
)
from perf.runner.benchmark_ci_contract import INTERPRETATION_CONDITIONS, _trial_dict  # noqa: E402
from perf.runner.benchmark_warm_cold import BROWSER_TARGETS, _start_server, _stop_server  # noqa: E402
from perf.runner.witness import DEFAULT_SKEW_BOUND_MS, validate_witness  # noqa: E402
from perf.schema import validate_environment, validate_trial  # noqa: E402

#: The workload the scroll criterion runs on (#100's size ladder).
WORKLOAD_ID = "prose-50kw"

#: The execution profiles the runner accepts. They belong to the run
#: (``run_cli`` owns ``--execution-profile`` since #132); this lane only reads
#: them. ``dedicated_publish`` is the only profile whose workload cap admits
#: prose-50kw, so a run under ``ci_broad`` or ``ci_contract`` is refused with
#: a reason instead of measuring a smaller document.
EXECUTION_PROFILES = ("ci_contract", "ci_broad", "dedicated_publish")
DEFAULT_EXECUTION_PROFILE = "ci_broad"

#: The host class the environment records. ``dedicated`` is the publish
#: machine; ``ci_coarse`` is every other machine, and the default is the
#: honest one: a shared box never claims to be dedicated.
HOST_CLASSES = ("ci_coarse", "dedicated")
DEFAULT_HOST_CLASS = "ci_coarse"

#: The editor id of the fake hosts the acceptance measurers use.
FAKE_EDITOR = "b5-fake"
FAKE_EDITOR_VERSION = "fake-host:b5-scroll"

SCROLL_PROBE = REPO / "perf" / "runner" / "adversarial_c10_scroll.mjs"

#: The evidence the C10 trial claims. ``perf/layers/classify.py`` (B2's file)
#: says which evidence a ``browser_visible`` trial may carry.
VISIBLE_EVIDENCE = "presented_frame"

#: How far two rectangles may differ, in CSS pixels, before the witness's
#: region is not the container it claims to be.
REGION_TOLERANCE_PX = 2.0


# --------------------------------------------------------------------------- #
# The pure parts: the profile gate, the environment, the sample verdict
# --------------------------------------------------------------------------- #


def profile_admits_workload(execution_profile: str, workload_id: str = WORKLOAD_ID) -> bool:
    """Does this execution profile's workload cap admit this workload?

    ``ci_contract`` stops at prose-500w and ``ci_broad`` at prose-5kw, so
    neither admits prose-50kw; ``dedicated_publish`` admits every rung of the
    ladder.
    """
    return workload_id in allowed_workloads(execution_profile)


def scroll_fixture() -> dict:
    """The prose-50kw document: its bytes, its metadata and its ladder row."""
    row = next(r for r in size_ladder() if r["workload_id"] == WORKLOAD_ID)
    built = workload_docx(WORKLOAD_ID)
    return {**built, "workload_row": row}


def scroll_env(
    *,
    editor_id: str,
    editor_version: str,
    execution_profile: str,
    host_class: str,
    fixture: dict,
) -> dict:
    """The trial environment: the profile, the workload and the host facts.

    B1a's ``_host_base`` builds the same environment but validates it inside
    and takes the profile and the host class from the *run*. A run whose
    profile and host class do not satisfy ``perf/schema.py`` (a publish
    profile on a shared box) therefore cannot be described at all, and the
    lane could only crash or hide the complaint. The C10 lane has to be able
    to say *why* a trial is not publishable, so it builds the environment
    itself and records the schema's verdict next to it.
    ``test_the_environment_matches_b1s_builder`` pins the two together.
    """
    from perf.fixtures.profiles import feature_profile
    from perf.runner.benchmark_ci_contract import _host, _ram_bytes

    feats = feature_profile("P0")
    host = _host()
    row = fixture["workload_row"]
    return {
        "host_class": host_class,
        "execution_profile": execution_profile,
        "cpu_model": host["cpu_model"],
        "os": sys.platform,
        "os_version": host["os_version"],
        "arch": platform.machine(),
        "ram_bytes": _ram_bytes(),
        "cpu_cores_logical": host["cpu_cores_logical"],
        "power_source": host["power_source"],
        "editor_id": editor_id,
        "editor_version": editor_version,
        "fixture_sha256": fixture["sha256"],
        "cache_state": "warm_steady",
        "feature_profile": "P0",
        "workload_id": row["workload_id"],
        "fixture_byte_size": int(fixture["byte_size"]),
        "fixture_paragraph_count": int(fixture["paragraph_count"]),
        "paragraph_shape": str(row.get("shape") or "unknown"),
        "unicode_class": str(row["unicode_class"]),
        "match_count": int(row["match_count"]),
        "repetition_unit": "fresh_process",
        "run_kind": "timing",
        "headless": True,
        "display_refresh_hz": None,
        "interpretation_conditions": list(INTERPRETATION_CONDITIONS),
        "feature_fallback": list(feats.get("disabled_features") or []),
    }


def scroll_publication_flags(env: dict, sample_count: int | None = None):
    """``(publishable, block_reason)`` for a measured C10 trial.

    The answer comes from the policy (``perf/analysis/publication_gate.py``):
    a ``ci_coarse`` host cannot publish visible latency and a dedicated
    timing run on a dedicated host may. The lane never hardcodes it.

    ``sample_count`` is the count of the *published distribution*. The C10
    lane writes one trial per repetition (``run_cli`` opens a cell per
    repetition), so a cell's trial carries one sample and the I10 rule ("a
    publishable distribution needs n>=2 independent samples") belongs to the
    report layer that assembles the repetitions, not to a single repetition's
    trial. The lane therefore passes ``None`` and records the count it
    measured in the trial's diagnostic.
    """
    return trial_publishable_flags(env, "browser_visible", sample_count)


def _same_rect(left, right, tolerance: float = REGION_TOLERANCE_PX) -> bool:
    """Do two CSS rectangles describe the same box?"""
    if not isinstance(left, dict) or not isinstance(right, dict):
        return False
    for key in ("x", "y", "width", "height"):
        a = left.get(key)
        b = right.get(key)
        if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
            return False
        if abs(float(a) - float(b)) > tolerance:
            return False
    return True


def scroll_sample_verdict(sample: dict, *, bound_ms: float = DEFAULT_SKEW_BOUND_MS):
    """Judge one probe sample.

    Returns ``(outcome, reason, value_ms)``. A sample is ``measured`` only
    when the browser scrolled a container it can name, the ``scrollTop``
    really moved, the document's content really moved, the witness saw a
    frame **inside that container** and the witness record passes B1c's
    validator. Everything else is a refusal with a reason.
    """
    if not isinstance(sample, dict):
        return "failed", "the probe produced no sample record", None
    outcome = sample.get("outcome")
    if outcome != "measured":
        reason = sample.get("reason") or "the probe refused the sample"
        return outcome or "failed", reason, None

    witness = sample.get("witness")
    if not isinstance(witness, dict):
        return "failed", "the sample carries no witness record", None
    verdict = validate_witness(witness, bound_ms=bound_ms)
    if verdict.get("refused"):
        return (
            "failed",
            "the witness refused the sample: %s (%s)"
            % (verdict.get("reason"), "; ".join(verdict.get("errors") or [])),
            None,
        )

    container = sample.get("container") or {}
    selector = str(container.get("selector") or "").strip()
    if not selector:
        return "failed", "the sample recorded no scroll container selector", None

    delta = sample.get("scroll_top_delta")
    if isinstance(delta, bool) or not isinstance(delta, (int, float)) or delta <= 0:
        return (
            "failed",
            "the scroll did not move: the scrollTop delta %r is not above 0" % (delta,),
            None,
        )

    # The document's content must have moved: a frame that changed is not
    # evidence that the document scrolled.
    moved = sample.get("content_moved_px")
    if isinstance(moved, bool) or not isinstance(moved, (int, float)) or moved <= 0:
        return (
            "failed",
            "the document did not scroll: the content of the container moved %r px"
            % (moved,),
            None,
        )

    # The witness must have looked at the container: a change elsewhere in the
    # frame is shell damage, not the document's paint.
    region = (witness.get("document_region") or {}).get("rect_css_px")
    container_rect = container.get("rect_css_px")
    if isinstance(container_rect, dict) and not _same_rect(region, container_rect):
        return (
            "failed",
            "the witness's region is not the scroll container %s (%r vs %r)"
            % (selector, region, container_rect),
            None,
        )

    value = sample.get("scroll_frame_ms")
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        return "failed", "the sample carries no scroll-to-frame latency", None
    return "measured", None, float(value)


def classify_payload(payload: dict, *, bound_ms: float = DEFAULT_SKEW_BOUND_MS):
    """Judge the probe's whole payload.

    Returns ``(outcome, reason, samples)`` where ``samples`` is the list of
    the measured samples (each ``{"value": ms, "record": sample}``).
    """
    records = payload.get("samples") if isinstance(payload, dict) else None
    if not isinstance(records, list):
        return "failed", "the probe produced no sample list", []
    measured = []
    refusals = []
    for record in records:
        outcome, reason, value = scroll_sample_verdict(record, bound_ms=bound_ms)
        if outcome == "measured":
            measured.append({"value": value, "record": record})
        else:
            refusals.append((outcome, reason))
    if measured:
        return "measured", None, measured
    if refusals:
        outcome, reason = refusals[0]
        return outcome, reason, []
    return "failed", "the probe produced no sample", []


# --------------------------------------------------------------------------- #
# The browser side
# --------------------------------------------------------------------------- #


def _run_probe(
    *,
    target: dict,
    corpus_path: Path,
    pairs: int,
    skew_bound_ms: float = DEFAULT_SKEW_BOUND_MS,
    container_selector: str = "",
) -> dict:
    """Run the scroll probe against a host and return its JSON payload."""
    from perf.runner.browser_hosts import select_fixture

    select_fixture(target, corpus_path)
    node = shutil.which("node") or "node"
    cmd = [
        node,
        str(SCROLL_PROBE),
        "--url",
        target["url"],
        "--corpus",
        str(corpus_path.resolve()),
        "--corpus-route",
        target.get("corpus_route", "/corpus.docx"),
        "--ready-selector",
        target.get("ready_selector", "") or "",
        "--pairs",
        str(pairs),
        "--skew-bound-ms",
        str(skew_bound_ms),
    ]
    if container_selector:
        cmd.extend(["--container-selector", container_selector])
    if target.get("sample_route"):
        cmd.extend(["--sample-route", target["sample_route"]])
    if target.get("ready_js"):
        cmd.extend(["--ready-js", target["ready_js"]])
    if target.get("ready_text"):
        cmd.extend(["--ready-text", target["ready_text"]])
    if target.get("wait_after_ready"):
        cmd.extend(["--wait-after-ready", str(target["wait_after_ready"])])
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=900,
    )
    record_process(proc)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout or "scroll probe failed")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("the scroll probe printed no JSON: %s" % (exc,)) from exc


def _flag_value(argv, name):
    """The value of ``--name value`` in an argument list, or None."""
    if name in argv:
        at = argv.index(name)
        if at + 1 < len(argv):
            return argv[at + 1]
    return None


# --------------------------------------------------------------------------- #
# The cell
# --------------------------------------------------------------------------- #


def _write_outcome(
    *,
    attempt_dir: Path,
    outcome: str,
    reason: str | None,
    samples: list,
    env: dict,
    editor_id: str,
    lane: str,
    diagnostic: dict,
    seed: int,
) -> Path:
    """Write the C10 attempt: a measured trial, or a refusal with a reason."""
    if outcome == "measured":
        assert_visible_evidence("C10", VISIBLE_EVIDENCE)
        values = [entry["value"] for entry in samples]
        stats = summarize(values, "warm_steady", "fresh_process", seed=seed)
        # The publishability follows the policy: a ci_coarse host cannot
        # publish visible latency, a dedicated timing run on a dedicated host
        # may. The decision is recorded in the diagnostic as well, so it stays
        # visible when the host's own stamp (a fake host) has the last word on
        # the trial.
        publishable, block_reason = scroll_publication_flags(env)
        diagnostic["publication"] = {
            "publishable": publishable,
            "block_reason": block_reason,
            "samples": len(values),
        }
        trial = _trial_dict(
            criterion_id="C10",
            layer="browser_visible",
            boundary="frame_time",
            outcome="measured",
            env=env,
            samples_ms=values,
            editor_id=editor_id,
            lane=lane,
            summary_stats=stats,
            publishable=publishable,
            publication_block_reason=block_reason,
            diagnostic=diagnostic,
        )
    else:
        if not reason or not str(reason).strip():
            raise ValueError("a refused C10 trial needs a reason")
        trial = _trial_dict(
            criterion_id="C10",
            layer="browser_visible",
            boundary="frame_time",
            outcome=outcome,
            env=env,
            samples_ms=[],
            failure_reason=reason,
            editor_id=editor_id,
            lane=lane,
            publishable=False,
            publication_block_reason=reason,
            diagnostic=diagnostic,
        )
    validate_trial(trial)
    return write_attempt(
        attempt_dir,
        "c10-%s-%s" % (editor_id, Path(attempt_dir).parent.name),
        trial,
    )


def _refuse(
    *,
    out_root: Path,
    attempt_dir: Path,
    outcome: str,
    reason: str,
    env: dict,
    editor_id: str,
    lane: str,
    diagnostic: dict,
    execution_profile: str,
    host_class: str,
    seed: int,
) -> Path:
    """Write the refusal (a trial with a reason and no samples) and the summary."""
    path = _write_outcome(
        attempt_dir=attempt_dir,
        outcome=outcome,
        reason=reason,
        samples=[],
        env=env,
        editor_id=editor_id,
        lane=lane,
        diagnostic=diagnostic,
        seed=seed,
    )
    write_json(
        out_root / "summary_c10.json",
        {
            "criterion_id": "C10",
            "editor_id": editor_id,
            "outcome": outcome,
            "failure_reason": reason,
            "attempt_file": str(path.resolve()),
            "execution_profile": execution_profile,
            "host_class": host_class,
            "profile_admits_workload": profile_admits_workload(execution_profile),
            "workload_id": WORKLOAD_ID,
            "seed": seed,
            "publishable": False,
        },
    )
    return path


def _main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--editor", default="plate")
    parser.add_argument("--out-root", type=Path, required=True)
    parser.add_argument("--pairs", type=int, default=1)
    parser.add_argument(
        "--fake-host",
        default=None,
        help="A directory of fake hosts to measure instead of a production editor",
    )
    parser.add_argument("--fake-page", default="prose.html")
    parser.add_argument(
        "--container-selector",
        default="",
        help="The per-host override: the selector of the element that scrolls the document",
    )
    args = parser.parse_args()

    if args.fake_host and args.editor != FAKE_EDITOR:
        sys.stderr.write(
            "--fake-host and --editor are mutually exclusive: a fake host is a test "
            "fixture, not an editor, and its measurement must never be filed under "
            "an editor's id\n"
        )
        return 2

    run = ACTIVE.get()
    seed = getattr(run, "seed", 0)
    # The execution profile and the host class belong to the run (#132).
    profile = run_profile(DEFAULT_EXECUTION_PROFILE)
    host = run_host_class(DEFAULT_HOST_CLASS)
    out_root = args.out_root
    attempt_dir = out_root / "attempts"
    attempt_dir.mkdir(parents=True, exist_ok=True)

    fixture = scroll_fixture()
    fixture_path = run_fixture(WORKLOAD_ID, fixture["docx"], out_root / "fixture.docx")

    editor_id = args.editor
    editor_version = FAKE_EDITOR_VERSION
    if args.fake_host:
        editor_id = FAKE_EDITOR
    else:
        editor_version = pin_label(editor_id)

    env = scroll_env(
        editor_id=editor_id,
        editor_version=editor_version,
        execution_profile=profile,
        host_class=host,
        fixture=fixture,
    )
    lane = "fake" if args.fake_host else (BROWSER_TARGETS.get(editor_id, {}).get("lane") or default_lane(editor_id))

    diagnostic = {
        "suite": "adversarial",
        "probe": "scroll_container",
        "criterion": "C10",
        "workload_id": WORKLOAD_ID,
        "execution_profile": profile,
        "host_class": host,
        "seed": seed,
        "visible_evidence": VISIBLE_EVIDENCE,
    }
    if args.container_selector:
        diagnostic["container_override"] = args.container_selector
    try:
        validate_environment(env)
    except ValueError as exc:
        # `perf/schema.py` refuses `dedicated_publish` on a host that is not
        # dedicated. The refusal is recorded, not hidden: the trial stays
        # unpublishable either way.
        diagnostic["environment_schema_error"] = str(exc)

    # The profile gate: prose-50kw is only admitted by `dedicated_publish`.
    try:
        assert_workload_allowed(profile, WORKLOAD_ID)
    except ValueError as exc:
        reason = "execution_profile: %s" % (exc,)
        diagnostic["profile_admits_workload"] = False
        _refuse(
            out_root=out_root,
            attempt_dir=attempt_dir,
            outcome="not_run",
            reason=reason,
            env=env,
            editor_id=editor_id,
            lane=lane,
            diagnostic=diagnostic,
            execution_profile=profile,
            host_class=host,
            seed=seed,
        )
        return 0
    diagnostic["profile_admits_workload"] = True

    server = None
    proc = None
    payload: dict = {}
    sample_path = None
    try:
        if args.fake_host:
            from perf.runner.browser_hosts import StaticHost

            server = StaticHost(
                Path(args.fake_host).resolve(),
                corpus_route="/corpus.docx",
                fixture=fixture_path,
            )
            target = {
                "lane": "fake",
                "url": server.url + "/" + str(args.fake_page).lstrip("/"),
                "corpus_route": "/corpus.docx",
                "ready_js": "window.__docxReady === true",
                "ready_selector": "",
                "driver": "playwright",
            }
            if run is not None:
                run.hosts[editor_id] = {
                    "host_build": "fake_host",
                    "publishable": False,
                    "publication_block_reason": "fake host: a test fixture, not an editor",
                }
        else:
            target = dict(BROWSER_TARGETS[editor_id])
            try:
                proc = _start_server(editor_id, target)
            except Exception as exc:
                # The host did not come up: a refusal with the reason, not a
                # crash and not a missing trial.
                reason = "host_build: %s" % (exc,)
                diagnostic["host_build_error"] = reason
                _refuse(
                    out_root=out_root,
                    attempt_dir=attempt_dir,
                    outcome="failed",
                    reason=reason,
                    env=env,
                    editor_id=editor_id,
                    lane=lane,
                    diagnostic=diagnostic,
                    execution_profile=profile,
                    host_class=host,
                    seed=seed,
                )
                return 0

        sample_name = "c10-%s" % (Path(out_root).name,)
        # A nested bracket: the cell's bracket (opened by `run_cli`) stays the
        # cell's, and this one covers the probe alone, so a sample that was
        # throttled is refused here instead of published.
        bracket = run.begin_sample() if run is not None else contextlib.nullcontext()
        with bracket:
            try:
                payload = _run_probe(
                    target=target,
                    corpus_path=fixture_path,
                    pairs=max(1, args.pairs),
                    container_selector=args.container_selector,
                )
            except Exception as exc:  # record, never abort the run
                payload = {
                    "status": "error",
                    "outcome": "failed",
                    "reason": "scroll_probe: %s" % (exc,),
                    "samples": [],
                }
            outcome, reason, samples = classify_payload(payload)
            row = {
                "outcome": outcome,
                "failure_reason": reason,
                "scroll_frame_ms": [entry["value"] for entry in samples] or None,
                "container_selectors": [
                    (entry["record"].get("container") or {}).get("selector") for entry in samples
                ],
                "scroll_top_deltas": [entry["record"].get("scroll_top_delta") for entry in samples],
                "content_moved_px": [entry["record"].get("content_moved_px") for entry in samples],
                "probe": payload,
            }
            if run is not None:
                sample_path = run.sample(sample_name, row)
    finally:
        if proc is not None:
            _stop_server(proc)
        if server is not None:
            server.stop()

    # The throttle refusal reads the sample that was written, not the last
    # entry of `run.samples`: the cell's own sample is appended later, and a
    # lane must not depend on that order.
    if sample_path is not None:
        written = json.loads(Path(sample_path).read_text(encoding="utf-8"))
        if written.get("failure_reason") == "cpu_throttled":
            outcome, reason, samples = "failed", "cpu_throttled: the sample was refused", []

    diagnostic["probe"] = {
        "status": payload.get("status"),
        "outcome": payload.get("outcome"),
        "reason": payload.get("reason"),
        "scroll_step_px": payload.get("scroll_step_px"),
        "witness_window_ms": payload.get("witness_window_ms"),
        "skew_bound_ms": payload.get("skew_bound_ms"),
        "container_override": payload.get("container_override"),
    }
    diagnostic["samples"] = [
        {
            "sample_index": entry["record"].get("sample_index"),
            "container": entry["record"].get("container"),
            "container_how": entry["record"].get("container_how"),
            "scroll_top_before": entry["record"].get("scroll_top_before"),
            "scroll_top_after": entry["record"].get("scroll_top_after"),
            "scroll_top_delta": entry["record"].get("scroll_top_delta"),
            "content_top_before": entry["record"].get("content_top_before"),
            "content_top_after": entry["record"].get("content_top_after"),
            "content_moved_px": entry["record"].get("content_moved_px"),
            "scroll_frame_ms": entry["value"],
            "clock_skew": entry["record"].get("clock_skew"),
            "caret_mask_shadow_roots": entry["record"].get("caret_mask_shadow_roots"),
            "witness": entry["record"].get("witness"),
        }
        for entry in samples
    ]
    if not samples:
        diagnostic["refusals"] = [
            {
                "sample_index": record.get("sample_index"),
                "outcome": record.get("outcome"),
                "reason": record.get("reason"),
                "search": record.get("search"),
            }
            for record in (payload.get("samples") or [])
            if isinstance(record, dict)
        ]

    path = _write_outcome(
        attempt_dir=attempt_dir,
        outcome=outcome,
        reason=reason,
        samples=samples,
        env=env,
        editor_id=editor_id,
        lane=lane,
        diagnostic=diagnostic,
        seed=seed,
    )
    values = [entry["value"] for entry in samples]
    write_json(
        out_root / "summary_c10.json",
        {
            "criterion_id": "C10",
            "editor_id": editor_id,
            "outcome": outcome,
            "failure_reason": reason,
            "median_ms": summarize(values, "warm_steady", "fresh_process", seed=seed)["median"] if values else None,
            "samples_ms": values,
            "containers": [
                (entry["record"].get("container") or {}).get("selector") for entry in samples
            ],
            "scroll_top_deltas": [entry["record"].get("scroll_top_delta") for entry in samples],
            "content_moved_px": [entry["record"].get("content_moved_px") for entry in samples],
            "attempt_file": str(path.resolve()),
            "execution_profile": profile,
            "host_class": host,
            "profile_admits_workload": profile_admits_workload(profile),
            "workload_id": WORKLOAD_ID,
            "container_override": args.container_selector or None,
            "seed": seed,
            "publishable": False,
        },
    )
    print(
        json.dumps(
            {
                "criterion_id": "C10",
                "editor_id": editor_id,
                "outcome": outcome,
                "failure_reason": reason,
                "samples": len(values),
                "attempt_file": str(path.resolve()),
            }
        )
    )
    return 0


def main() -> int:
    argv = sys.argv[1:]
    targets = dict(BROWSER_TARGETS)
    if _flag_value(argv, "--fake-host") is not None:
        if "--editor" in argv:
            # A fake host is a test fixture. Its measurement must never be
            # filed under an editor's id.
            sys.stderr.write(
                "--fake-host and --editor are mutually exclusive: a fake host is a "
                "test fixture, not an editor, and its measurement must never be "
                "filed under an editor's id\n"
            )
            return 2
        targets[FAKE_EDITOR] = {"lane": "fake"}
        argv = argv + ["--editor", FAKE_EDITOR]
        sys.argv = [sys.argv[0]] + argv
    return run_cli(
        _main,
        "adversarial_c10_scroll",
        targets,
        count_flag="--pairs",
        default_count=3,
        single=True,
    )


if __name__ == "__main__":
    raise SystemExit(main())
