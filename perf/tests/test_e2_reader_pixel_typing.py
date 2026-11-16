"""#245: a typing launch of an editor that draws its text on a canvas ends on the settled-pixel witness.

The harness writes such a trial as measured, with ``witness: settled_pixels``. The reader checks every key
press behind it before a cell is built, and labels the cell with the smallest edit seen. A launch refused
for the missing glyph outline stays refused whatever its first changed frame held: Docen's is its caret
moving plus the harness's own mark, 102 pixels (#238, #247).
"""
import copy
import json
from pathlib import Path

from perf.analysis import e2_cells as cells

GLYPH = 'no_glyph_geometry_to_witness_the_keystrokes_own_paint'
#: The environment a published warm/cold launch records (round228, job 83), without the fixture's identity.
ENV = {"arch": "x86_64", "cache_state": "warm_steady", "cpu_cores_logical": 64, "cpu_model": "AMD EPYC 7R13 Processor",
       "display_refresh_hz": None, "editor_version": "1890b15aa", "execution_profile": "dedicated_publish",
       "feature_fallback": [], "feature_profile": "P0", "headless": True, "host_class": "shared_guarded",
       "interpretation_conditions": ["I01", "I02", "I03", "I04", "I05", "I06", "I07", "I08", "I09", "I10", "I11", "I12"],
       "load_timeout_ms": 300000, "match_count": 0, "os": "linux", "os_version": "6.12", "paragraph_shape": "prose",
       "power_source": "ac", "ram_bytes": 529681694720, "repetition_unit": "fresh_process", "run_kind": "timing",
       "unicode_class": "ascii", "workload_id": "prose-500w"}


COLUMNS = [{'x': 596, 'y': 510, 'width': 3, 'height': 49}, {'x': 604, 'y': 510, 'width': 3, 'height': 49}]


def _key(ms, pixels=34, columns=COLUMNS, adapter='model', confirmed=True, failure=None, kind='settled_pixels', interval=16.7):
    return {'mechanism': 'cdp_screencast_changed_frame', 'edit_ms': ms, 'paint_ms': ms, 'outcome': 'measured',
            'witness_kind': kind, 'clock_skew': {'frame_interval_ms': interval, 'acceptable': True, 'skew_ms': 0},
            'witness': {'changed_pixels': 102, 'outcome': 'witnessed'},
            'edit_confirmation': {'confirmed': confirmed, 'adapter': {'adapter': adapter, 'confirmed': confirmed},
                                  'pixel_settle': {'failure_reason': failure, 'edit_pixels': pixels,
                                                   'caret_columns_device_px': columns}}}


def _trial(criterion, keys, samples, **over):
    row = dict(editor_id='docen', criterion_id=criterion, measure='warm_steady', layer='browser_visible',
               outcome='measured', refusal_code=None, samples_ms=samples, witness='settled_pixels',
               environment=dict(ENV, editor_id='docen'),
               diagnostic={'observations': keys if criterion == 'C05' else [keys], 'frame_interval_ms': 16.7})
    row.update(over)
    return row


def test_a_trial_whose_every_key_press_settled_is_labelled_with_its_smallest_edit():
    row = _trial('C06', [_key(50.0, 34), _key(52.0, 31), _key(49.0, 36)], [50.0])
    before = copy.deepcopy(row)
    read = cells.settled_pixel_typing(row)
    assert read['outcome'] == 'measured' and read['samples_ms'] == [50.0]
    assert read['pixel_witness'] == {'issue': 245, 'keystrokes': 3, 'least_changed_pixels': 31}
    assert row == before  # the cached row is not mutated


