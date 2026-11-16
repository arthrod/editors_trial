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


def _blocks(root, seed, *, editor='plate', workload='prose-250kw', records=None, summary=None, tree=TREE):
    """The decided resources schedule: 2 blocks of 5."""
    seq = None if records is None else list(records[:10])
    for index, first in ((1, 0), (2, 5)):
        extra = dict(summary or {})
        extra['block'] = {'index': index, 'of': 2, 'repetitions': 5}
        _job(
            root, '%s-s%d-b%d' % (editor, seed, index), editor=editor, workload=workload, seed=seed,
            launches=5, records=None if seq is None else seq[first:first + 5], summary=extra, tree=tree, first=first,
        )


def _two_seeds(tmp_path, **second):
    second.pop('launches', None)
    records = second.pop('records', None)
    summary = second.pop('summary', None)
    tree = second.pop('tree', TREE)
    _blocks(tmp_path, 1)
    _blocks(tmp_path, 2, records=records, summary=summary, tree=tree, **second)
    return res.read_cell([tmp_path], 'plate', 'prose-250kw')


def test_two_seeds_that_agree_publish_each_measure(tmp_path):
    cell = _two_seeds(tmp_path)
    assert cell['published'] is True and cell['reason'] is None
    assert cell['seeds'] == [1, 2]
    assert cell['kept'] == [10, 10] and cell['scheduled'] == [10, 10]
    open_cpu = cell['measures']['open_cpu_ms']
    # opening is the load phase plus the work after the ready signal
    assert (open_cpu['medians'], open_cpu['reproduced'], open_cpu['unit']) == ([1200, 1200], True, 'ms')
    assert cell['measures']['peak_ram_bytes']['medians'] == [2 ** 30, 2 ** 30]


def test_pooled_spaces_are_grouped_by_seed_not_by_root(tmp_path):
    # Interleaved blocks: one seed's launches can sit on several Spaces.
    block = {'of': 2, 'repetitions': 5}
    _job(tmp_path / 'space-a', 'j1', seed=1, launches=5, summary={'block': {**block, 'index': 1}})
    _job(tmp_path / 'space-b', 'j2', seed=1, launches=5, first=5, summary={'block': {**block, 'index': 2}})
    _job(tmp_path / 'space-c', 'j3', seed=2, launches=5, summary={'block': {**block, 'index': 1}})
    _job(tmp_path / 'space-c', 'j4', seed=2, launches=5, first=5, summary={'block': {**block, 'index': 2}})
    cell = res.read_cell([tmp_path / 'space-a', tmp_path / 'space-b', tmp_path / 'space-c'], 'plate', 'prose-250kw')
    assert cell['published'] is True
    assert cell['kept'] == [10, 10]


def test_one_seed_is_not_a_publication(tmp_path):
    _job(tmp_path, 'j1', seed=1)
    cell = res.read_cell([tmp_path], 'plate', 'prose-250kw')
    assert cell['published'] is False and cell['reason'] == 'two seeds required'
    assert cell['measures'] == {}


def test_fewer_than_the_minimum_kept_launches_do_not_publish_and_store_no_median(tmp_path):
    refused = _record(outcome='refused', refusal_code='editor_crashed', editor_error='renderer crashed during edit')
    cell = _two_seeds(tmp_path, launches=10, records=[_record()] * 4 + [refused] * 6)
    assert cell['published'] is False
    assert cell['reason'] == 'second seed: 4 of 10 launches kept (editor_crashed 6)'
    assert cell['measures'] == {}
    assert cell['editor_errors'] == {'renderer crashed during edit': 6}


def test_five_kept_of_ten_publishes(tmp_path):
    refused = _record(outcome='refused', refusal_code='editor_crashed')
    cell = _two_seeds(tmp_path, launches=10, records=[_record()] * 5 + [refused] * 5)
    assert cell['published'] is True, cell['reason']


