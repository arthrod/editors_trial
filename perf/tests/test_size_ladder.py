"""#141 ladder and #128 workload cells; F1 includes a real-data integration probe."""
import json
from pathlib import Path

import pytest

from perf.container.policy import publication_jobs
from perf.runner import benchmark_document as document, benchmark_input as inputs
from perf.runner import adversarial_c10_scroll as scroll
from perf.fixtures.profiles import size_ladder
from perf.fixtures.docx_workload import workload_docx
from perf.analysis.e2_cells import build_run_cell
from build.perf_e2_tables import _criterion_table

LADDER = ('prose-500w', 'prose-5kw', 'prose-50kw', 'prose-250kw', 'complex-corpus')


def test_publication_ladder_jobs():
    jobs = publication_jobs(['plate'], 1, 2, 'shared_guarded')
    for lane in ('benchmark_warm_cold', 'benchmark_document', 'benchmark_input',
                 'adversarial_c10_scroll', 'benchmark_memory', 'benchmark_resources'):
        lane_jobs = [args for name, args in jobs if name == lane]
        for workload in LADDER:
            matches = [args for args in lane_jobs if '--workload' in args and args[args.index('--workload') + 1] == workload]
            assert len(matches) == 2, (lane, workload, matches)
        if lane == 'benchmark_document':
            assert sum(args[args.index('--criteria') + 1:] == ['C14'] for args in lane_jobs) == 2
            assert all('--criteria' in args for args in lane_jobs)
    assert len([1 for name, _ in jobs if name == 'benchmark_typing']) == 4


def test_workload_cli_and_fixture(monkeypatch, capsys, fs):
    for module in (document, inputs, scroll):
        monkeypatch.setattr('sys.argv', ['runner', '--help'])
        with pytest.raises(SystemExit) as exit_info:
            module._main()
        assert exit_info.value.code == 0
        assert '--workload' in capsys.readouterr().out
    workload = 'prose-500w'
    row = next(row for row in size_ladder() if row['workload_id'] == workload)
    expected = workload_docx(workload)['docx']
    assert document.build_fixture(row)['bytes'] == expected
    assert inputs._fixture('plate', workload)[0].read_bytes() == expected
    assert scroll.scroll_fixture(workload)['docx'] == expected


def test_c14_uses_whole_ladder():
    assert document.C14_RUNGS == LADDER
    assert set(document.C14_RUNG_LABEL) == set(LADDER)


def test_workloads_have_separate_cells_and_table_groups(fs):
    # A cell stores figures only when it publishes: two seeds, ten kept launches each (#154.1).
    roots = [Path('/primary'), Path('/repro')]
    for seed, root in enumerate(roots, 1):
        root.mkdir()
        (root / 'summary.json').write_text(json.dumps(
            {'order': [[i, 'plate'] for i in range(10)], 'publishable': True, 'seed': seed}))
        for workload, value in zip(LADDER[:2], (20, 40)):
            for launch in range(10):
                path = root / f'cells/{launch:04d}-plate/attempts' / (workload + '.json')
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(dict(editor_id='plate', criterion_id='C11', workload_id=workload,
                    outcome='measured', publishable=True, refusal_code=None, samples_ms=[value],
                    sub_frame_samples=[False], diagnostic={'frame_interval_ms': 16.7},
                    host_provenance={'host_build': 'production', 'publishable': True, 'tree_sha256': 'tree-a'})))
    facts = {}
    table = _criterion_table(facts, roots, 'C11', ['plate'])
    assert all(workload in table for workload in LADDER[:2])
    cells = [v for k, v in facts.items() if k.endswith('.primary')]
    assert len(cells) == 2
    assert [c['kept_ms'] for c in cells] == [[20.0] * 10, [40.0] * 10]
    assert {c['workload_id'] for c in cells} == set(LADDER[:2])


def test_f1_real_smoke_launch_accounting():
    root = Path('/Users/arthrod/temp/T/e2-logs/integration-2/step2b/smoke-verified/benchmark_document/benchmark_document')
    if not root.is_dir():
        pytest.skip('real smoke evidence not installed (integration test)')
    cell = build_run_cell(root, 'plate', 'C11', scheduled=1)
    print(f"F1 C11 failed={cell['failed_launches']} kept={len(cell['kept_ms'])} refusals={cell['refusals']}")
    # The smoke run started with a dirty repos/ checkout: a blocked run is
    # named and nothing of it is aggregated (reader review, MAJOR A).
    assert cell['blocked'] is True and cell['block_reason'] == 'repos_dirty_at_start'
    assert cell['kept_ms'] == [] and cell['stats'] is None


def test_f1_diagnostics_cannot_drop_measured_launch(fs):
    root = Path('/run')
    path = root / 'cells/0000-plate/attempts/c11.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(dict(editor_id='plate', criterion_id='C11', outcome='measured',
        publishable=True, refusal_code=None, samples_ms=[20], sub_frame_samples=[False],
        diagnostic={'frame_interval_ms': 16.7},
        host_provenance={'host_build': 'production', 'publishable': True, 'tree_sha256': 'tree-a'})))
    samples = root / 'samples'
    samples.mkdir()
    for name in ('0000-plate', 'doc-C11-x', 'probe-x', 'input-x', 'c10-0000-plate', 'saturation-0-plate'):
        (samples / (name + '.json')).write_text(json.dumps(dict(editor_id='plate',
            outcome='ok', refusal_code='cpu_accounting_unavailable')))
    (samples / 'nested').mkdir()
    (samples / 'nested/0001-plate.json').write_text(json.dumps(dict(editor_id='plate',
        outcome='failed', accounting_scope='diagnostic', refusal_code='crash')))
    cell = build_run_cell(root, 'plate', 'C11', scheduled=1)
    assert (cell['failed_launches'], cell['kept_ms']) == (0, [20])


def test_memory_accepts_publication_editor_selection():
    from perf.runner import benchmark_memory as memory
    parser = memory._build_parser()
    assert '--editors' in parser.format_help()
    args = parser.parse_args(['--editors', 'plate', 'folio', '--workload', 'prose-500w'])
    assert args.editor == ['plate', 'folio']
    assert args.workload == 'prose-500w'


def test_other_workload_refusal_does_not_veto_cell(fs):
    root = Path('/run')
    attempts = root / 'cells/0000-plate/attempts'
    attempts.mkdir(parents=True)
    for workload, code in [('prose-500w', None), ('prose-5kw', 'host_build')]:
        (attempts / (workload + '.json')).write_text(json.dumps(dict(editor_id='plate',
            criterion_id='C11', environment={'workload_id': workload},
            outcome='measured' if code is None else 'not_run', publishable=code is None,
            refusal_code=code, samples_ms=[20], sub_frame_samples=[False],
            diagnostic={'frame_interval_ms': 16.7},
            host_provenance={'host_build': 'production', 'publishable': True, 'tree_sha256': 'tree-a'})))
    cell = build_run_cell(root, 'plate', 'C11', workload_id='prose-500w')
    assert cell['kept_ms'] == [20]
    assert cell['refusals'] == {}
