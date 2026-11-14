"""Report E2 facts from browser publication runs (synthetic trial trees).

Run with uv run --no-project --with pytest --with pytest-cov --with pyfakefs
python -m pytest build/test_perf_e2_tables.py --cov=perf_e2_tables
--cov=perf.analysis.e2_cells --cov-branch --cov-report=term-missing.
Artifact existence checks are integration checks; run-tree unit tests use pyfakefs.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "build"))
sys.path.insert(0, str(ROOT))

import perf_e2_tables as E2
import render_reports
from perf.analysis.anti_ranking import assert_markdown_no_editor_speed_ranking

DISPLAY = {
    "plate": "Plate.js",
    "wordcraft": "WordCraft",
    "docen": "Docen",
}


def _env(editor: str = "plate") -> dict:
    return {
        "host_class": "shared_guarded",
        "execution_profile": "dedicated_publish",
        "editor_id": editor,
        "power_source": "ac",
    }


def _trial(editor: str, criterion: str, outcome: str, samples=None, **extra) -> dict:
    row = {
        "schema_version": 1,
        "criterion_id": criterion,
        "editor_id": editor,
        "outcome": outcome,
        "samples_ms": samples or [],
        "layer": "browser_visible",
        "boundary": "input_to_next_paint",
        "environment": _env(editor),
        # The built-editor identity every real trial carries (#149); the
        # runner stamps environment.editor_version with the slug, not a pin.
        "host_provenance": {"host_build": "production", "publishable": True, "tree_sha256": "tree-fixture"},
        "diagnostic": {"frame_interval_ms": 16.7},
    }
    row.update(extra)
    row.setdefault('publishable', outcome == 'measured')
    row.setdefault('refusal_code', None if outcome == 'measured' else 'crash')
    frame = row.get('diagnostic', {}).get('frame_interval_ms')
    row.setdefault('sub_frame_samples', [bool(frame and isinstance(x, (int, float)) and x < frame) for x in (samples or [])])
    return row


def _block_dir(root: Path, rep: int) -> Path:
    """The decided block job that owns this repetition, or the root when it is one job."""
    found = []
    for summary_path in sorted(root.glob("*/*/summary.json")):
        try:
            summary = json.loads(summary_path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if not (summary.get("block") or {}).get("index"):
            continue
        reps = [item[0] for item in (summary.get("order") or []) if item]
        if rep in reps:
            return summary_path.parent
        found.append(summary_path.parent)
    if found and rep >= 10:
        return found[-1]
    return root


def _lay_blocks(root: Path) -> None:
    """Turn a flat job of exactly 10 into the decided 2 blocks of 5.

    The parent summary stays so comparability still reads it. Measurement
    files belong on the block jobs.
    """
    summary_path = root / "summary.json"
    if not summary_path.is_file() or any(root.glob("*/*/summary.json")):
        return
    summary = json.loads(summary_path.read_text())
    order = summary.get("order") or []
    reps = sorted({rep for rep, _ed in order if isinstance(rep, int)})
    if reps != list(range(10)):
        return
    total = (summary.get("cpu_accounting") or {}).get("samples_total")
    if total is None:
        total = len(order)
    accounting = {**(summary.get("cpu_accounting") or {}), "samples_total": total}
    for index, lo, hi in ((1, 0, 5), (2, 5, 10)):
        job = root / "benchmark_input" / ("b%d" % index)
        job.mkdir(parents=True)
        block = {
            **summary,
            "run_id": "%s-b%d" % (summary.get("run_id"), index),
            "order": [[rep, ed] for rep, ed in order if isinstance(rep, int) and lo <= rep < hi],
            "block": {"index": index, "of": 2, "repetitions": 5},
            "cpu_accounting": accounting,
        }
        (job / "summary.json").write_text(json.dumps(block))


def _write_trial(root: Path, rep: int, editor: str, criterion: str, **kwargs) -> None:
    job = _block_dir(root, rep)
    cell = job / "cells" / f"{rep:04d}-{editor}" / "attempts"
    cell.mkdir(parents=True, exist_ok=True)
    path = cell / f"{criterion.lower()}.json"
    path.write_text(json.dumps(_trial(editor, criterion, **kwargs)), encoding="utf-8")


def _summary(root: Path, *, run_id: str, seed: int, editors: list[str], reps: int = 10) -> dict:
    host = dict(
        cpu_model="fixture CPU",
        cpu_cores_logical=16,
        os="Linux",
        os_version="fixture",
        power_source="ac",
        container=True,
        cpu_quota=8,
        machine_vendor="Amazon EC2",
        machine_product="r6a.16xlarge",
        hypervisor=True,
    )
    return {
        "run_id": run_id,
        "seed": seed,
        "execution_profile": "dedicated_publish",
        "host_class": "shared_guarded",
        "publishable": True,
        "order": [[i, e] for i in range(reps) for e in editors],
        "host": host,
        "rendering": {
            "headless": True,
            "browser_version": "130.0.6723.31",
            "renderer": "ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero)), SwiftShader driver)",
        },
        "versions": {
            "editors": {e: {"pin": f"pin-{e}"} for e in editors},
            "tools": {"playwright": "1.64.1", "node": "v22"},
        },
        "cpu_steal_percent": 0.027,
        "cpu_throttle_refused_samples": 2,
        "cpu_accounting": {"samples_total": reps * len(editors), "samples_refused": 2},
        "samples": [],
    }


def _write_run(root: Path, **summary_kw) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    summary = _summary(root, **summary_kw)
    (root / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    _lay_blocks(root)
    return root


@pytest.mark.usefixtures("fake_legacy_tree")
class ReportE2Facts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)

    def _pair(self, primary_kw, repro_kw, writer):
        primary = _write_run(self.base / "primary", **primary_kw)
        repro = _write_run(self.base / "repro", **repro_kw)
        writer(primary)
        writer(repro)
        return primary, repro

    def test_nine_kept_samples_print_median_and_range(self):
        primary, _ = self._pair(
            {"run_id": "a", "seed": 1, "editors": ["plate"]},
            {"run_id": "b", "seed": 2, "editors": ["plate"]},
            lambda root: [
                _write_trial(root, i, "plate", "C07", outcome="measured", samples=[20.0]) for i in range(9)
            ] + [_write_trial(root, 9, "plate", "C07", outcome="refused", samples=[])],
        )
        facts = E2.facts_from_runs(primary, self.base / "repro")
        table = facts["perf.e2.table.C07"]
        self.assertNotIn("not enough samples", table)
        self.assertIn("n = 9 of 10", table)
        self.assertNotIn("p90", table)
        self.assertIn("range", table)

    def test_ten_kept_samples_publish_when_runs_agree(self):
        def fill(root):
            for i in range(10):
                _write_trial(root, i, "plate", "C07", outcome="measured", samples=[20.0])

        primary, repro = self._pair(
            {"run_id": "a", "seed": 1, "editors": ["plate"]},
            {"run_id": "b", "seed": 2, "editors": ["plate"]},
            fill,
        )
        facts = E2.facts_from_runs(primary, repro)
        table = facts["perf.e2.table.C07"]
        self.assertIn("20.0 ms", table)
        self.assertIn("p90", table)
        self.assertNotIn("range", table)
        self.assertNotIn("not reproduced", table)

    def test_non_reproducing_pair_shows_both_medians(self):
        primary = _write_run(self.base / "primary", run_id="a", seed=1, editors=["plate"])
        repro = _write_run(self.base / "repro", run_id="b", seed=2, editors=["plate"])
        for i in range(10):
            _write_trial(primary, i, "plate", "C07", outcome="measured", samples=[20.0])
            _write_trial(repro, i, "plate", "C07", outcome="measured", samples=[50.0])
        facts = E2.facts_from_runs(primary, repro)
        table = facts["perf.e2.table.C07"]
        self.assertIn("not reproduced", table)
        self.assertIn("20.0 ms", table)
        self.assertIn("50.0 ms", table)
        self.assertIn("Plate.js", facts["perf.e2.not_reproduced"])
        self.assertIn("50.0 ms", facts["perf.e2.not_reproduced"])

    def test_sub_frame_median_bucket(self):
        def fill(root):
            for i in range(10):
                _write_trial(
                    root,
                    i,
                    "plate",
                    "C07",
                    outcome="measured",
                    samples=[9.9],
                    sub_frame_samples=[True],
                )

        primary, repro = self._pair(
            {"run_id": "a", "seed": 1, "editors": ["plate"]},
            {"run_id": "b", "seed": 2, "editors": ["plate"]},
            fill,
        )
        facts = E2.facts_from_runs(primary, repro)
        self.assertIn("< 1 frame (16.7 ms)", facts["perf.e2.table.C07"])
        self.assertNotIn("9.9", facts["perf.e2.table.C07"])

    def test_refused_only_cell_lists_reasons(self):
        def fill(root):
            for i in range(5):
                _write_trial(root, i, "plate", "C07", outcome="failed", failure_reason="timeout")
            for i in range(5, 10):
                _write_trial(root, i, "plate", "C07", outcome="refused", refusal_code="cpu_throttled")

        primary, repro = self._pair(
            {"run_id": "a", "seed": 1, "editors": ["plate"]},
            {"run_id": "b", "seed": 2, "editors": ["plate"]},
            fill,
        )
        facts = E2.facts_from_runs(primary, repro)
        table = facts["perf.e2.table.C07"]
        self.assertIn("not enough samples", table)
        self.assertIn("crash: 5", table)

    def test_not_run_editor_shows_recorded_reason(self):
        primary = _write_run(self.base / "primary", run_id="a", seed=1, editors=["plate", "docen"])
        repro = _write_run(self.base / "repro", run_id="b", seed=2, editors=["plate", "docen"])
        for i in range(10):
            _write_trial(primary, i, "plate", "C07", outcome="measured", samples=[20.0])
            _write_trial(repro, i, "plate", "C07", outcome="measured", samples=[20.0])
            _write_trial(primary, i, "docen", "C07", outcome="not_run", failure_reason="host_build: dev_server", refusal_code="host_build")
            _write_trial(repro, i, "docen", "C07", outcome="not_run", failure_reason="host_build: dev_server", refusal_code="host_build")
        facts = E2.facts_from_runs(primary, repro)
        table = facts["perf.e2.table.C07"]
        self.assertIn("Docen", table)
        self.assertRegex(table, r"not run|host_build|dev_server")

    def test_same_seed_refusal(self):
        primary = _write_run(self.base / "primary", run_id="a", seed=1, editors=["plate"])
        repro = _write_run(self.base / "repro", run_id="b", seed=1, editors=["plate"])
        with self.assertRaises(ValueError) as ctx:
            E2.facts_from_runs(primary, repro)
        self.assertIn("seed", str(ctx.exception).lower())

    def test_rows_are_alphabetical(self):
        primary = _write_run(self.base / "primary", run_id="a", seed=1, editors=["plate", "wordcraft"])
        repro = _write_run(self.base / "repro", run_id="b", seed=2, editors=["plate", "wordcraft"])
        for i in range(10):
            for editor in ("plate", "wordcraft"):
                _write_trial(primary, i, editor, "C07", outcome="measured", samples=[20.0])
                _write_trial(repro, i, editor, "C07", outcome="measured", samples=[20.0])
        facts = E2.facts_from_runs(primary, repro)
        rows = [
            line.split("|")[1].strip()
            for line in facts["perf.e2.table.C07"].splitlines()[2:]
            if line.startswith("|")
        ]
        self.assertEqual(rows, sorted(rows, key=str.casefold))

    def test_mutated_median_changes_rendered_report(self):
        primary = _write_run(self.base / "primary", run_id="a", seed=1, editors=["plate"])
        repro = _write_run(self.base / "repro", run_id="b", seed=2, editors=["plate"])
        for i in range(10):
            _write_trial(primary, i, "plate", "C07", outcome="measured", samples=[20.0])
            _write_trial(repro, i, "plate", "C07", outcome="measured", samples=[20.0])
        facts = E2.facts_from_runs(primary, repro)
        tpl = (render_reports.TEMPLATES / "reports/Report E2 - Speed in the Browser (2026).md").read_text()
        rendered_a = render_reports.reportgen.render(tpl, facts)
        facts["perf.e2.table.C07"] = facts["perf.e2.table.C07"].replace("20.0 ms", "99.9 ms")
        rendered_b = render_reports.reportgen.render(tpl, facts)
        self.assertNotEqual(rendered_a, rendered_b)

    def test_tables_pass_anti_ranking_guard(self):
        primary = _write_run(self.base / "primary", run_id="a", seed=1, editors=["plate", "wordcraft"])
        repro = _write_run(self.base / "repro", run_id="b", seed=2, editors=["plate", "wordcraft"])
        for i in range(10):
            for editor in ("plate", "wordcraft"):
                _write_trial(primary, i, editor, "C07", outcome="measured", samples=[20.0 + i])
                _write_trial(repro, i, editor, "C07", outcome="measured", samples=[20.0 + i])
        facts = E2.facts_from_runs(primary, repro)
        for key in facts:
            if key.startswith("perf.e2.table."):
                assert_markdown_no_editor_speed_ranking(facts[key])


if __name__ == "__main__":
    unittest.main()


# Regression fixtures mirror run_cli's cells / samples / rejected-evidence layout.
# pyfakefs keeps these unit tests independent of the real filesystem and host.

@pytest.fixture
def runs(fs):
    roots = [Path('/runs/a'), Path('/runs/b')]
    for seed, root in enumerate(roots):
        root.mkdir(parents=True)
        summary = dict(run_id=root.name, seed=seed, execution_profile='dedicated_publish',
                       publishable=True, host_class='dedicated', host={}, rendering={},
                       order=[[i, e] for i in range(10) for e in ['plate', 'docen']])
        (root / 'summary.json').write_text(json.dumps(summary))
        _lay_blocks(root)
        for i in range(10):
            _write_trial(root, i, 'plate', 'C07', outcome='measured', samples=[100], diagnostic={'frame_interval_ms':16.7})
    return roots

def change_summary(root, **kw):
    def write(path, extra):
        path.write_text(json.dumps({**json.loads(path.read_text()), **extra}))

    write(root / 'summary.json', kw)
    for path in sorted(root.glob('*/*/summary.json')):
        current = json.loads(path.read_text())
        extra = dict(kw)
        index = (current.get('block') or {}).get('index')
        if 'run_id' in extra and index:
            extra['run_id'] = '%s-b%s' % (extra['run_id'], index)
        if 'order' in extra and index:
            lo, hi = (0, 5) if index == 1 else (5, 10)
            extra['order'] = [pair for pair in (extra['order'] or [])
                              if isinstance(pair[0], int) and lo <= pair[0] < hi]
        write(path, extra)

def fill(root, samples, frame=16.7, n=10):
    for path in root.rglob('*.json'):
        if 'cells' in path.parts and path.is_file():
            path.unlink()
    diagnostic = {} if frame is None else {'frame_interval_ms': frame}
    for i in range(10):
        if i < n:
            _write_trial(root, i, 'plate', 'C07', outcome='measured', samples=samples, diagnostic=diagnostic)
        else:
            _write_trial(root, i, 'plate', 'C07', outcome='refused', samples=[], diagnostic=diagnostic)

def table(runs):
    return E2.facts_from_runs(*runs)['perf.e2.table.C07']

def test_finding_01_no_invented_frame(runs):
    fill(runs[1], [115])
    fill(runs[0], [100], frame=None)
    fill(runs[1], [115], frame=None)
    assert 'sub_frame_flag_mismatch' in table(runs)
    assert '100.0 ms' not in table(runs)

def test_finding_02_symmetric_larger_interval(runs):
    fill(runs[0], [140], 16.7)
    fill(runs[1], [100], 50)
    for pair in (runs, runs[::-1]):
        assert E2.facts_from_runs(*pair)['perf.e2.plate.C07.reproduced'] is True

def test_finding_03_kept_frame_median(runs):
    for root in runs:
        fill(root, [8], 16.7)
        # The campaign schedules exactly 10, and r3s2fix 3 refuses a launch
        # the order never named, so the not_run rows replace fill's reps
        # 5–9. Five measured frames of 16.7 keep the median at 16.7. Five
        # frames of 1, if included, pull that median off 16.7.
        for rep in range(5, 10):
            _write_trial(root, rep, 'plate', 'C07', outcome='not_run', diagnostic={'frame_interval_ms': 1})
    assert '< 1 frame (16.7 ms)' in table(runs)
    cell = E2.e2_cells.build_run_cell(runs[0], 'plate', 'C07')
    assert cell['frame_interval_ms'] == 16.7

def test_finding_04_rejected_and_sample_refused(runs):
    for root in runs:
        job = _block_dir(root, 9)
        # The launch file stays: dropping it leaves the block short of five
        # files and the layout gate hides the quarantine.
        (job / 'rejected-evidence/0009-plate/cell').mkdir(parents=True)
        (job / 'samples').mkdir(exist_ok=True)
        (job / 'samples/0009-plate.json').write_text(json.dumps(dict(editor_id='plate', repetition=9, outcome='failed', failure_reason='cpu_throttled', refusal_code='cpu_throttled')))
    assert 'n = 9 of 10' in table(runs)
    assert 'cpu_throttled' in table(runs)
    # A refusal must also veto an otherwise measured file still under cells.
    for root in runs:
        _write_trial(root, 9, 'plate', 'C07', outcome='measured', samples=[100])
    assert 'n = 9 of 10' in table(runs)

def test_finding_05_launch_not_click_count(runs):
    for root in runs:
        fill(root, [20, 21, 22], n=4)
    assert 'n = 4 of 10' in table(runs)
    for root in runs:
        fill(root, [20, 21, 22])
    cell = E2.e2_cells.build_run_cell(runs[0], 'plate', 'C07')
    assert cell['stats']['n'] == 10
    assert cell['stats']['p90'] == 21
    assert cell['raw_samples_ms'] == [[20, 21, 22]] * 10

def test_finding_06_host_both_runs(runs):
    for root in runs:
        change_summary(root, host={'cpu_quota': 2, 'os': 'Darwin'}, rendering={'renderer': 'NVIDIA'})
    change_summary(runs[1], cpu_steal_percent=37.5, cpu_throttle_refused_samples=20)
    note = E2.facts_from_runs(*runs)['perf.e2.host_note']
    assert '37.50%' in note and '20 of 20' in note
    assert 'Darwin' in note and 'NVIDIA' in note
    assert '8-CPU' not in note and 'software rasterization' not in note

def test_finding_07_unpublishable_run(runs):
    change_summary(runs[1], publishable=False, publication_block_reason='cpu_accounting_unavailable')
    assert 'cpu_accounting_unavailable' in table(runs)
    assert '100.0 ms' not in table(runs)

@pytest.mark.parametrize('field', ['tree', 'playwright_version', 'vendor', 'browser_version', 'host_class'])
def test_finding_08_real_version_locations(runs, field):
    if field == 'tree':
        for p in (runs[1]).rglob('cells/**/*.json'):
            row = json.loads(p.read_text()); row['host_provenance']['tree_sha256'] = 'tree-other'
            p.write_text(json.dumps(row))
    elif field == 'host_class':
        change_summary(runs[1], host_class='other')
    else:
        change_summary(runs[1], rendering={field: 'different'})
    with pytest.raises(ValueError):
        table(runs)

def test_finding_09_all_scheduled_editors_count(runs):
    facts = E2.facts_from_runs(*runs)
    assert facts['perf.e2.cells_checked'] == 2  # two scheduled editors; only C07 is present
    assert facts['perf.e2.cells_reproduced'] == 1
    assert 'Docen' in facts['perf.e2.not_reproduced']

def test_finding_10_missing_date(runs):
    assert E2.facts_from_runs(*runs)['perf.e2.date'] == 'not recorded'

def test_finding_11_unmeasured_prose():
    tpl = (render_reports.TEMPLATES / 'reports/Report E2 - Speed in the Browser (2026).md').read_text()
    text = render_reports.reportgen.render(tpl, E2.unset_facts())
    assert 'not yet measured' in text
    assert 'It was measured' not in text
    assert '0 of 0 cells reproduced' not in text

def test_finding_12_docx_exists_and_word_registered():
    import verify_deliverables
    name = 'Report E2 - Speed in the Browser (2026).docx'
    assert (ROOT / 'reports' / name).is_file()
    assert name in [Path(p).name for p, _ in verify_deliverables.DELIVERABLES]

def test_finding_13_missing_flags_are_unknown(runs):
    assert 'sub-frame samples' not in table(runs)

def test_finding_14_asymmetric_gate_and_sample_mutation(runs):
    fill(runs[1], [100], n=4)
    assert 'n = 4 of 10' in table(runs)
    fill(runs[1], [100])
    before = table(runs)
    for root in runs:
        fill(root, [200])
    assert table(runs) != before


@pytest.fixture
def fake_legacy_tree(fs):
    template = render_reports.TEMPLATES / 'reports/Report E2 - Speed in the Browser (2026).md'
    fs.add_real_file(template)

@pytest.mark.parametrize('left,right', [(True, False), (False, True)])
def test_both_run_verdicts_required(runs, left, right):
    # A genuinely blocked run (real publication_block_reason, as the runner
    # writes for cpu-accounting loss or dirty repos) on either side refuses.
    # publishable False alone is the job-summary shape whose publishability
    # lives in the trials (see test_job_summaries_delegate_publishability).
    change_summary(runs[0], publishable=left,
                   **({} if left else {'publication_block_reason': 'cpu_accounting_unavailable'}))
    change_summary(runs[1], publishable=right,
                   **({} if right else {'publication_block_reason': 'cpu_accounting_unavailable'}))
    assert 'unpublishable' in table(runs)
    assert E2.facts_from_runs(*runs)['perf.e2.cells_reproduced'] == 0

def test_unequal_click_counts_equal_launch_weight_and_interval_median(runs):
    for root in runs:
        fill(root, [10], 20)
        _write_trial(root, 0, 'plate', 'C07', outcome='measured', samples=[1000]*100,
                     diagnostic={'frame_interval_ms': 1})
    cell = E2.e2_cells.build_run_cell(runs[0], 'plate', 'C07')
    assert cell['stats']['median'] == 10
    assert cell['frame_interval_ms'] == 20
    assert '< 1 frame (20 ms)' in table(runs)

def test_summary_scheduled_count_missing_blocks_publication(runs):
    change_summary(runs[0], order=[])
    assert 'scheduled count not recorded' in table(runs)

@pytest.mark.parametrize('change,match', [({'run_id':'a'}, 'same run'), ({'host':{'cpu_model':'other'}}, 'host'),
    ({'versions':{'tools':{'playwright':'other'}}}, 'versions'), ({'execution_profile':'ci_contract'}, 'dedicated_publish')])
def test_other_comparability_guards(runs, change, match):
    change_summary(runs[1], **change)
    with pytest.raises(ValueError, match=match):
        table(runs)

def test_same_directory_refused(runs):
    with pytest.raises(ValueError, match='same run directory'):
        table([runs[0], runs[0]])

def test_sample_flags_and_invalid_trial_values(runs):
    root = runs[0]
    _write_trial(root, 0, 'plate', 'C07', outcome='measured', samples=[None, True, 'bad'], diagnostic={})
    _write_trial(root, 1, 'plate', 'C07', outcome='measured', samples=[20], sub_frame_samples=[False, True])
    job = _block_dir(root, 0)
    (job / 'cells/extra.json').write_text('bad json')
    (job / 'cells/list.json').write_text('[]')
    cell = E2.e2_cells.build_run_cell(root, 'plate', 'C07')
    assert cell['stats']['n'] == 8
    assert cell['refusals'] == {'malformed_samples': 2}

def test_recorded_dates_and_accounting_fallback(runs):
    for root in runs:
        change_summary(root, started_at='2026-11-01T12:00:00Z', cpu_accounting={'steal_percent':2, 'samples_refused':3, 'samples_total':80})
    facts = E2.facts_from_runs(*runs)
    assert facts['perf.e2.date'] == '2026-11-01'
    assert '3 of 80' in facts['perf.e2.host_note']


def sample_row(root, rep, reason, code="crash"):
    job = _block_dir(root, rep)
    directory = job / 'cells' / f'{rep:04d}-plate'
    samples = job / 'samples'
    samples.mkdir(exist_ok=True)
    (samples / f'{rep:04d}-plate.json').write_text(json.dumps(dict(
        outcome='failed', non_failure_outcomes=[], failure_reason=reason, refusal_code=code,
        exit_code=0, cell_directory=str(directory), repetition=rep, editor_id='plate')))


def test_failed_sibling_keeps_measured_criterion(runs):
    for root in runs:
        for rep in range(10):
            _write_trial(root, rep, 'plate', 'C04', outcome='failed',
                         failure_reason='search_timeout: selector', refusal_code='search_timeout')
            sample_row(root, rep, 'search_timeout: selector')
    facts = E2.facts_from_runs(*runs)
    assert facts['perf.e2.plate.C07.reproduced'] is True
    assert facts['perf.e2.plate.C07.primary']['stats']['n'] == 10
    assert '100.0 ms' in facts['perf.e2.table.C07']
    assert 'n = 0 of 10' in facts['perf.e2.table.C04']
    assert 'search_timeout: 10' in facts['perf.e2.table.C04']


@pytest.mark.parametrize('reason', ['cpu_throttled', 'cpu_accounting_unavailable', 'host_build: dev_server'])
def test_launch_wide_refusal_still_vetoes_measured_trials(runs, reason):
    for root in runs:
        sample_row(root, 9, reason, reason.split(':')[0])
    assert 'n = 9 of 10' in table(runs)


def test_quarantined_launch_vetoes_leftover_cells(runs):
    for root in runs:
        (_block_dir(root, 9) / 'rejected-evidence/0009-plate/cell').mkdir(parents=True)
    assert 'n = 9 of 10' in table(runs)


@pytest.mark.parametrize('bad_summary', [None, '{not json'])
def test_dual_api_requires_readable_summaries(runs, bad_summary):
    path = runs[1] / 'summary.json'
    if bad_summary is None:
        path.unlink()
    else:
        path.write_text(bad_summary)
    with pytest.raises((FileNotFoundError, json.JSONDecodeError)):
        E2.e2_cells.publish_dual_runs(*runs, 'plate', 'C07')


@pytest.mark.parametrize('short_primary', [False, True])
def test_dual_api_reports_blocked_reproduction(runs, short_primary):
    if short_primary:
        fill(runs[0], [100], n=4)
    change_summary(runs[1], publishable=False, publication_block_reason='repos_modified')
    text = E2.e2_cells.publish_dual_runs(*runs, 'plate', 'C07')
    assert 'second run unpublishable: repos_modified' in text
    assert '100.0 ms' not in text
    if short_primary:
        assert 'n = 4 of 10' in text


@pytest.mark.parametrize('left,right,frames,expected', [
    (1, 25, (16.7, 16.7), False), (100, 140, (50, 16.7), True),
    (100, 160, (50, 16.7), False), (100, 115, (None, None), False),
])
def test_dual_api_uses_same_raw_median_gate(runs, left, right, frames, expected):
    for root, value, frame in zip(runs, (left, right), frames):
        fill(root, [value], frame)
    for pair in (runs, runs[::-1]):
        facts = E2.facts_from_runs(*pair)
        text = E2.e2_cells.publish_dual_runs(*pair, 'plate', 'C07')
        assert facts['perf.e2.plate.C07.reproduced'] is expected
        assert text in facts['perf.e2.table.C07']
        if frames == (None, None):
            assert 'sub_frame_flag_mismatch' in text
        else:
            assert ('not reproduced' in text) is not expected


def test_partial_sub_frame_flags_do_not_publish_subset_share(runs):
    for root in runs:
        for rep in range(5):
            _write_trial(root, rep, 'plate', 'C07', outcome='measured',
                         samples=[8], sub_frame_samples=[True])
        for rep in range(5, 10):
            _write_trial(root, rep, 'plate', 'C07', outcome='measured', samples=[20], sub_frame_samples=None)
    text = table(runs)
    # Kept launches publish their own share. Malformed launches stay out of it.
    assert '100% sub-frame launches' in text
    assert '50% sub-frame' not in text
    assert 'malformed_samples: 5' in text


def test_sub_frame_share_counts_launch_medians_not_clicks(runs):
    for root in runs:
        for rep in range(10):
            _write_trial(root, rep, 'plate', 'C07', outcome='measured',
                         samples=[8.5, 20, 30], sub_frame_samples=[True, False, False])
    assert '0% sub-frame launches' in table(runs)
    for root in runs:
        _write_trial(root, 0, 'plate', 'C07', outcome='measured',
                     samples=[8]*100, sub_frame_samples=[True]*100)
    assert '10% sub-frame launches' in table(runs)


def test_job_summaries_delegate_publishability_to_trials(runs):
    # browser_run.py hardwires job summaries to publishable False and sets
    # publication_block_reason only for cpu-accounting loss or dirty repos;
    # publishability rides on each trial. A job summary in that real shape
    # must not blank every timing cell behind "publishable not true".
    for root in runs:
        change_summary(root, publishable=False)
    plate = next(line for line in table(runs).splitlines() if 'Plate' in line)
    assert 'unpublishable' not in plate
    assert '100.0 ms' in plate
    assert E2.facts_from_runs(*runs)['perf.e2.plate.C07.reproduced'] is True


def test_quarantine_refusals_are_scoped_to_editor(runs):
    (_block_dir(runs[0], 9) / 'rejected-evidence/0009-docen/cell').mkdir(parents=True)
    cell = E2.e2_cells.build_run_cell(runs[0], 'plate', 'C07')
    assert cell['stats']['n'] == 10
    assert cell['refusals'] == {}


# Issue #178: a publication campaign is many run folders over two seeds, not
# a primary and a reproduction run. The header facts must describe the
# campaign; the classic two-root output stays byte-identical.


def _campaign_farm(base: Path, *, chromium_diff: bool = False) -> list[Path]:
    """Six farm roots — three per seed on two named Spaces, one lane job each."""
    specs = [
        ("e2-alpha", "r1a", 1, {"started_at": "2026-11-10T08:00:00Z", "finished_at": "2026-11-10T09:30:00Z"}),
        ("e2-alpha", "r1b", 1, {"started_at": "2026-11-10T10:00:00Z", "finished_at": "2026-11-10T10:45:00Z"}),
        ("e2-beta", "r1c", 1, {"started_at": "2026-11-10T11:00:00Z", "finished_at": "2026-11-10T11:20:00Z"}),
        ("e2-alpha", "r2a", 2, {"started_at": "2026-11-11T08:00:00Z", "finished_at": "2026-11-11T08:30:00Z"}),
        ("e2-beta", "r2b", 2, {"run_id": "20261113T235959Z-9-9"}),  # the run stamp is the only recorded day
        ("e2-apryse", "r2c", 2, {"started_at": "2026-11-12T08:00:00Z", "finished_at": "2026-11-12T09:00:00Z"}),
    ]
    roots = []
    for index, (space, rid, seed, extra) in enumerate(specs):
        root = base / ("%s--%s" % (space, rid))
        job = root / "benchmark_input" / ("%s-1" % rid)
        job.mkdir(parents=True)
        summary = _summary(job, run_id="%s-1" % rid, seed=seed, editors=["plate"], reps=5)
        summary["block"] = {"index": 1, "of": 2, "repetitions": 5}
        summary["hosts"] = {"plate": {"host_build": "production", "tree_sha256": "tree-fixture"}}
        summary.update(extra)
        if chromium_diff and index == 2:
            summary["rendering"] = {**summary["rendering"], "browser_version": "154.0.0.0"}
        (job / "summary.json").write_text(json.dumps(summary))
        for rep in range(3):
            _write_trial(root, rep, "plate", "C07", outcome="measured", samples=[20.0])
        roots.append(root)
    return roots


@pytest.mark.usefixtures("fake_legacy_tree")
def test_campaign_header_describes_the_campaign(fs):
    roots = _campaign_farm(Path("/farm"))
    facts = E2.facts_from_roots(roots)
    intro = facts["perf.e2.intro"]
    assert "two runs" not in intro
    assert "Primary run" not in intro and "Reproduction run" not in intro
    assert "seed 1" in intro and "seed 2" in intro
    assert "6 run folders" in intro and "6 jobs" in intro
    assert "not recorded" not in intro
    assert "2026-11-10" in intro and "2026-11-13" in intro
    line = facts["perf.e2.runs"]
    assert "Primary run" not in line and "Reproduction run" not in line
    assert "3" in line and "seed 1" in line and "seed 2" in line
    assert "2026-11-10" in line and "2026-11-13" in line
    note = facts["perf.e2.host_note"]
    assert "--" not in note.split("Chromium")[0].split("renderer")[0]
    assert "e2-alpha" in note and "e2-beta" in note and "e2-apryse" in note
    assert "machine name" in note
    header = facts["perf.e2.not_reproduced"].splitlines()[0]
    assert "First seed" in header and "Second seed" in header
    assert "First run" not in header and "Second run" not in header
    assert "Both runs" not in facts["perf.e2.rule"]
    assert "seed" in facts["perf.e2.rule"].lower()
    provenance = facts["perf.e2.provenance"]
    assert "e2-alpha" in provenance and "e2-beta" in provenance
    tpl = (render_reports.TEMPLATES / "reports/Report E2 - Speed in the Browser (2026).md").read_text()
    rendered = render_reports.reportgen.render(tpl, facts)
    assert "Primary run" not in rendered and "Reproduction run" not in rendered
    assert "2026-11-13" in rendered


def test_campaign_host_note_discloses_distinct_job_values(fs):
    roots = _campaign_farm(Path("/farm"), chromium_diff=True)
    facts = E2.facts_from_roots(roots)
    note = facts["perf.e2.host_note"]
    assert "130.0.6723.31" in note and "154.0.0.0" in note
    # One seed-1 job disagrees on Chromium: both versions, with job counts.
    assert "(2 jobs)" in note and "(1 job)" in note


def test_classic_header_facts_byte_identical(runs):
    facts = E2.facts_from_runs(*runs)
    assert facts["perf.e2.intro"] == (
        "1 of 2 scheduled editor/criterion/measure cells reproduced between the two runs. "
        "Dates: first not recorded; second not recorded."
    )
    assert facts["perf.e2.date"] == "not recorded"
    assert facts["perf.e2.repro_date"] == "not recorded"
    assert facts["perf.e2.run_id"] == "a" and facts["perf.e2.repro_run_id"] == "b"
    assert facts["perf.e2.seed"] == 0 and facts["perf.e2.repro_seed"] == 1
    assert facts["perf.e2.provenance"] == "Per-Space provenance not supplied."
    assert "| First run / reason | Second run, median |" in facts["perf.e2.not_reproduced"]
    assert "Both runs must keep at least 5 launches per cell" in facts["perf.e2.rule"]
    assert facts["perf.e2.host_note"] == (
        "First run: Host class: dedicated. not recorded; CPU quota not recorded; "
        "logical CPUs not recorded; OS not recorded not recorded; power not recorded. "
        "Playwright not recorded; Chromium not recorded; renderer not recorded; headless not recorded. "
        "Stolen CPU time: not recorded. Throttle: not recorded. Editor pins: {'plate': ['tree-fixture']}.\n\n"
        "Second run: Host class: dedicated. not recorded; CPU quota not recorded; "
        "logical CPUs not recorded; OS not recorded not recorded; power not recorded. "
        "Playwright not recorded; Chromium not recorded; renderer not recorded; headless not recorded. "
        "Stolen CPU time: not recorded. Throttle: not recorded. Editor pins: {'plate': ['tree-fixture']}."
    )


def test_classic_run_line_unchanged(runs):
    facts = E2.facts_from_runs(*runs)
    assert facts["perf.e2.runs"] == (
        "Primary run `a`, seed 0 (not recorded). "
        "Reproduction run `b`, seed 1 (not recorded)."
    )


def _blocked_pool(*_args, **_kwargs):
    group = {'scheduled': 5, 'blocked': True, 'block_reason': 'repos_modified', 'refusals': {}}
    return {'published': False, 'reason': 'blocked', 'groups': [dict(group), dict(group)]}


@pytest.mark.parametrize('word', ['run', 'seed'])
def test_unpublishable_rows_name_the_group_the_table_compares(monkeypatch, word):
    """Campaign cells compare seeds, classic cells runs; the row says which (#178 review)."""
    monkeypatch.setattr(E2.e2_cells, 'read_criterion_cell', _blocked_pool)
    facts: dict = {}
    text = E2._cell_text(facts, [], 'plate', 'C07', word=word)
    assert 'first %s unpublishable: repos_modified (blocked)' % word in text
    assert 'second %s unpublishable: repos_modified (blocked)' % word in text


def test_campaign_throttle_sum_keeps_the_unavailable_accounting_disclosure():
    """A seed's sum says when CPU accounting was unavailable, as the classic note does (#178 review)."""
    rows = [
        {'cpu_accounting': {'samples_total': 10, 'samples_refused': 1, 'samples_unavailable': 2}},
        {'cpu_accounting': {'samples_total': 10, 'samples_refused': 0}},
    ]
    assert E2._throttle_sum(rows) == (
        '2 of 20 samples had CPU accounting unavailable; 1 of 20 samples refused for cgroup CPU throttling')
    assert E2._throttle_sum(rows[1:]) == '0 of 10 samples refused for cgroup CPU throttling'


@pytest.mark.usefixtures("fake_legacy_tree")
def test_campaign_names_the_editors_the_browser_run_did_not_measure(fs):
    """Every roster editor without browser data is named with its reason, never '- none' (#178 follow-up)."""
    roots = _campaign_farm(Path("/farm"))
    text = E2.facts_from_roots(roots)["perf.e2.not_run"]
    assert text != "- none"
    for name, reason in (("Apryse", "licence key"), ("docs.plus", "application servers"),
                         ("Fidus", "application server"), ("office-open", "library"),
                         ("LibreOffice", "conversion baseline")):
        line = next((item for item in text.splitlines() if name in item), None)
        assert line is not None, name
        assert reason in line, line
    assert "Plate" not in text


def test_placeholder_rows_never_make_a_table_row(monkeypatch):
    """warm/cold's adapter-not-implemented C10 rows add no 'warm_steady' row beside the scroll lane's (#179)."""
    rows = [
        {'editor_id': 'plate', 'criterion_id': 'C10', 'workload_id': 'prose-500w', 'outcome': 'measured'},
        {'editor_id': 'plate', 'criterion_id': 'C10', 'workload_id': 'prose-500w', 'measure': 'warm_steady',
         'outcome': 'not_run', 'failure_reason': 'adapter-not-implemented: criterion C10 not driven on warm_cold host yet'},
    ]
    monkeypatch.setattr(E2.e2_cells, '_iter_trials', lambda root: iter(rows))
    seen = []
    monkeypatch.setattr(E2, '_cell_text', lambda facts, roots, editor, criterion, measure, workload, word='run': seen.append(measure) or 'x')
    E2._criterion_table({}, ['/r'], 'C10', ['plate'])
    assert 'warm_steady' not in seen and seen == ['']


def test_a_criterion_with_only_placeholder_rows_keeps_its_row(monkeypatch):
    rows = [{'editor_id': 'plate', 'criterion_id': 'C22', 'workload_id': 'prose-500w', 'measure': 'warm_steady',
             'outcome': 'not_run', 'failure_reason': 'adapter-not-implemented: criterion C22 not driven on warm_cold host yet'}]
    monkeypatch.setattr(E2.e2_cells, '_iter_trials', lambda root: iter(rows))
    seen = []
    monkeypatch.setattr(E2, '_cell_text', lambda facts, roots, editor, criterion, measure, workload, word='run': seen.append(measure) or 'x')
    E2._criterion_table({}, ['/r'], 'C22', ['plate'])
    assert seen == ['warm_steady']


def test_reruns_text_states_the_campaign_counts():
    text = E2.reruns_text({'first_pass_superseded': 32, 'rerun_kept': 32, 'first_pass_unsealed': 0,
                           'rerun_unsealed': 0, 'missing_runs': []})
    assert '32 first-pass jobs' in text and '32 re-run jobs' in text
    assert '#173' in text and 'e2_publication.json' in text
    assert 'missing' not in text and 'unsealed' not in text
    partial = E2.reruns_text({'first_pass_superseded': 32, 'rerun_kept': 31, 'rerun_unsealed': 1,
                              'missing_runs': ['space/run']})
    assert '1 re-run job was not sealed' in partial and '1 run of the manifest is missing' in partial
    assert E2.reruns_text(None).startswith('- **Re-run jobs.** None')
    assert E2.unset_facts()['perf.e2.reruns'] == E2.reruns_text(None)


def test_pins_text_is_prose_not_a_python_dict():
    text = E2._pins_text({'plate': ['0b3c24cc2bf9348a9e904d22' + 'f' * 40], 'canvas': ['db742f005c45' + 'e' * 52, 'not recorded']})
    assert '{' not in text and '[' not in text
    assert text.startswith('Editor pins (built-editor tree SHA-256 of every attempt that ran, in every run folder):')
    assert 'canvas-editor + plugin: db742f005c45%s, not recorded' % ('e' * 52) in text
    assert 'Plate.js: 0b3c24cc2bf9348a9e904d22' in text


def test_campaign_pins_are_read_from_every_root(fs, monkeypatch):
    seen = []
    monkeypatch.setattr(E2, '_pins', lambda root, **kw: seen.append(root) or {'plate': ['tree-%s' % len(seen)]})
    merged = E2._campaign_pins([Path('/a'), Path('/b')])
    assert seen == [Path('/a'), Path('/b')]
    assert merged == {'plate': ['tree-1', 'tree-2']}


def test_throttle_sum_reports_unavailable_accounting_without_refusals():
    """A seed with unavailable accounting and no refused-sample key is not 'not recorded' (GLM M2)."""
    rows = [{'cpu_accounting': {'samples_total': 10, 'samples_unavailable': 3}}]
    assert E2._throttle_sum(rows) == (
        '3 of 10 samples had CPU accounting unavailable; refused samples not recorded')


def test_throttle_sum_counts_refusals_when_any_job_recorded_them():
    rows = [{'cpu_accounting': {'samples_total': 10, 'samples_unavailable': 3, 'samples_refused': 1}}]
    assert E2._throttle_sum(rows) == (
        '3 of 10 samples had CPU accounting unavailable; 1 of 10 samples refused for cgroup CPU throttling')


def test_pins_text_names_versions_when_a_pin_is_not_a_tree_hash():
    """editor_pin can fall back to environment.editor_version; the label must not call it a SHA-256 (GLM m5)."""
    sha = 'a' * 64
    assert E2._pins_text({'plate': [sha, 'not recorded']}).startswith(
        'Editor pins (built-editor tree SHA-256 of every attempt that ran, in every run folder):')
    text = E2._pins_text({'plate': [sha], 'folio': ['1.4.2']})
    assert text.startswith(
        'Editor pins (built-editor tree SHA-256, or the editor version where no tree was recorded, '
        'of every attempt that ran, in every run folder):')


def test_campaign_pins_skip_attempts_that_never_ran(monkeypatch):
    """A not_run row (typing_sessions_unreachable) built nothing; it adds no 'not recorded' pin."""
    rows = [
        {'editor_id': 'plate', 'outcome': 'measured', 'host_provenance': {'tree_sha256': 'tree-a'}},
        {'editor_id': 'plate', 'outcome': 'not_run', 'failure_reason': 'typing_sessions_unreachable'},
    ]
    monkeypatch.setattr(E2.e2_cells, '_iter_trials', lambda root: iter(rows))
    assert E2._campaign_pins([Path('/a')]) == {'plate': ['tree-a']}


@pytest.mark.usefixtures("fake_legacy_tree")
def test_word_verification_names_the_release_gate(fs):
    """The twin is a gated deliverable; the report says how Word checks it, not 'not recorded'."""
    facts = E2.facts_from_roots(_campaign_farm(Path("/farm")))
    text = facts["perf.e2.word_verification"]
    assert "not recorded" not in text
    assert "build/verify_publication.sh --with-word" in text and "Microsoft Word" in text
    assert E2.unset_facts()["perf.e2.word_verification"] == text


def test_throttle_sum_denominator_covers_only_jobs_that_recorded_refusals():
    """A job without a refused count must not inflate the refused fraction's denominator (GLM n1)."""
    rows = [
        {'cpu_accounting': {'samples_total': 10, 'samples_refused': 1}},
        {'cpu_accounting': {'samples_total': 10, 'samples_unavailable': 3}},
    ]
    assert E2._throttle_sum(rows) == (
        '3 of 20 samples had CPU accounting unavailable; 1 of 10 samples refused for cgroup CPU throttling'
        ' (refusals not recorded for the other 10 samples)')


def test_reruns_text_states_a_second_round():
    text = E2.reruns_text({'first_pass_superseded': 32, 'rerun_kept': 28, 'rerun_superseded': 4,
                           'rerun2_kept': 4, 'rerun2_unsealed': 0, 'missing_runs': []})
    assert '32 first-pass jobs' in text and '28 re-run jobs' in text
    assert '#181' in text and '4 C14 jobs' in text and 'second round' in text
    unsealed = E2.reruns_text({'first_pass_superseded': 32, 'rerun_kept': 28, 'rerun_superseded': 4,
                               'rerun2_kept': 3, 'rerun2_unsealed': 1, 'missing_runs': []})
    assert '1 re-run job was not sealed' in unsealed


def test_reruns_text_states_a_third_round():
    campaign = {'first_pass_superseded': 32, 'rerun_kept': 28, 'rerun_superseded': 4,
                'rerun2_kept': 0, 'rerun2_superseded': 4, 'rerun2_unsealed': 0,
                'rerun3_kept': 4, 'rerun3_unsealed': 0, 'missing_runs': []}
    text = E2.reruns_text(campaign)
    assert 'second round' in text and 'third round' in text
    assert '#183' in text and '#184' in text and '1,000-second' in text
    assert 'the tables read the 4 third-round jobs' in text
    # The superseded second round is never what the tables read.
    assert 'the tables read the 0 second-round jobs' not in text
    unsealed = E2.reruns_text({**campaign, 'rerun3_kept': 3, 'rerun3_unsealed': 1})
    assert '1 re-run job was not sealed' in unsealed


def test_reruns_text_states_the_canvas_editor_round():
    # #185: canvas-editor's C11 and C14 timed its empty page; its cells were measured again alone.
    campaign = {'first_pass_superseded': 32, 'rerun_kept': 28, 'rerun_superseded': 4,
                'rerun2_kept': 0, 'rerun2_superseded': 4, 'rerun2_unsealed': 0,
                'rerun3_kept': 4, 'rerun3_unsealed': 0, 'editor_rerun_kept': 24, 'editor_rerun_unsealed': 0,
                'editor_superseded': {'canvas': 24}, 'missing_runs': []}
    text = E2.reruns_text(campaign)
    assert 'third round' in text
    assert '#185' in text
    assert "canvas-editor's cells of 24 document jobs" in text
    assert 'the other editors of those jobs stay as measured' in text
    assert 'canvas-editor alone' in text
    unsealed = E2.reruns_text({**campaign, 'editor_rerun_kept': 23, 'editor_rerun_unsealed': 1})
    assert '1 re-run job was not sealed' in unsealed
    # No editor round: no sentence about it.
    assert '#185' not in E2.reruns_text({k: v for k, v in campaign.items() if not k.startswith('editor_')})


def test_reruns_text_names_each_editor_round_by_its_own_issue():
    # #190: Plate's prose-250kw round is not canvas-editor's empty-page round (#185).
    campaign = {'first_pass_superseded': 32, 'rerun_kept': 28, 'rerun_superseded': 4,
                'rerun2_kept': 0, 'rerun2_superseded': 4, 'rerun2_unsealed': 0,
                'rerun3_kept': 4, 'rerun3_unsealed': 0, 'editor_rerun_kept': 28, 'editor_rerun_unsealed': 0,
                'editor_superseded': {'canvas': 24, 'plate': 4},
                'editor_rounds': [{'issue': '185', 'editor': 'canvas', 'jobs': 24, 'workload': None},
                                  {'issue': '190', 'editor': 'plate', 'jobs': 4, 'workload': 'prose-250kw'}],
                'missing_runs': []}
    text = E2.reruns_text(campaign)
    assert "canvas-editor's cells of 24 document jobs" in text and '#185' in text
    assert "Plate.js's cells of the 4 prose-250kw document jobs" in text and '#190' in text
    plate = text[text.index("Plate.js's cells"):]
    assert 'empty page' not in plate
    assert '300' in plate and '600' in plate


def test_reruns_text_states_the_late_round():
    # #192: the C10 complex-document jobs were measured again for every editor.
    campaign = {'first_pass_superseded': 32, 'rerun_kept': 32, 'late_superseded': 4, 'late_rerun_kept': 4,
                'late_rerun_unsealed': 0, 'missing_runs': []}
    text = E2.reruns_text(campaign)
    assert '#192' in text
    assert '4 C10 jobs on the complex document' in text
    assert 'every editor' in text
    unsealed = E2.reruns_text({**campaign, 'late_rerun_kept': 3, 'late_rerun_unsealed': 1})
    assert '1 re-run job was not sealed' in unsealed
    assert '#192' not in E2.reruns_text({k: v for k, v in campaign.items() if not k.startswith('late_')})


def test_reruns_text_states_docens_clock_round():
    campaign = {'first_pass_superseded': 32, 'rerun_kept': 32, 'editor_rerun_kept': 20, 'editor_rerun_unsealed': 0,
                'editor_superseded': {'docen': 20},
                'editor_rounds': [{'issue': '193', 'editor': 'docen', 'jobs': 20, 'workload': None,
                                   'workloads': ['prose-500w', 'prose-5kw', 'prose-50kw', 'prose-250kw',
                                                 'complex-corpus']}],
                'missing_runs': []}
    text = E2.reruns_text(campaign)
    assert '#193' in text and 'two different clocks' in text
    assert "Docen's cells of the 20 document jobs below the 500k rung" in text


def test_reruns_text_states_the_memory_round_for_each_editor():
    campaign = {'first_pass_superseded': 32, 'rerun_kept': 32, 'editor_rerun_kept': 8, 'editor_rerun_unsealed': 0,
                'editor_superseded': {'docen': 4, 'canvas': 4},
                'editor_rounds': [{'issue': '194', 'editor': 'docen', 'jobs': 4, 'workload': 'prose-250kw'},
                                  {'issue': '194', 'editor': 'canvas', 'jobs': 4, 'workload': 'prose-250kw'}],
                'missing_runs': []}
    text = E2.reruns_text(campaign)
    # The same runs measured both editors: one sentence, never "measured Docen alone" (review of the 14 Nov rounds).
    assert "Docen's and canvas-editor's cells of the 4 prose-250kw memory jobs (C17 and C19)" in text
    assert text.count('(issue #194)') == 1


def test_reruns_text_tells_the_500k_part_of_a_round_apart():
    campaign = {'first_pass_superseded': 32, 'rerun_kept': 32, 'editor_rerun_kept': 24, 'editor_rerun_unsealed': 0,
                'editor_superseded': {'docen': 24},
                'editor_rounds': [{'issue': '193', 'editor': 'docen', 'jobs': 20, 'workload': None,
                                   'workloads': ['prose-500w'], 'extension': False},
                                  {'issue': '193', 'editor': 'docen', 'jobs': 4, 'workload': 'prose-500kw',
                                   'extension': True}],
                'missing_runs': []}
    text = E2.reruns_text(campaign)
    assert "Docen's cells of the 20 document jobs below the 500k rung" in text
    assert "Docen's cells of the 4 prose-500kw document jobs of the 500k rung" in text



def test_reruns_text_survives_an_issue_it_has_no_wording_for():
    campaign = {'first_pass_superseded': 32, 'rerun_kept': 32, 'editor_rerun_kept': 2, 'editor_rerun_unsealed': 0,
                'editor_superseded': {'plate': 2},
                'editor_rounds': [{'issue': '999', 'editor': 'plate', 'jobs': 2, 'workload': None}],
                'missing_runs': []}
    text = E2.reruns_text(campaign)
    assert '(issue #999)' in text and "Plate.js's cells of 2 jobs" in text


def test_reruns_text_states_the_wordcraft_rounds_lane_by_lane():
    # #196-#198: one issue may re-measure an editor in several lanes; each lane names its own criteria.
    rounds = [{'issue': '196', 'editor': 'wordcraft', 'jobs': 20, 'lane': 'benchmark_warm_cold', 'workload': None},
              {'issue': '196', 'editor': 'wordcraft', 'jobs': 20, 'lane': 'benchmark_document', 'workload': None,
               'workloads': ['prose-500w']},
              {'issue': '196', 'editor': 'wordcraft', 'jobs': 4, 'lane': 'benchmark_document',
               'workload': 'prose-500kw', 'extension': True},
              {'issue': '197', 'editor': 'wordcraft', 'jobs': 20, 'lane': 'benchmark_input', 'workload': None},
              {'issue': '198', 'editor': 'wordcraft', 'jobs': 20, 'lane': 'adversarial_c10_scroll', 'workload': None}]
    campaign = {'first_pass_superseded': 32, 'rerun_kept': 32, 'editor_rerun_kept': 84, 'editor_rerun_unsealed': 0,
                'editor_superseded': {'wordcraft': 84}, 'editor_rounds': rounds, 'missing_runs': []}
    text = E2.reruns_text(campaign)
    assert "WordCraft's cells of the 20 warm and cold load jobs (C03, with C05 and C06" in text
    assert "WordCraft's cells of the 20 document jobs below the 500k rung (C11" in text
    assert "WordCraft's cells of the 4 prose-500kw document jobs of the 500k rung (C11" in text
    assert "WordCraft's cells of the 20 input jobs (C08 and C09" in text
    assert "WordCraft's cells of the 20 C10 scroll jobs" in text
    assert text.count('(issue #196)') == 3 and '(issue #197)' in text and '(issue #198)' in text


def test_reruns_text_names_the_jobs_stopped_when_their_work_moved():
    base = {'first_pass_superseded': 32, 'rerun_kept': 32}
    assert 'stopped' not in E2.reruns_text(base)
    text = E2.reruns_text({**base, 'editor_rerun_stopped': 2})
    assert ('2 editor-round jobs were stopped part-way when their work moved to another Space; each was '
            'measured whole there, and the tables never read the stopped parts.') in text
    one = E2.reruns_text({**base, 'editor_rerun_stopped': 1})
    assert '1 editor-round job was stopped part-way' in one


def test_reruns_text_names_one_round_that_measured_two_editors_once():
    """#194's runs measured Docen and canvas-editor together; neither was measured "alone"."""
    rounds = [{'issue': '194', 'editor': 'docen', 'jobs': 4, 'lane': 'benchmark_memory', 'workload': 'prose-250kw',
               'extension': False},
              {'issue': '194', 'editor': 'canvas', 'jobs': 4, 'lane': 'benchmark_memory', 'workload': 'prose-250kw',
               'extension': False}]
    text = E2.reruns_text({'first_pass_superseded': 32, 'rerun_kept': 32, 'editor_rounds': rounds})
    assert text.count('(issue #194)') == 1
    assert "Then Docen's and canvas-editor's cells of the 4 prose-250kw memory jobs" in text
    assert 'Those runs measured Docen and canvas-editor alone' in text
    assert 'the tables read them for Docen and canvas-editor' in text
    assert 'measured Docen alone' not in text


def test_reruns_text_places_the_late_round_without_calling_it_last():
    text = E2.reruns_text({'first_pass_superseded': 32, 'rerun_kept': 32, 'late_superseded': 4,
                           'late_rerun_kept': 4})
    assert 'Last,' not in text
    assert 'In a late round, the 4 C10 jobs on the complex document were measured again for every editor' in text


def test_reruns_text_states_the_frame_cap_rounds():
    """#202: the recorder's 1,200-frame cap froze the frame cursors; Docen's 500k jobs and
    canvas-editor's 250k input jobs were measured again."""
    rounds = [{'issue': '202', 'editor': 'canvas', 'jobs': 4, 'lane': 'benchmark_input', 'workload': 'prose-250kw',
               'extension': False},
              {'issue': '202', 'editor': 'docen', 'jobs': 8, 'lane': 'benchmark_document', 'workload': None,
               'extension': True}]
    text = E2.reruns_text({'first_pass_superseded': 32, 'rerun_kept': 32, 'editor_rounds': rounds})
    assert ("Then canvas-editor's cells of the 4 prose-250kw input jobs (C08 and C09, with C04 and C07 of the "
            "same jobs) were measured again after the screencast recorder was found to stop seeing new frames "
            "once it held 1,200") in text
    assert "Then Docen's cells of the 8 jobs of the 500k rung (C11 and C14, with C12 and C15 of the same jobs)" in text
    assert text.count('(issue #202)') == 2


def test_reruns_text_keeps_two_rounds_of_one_issue_apart_by_their_manifest_key():
    """WordCraft's 500k rung has two rounds under #196: its document jobs (the C11 fix) and its C14 jobs,
    measured again only so that one harness measures all of WordCraft's 500k cells. Same issue, lane,
    workload and job count: each keeps its own sentence, and neither says the other's reason."""
    common = {'issue': '196', 'editor': 'wordcraft', 'jobs': 4, 'lane': 'benchmark_document',
              'workload': 'prose-500kw', 'extension': True}
    rounds = [{**common, 'key': '196-extension'}, {**common, 'key': '196-c14'}]
    text = E2.reruns_text({'first_pass_superseded': 32, 'rerun_kept': 32, 'editor_rounds': rounds})
    assert text.count('(issue #196)') == 2
    assert 'WordCraft and WordCraft' not in text
    assert "Then WordCraft's cells of the 4 prose-500kw document jobs of the 500k rung (C11" in text
    assert ("Then WordCraft's cells of the 4 prose-500kw C14 jobs of the 500k rung were measured again so that "
            "one harness measures all of WordCraft's 500k cells; the #196 fix does not change C14") in text


def test_reruns_text_still_joins_one_round_of_two_editors_when_keys_differ():
    """#194's keys are "194" and "194-canvas": one reason, so one sentence."""
    rounds = [{'issue': '194', 'key': '194', 'editor': 'docen', 'jobs': 4, 'lane': 'benchmark_memory',
               'workload': 'prose-250kw', 'extension': False},
              {'issue': '194', 'key': '194-canvas', 'editor': 'canvas', 'jobs': 4, 'lane': 'benchmark_memory',
               'workload': 'prose-250kw', 'extension': False}]
    text = E2.reruns_text({'first_pass_superseded': 32, 'rerun_kept': 32, 'editor_rounds': rounds})
    assert text.count('(issue #194)') == 1
    assert "Then Docen's and canvas-editor's cells" in text