def test_a_measure_that_disagrees_is_not_reproduced_and_keeps_no_figure(tmp_path):
    cell = _two_seeds(tmp_path, records=[_record(edit=900)] * 30)
    assert cell['published'] is True
    edit = cell['measures']['edit_cpu_ms']
    assert edit['medians'] is None and edit['reproduced'] is False and edit['unit'] == 'ms'
    assert edit['seed_medians'] == [300, 900]  # #226: said, not published
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
    assert 'edit_unverified 10' in cell['reason']


def test_different_built_editors_are_never_compared(tmp_path):
    cell = _two_seeds(tmp_path, tree='b' * 64)
    assert cell['published'] is False and cell['reason'] == 'the two seeds measured different editor builds'


def test_an_editor_that_never_idled_is_counted(tmp_path):
    capped = _record(settle={'after_load': 'capped', 'after_edit': 'capped'})
    cell = _two_seeds(tmp_path, records=[capped] * 30)
    assert cell['published'] is True
    assert cell['never_idle'] == [0, 10]


def test_table_names_refusals_and_never_prints_a_blocked_median(tmp_path):
    _blocks(tmp_path, 1)
    _blocks(tmp_path, 2)
    crash = _record('canvas', outcome='refused', refusal_code='editor_crashed', editor_error='renderer crashed during edit',
                    load=77777)
    _blocks(tmp_path, 1, editor='canvas', records=[crash] * 10)
    _blocks(tmp_path, 2, editor='canvas', records=[crash] * 10)
    facts = {}
    text = res.resources_tables(facts, [tmp_path], ['plate', 'canvas'], {'plate': 'Plate', 'canvas': 'canvas-editor'})
    assert '### 250,000 words' in text
    assert '| Plate | 1.20 s / 1.20 s | 300 ms / 300 ms | window not recorded | 1024.0 MiB / 1024.0 MiB |' in text
    assert 'canvas-editor: first seed: 0 of 10 launches kept (editor_crashed 10); renderer crashed during edit' in text
    assert '77777' not in json.dumps(facts) and '77.78 s' not in text
    assert facts['perf.e2.plate.B8.prose-250kw.open_cpu_ms.reproduced'] is True
    assert facts['perf.e2.canvas.B8.prose-250kw.published'] is False


def test_blockless_ten_is_the_wrong_resources_schedule(tmp_path):
    _job(tmp_path, 'j1', seed=1, launches=10)
    _job(tmp_path, 'j2', seed=2, launches=10)
    cell = res.read_cell([tmp_path], 'plate', 'prose-250kw')
    assert cell['published'] is False
    assert cell['reason'] is not None
    assert 'wrong schedule' in cell['reason']
    assert 'n = 10 of 10' in cell['reason']
    assert 'this campaign schedules 10 per seed' in cell['reason']
    assert cell['measures'] == {}


def test_two_blocks_of_five_publish_the_resources_cell(tmp_path):
    block = {'of': 2, 'repetitions': 5}
    for seed in (1, 2):
        _job(tmp_path, 's%d-b1' % seed, seed=seed, launches=5, first=0,
             summary={'block': {**block, 'index': 1}})
        _job(tmp_path, 's%d-b2' % seed, seed=seed, launches=5, first=5,
             summary={'block': {**block, 'index': 2}})
    cell = res.read_cell([tmp_path], 'plate', 'prose-250kw')
    assert cell['published'] is True, cell['reason']
    assert cell['kept'] == [10, 10]
    assert cell['scheduled'] == [10, 10]


def test_report_e2_has_a_resources_section_fed_by_the_facts(tmp_path):
    from build import perf_e2_tables as report

    template = (Path(__file__).resolve().parents[2] / 'templates' / 'reports'
                / 'Report E2 - Speed in the Browser (2026).md').read_text(encoding='utf-8')
    assert '### B8 — resources while opening and editing' in template
    assert '{{perf.e2.table.B8}}' in template and '{{perf.e2.criterion.B8}}' in template
    unset = report.unset_facts()
    assert unset['perf.e2.table.B8'] == 'not yet measured'
    assert 'verified' in unset['perf.e2.criterion.B8']
    _blocks(tmp_path, 1)
    _blocks(tmp_path, 2)
    facts = report.resource_facts([tmp_path], ['plate'])
    assert '| %s | 1.20 s / 1.20 s |' % report.DISPLAY['plate'] in facts['perf.e2.table.B8']
    assert facts['perf.e2.plate.B8.prose-250kw.edit_cpu_ms.reproduced'] is True


