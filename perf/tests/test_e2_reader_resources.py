"""Report E2's resources section (#155.4): the B8 lane was measured and never published."""
from __future__ import annotations

import json
from pathlib import Path

from perf.analysis import e2_resources as res

TREE = 'a' * 64


def _job(root: Path, name: str, *, editor='plate', workload='prose-250kw', seed=1, launches=30, records=None,
         summary=None, tree=TREE, first=0):
    job = root / 'benchmark_resources' / name
    (job / 'cells').mkdir(parents=True)
    base = {
        'runner': 'benchmark_resources', 'run_id': name, 'seed': seed, 'publishable': False,
        'publication_block_reason': 'summary is not a trial; trials carry publishability',
        'execution_profile': 'dedicated_publish', 'host_class': 'shared_guarded',
        'order': [[first + i, editor] for i in range(launches)],
        'hosts': {editor: {'host_build': 'production', 'publishable': True, 'tree_sha256': tree}},
    }
    (job / 'summary.json').write_text(json.dumps({**base, **(summary or {})}))
    for index in range(launches):
        record = (records[index] if records else _record(editor, workload))
        if record is None:
            continue
        cell = job / 'cells' / f'{first + index:04d}-{editor}'
        cell.mkdir()
        (cell / 'resource.json').write_text(json.dumps(record))
    return job


def _record(editor='plate', workload='prose-250kw', *, load=1000, open_settle=200, edit=300, quiet=50, ram=2 ** 30, **over):
    return {
        'record_kind': 'browser_resources', 'editor_id': editor, 'workload_id': workload, 'outcome': 'measured',
        'refusal_code': None, 'execution_profile': 'dedicated_publish', 'host_class': 'shared_guarded',
        'load_cpu_ms': load, 'open_settle_cpu_ms': open_settle, 'edit_cpu_ms': edit, 'quiescence_cpu_ms': quiet,
        'peak_ram_bytes': ram, 'peak_js_heap_used_bytes': 50 * 2 ** 20, 'load_network_encoded_bytes': 3 * 2 ** 20,
        'edit_oracle': {'mode': 'caret_block_text', 'status': 'verified'}, 'edit_cpu_publication': 'published',
        'settle': {'after_load': 'reached', 'after_edit': 'reached'}, **over,
    }


def _two_seeds(tmp_path, **second):
    _job(tmp_path, 'j1', seed=1)
    _job(tmp_path, 'j2', seed=2, **second)
    return res.read_cell([tmp_path], 'plate', 'prose-250kw')


def test_two_seeds_that_agree_publish_each_measure(tmp_path):
    cell = _two_seeds(tmp_path)
    assert cell['published'] is True and cell['reason'] is None
    assert cell['seeds'] == [1, 2]
    assert cell['kept'] == [30, 30] and cell['scheduled'] == [30, 30]
    open_cpu = cell['measures']['open_cpu_ms']
    # opening is the load phase plus the work after the ready signal
    assert open_cpu == {'medians': [1200, 1200], 'reproduced': True, 'unit': 'ms'}
    assert cell['measures']['peak_ram_bytes']['medians'] == [2 ** 30, 2 ** 30]


def test_pooled_spaces_are_grouped_by_seed_not_by_root(tmp_path):
    # Interleaved blocks: one seed's launches can sit on several Spaces.
    _job(tmp_path / 'space-a', 'j1', seed=1, launches=15)
    _job(tmp_path / 'space-b', 'j2', seed=1, launches=15, first=15)
    _job(tmp_path / 'space-c', 'j3', seed=2, launches=30)
    cell = res.read_cell([tmp_path / 'space-a', tmp_path / 'space-b', tmp_path / 'space-c'], 'plate', 'prose-250kw')
    assert cell['published'] is True
    assert cell['kept'] == [30, 30]


def test_one_seed_is_not_a_publication(tmp_path):
    _job(tmp_path, 'j1', seed=1)
    cell = res.read_cell([tmp_path], 'plate', 'prose-250kw')
    assert cell['published'] is False and cell['reason'] == 'two seeds required'
    assert cell['measures'] == {}


