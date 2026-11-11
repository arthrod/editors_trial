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
* every sample records the **container selector** it scrolled, the shadow host
  chain it lives under and the **`scrollTop` delta** it produced;
* every sample records the **content probe**: where the scrolled content was
  before the scroll and after it, and the text visible at the top of the
  scroller before and after. A ``scrollTop`` that moves without the content
  moving is not a scroll of the document (#134);
* the frame is **witnessed** by B1c's shared module (``witness.mjs``): the
  first presented frame at or after the scroll whose pixels really changed
  **inside the scrolled container** (the document region #130 demands), in the
  page's own clock, against the run's **clock check** (with its pixel anchor);
* a sample with no container, an unmoved ``scrollTop``, an unmoved content, no
  witnessed frame or a clock skew above the bound is **refused with a
  reason** — ``not_applicable`` or ``failed``, never ``measured``;
* the trial environment records the **execution profile** (which must admit
  prose-50kw) and the run records the **seed**;
* the trial's **publishability** is derived from the profile and the host
  class (the publication gate), not hardcoded (#134).

The Python side is the authority: every witness record is re-validated with
B1c's reader (``perf/runner/witness.py``) before a sample may become a
number, and a sample without a container selector, without a ``scrollTop``
delta or without a moved content is refused even if the browser said it was
fine.

Usage (production host)::

    python3 perf/runner/adversarial_c10_scroll.py --editor plate --out-root out/c10 \\
        --execution-profile dedicated_publish --host-class dedicated

Usage (the fake hosts of the acceptance measurers)::

    python3 perf/runner/adversarial_c10_scroll.py --fake-host \\
        perf/tests/fixtures/hosts/b5_scroll --fake-page prose.html --out-root out/c10 \\
        --execution-profile dedicated_publish
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import shutil
import subprocess
import sys
from contextlib import nullcontext
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
    BrowserRun,
    execution_profile as run_profile,
    fixture_path as run_fixture,
    host_class as run_host_class,
    record_process,
    run_cli,
    write_json,
)
from perf.runner.benchmark_ci_contract import INTERPRETATION_CONDITIONS, _host_base, _trial_dict  # noqa: E402
from perf.runner.benchmark_warm_cold import BROWSER_TARGETS, _start_server, _stop_server  # noqa: E402
from perf.runner.witness import DEFAULT_SKEW_BOUND_MS, validate_witness  # noqa: E402
from perf.schema import validate_environment, validate_trial  # noqa: E402

#: The workload the scroll criterion runs on (#100's size ladder).
WORKLOAD_ID = "prose-50kw"

#: The execution profiles the runner accepts. ``dedicated_publish`` is the
#: only one whose workload cap admits prose-50kw, so it is the default when
#: the runner is called outside ``run_cli``. Inside ``run_cli`` the profile is
#: the run's (B1 owns ``--execution-profile``).
EXECUTION_PROFILES = ("ci_contract", "ci_broad", "dedicated_publish")
DEFAULT_EXECUTION_PROFILE = "dedicated_publish"

#: The host class the environment records. ``dedicated`` is the publish
#: machine; ``ci_coarse`` is every other machine, and the default is the
#: honest one: a shared box never claims to be dedicated.
#:
#: ``shared_guarded`` is the class B7 adds to ``perf/schema.py``. This
#: branch's schema may not list it yet. The lane accepts every class the
#: schema lists, and ``shared_guarded``, so the two changes compose. ``main``
#: stamps a class ``run_cli`` does not list yet; once B7's ``browser_run.py``
#: lists it, that stamp is unused.
DEFAULT_HOST_CLASS = "ci_coarse"

#: A witness rectangle and the container's rectangle are the same box when
#: every edge is within this many CSS pixels (#134, the blink record).
REGION_TOLERANCE_PX = 1.0

#: The editor id of the fake hosts the acceptance measurers use.
FAKE_EDITOR = "b5-fake"
FAKE_EDITOR_VERSION = "fake-host:b5-scroll"

#: The scroll container of a host whose page cannot prove which scroller holds
#: the document (a canvas editor, a host that scrolls a box the text is not
#: in). Empty by default; every use is recorded in the trial's diagnostic and
#: in the sample record, so an override is never invisible.
HOST_SCROLL_CONTAINERS: dict[str, str] = {}

SCROLL_PROBE = REPO / "perf" / "runner" / "adversarial_c10_scroll.mjs"

#: The evidence the C10 trial claims. ``perf/layers/classify.py`` (B2's file)
#: says which evidence a ``browser_visible`` trial may carry.
VISIBLE_EVIDENCE = "presented_frame"

#: The layer the C10 trial belongs to (the publication gate's layer).
VISIBLE_LAYER = "browser_visible"


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


def scroll_fixture(workload_id: str = WORKLOAD_ID) -> dict:
    """The prose-50kw document: its bytes, its metadata and its ladder row."""
    row = next(r for r in size_ladder() if r["workload_id"] == workload_id)
    built = workload_docx(workload_id)
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

    ``perf/schema.py`` refuses ``dedicated_publish`` on a host that is not
    dedicated, and ``_host_base`` validates the environment it builds. The
    refusal is recorded, not hidden: the environment is built with a pair the
    schema accepts and the operator's declaration is what the trial carries.
    ``environment_schema_error()`` says what the schema thinks of it.
    """
    run = ACTIVE.get()
    saved = None
    if run is not None:
        saved = (run.execution_profile, run.host_class)

    def build(profile: str, klass: str) -> dict:
        if run is not None:
            run.execution_profile = profile
            run.host_class = klass
        return _host_base(
            editor_id=editor_id,
            editor_version=editor_version,
            execution_profile=profile,
            fixture_sha256=fixture["sha256"],
            workload_row=fixture["workload_row"],
            docx_size=fixture["byte_size"],
            cache_state="warm_steady",
            repetition_unit="fresh_process",
            run_kind="timing",
            feature_profile_name="P0",
        )

    try:
        try:
            env = build(execution_profile, host_class)
        except ValueError:
            env = build("ci_broad", "ci_coarse")
    finally:
        if run is not None:
            run.execution_profile, run.host_class = saved
    env["execution_profile"] = execution_profile
    env["host_class"] = host_class
    env["fixture_paragraph_count"] = int(fixture["paragraph_count"])
    env["interpretation_conditions"] = list(INTERPRETATION_CONDITIONS)
    return env


def environment_schema_error(env: dict) -> str | None:
    """What ``perf/schema.py`` says about this environment, or None."""
    try:
        validate_environment(env)
    except ValueError as exc:
        return str(exc)
    return None


def _schema_host_classes() -> tuple[str, ...]:
    """The host classes ``perf/schema.py`` actually accepts, read from the file.

    B7's schema lists ``shared_guarded``. This branch's schema may not. The
    lane does not edit ``schema.py``.
    """
    source = (REPO / "perf" / "schema.py").read_text(encoding="utf-8")
    match = re.search(r'env\["host_class"\] not in \(([^)]*)\)', source)
    if match is None:
        return ("dedicated", "ci_coarse")
    found = ast.literal_eval("(" + match.group(1) + ")")
    return tuple(found)


HOST_CLASSES = tuple(dict.fromkeys((*_schema_host_classes(), "shared_guarded")))


def scroll_publishability(env: dict, sample_count: int | None = None) -> tuple[bool, str | None]:
    """May this cell be published? The publication gate decides (#134, #136).

    One sample per cell is the design. ``run_cli`` gives one sample per fresh
    launch, and #136 aggregates the launches. This per-cell gate does not
    apply the per-cell n>=2 rule: a one-sample cell is not stamped I10.
    Publication n is decided by ``perf/analysis/e2_cells.py`` (n >= 10 per
    run). ``sample_count`` is the cell's count and is not that n.
    """
    del sample_count
    return trial_publishable_flags(env, VISIBLE_LAYER, None)


def _number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _rect_of(value) -> dict | None:
    """A CSS rectangle, or the ``rect_css_px`` nested in a document region."""
    if not isinstance(value, dict):
        return None
    nested = value.get("rect_css_px")
    if isinstance(nested, dict):
        value = nested
    rect = {}
    for key in ("x", "y", "width", "height"):
        number = value.get(key)
        if not _number(number):
            return None
        rect[key] = float(number)
    return rect


def _rects_within(left, right, tolerance: float = REGION_TOLERANCE_PX) -> bool:
    if left is None or right is None:
        return False
    return all(abs(left[key] - right[key]) <= tolerance for key in ("x", "y", "width", "height"))


def scroll_sample_verdict(sample: dict, *, bound_ms: float = DEFAULT_SKEW_BOUND_MS):
    """Judge one probe sample.

    Returns ``(outcome, reason, value_ms)``. A sample is ``measured`` only
    when the browser scrolled a container it can name, the ``scrollTop``
    really moved, the **content moved with it**, the witness saw a frame
    inside the scrolled container and the witness record passes B1c's
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
    if not _number(delta) or delta <= 0:
        return (
            "failed",
            "the scroll did not move: the scrollTop delta %r is not above 0" % (delta,),
            None,
        )

    # The content must have moved with the scroll (#134): a scrollTop that
    # moves without the content moving is not a scroll of the document.
    content = sample.get("content") or {}
    moved = content.get("moved_px")
    if not _number(moved) or moved <= 0:
        return (
            "failed",
            "the scroll did not move the content: the content of the scroller moved by %r px"
            % (moved,),
            None,
        )

    # The witness must have watched this container. A 40×40 blink whose
    # changed_pixels equal its own region_pixels is still not the document
    # (#134). The two rectangles are the same box within 1 px.
    container_rect = _rect_of(container.get("region_rect"))
    if container_rect is None:
        container_rect = _rect_of(container.get("rect_css_px"))
    if container_rect is not None and not _rects_within(_rect_of(witness.get("document_region")), container_rect):
        return (
            "failed",
            "the witness's document_region is not the scroll container's region_rect "
            "(within %s px): %r vs %r"
            % (REGION_TOLERANCE_PX, witness.get("document_region"), container.get("region_rect")),
            None,
        )

    # The witness must be scoped to the scrolled container (#130): a
    # whole-frame diff lets shell damage pose as document paint.
    region_pixels = witness.get("region_pixels")
    if not _number(region_pixels) or region_pixels <= 0:
        return (
            "failed",
            "the witness was not scoped to the scrolled container: the record carries no document region",
            None,
        )
    changed = witness.get("changed_pixels")
    if _number(changed) and changed > region_pixels:
        return (
            "failed",
            "the witness counted %r changed pixels outside the %r pixel document region"
            % (changed, region_pixels),
            None,
        )

    value = sample.get("scroll_frame_ms")
    if not _number(value) or value <= 0:
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
    scroll_container: str | None = None,
    skew_bound_ms: float = DEFAULT_SKEW_BOUND_MS,
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
    if target.get("sample_route"):
        cmd.extend(["--sample-route", target["sample_route"]])
    if target.get("ready_js"):
        cmd.extend(["--ready-js", target["ready_js"]])
    if target.get("ready_text"):
        cmd.extend(["--ready-text", target["ready_text"]])
    if target.get("wait_after_ready"):
        cmd.extend(["--wait-after-ready", str(target["wait_after_ready"])])
    if scroll_container:
        cmd.extend(["--container-selector", scroll_container])
    from perf.runner.load_timeouts import load_timeout_env

    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=900,
        # Lax layer (owner 2026-11-11): the probe's ready/navigation waits are
        # minutes, not 120 s; the 900 s wall clock above stays above them.
        env={**os.environ, **load_timeout_env(WORKLOAD_ID)},
    )
    record_process(proc)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout or "scroll probe failed")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("the scroll probe printed no JSON: %s" % (exc,)) from exc


def throttle_refusal_reason(row) -> str | None:
    """The reason this row was refused for CPU throttling, or None.

    The refusal is not one string match on one sample: the row's own outcome,
    its failure reason and its own CPU accounting are all evidence, so a
    renamed reason or a moved sample cannot smuggle a throttled measurement
    through (#134, finding 6).
    """
    if not isinstance(row, dict):
        return None
    if row.get("failure_reason") == "cpu_throttled":
        return "cpu_throttled"
    if row.get("rejected_evidence_directory"):
        return "cpu_throttled"
    accounting = row.get("cpu_accounting") or {}
    if not isinstance(accounting, dict) or not accounting.get("available"):
        return None
    delta = accounting.get("delta") or {}
    if not isinstance(delta, dict):
        return None
    # Lax layer (owner decision 2026-11-11): the same tolerance the run
    # recorder applies -- max(1 ms, 1 % of the sample's span) of throttled
    # time is tolerated and disclosed on the row, only more refuses. A row
    # without a recorded span keeps the 1 ms floor (never the percentage).
    from perf.runner.browser_throttle import throttled_within_tolerance

    if not throttled_within_tolerance(delta, accounting.get("span_ms")):
        return "cpu_throttled"
    return None


def _option_name(token) -> str:
    """``--name=value`` and ``--name`` both name ``--name``."""
    text = str(token)
    if text.startswith("--") and "=" in text:
        return text.split("=", 1)[0]
    return text


def _has_option(argv, name: str) -> bool:
    """True when ``--name`` or ``--name=value`` is present."""
    return any(_option_name(token) == name for token in argv)


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
    diagnostic = dict(diagnostic)
    intervals = [(entry.get("record", {}).get("witness") or {}).get("clock_check", {}).get("frame_interval_ms")
                 for entry in samples]
    if intervals and all(_number(value) and value > 0 for value in intervals):
        diagnostic["frame_intervals_ms"] = intervals
        if len(set(intervals)) == 1:
            diagnostic["frame_interval_ms"] = intervals[0]
    if outcome == "measured" and "frame_interval_ms" not in diagnostic:
        outcome = "failed"
        reason = "frame_interval_inconsistent" if intervals and len(set(intervals)) > 1 else "frame_interval_unavailable"
        samples = []
    if outcome == "measured":
        assert_visible_evidence("C10", VISIBLE_EVIDENCE)
        values = [entry["value"] for entry in samples]
        stats = summarize(values, "warm_steady", "fresh_process", seed=seed)
        # None: one sample is a cell, not a distribution. e2_cells.py owns n >= 10.
        publishable, block_reason = scroll_publishability(env, None)
        trial = _trial_dict(
            criterion_id="C10",
            layer=VISIBLE_LAYER,
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
            layer=VISIBLE_LAYER,
            boundary="frame_time",
            outcome=outcome,
            env=env,
            samples_ms=[],
            failure_reason=reason,
            editor_id=editor_id,
            lane=lane,
            publishable=False,
            publication_block_reason="the trial is not a measured distribution: %s" % (outcome,),
            diagnostic=diagnostic,
        )
    interval = diagnostic.get("frame_interval_ms")
    if outcome == "measured":
        trial["refusal_code"] = None
        if _number(interval) and interval > 0:
            trial["sub_frame_samples"] = [entry["value"] < interval for entry in samples]
    else:
        token = str(reason).split(":", 1)[0]
        trial["refusal_code"] = (token if token in ("cpu_throttled", "host_build")
                                 else outcome if outcome in ("not_run", "not_applicable", "unsupported", "unverified")
                                 else "crash" if token == "scroll_probe"
                                 else "paint_witness_unavailable")
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
            "profile_admits_workload": profile_admits_workload(execution_profile, diagnostic["workload_id"]),
            "workload_id": diagnostic["workload_id"],
            "seed": seed,
            "publishable": False,
        },
    )
    return path