def _never_idle_cell(tmp_path):
    capped = _record(load=7000, open_settle=70000, edit=17000, quiet=72000,
                     settle={'after_load': 'capped', 'after_edit': 'capped'})
    _blocks(tmp_path, 1, records=[capped] * 10)
    _blocks(tmp_path, 2, records=[capped] * 10)


def test_a_never_idle_editor_prints_no_cpu_figure(tmp_path):
    """#211: the cap is not the editor. WordCraft printed 81 s 'to open' a 500-word document."""
    _never_idle_cell(tmp_path)
    facts = {}
    text = res.resources_tables(facts, [tmp_path], ['plate'], {'plate': 'Plate'})
    assert '| Plate | never idle | never idle | never idle | 1024.0 MiB / 1024.0 MiB | n = 10, 10 |' in text
    assert '77.00 s' not in text and '72.00 s' not in text and '17.00 s' not in text
    assert ('- Plate never went idle: it was still working when the 30-second cap ended, after opening in 10 and 10 '
            'of its kept launches and after the edit in 10 and 10. Its three CPU columns are not printed: they would '
            'time the cap, not the editor. Up to its ready signal it used 7.00 s / 7.00 s of processor time; in the '
            'capped wait that followed, 70.00 s / 70.00 s.') in text
    prefix = 'perf.e2.plate.B8.prose-250kw.'
    assert facts[prefix + 'never_idle'] is True
    assert facts[prefix + 'ready_cpu_ms.medians'] == [7000, 7000]
    assert facts[prefix + 'capped_open_settle_cpu_ms.medians'] == [70000, 70000]
    assert prefix + 'open_cpu_ms.medians' not in facts
    assert prefix + 'edit_cpu_ms.medians' not in facts
    assert prefix + 'edit_settle_cpu_ms.medians' not in facts


def test_a_cap_after_the_edit_only_hides_the_settle_column(tmp_path):
    capped = _record(settle={'after_load': 'reached', 'after_edit': 'capped'})
    _blocks(tmp_path, 1, records=[capped] * 10)
    _blocks(tmp_path, 2, records=[capped] * 10)
    text = res.resources_tables({}, [tmp_path], ['plate'], {'plate': 'Plate'})
    assert '| Plate | 1.20 s / 1.20 s | 300 ms / 300 ms | never idle | 1024.0 MiB / 1024.0 MiB |' in text
    assert 'after the edit in 10 and 10 of its kept launches' in text
    assert 'Its settling column is not printed' in text


def test_one_capped_launch_is_enough_to_hide_the_column(tmp_path):
    """codex review of #211: five idle and five capped launches printed a median that holds the cap."""
    idle = _record()
    capped = _record(load=1000, open_settle=70000, settle={'after_load': 'capped', 'after_edit': 'reached'})
    for seed in (1, 2):
        _blocks(tmp_path, seed, records=[idle] * 9 + [capped])
    facts = {}
    text = res.resources_tables(facts, [tmp_path], ['plate'], {'plate': 'Plate'})
    assert '| Plate | never idle | never idle | window not recorded | 1024.0 MiB / 1024.0 MiB |' in text
    assert 'after opening in 1 and 1 of its kept launches. Its CPU to open and CPU of the edit columns are not printed' in text
    assert 'perf.e2.plate.B8.prose-250kw.open_cpu_ms.medians' not in facts


def test_note_figures_that_disagree_between_seeds_are_not_printed(tmp_path):
    """codex review of #211: the note printed 1.00 s / 100.00 s."""
    def capped(load):
        return _record(load=load, open_settle=70000, settle={'after_load': 'capped', 'after_edit': 'capped'})
    _blocks(tmp_path, 1, records=[capped(1000)] * 10)
    _blocks(tmp_path, 2, records=[capped(100000)] * 10)
    facts = {}
    text = res.resources_tables(facts, [tmp_path], ['plate'], {'plate': 'Plate'})
    assert '100.00 s' not in text
    assert 'Up to its ready signal its processor time did not reproduce between the seeds; in the capped wait that followed it used 70.00 s / 70.00 s.' in text
    assert 'perf.e2.plate.B8.prose-250kw.ready_cpu_ms.medians' not in facts


