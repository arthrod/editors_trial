"""Third adversarial reader review (r3reader3 findings accepted in r3reader4)."""
import json
import re
from pathlib import Path

import pytest

from build import perf_e2_tables as report
from perf.analysis import e2_cells as cells
from perf.analysis import e2_resources
from perf.tests.test_e2_reader_r3reader3 import (
    _summary,
    _write_job,
    _write_resource_job,
    _write_typing_job,
)


def _blocks_camp(tmp_path, space, seed, *, extra_job=None, delete_block10=False, extra_block11=False):
    base = tmp_path / space
    camp = None
    for index in range(1, 11):
        reps = range((index - 1) * 3, index * 3)
        camp = _write_job(
            base, "benchmark_input", "b%02d" % index, seed, reps,
            summary=_summary(
                "run-b%02d-%s" % (index, seed), seed,
                order=[[r, "plate"] for r in reps],
                block={"index": index, "of": 10, "repetitions": 3},
                hosts={"plate": {"tree_sha256": "tree-a"}},
            ),
        )
    if extra_block11:
        extra = range(30, 33)
        _write_job(
            base, "benchmark_input", "extra", seed, extra,
            summary=_summary(
                "run-extra-%s" % seed, seed, order=[[r, "plate"] for r in extra],
                block={"index": 11, "of": 10, "repetitions": 3},
                hosts={"plate": {"tree_sha256": "tree-a"}},
            ),
            values={i: 80.0 for i in extra},
        )
    if delete_block10:
        empty = camp / "benchmark_input" / "b10" / "cells"
        for child in empty.iterdir():
            for f in child.rglob("*"):
                if f.is_file():
                    f.unlink()
    if extra_job:
        extra_job(base, seed, camp)
    return camp


# MAJOR 1 — block campaign plus whole re-run must not publish


def test_block_campaign_plus_whole_rerun_refused(tmp_path):
    def whole(base, seed, _camp):
        _write_job(
            base, "benchmark_input", "whole", seed, range(30),
            summary=_summary("run-whole-%s" % seed, seed, hosts={"plate": {"tree_sha256": "tree-a"}}),
            values={i: 80.0 for i in range(30)},
        )

    a = _blocks_camp(tmp_path, "ra", 1, extra_job=whole)
    b = _blocks_camp(tmp_path, "rb", 2, extra_job=whole)
    pooled = cells.read_criterion_cell([a, b], "plate", "C07")
    assert pooled["published"] is False, pooled.get("reason")
    facts = report.facts_from_roots([a, b])
    assert facts.get("perf.e2.plate.C07.reproduced") is not True


# MAJOR 2 — block index above of


def test_block_index_above_of_refused(tmp_path):
    a = _blocks_camp(tmp_path, "xa", 1, extra_block11=True)
    b = _blocks_camp(tmp_path, "xb", 2, extra_block11=True)
    pooled = cells.read_criterion_cell([a, b], "plate", "C07")
    assert pooled["published"] is False, pooled.get("reason")


# MAJOR 3 — block summary without launch files


def test_block_summary_without_launches_refused(tmp_path):
    a = _blocks_camp(tmp_path, "ea", 1, delete_block10=True)
    b = _blocks_camp(tmp_path, "eb", 2, delete_block10=True)
    pooled = cells.read_criterion_cell([a, b], "plate", "C07")
    assert pooled["published"] is False, pooled.get("reason")


# MAJOR 4 — 31-name schedule beside 30-name


def test_near_copy_31_launch_names_refused(tmp_path):
    root = tmp_path / "space-a"
    _write_job(root, "benchmark_input", "j30", 1, range(30), values={i: 20.0 for i in range(30)})
    _write_job(root, "benchmark_input", "j31", 1, range(31), values={i: 80.0 for i in range(31)})
    seed2 = _write_job(tmp_path / "space-b", "benchmark_input", "j2", 2, range(30))
    pooled = cells.read_criterion_cell([root / "runs" / "camp", seed2], "plate", "C07")
    assert pooled["published"] is False, pooled.get("reason")