def _main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workload", default=WORKLOAD_ID)
    parser.add_argument("--editor", default="plate")
    parser.add_argument("--out-root", type=Path, required=True)
    parser.add_argument("--pairs", type=int, default=1)
    parser.add_argument(
        "--container-selector",
        default=None,
        help="The editor adapter's scroller (a >> b walks into an open shadow root); recorded as container_rule adapter",
    )
    parser.add_argument(
        "--scroll-container",
        default=None,
        help="Alias of --container-selector",
    )
    parser.add_argument(
        "--fake-host",
        default=None,
        help="A directory of fake hosts to measure instead of a production editor",
    )
    parser.add_argument("--fake-page", default="prose.html")
    args = parser.parse_args()

    run = ACTIVE.get()
    seed = getattr(run, "seed", 0)
    # B1 owns the execution profile and the host class (`run_cli` parses
    # `--execution-profile` and `--host-class`); the lane reads the run.
    execution_profile = run_profile(DEFAULT_EXECUTION_PROFILE)
    host_class = run_host_class(DEFAULT_HOST_CLASS)
    out_root = args.out_root
    attempt_dir = out_root / "attempts"
    attempt_dir.mkdir(parents=True, exist_ok=True)

    fixture = scroll_fixture(args.workload)
    fixture_path = run_fixture(args.workload, fixture["docx"], out_root / "fixture.docx")

    editor_id = args.editor
    editor_version = FAKE_EDITOR_VERSION
    if args.fake_host:
        editor_id = FAKE_EDITOR
    else:
        editor_version = pin_label(editor_id)

    env = scroll_env(
        editor_id=editor_id,
        editor_version=editor_version,
        execution_profile=execution_profile,
        host_class=host_class,
        fixture=fixture,
    )
    lane = "fake" if args.fake_host else (BROWSER_TARGETS.get(editor_id, {}).get("lane") or default_lane(editor_id))

    scroll_container = (
        args.container_selector or args.scroll_container or HOST_SCROLL_CONTAINERS.get(editor_id)
    )

    from perf.runner.benchmark_document import (
        content_gate_record,
        content_meta_for_workload,
        gate_length_check_for,
    )

    content_meta = content_meta_for_workload(args.workload)
    diagnostic = {
        "suite": "adversarial",
        "probe": "scroll_container",
        "criterion": "C10",
        "workload_id": args.workload,
        "execution_profile": execution_profile,
        "seed": seed,
        "host_class": host_class,
        "visible_evidence": VISIBLE_EVIDENCE,
        "scroll_container_override": scroll_container,
        **content_gate_record(content_meta, gate_length_check_for(editor_id, content_meta)),
    }
    schema_error = environment_schema_error(env)
    if schema_error:
        # `perf/schema.py` refuses `dedicated_publish` on a host that is not
        # dedicated. The refusal is recorded, not hidden.
        diagnostic["environment_schema_error"] = schema_error

    # The profile gate: prose-50kw is only admitted by `dedicated_publish`.
    try:
        assert_workload_allowed(execution_profile, args.workload)
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
            execution_profile=execution_profile,
            seed=seed,
        )
        return 0
    diagnostic["profile_admits_workload"] = True

    server = None
    proc = None
    payload: dict = {}
    current_row = None
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
                    execution_profile=execution_profile,
                    seed=seed,
                )
                return 0

        sample_name = "c10-%s" % (Path(out_root).name,)
        # B1's nested bracket: the cell's bracket is not shrunk by this one
        # (#132), and a throttled sample is refused here, not published.
        bracket = run.begin_sample() if run is not None else nullcontext()
        with bracket:
            try:
                payload = _run_probe(
                    target=target,
                    corpus_path=fixture_path,
                    pairs=max(1, args.pairs),
                    scroll_container=scroll_container,
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
                "content_moved_px": [
                    (entry["record"].get("content") or {}).get("moved_px") for entry in samples
                ],
                "probe": payload,
            }
            if run is not None:
                # Only the row this cell just wrote can refuse it. A prior
                # throttled repetition stays in run.samples and must not
                # poison a later clean cell (#134).
                before_n = len(run.samples)
                run.sample(sample_name, row)
                if len(run.samples) > before_n:
                    current_row = run.samples[-1]
    finally:
        if proc is not None:
            _stop_server(proc)
        if server is not None:
            server.stop()

    throttled = throttle_refusal_reason(current_row)
    if throttled:
        outcome, reason, samples = "failed", "cpu_throttled: the sample was refused", []

    diagnostic["probe"] = {
        "status": payload.get("status"),
        "outcome": payload.get("outcome"),
        "reason": payload.get("reason"),
        "scroll_step_px": payload.get("scroll_step_px"),
        "witness_window_ms": payload.get("witness_window_ms"),
        "skew_bound_ms": payload.get("skew_bound_ms"),
        "scroll_container_override": payload.get("scroll_container_override"),
    }
    diagnostic["samples"] = [
        {
            "sample_index": entry["record"].get("sample_index"),
            "container": entry["record"].get("container"),
            "content": entry["record"].get("content"),
            "scroll_top_before": entry["record"].get("scroll_top_before"),
            "scroll_top_after": entry["record"].get("scroll_top_after"),
            "scroll_top_delta": entry["record"].get("scroll_top_delta"),
            "scroll_frame_ms": entry["value"],
            "clock_skew": entry["record"].get("clock_skew"),
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
    written = json.loads(path.read_text())
    if written["outcome"] != "measured":
        outcome, reason, samples = written["outcome"], written.get("failure_reason"), []
    values = [entry["value"] for entry in samples]
    if values:
        publishable, block_reason = scroll_publishability(env, None)
    else:
        publishable, block_reason = False, "the trial is not a measured distribution"
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
            "attempt_file": str(path.resolve()),
            "execution_profile": execution_profile,
            "profile_admits_workload": profile_admits_workload(execution_profile, args.workload),
            "workload_id": args.workload,
            "seed": seed,
            "publishable": publishable,
            "publication_block_reason": block_reason,
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
                "publishable": publishable,
                "attempt_file": str(path.resolve()),
            }
        )
    )
    return 0


def main() -> int:
    argv = list(sys.argv[1:])
    targets = dict(BROWSER_TARGETS)
    # Every spelling (--fake-host=PATH, --editor=plate, --editor plate) is
    # refused here, before run_cli can file the fake host under an editor id.
    if _has_option(argv, "--fake-host") and _has_option(argv, "--editor"):
        sys.stderr.write(
            "adversarial_c10_scroll: --fake-host and --editor are mutually exclusive: "
            "a fake host is a test fixture, not an editor, and its measurement must not "
            "be filed under an editor's id.\n"
        )
        return 2
    if _has_option(argv, "--fake-host"):
        targets[FAKE_EDITOR] = {"lane": "fake"}
        argv = argv + ["--editor", FAKE_EDITOR]

    sys.argv = [sys.argv[0], *argv]
    return run_cli(
        _main,
        "adversarial_c10_scroll",
        targets,
        count_flag="--pairs",
        default_count=3,
        single=True,
        run_factory=BrowserRun,
    )


if __name__ == "__main__":
    raise SystemExit(main())