def test_a_launch_that_does_not_record_its_settle_is_not_kept(tmp_path):
    """codex review of #211: no settle record is not evidence of an idle page."""
    record = _record()
    del record['settle']
    assert res.launch_refusal(record) == 'settle_not_recorded'
    assert res.launch_refusal(_record(settle={'after_load': 'reached'})) == 'settle_not_recorded'
    assert res.launch_refusal(_record()) is None


def test_the_memory_column_is_a_reading_not_a_peak(tmp_path):
    _blocks(tmp_path, 1)
    _blocks(tmp_path, 2)
    text = res.resources_tables({}, [tmp_path], ['plate'], {'plate': 'Plate'})
    assert '| Highest memory reading |' in text and 'Peak memory' not in text


# ---- #226: what a "not reproduced" cell hides, and what is still said of a never-idle editor ----


def test_a_cell_that_did_not_reproduce_prints_both_seed_medians_and_the_launch_range(tmp_path):
    """#226: canvas-editor's 3.4 to 5.1 GiB was hidden behind 'not reproduced'."""
    first = [_record(ram=(3400 + 100 * i) * 2 ** 20, quiet=40 + 10 * (i % 3)) for i in range(10)]
    second = [_record(ram=(4400 + 60 * i) * 2 ** 20, quiet=90 + 10 * (i % 3)) for i in range(10)]
    _blocks(tmp_path, 1, records=first)
    _blocks(tmp_path, 2, records=second)
    facts = {}
    text = res.resources_tables(facts, [tmp_path], ['plate'], {'plate': 'Plate'})
    assert ('not reproduced (first 3850.0 MiB; second 4670.0 MiB; launches 3400.0 MiB to 4940.0 MiB)') in text
    # The settling total is no longer printed (#226 follow-up); what each seed read stays in the facts.
    settle = 'perf.e2.plate.B8.prose-250kw.edit_settle_cpu_ms.'
    assert facts[settle + 'seed_medians'] == [50, 100] and facts[settle + 'launch_range'] == [40, 110]
    assert facts[settle + 'totals_agree'] is False
    prefix = 'perf.e2.plate.B8.prose-250kw.peak_ram_bytes.'
    assert facts[prefix + 'reproduced'] is False
    assert prefix + 'medians' not in facts  # no published figure
    assert facts[prefix + 'seed_medians'] == [3850.0 * 2 ** 20, 4670.0 * 2 ** 20]
    assert facts[prefix + 'launch_range'] == [3400 * 2 ** 20, 4940 * 2 ** 20]


def test_a_reproduced_cell_is_printed_as_before(tmp_path):
    cell = _two_seeds(tmp_path)
    assert cell['measures']['open_cpu_ms']['medians'] == [1200, 1200]
    assert cell['measures']['open_cpu_ms']['seed_medians'] == [1200, 1200]
    text = res.resources_tables({}, [tmp_path], ['plate'], {'plate': 'Plate'})
    assert '| Plate | 1.20 s / 1.20 s | 300 ms / 300 ms | window not recorded | 1024.0 MiB / 1024.0 MiB | n = 10, 10 |' in text


def _phases(gpu_before, gpu_after, longtasks, longtask_ms):
    def processes(gpu):
        return [{'role': 'browser', 'cpu_ms': 100}, {'role': 'gpu', 'cpu_ms': gpu}, {'role': 'renderer', 'cpu_ms': 900}]
    return {'load': {'processes': processes(gpu_before)},
            'after_load': {'processes': processes(gpu_after), 'longtask_count': longtasks, 'longtask_sum_ms': longtask_ms}}


