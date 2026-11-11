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


def _write_trial(root: Path, rep: int, editor: str, criterion: str, **kwargs) -> None:
    cell = root / "cells" / f"{rep:04d}-{editor}" / "attempts"
    cell.mkdir(parents=True, exist_ok=True)
    path = cell / f"{criterion.lower()}.json"
    path.write_text(json.dumps(_trial(editor, criterion, **kwargs)), encoding="utf-8")


def _summary(root: Path, *, run_id: str, seed: int, editors: list[str], reps: int = 30) -> dict:
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

    def test_nine_kept_samples_not_enough(self):
        primary, _ = self._pair(
            {"run_id": "a", "seed": 1, "editors": ["plate"]},
            {"run_id": "b", "seed": 2, "editors": ["plate"]},
            lambda root: [_write_trial(root, i, "plate", "C07", outcome="measured", samples=[20.0]) for i in range(9)],
        )
        facts = E2.facts_from_runs(primary, self.base / "repro")
        table = facts["perf.e2.table.C07"]
        self.assertIn("not enough samples", table)
        self.assertIn("n = 9 of 30", table)

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
                       order=[[i, e] for i in range(40) for e in ['plate', 'docen']])
        (root / 'summary.json').write_text(json.dumps(summary))
        for i in range(10):
            _write_trial(root, i, 'plate', 'C07', outcome='measured', samples=[100], diagnostic={'frame_interval_ms':16.7})
    return roots

def change_summary(root, **kw):
    p = root / 'summary.json'
    p.write_text(json.dumps({**json.loads(p.read_text()), **kw}))

def fill(root, samples, frame=16.7, n=10):
    for p in (root / 'cells').rglob('*.json'):
        p.unlink()
    for i in range(n):
        _write_trial(root, i, 'plate', 'C07', outcome='measured', samples=samples,
                     diagnostic={} if frame is None else {'frame_interval_ms': frame})

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
        _write_trial(root, -1, 'plate', 'C07', outcome='not_run', diagnostic={'frame_interval_ms': 1})
    assert '< 1 frame (16.7 ms)' in table(runs)

def test_finding_04_rejected_and_sample_refused(runs):
    for root in runs:
        source = root / 'cells/0009-plate'
        dest = root / 'rejected-evidence/0009-plate/cell'
        dest.parent.mkdir(parents=True)
        source.rename(dest)
        (root / 'samples').mkdir()
        (root / 'samples/0009-plate.json').write_text(json.dumps(dict(editor_id='plate', repetition=9, outcome='failed', failure_reason='cpu_throttled', refusal_code='cpu_throttled')))
    assert 'n = 9 of 40' in table(runs)
    assert 'cpu_throttled' in table(runs)
    # A refusal must also veto an otherwise measured file still under cells.
    for root in runs:
        _write_trial(root, 9, 'plate', 'C07', outcome='measured', samples=[100])
    assert 'n = 9 of 40' in table(runs)

def test_finding_05_launch_not_click_count(runs):
    for root in runs:
        fill(root, [20, 21, 22], n=4)
    assert 'n = 4 of 40' in table(runs)
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
    assert '37.50%' in note and '20 of 80' in note
    assert 'Darwin' in note and 'NVIDIA' in note
    assert '8-CPU' not in note and 'software rasterization' not in note

def test_finding_07_unpublishable_run(runs):
    change_summary(runs[1], publishable=False, publication_block_reason='cpu_accounting_unavailable')
    assert 'cpu_accounting_unavailable' in table(runs)
    assert '100.0 ms' not in table(runs)

@pytest.mark.parametrize('field', ['tree', 'playwright_version', 'vendor', 'browser_version', 'host_class'])
def test_finding_08_real_version_locations(runs, field):
    if field == 'tree':
        for p in (runs[1] / 'cells').rglob('*.json'):
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
    fill(runs[1], [100], n=9)
    assert 'n = 9 of 40' in table(runs)
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
    (root / 'cells/extra.json').write_text('bad json')
    (root / 'cells/list.json').write_text('[]')
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
    directory = root / 'cells' / f'{rep:04d}-plate'
    samples = root / 'samples'
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
    assert 'n = 0 of 40' in facts['perf.e2.table.C04']
    assert 'search_timeout: 10' in facts['perf.e2.table.C04']


@pytest.mark.parametrize('reason', ['cpu_throttled', 'cpu_accounting_unavailable', 'host_build: dev_server'])
def test_launch_wide_refusal_still_vetoes_measured_trials(runs, reason):
    for root in runs:
        sample_row(root, 9, reason, reason.split(':')[0])
    assert 'n = 9 of 40' in table(runs)


def test_quarantined_launch_vetoes_leftover_cells(runs):
    for root in runs:
        (root / 'rejected-evidence/0009-plate/cell').mkdir(parents=True)
    assert 'n = 9 of 40' in table(runs)


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
        fill(runs[0], [100], n=9)
    change_summary(runs[1], publishable=False, publication_block_reason='repos_modified')
    text = E2.e2_cells.publish_dual_runs(*runs, 'plate', 'C07')
    assert 'second run unpublishable: repos_modified' in text
    assert '100.0 ms' not in text
    if short_primary:
        assert 'n = 9 of 40' in text


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
    assert '% sub-frame' not in table(runs)
    assert 'malformed_samples: 5' in table(runs)


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
    assert 'unpublishable' not in table(runs)
    assert '100.0 ms' in table(runs)
    assert E2.facts_from_runs(*runs)['perf.e2.plate.C07.reproduced'] is True


def test_quarantine_refusals_are_scoped_to_editor(runs):
    (runs[0] / 'rejected-evidence/0009-docen/cell').mkdir(parents=True)
    cell = E2.e2_cells.build_run_cell(runs[0], 'plate', 'C07')
    assert cell['stats']['n'] == 10
    assert cell['refusals'] == {}