def test_the_smaller_floor_needs_the_carets_two_columns():
    assert cells.settled_pixel_typing(_trial('C05', [_key(50.0, 34)], [50.0]))['outcome'] == 'measured'
    for key in (_key(50.0, 34, columns=None), _key(50.0, 99, columns=COLUMNS[:1]), _key(50.0, 15)):
        read = cells.settled_pixel_typing(_trial('C05', [key], [50.0]))
        assert read['outcome'] == 'refused' and read['samples_ms'] == [], key
        assert read['refusal_code'] == 'paint_witness_unavailable' and read['failure_reason'] == 'pixel_witness_incomplete'
    assert cells.settled_pixel_typing(_trial('C05', [_key(50.0, 500, columns=None)], [50.0]))['outcome'] == 'measured'


def test_one_key_press_that_did_not_settle_or_was_not_confirmed_by_text_refuses_the_trial():
    good = _key(50.0)
    for bad in (_key(50.0, failure='not_settled'), _key(50.0, confirmed=False), _key(50.0, adapter='flag'),
                _key(50.0, kind=None), {**_key(50.0), 'edit_confirmation': {'adapter': {'adapter': 'model', 'confirmed': True}}}):
        read = cells.settled_pixel_typing(_trial('C06', [good, bad, good], [50.0]))
        assert read['outcome'] == 'refused', bad


def test_a_trial_that_mixes_witnesses_or_has_no_key_presses_is_refused():
    assert cells.settled_pixel_typing(_trial('C05', [_key(50.0)], [50.0], witness='mixed'))['outcome'] == 'refused'
    assert cells.settled_pixel_typing(_trial('C05', [], [50.0]))['outcome'] == 'refused'


def test_trials_of_other_criteria_and_of_glyph_witnessed_editors_pass_unchanged():
    glyph = _trial('C05', [_key(50.0, kind=None)], [50.0], witness=None)
    assert cells.settled_pixel_typing(glyph) is glyph
    other = _trial('C07', [_key(50.0)], [50.0])
    assert cells.settled_pixel_typing(other) is other


def _launch(run, editor, criterion, row, *, rep=0, job_id='run-001'):
    job = run / 'benchmark_warm_cold' / job_id
    path = job / 'cells' / f'{rep:04d}-{editor}' / 'attempts' / f'{criterion.lower()}.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(row, editor_id=editor, environment=dict(ENV, editor_id=editor),
                                    host_provenance={'host_build': 'production', 'publishable': True, 'tree_sha256': 'tree-a'})))
    (job / 'summary.json').write_text(json.dumps(dict(
        run_id=job_id, seed=1, execution_profile='dedicated_publish', order=[[i, editor] for i in range(rep + 1)])))


def test_a_launch_refused_for_the_missing_outline_stays_refused_whatever_its_first_frame_held(fs):
    """#238: 102 changed pixels in Docen's first frame are its caret and the harness's own mark."""
    run = Path('/runs/campaign')
    observation = {'mechanism': 'cdp_screencast_changed_frame', 'paint_ms': 28.0,
                   'clock_skew': {'frame_interval_ms': 16.7, 'acceptable': True},
                   'edit_confirmation': {'adapter': {'adapter': 'model', 'confirmed': True}},
                   'witness': {'changed_pixels': 102, 'outcome': 'witnessed', 'time_origin_ms': 1000.0}}
    burst = [copy.deepcopy(observation) for _ in range(3)]
    arm = [dict(observation, burst=burst)] + burst
    _launch(run, 'docen', 'C05', dict(
        criterion_id='C05', measure='warm_steady', layer='browser_visible', outcome='not_applicable',
        refusal_code='not_applicable', failure_reason=GLYPH, failure_reasons=[GLYPH], samples_ms=[],
        diagnostic={'observations': arm + copy.deepcopy(arm)}))
    for measure in ('warm_steady', 'process_cold_fs_warm'):
        cell = cells.build_run_cell(run, 'docen', 'C05', measure=measure)
        assert cell['kept_ms'] == [] and cell.get('witness') is None, measure
    assert cells.build_run_cell(run, 'docen', 'C05', measure='warm_steady')['refusals'] == {'not_applicable': 1}