def test_a_never_idle_note_says_where_the_cpu_went_and_how_much_memory(tmp_path):
    """#226: WordCraft's 75 s in a 30 s wait was the browser's GPU process drawing in software."""
    def capped(ram):
        return _record(load=6000, open_settle=76000, edit=17000, quiet=72000, ram=ram * 2 ** 20,
                       open_settle_renderer_cpu_ms=4000, phases=_phases(2000, 75000, 160, 13000),
                       settle={'after_load': 'capped', 'after_edit': 'capped'})
    _blocks(tmp_path, 1, records=[capped(900 + 10 * i) for i in range(10)])
    _blocks(tmp_path, 2, records=[capped(905 + 10 * i) for i in range(10)])
    facts = {}
    text = res.resources_tables(facts, [tmp_path], ['plate'], {'plate': 'Plate'})
    assert ('Of the capped wait, the browser\'s GPU process used 73.00 s / 73.00 s and the page\'s own process '
            '4.00 s / 4.00 s; the page had 160 / 160 long tasks, 13.00 s / 13.00 s in all.') in text
    assert 'Its memory readings ran from 900.0 MiB to 995.0 MiB across the kept launches.' in text
    prefix = 'perf.e2.plate.B8.prose-250kw.'
    assert facts[prefix + 'capped_gpu_cpu_ms.medians'] == [73000, 73000]
    assert facts[prefix + 'capped_renderer_cpu_ms.medians'] == [4000, 4000]


def test_a_never_idle_note_without_process_records_says_nothing_about_the_split(tmp_path):
    _never_idle_cell(tmp_path)
    text = res.resources_tables({}, [tmp_path], ['plate'], {'plate': 'Plate'})
    assert 'GPU process' not in text
    assert 'Its memory readings ran from 1024.0 MiB to 1024.0 MiB across the kept launches.' in text


def test_the_settle_column_states_how_often_the_first_seed_is_the_higher(tmp_path):
    """#226: the settle window is not a fixed length, and the first seed's was the longer one."""
    for editor, first, second in (('plate', 60, 45), ('folio', 55, 30), ('docen', 30, 30)):
        _blocks(tmp_path, 1, editor=editor, records=[_record(editor, quiet=first)] * 10)
        _blocks(tmp_path, 2, editor=editor, records=[_record(editor, quiet=second)] * 10)
    facts = {}
    res.resources_tables(facts, [tmp_path], ['docen', 'folio', 'plate'], {})
    assert facts['perf.e2.B8.settle_first_higher'] == 2
    assert facts['perf.e2.B8.settle_first_lower'] == 0
    assert facts['perf.e2.B8.settle_cells'] == 3
    # The totals are still counted (their facts stay); the note speaks of them only beside the windows.
    assert 'first seed' not in res.settle_window_note(facts)


def test_a_split_figure_that_disagrees_is_marked_and_not_stored_as_a_result(tmp_path):
    def capped(renderer):
        return _record(load=6000, open_settle=76000, open_settle_renderer_cpu_ms=renderer,
                       phases=_phases(2000, 75000, 160, 13000), settle={'after_load': 'capped', 'after_edit': 'capped'})
    _blocks(tmp_path, 1, records=[capped(4400)] * 10)
    _blocks(tmp_path, 2, records=[capped(3800)] * 10)
    facts = {}
    text = res.resources_tables(facts, [tmp_path], ['plate'], {'plate': 'Plate'})
    assert "the page's own process 4.40 s / 3.80 s (not reproduced);" in text
    prefix = 'perf.e2.plate.B8.prose-250kw.capped_renderer_cpu_ms.'
    assert prefix + 'medians' not in facts and facts[prefix + 'seed_medians'] == [4400, 3800]


def test_the_settle_note_claims_nothing_about_cells_it_did_not_count():
    """Review of #226: with no settling figure the note still blamed the window."""
    note = res.settle_window_note({})
    assert 'cells' not in note and 'first seed' not in note and 'ms/s' not in note
    counted = res.settle_window_note({'perf.e2.B8.settle_cells': 3, 'perf.e2.B8.settle_first_higher': 2,
                                      'perf.e2.B8.settle_first_lower': 0, 'perf.e2.B8.settle_window_min_s': 0.2,
                                      'perf.e2.B8.settle_window_max_s': 2.4})
    assert "Across the 3 cells that had one, the first seed's median was the higher in 2 and the lower in 0" in counted
    assert 'it is not the rate at which the editor works' in counted
    assert 'can begin before the first of these readings' in counted
    assert 'are kept in the facts and are not printed' in counted