# MAJOR 5 — criterion build identity from summary hosts


def test_criterion_refuses_different_summary_build_trees(tmp_path):
    a = _write_job(
        tmp_path / "sa", "benchmark_input", "j1", 1, range(30),
        summary=_summary("j1", 1, hosts={"plate": {"tree_sha256": "tree-a"}}),
    )
    b = _write_job(
        tmp_path / "sb", "benchmark_input", "j2", 2, range(30),
        summary=_summary("j2", 2, hosts={"plate": {"tree_sha256": "tree-b"}}),
    )
    pooled = cells.read_criterion_cell([a, b], "plate", "C07")
    assert pooled["published"] is False
    assert "different editor builds" in (pooled["reason"] or "")


# MAJOR 6 — B8 duplicate run_id must hash resource.json


def test_b8_same_run_id_different_resource_refused(tmp_path):
    def plant(space, cpu):
        camp = _write_resource_job(
            tmp_path / space, "r1", 1, summary=_summary("same-run", 1), cpu=cpu,
        )
        job = camp / "benchmark_resources" / "r1"
        for cell in (job / "cells").iterdir():
            attempts = cell / "attempts"
            attempts.mkdir()
            (attempts / "note.json").write_text('{"same":true}')
        return camp

    low = plant("space-a", 100)
    high = plant("space-b", 9000)
    seed2 = _write_resource_job(tmp_path / "space-c", "r2", 2, cpu=100)
    cell = e2_resources.read_cell([high, low, seed2], "plate", "prose-500w")
    assert cell["published"] is False, cell.get("reason")
    assert "duplicate" in (cell["reason"] or "").casefold()


# MAJOR 7 — typing re-run with empty order


def test_typing_empty_order_rerun_refused(tmp_path):
    camp_a = tmp_path / "space-a" / "runs" / "camp"
    _write_typing_job(tmp_path / "space-a", "t1", 1)
    _write_typing_job(
        tmp_path / "space-a", "t1r", 1, launches=range(12),
        summary=_summary("t1r", 1, order=[]),
    )
    camp_b = _write_typing_job(tmp_path / "space-b", "t2", 2)
    facts = {}
    text = report.typing_table(facts, [camp_a, camp_b], "plate", "throughput")
    assert facts.get("perf.e2.plate.TYPING.throughput.reproduced") is not True
    assert "12" in text


# MAJOR 8 — unpublished typing cell must not store agreeing medians in facts table


def test_unpublished_typing_partial_agreement_withholds_figures(tmp_path):
    roots = [
        _write_typing_job(tmp_path / "sa", "t1", 1, summary=_summary("t1", 1, hosts={"plate": {"tree_sha256": "tree-a"}})),
        _write_typing_job(tmp_path / "sb", "t2", 2, summary=_summary("t2", 2, hosts={"plate": {"tree_sha256": "tree-a"}})),
    ]
    # Disagree on one resource measure, agree on throughput.
    for root in roots:
        job = root / "benchmark_typing" / ("t1" if "sa" in str(root) else "t2")
        for cell in (job / "cells").iterdir():
            path = cell / "attempts" / "typing.json"
            row = json.loads(path.read_text())
            if "sa" in str(root):
                row.setdefault("resources", {})["phase"] = {"cpu_ms": 111}
            else:
                row.setdefault("resources", {})["phase"] = {"cpu_ms": 99999}
            path.write_text(json.dumps(row))
    facts = report.facts_from_roots(roots)
    assert facts["perf.e2.plate.TYPING.throughput.reproduced"] is False
    table = facts.get("perf.e2.table.TYPING", "")
    assert "111" not in table and "99999" not in table
    assert "chars/s" not in table or "not reproduced" in table