def test_fewer_than_ten_kept_launches_do_not_publish_and_store_no_median(tmp_path):
    refused = _record(outcome='refused', refusal_code='editor_crashed', editor_error='renderer crashed during edit')
    cell = _two_seeds(tmp_path, records=[_record()] * 9 + [refused] * 21)
    assert cell['published'] is False
    assert cell['reason'] == 'second seed: 9 of 30 launches kept (editor_crashed 21)'
    assert cell['measures'] == {}
    assert cell['editor_errors'] == {'renderer crashed during edit': 21}


def test_a_measure_that_disagrees_is_not_reproduced_and_keeps_no_figure(tmp_path):
    cell = _two_seeds(tmp_path, records=[_record(edit=900)] * 30)
    assert cell['published'] is True
    assert cell['measures']['edit_cpu_ms'] == {'medians': None, 'reproduced': False, 'unit': 'ms'}
    assert cell['measures']['open_cpu_ms']['reproduced'] is True


def test_a_shakedown_or_blocked_run_never_publishes(tmp_path):
    cell = _two_seeds(tmp_path, summary={'shakedown': True, 'publication_block_reason':
                                         'shakedown: few repetitions to find bugs; never a publication run'})
    assert cell['published'] is False and cell['reason'].startswith('second seed: run blocked (shakedown')
    assert cell['measures'] == {}


def test_unverified_edits_and_withheld_edit_cpu_are_not_kept(tmp_path):
    bad = _record(edit_oracle={'mode': 'caret_block_text', 'status': 'edit_unverified'}, edit_cpu_publication='withheld')
    cell = _two_seeds(tmp_path, records=[bad] * 30)
    assert cell['published'] is False
    assert 'edit_unverified 30' in cell['reason']


def test_different_built_editors_are_never_compared(tmp_path):
    cell = _two_seeds(tmp_path, tree='b' * 64)
    assert cell['published'] is False and cell['reason'] == 'the two seeds measured different editor builds'


def test_an_editor_that_never_idled_is_counted(tmp_path):
    capped = _record(settle={'after_load': 'capped', 'after_edit': 'capped'})
    cell = _two_seeds(tmp_path, records=[capped] * 30)
    assert cell['published'] is True
    assert cell['never_idle'] == [0, 30]


def test_table_names_refusals_and_never_prints_a_blocked_median(tmp_path):
    _job(tmp_path, 'j1', seed=1)
    _job(tmp_path, 'j2', seed=2)
    crash = _record('canvas', outcome='refused', refusal_code='editor_crashed', editor_error='renderer crashed during edit',
                    load=77777)
    _job(tmp_path, 'j3', editor='canvas', seed=1, records=[crash] * 30)
    _job(tmp_path, 'j4', editor='canvas', seed=2, records=[crash] * 30)
    facts = {}
    text = res.resources_tables(facts, [tmp_path], ['plate', 'canvas'], {'plate': 'Plate', 'canvas': 'canvas-editor'})
    assert '### 250,000 words' in text
    assert '| Plate | 1.20 s / 1.20 s | 300 ms / 300 ms | 50 ms / 50 ms | 1024.0 MiB / 1024.0 MiB |' in text
    assert 'canvas-editor: first seed: 0 of 30 launches kept (editor_crashed 30); renderer crashed during edit' in text
    assert '77777' not in json.dumps(facts) and '77.78 s' not in text
    assert facts['perf.e2.plate.B8.prose-250kw.open_cpu_ms.reproduced'] is True
    assert facts['perf.e2.canvas.B8.prose-250kw.published'] is False


def test_report_e2_has_a_resources_section_fed_by_the_facts(tmp_path):
    from build import perf_e2_tables as report

    template = (Path(__file__).resolve().parents[2] / 'templates' / 'reports'
                / 'Report E2 - Speed in the Browser (2026).md').read_text(encoding='utf-8')
    assert '### B8 — resources while opening and editing' in template
    assert '{{perf.e2.table.B8}}' in template and '{{perf.e2.criterion.B8}}' in template
    unset = report.unset_facts()
    assert unset['perf.e2.table.B8'] == 'not yet measured'
    assert 'verified' in unset['perf.e2.criterion.B8']
    _job(tmp_path, 'j1', seed=1)
    _job(tmp_path, 'j2', seed=2)
    facts = report.resource_facts([tmp_path], ['plate'])
    assert '| %s | 1.20 s / 1.20 s |' % report.DISPLAY['plate'] in facts['perf.e2.table.B8']
    assert facts['perf.e2.plate.B8.prose-250kw.edit_cpu_ms.reproduced'] is True