# --- #226: the settling column as CPU per second of the window each launch sampled ---

def _series(cpu_ms, window_s, *, start_cpu=20000, start_s=18.4, samples=4):
    """The sampler's rows of one launch: the edit burst, then `samples` settle rows over `window_s`."""
    rows = [{'phase': 'edit_burst', 'monotonic_s': start_s - 0.3, 'cpu_ms': start_cpu}]
    for index in range(samples):
        share = index / (samples - 1)
        rows.append({'phase': 'quiescence', 'monotonic_s': start_s + window_s * share,
                     'cpu_ms': start_cpu + round(cpu_ms * share)})
    rows.append({'phase': 'after_edits', 'monotonic_s': start_s + window_s + 0.25, 'cpu_ms': start_cpu + cpu_ms + 10})
    return rows


def _settling(cpu_ms, window_s, **over):
    return _record(quiet=cpu_ms, series=_series(cpu_ms, window_s), **over)


def _rate_cell(tmp_path, first, second):
    _blocks(tmp_path, 1, records=first)
    _blocks(tmp_path, 2, records=second)
    facts = {}
    text = res.resources_tables(facts, [tmp_path], ['plate'], {'plate': 'Plate'})
    return text, facts


def test_the_settling_column_is_cpu_per_second_of_the_window_each_launch_sampled(tmp_path):
    """A longer window costs more in total and the same per second: the total disagrees, the rate does not."""
    text, facts = _rate_cell(tmp_path, [_settling(90, 2.25)] * 10, [_settling(64, 1.6)] * 10)
    assert '| Editor | CPU to open | CPU of the edit | CPU per second while settling |' in text
    assert '| 40 ms/s / 40 ms/s |' in text
    prefix = 'perf.e2.plate.B8.prose-250kw.'
    assert facts[prefix + 'edit_settle_cpu_rate.medians'] == [40.0, 40.0]
    assert facts[prefix + 'edit_settle_cpu_rate.window_s'] == [1.6, 2.25]
    # The totals stay in the facts: what was read is not thrown away.
    assert facts[prefix + 'edit_settle_cpu_ms.seed_medians'] == [90, 64]
    assert facts[prefix + 'edit_settle_cpu_ms.totals_agree'] is False


def test_a_window_under_a_second_is_not_a_rate(tmp_path):
    """10 ms steps over a fifth of a second say nothing: such a launch is not counted, and five are needed."""
    short = _settling(0, 0.2, )
    text, facts = _rate_cell(tmp_path, [_settling(80, 2.0)] * 10, [short] * 7 + [_settling(80, 2.0)] * 3)
    assert 'wait too short to measure (10 and 3 of 10 and 10 launches waited a second or more)' in text
    prefix = 'perf.e2.plate.B8.prose-250kw.edit_settle_cpu_rate.'
    assert prefix + 'medians' not in facts and facts[prefix + 'counted'] == [10, 3]
    assert facts[prefix + 'reason'] == 'window too short'


def test_five_launches_with_a_full_window_are_enough(tmp_path):
    text, _facts = _rate_cell(tmp_path, [_settling(80, 2.0)] * 10, [_settling(0, 0.2)] * 5 + [_settling(84, 2.0)] * 5)
    assert '| 40 ms/s / 42 ms/s |' in text


def test_a_rate_that_disagrees_says_both_and_the_range(tmp_path):
    text, facts = _rate_cell(tmp_path, [_settling(1200, 2.0)] * 9 + [_settling(1400, 2.0)], [_settling(60, 2.0)] * 10)
    assert 'not reproduced (first 600 ms/s; second 30 ms/s; launches 30 ms/s to 700 ms/s)' in text
    prefix = 'perf.e2.plate.B8.prose-250kw.edit_settle_cpu_rate.'
    assert prefix + 'medians' not in facts and facts[prefix + 'seed_medians'] == [600.0, 30.0]