def test_unpublished_cell_facts_contain_no_timing_figures(tmp_path):
    """Walk perf.e2.* facts for a refused cell: only schedule counts, no medians."""
    a = _blocks_camp(tmp_path, "ra", 1, extra_block11=True)
    b = _blocks_camp(tmp_path, "rb", 2, extra_block11=True)
    facts = report.facts_from_roots([a, b])
    assert facts.get("perf.e2.plate.C07.reproduced") is not True
    number_pat = re.compile(r"\d+\.\d+")
    for key, value in facts.items():
        if not key.startswith("perf.e2.") or key.endswith(".reproduced"):
            continue
        if key.startswith("perf.e2.table."):
            continue
        if "C07" not in key and ".primary" not in key and ".reproduction" not in key:
            continue
        blob = json.dumps(value) if not isinstance(value, str) else value
        if "scheduled" in key or "cells_" in key:
            continue
        assert not number_pat.search(blob), "unexpected figure in %s: %s" % (key, blob[:200])


# MAJOR 9 — document probe argv timeout matches workload policy


def test_document_probe_timeout_ms_matches_workload_policy():
    from perf.fixtures.profiles import size_ladder
    from perf.runner.benchmark_document import _probe_cmd
    from perf.runner.load_timeouts import load_timeout_ms

    row = next(r for r in size_ladder() if r["workload_id"] == "prose-500w")
    cfg = {"doc_selector": ".d", "page_model": "p", "edit_selector": ".e"}
    cmd = _probe_cmd(
        mode="load", target={**row, "url": "http://127.0.0.1/", "corpus_route": "/c"},
        cfg=cfg, corpus_path=Path("/tmp/x.docx"), extra=[],
    )
    ix = cmd.index("--timeout-ms")
    assert int(cmd[ix + 1]) == load_timeout_ms("prose-500w")
    row_big = next(r for r in size_ladder() if r["workload_id"] == "prose-250kw")
    cmd_big = _probe_cmd(
        mode="load", target={**row_big, "url": "http://127.0.0.1/", "corpus_route": "/c"},
        cfg=cfg, corpus_path=Path("/tmp/x.docx"), extra=[],
    )
    ix = cmd_big.index("--timeout-ms")
    assert int(cmd_big[ix + 1]) == load_timeout_ms("prose-250kw")


# MAJOR 10 — memory probe uses workload policy only (no lane floor)


def test_memory_probe_uses_load_timeout_policy_only():
    text = (Path(__file__).resolve().parents[2] / "perf" / "runner" / "memory_probe.mjs").read_text()
    assert "Math.max(LANE_LOAD_TIMEOUT_MS" not in text
    assert "loadTimeoutMs()" in text


# MAJOR 11 — C14 no-damage sample without clock fields is refused


def test_c14_no_damage_without_clock_fields_refused():
    from perf.runner.benchmark_document import ProbeRefusal, c14_measured_sample

    with pytest.raises(ProbeRefusal):
        c14_measured_sample({"mechanism": "forced_repaint", "usable_ms": 1234.5})
    assert c14_measured_sample({"usable_ms": 800.0, "presented_frame_ms": 812.5}) == 812.5


# MAJOR 12 — relaxed bounds disclosure


def test_relaxed_bounds_template_matches_constants():
    from perf.runner import lax_bounds

    paragraph = lax_bounds.relaxed_bounds_paragraph()
    template = (Path(__file__).resolve().parents[2] / "templates" / "reports" / "Report E2 - Speed in the Browser (2026).md").read_text()
    assert "{{perf.e2.relaxed_bounds}}" in template
    for fragment in ("5 ms", "300 s", "600 s", "100 ms", "250 ms", "2%"):
        assert fragment in paragraph


# MINOR 13 — warm/cold row without bound_ms


def test_warm_cold_requires_declared_skew_bound():
    from perf.runner.benchmark_warm_cold import input_sample_record

    row = input_sample_record(
        dict(
            clock_skew=dict(skew_ms=4.0, acceptable=True),
            edit_ms=4321,
            outcome="measured",
        ),
        "C04",
    )
    assert row.get("failure_reason") is not None


# NIT 14 — load_timeout comment honesty (tested in node suite; spot-check comment)


def test_load_timeout_comment_does_not_claim_shorter_waits_are_impossible():
    text = (Path(__file__).resolve().parents[2] / "perf" / "runner" / "load_timeout.mjs").read_text()
    assert "never to a shorter wait" not in text