def test_the_rate_tolerance_is_the_counter_step_over_the_window(tmp_path):
    """20 ms of counter resolution over a 2-second window is 10 ms/s: 10 and 18 ms/s agree, 10 and 22 do not."""
    text, _facts = _rate_cell(tmp_path, [_settling(20, 2.0)] * 10, [_settling(36, 2.0)] * 10)
    assert '| 10 ms/s / 18 ms/s |' in text
    again = tmp_path / 'again'
    again.mkdir()
    text, _facts = _rate_cell(again, [_settling(20, 2.0)] * 10, [_settling(44, 2.0)] * 10)
    assert 'not reproduced (first 10 ms/s; second 22 ms/s;' in text


def test_a_launch_without_its_samples_has_no_rate(tmp_path):
    text, facts = _rate_cell(tmp_path, [_record(quiet=80)] * 10, [_record(quiet=80)] * 10)
    assert '| window not recorded |' in text
    assert facts['perf.e2.plate.B8.prose-250kw.edit_settle_cpu_rate.reason'] == 'window not recorded'


def test_the_settle_note_says_what_the_windows_were(tmp_path):
    _text, facts = _rate_cell(tmp_path, [_settling(90, 2.25)] * 10, [_settling(0, 0.2)] * 5 + [_settling(64, 1.6)] * 5)
    note = res.settle_window_note(facts)
    assert 'ran from 0.2 s to 2.2 s' in note or 'ran from 0.2 s to 2.3 s' in note
    assert 'per second' in note


def test_a_wait_of_exactly_one_second_counts_and_one_just_under_does_not(tmp_path):
    text, _facts = _rate_cell(tmp_path, [_settling(40, 1.0)] * 10, [_settling(40, 1.0)] * 10)
    assert '| 40 ms/s / 40 ms/s |' in text
    under = tmp_path / 'under'
    under.mkdir()
    text, _facts = _rate_cell(under, [_settling(40, 1.0)] * 10, [_settling(40, 0.99)] * 10)
    assert 'wait too short to measure (10 and 0 of 10 and 10 launches waited a second or more)' in text


def test_a_capped_settle_prints_no_rate_even_with_its_samples(tmp_path):
    """Review of #226: a wait that the cap ended is not a settle; its samples must not become a rate."""
    capped = _settling(70000, 30.0, settle={'after_load': 'reached', 'after_edit': 'capped'})
    text, facts = _rate_cell(tmp_path, [_settling(80, 2.0)] * 9 + [capped], [_settling(80, 2.0)] * 10)
    assert '| never idle | 1024.0 MiB' in text and 'ms/s' not in text.split('Not published')[0]
    assert not any('edit_settle_cpu_rate' in key for key in facts)


def test_the_settling_cell_is_counted_once_as_the_rate_not_also_as_the_total(tmp_path):
    """The report counts every fact ending in .reproduced as a scheduled cell: the unprinted total must not be one."""
    _text, facts = _rate_cell(tmp_path, [_settling(90, 2.25)] * 10, [_settling(64, 1.6)] * 10)
    prefix = 'perf.e2.plate.B8.prose-250kw.'
    assert prefix + 'edit_settle_cpu_ms.reproduced' not in facts
    assert facts[prefix + 'edit_settle_cpu_ms.totals_agree'] is False
    assert facts[prefix + 'edit_settle_cpu_rate.reproduced'] is True
    assert sum(1 for key in facts if key.startswith(prefix) and key.endswith('.reproduced')) == 4


def test_a_settling_cell_without_a_rate_is_a_scheduled_cell_that_did_not_reproduce(tmp_path):
    _text, facts = _rate_cell(tmp_path, [_settling(80, 2.0)] * 10, [_settling(0, 0.2)] * 10)
    assert facts['perf.e2.plate.B8.prose-250kw.edit_settle_cpu_rate.reproduced'] is False
    other = tmp_path / 'other'
    other.mkdir()
    _text, facts = _rate_cell(other, [_record(quiet=80)] * 10, [_record(quiet=80)] * 10)
    assert facts['perf.e2.plate.B8.prose-250kw.edit_settle_cpu_rate.reproduced'] is False
