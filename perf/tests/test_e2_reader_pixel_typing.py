"""#238: a typing launch refused only for the missing glyph outline is read on the pixel witness.

The harness times a key press to the first screencast frame that changed and then checks that frame
against the typed character's own outline. Editors that draw their text on a canvas have no outline,
so the launch is refused. Where every key press of the launch was confirmed in the editor's model and
its first changed frame changed at least 100 pixels (the bound the paste criterion uses to tell text
from a caret, #207), the same clock is published, and the cell says which witness it rests on.
"""
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


def _obs(paint, pixels=102, confirmed=True, burst=None, acceptable=True, outcome='witnessed'):
    row = {'mechanism': 'cdp_screencast_changed_frame', 'paint_ms': paint,
           'clock_skew': {'frame_interval_ms': 16.7, 'acceptable': acceptable},
           'edit_confirmation': {'adapter': {'adapter': 'model', 'confirmed': confirmed}},
           'witness': {'changed_pixels': pixels, 'outcome': outcome}}
    if burst is not None:
        row['burst'] = burst
    return row


def _arm(single, burst, **kw):
    """One cache state as the harness writes it: the single edit (carrying its burst), then the burst's keys."""
    keys = [_obs(value, **kw) for value in burst]
    return [_obs(single, pixels=kw.get('pixels', 1494) if kw.get('pixels', 102) >= 100 else kw['pixels'],
                 burst=keys, **{k: v for k, v in kw.items() if k != 'pixels'})] + keys


def _launch(run, editor, criterion, observations, *, rep=0, job_id='run-001', publishable=True):
    job = run / 'benchmark_warm_cold' / job_id
    path = job / 'cells' / f'{rep:04d}-{editor}' / 'attempts' / f'{criterion.lower()}.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(
        editor_id=editor, criterion_id=criterion, measure='warm_steady', layer='browser_visible',
        outcome='not_applicable', refusal_code='not_applicable', failure_reason=GLYPH, samples_ms=[],
        environment=dict(ENV, editor_id=editor),
        diagnostic={'observations': observations, 'aggregation': 'all samples required'},
        host_provenance={'host_build': 'production', 'publishable': publishable, 'tree_sha256': 'tree-a'})))
    (job / 'summary.json').write_text(json.dumps(dict(
        run_id=job_id, seed=1, execution_profile='dedicated_publish', order=[[i, editor] for i in range(rep + 1)])))


COLD = _arm(90.0, [80.0, 70.0, 75.0])
WARM = _arm(30.0, [20.0, 26.0, 22.0])


def test_the_single_edit_of_each_cache_state_is_the_c05_sample(fs):
    run = Path('/runs/campaign')
    _launch(run, 'docen', 'C05', COLD + WARM)
    warm = cells.build_run_cell(run, 'docen', 'C05', measure='warm_steady')
    cold = cells.build_run_cell(run, 'docen', 'C05', measure='process_cold_fs_warm')
    assert warm['kept_ms'] == [30.0] and cold['kept_ms'] == [90.0]
    assert warm['refusals'] == {} and cold['refusals'] == {}
    assert warm['witness'] == 'changed_pixels' and cold['witness'] == 'changed_pixels'
    assert warm['unwitnessed'] is None
    # The smallest change any key press of the kept launches made: how close the editor is to the bound.
    assert warm['least_changed_pixels'] == 102


def test_the_median_of_the_burst_is_the_c06_sample(fs):
    run = Path('/runs/campaign')
    _launch(run, 'docen', 'C06', COLD + WARM)
    assert cells.build_run_cell(run, 'docen', 'C06', measure='warm_steady')['kept_ms'] == [22.0]
    assert cells.build_run_cell(run, 'docen', 'C06', measure='process_cold_fs_warm')['kept_ms'] == [75.0]


def test_a_launch_with_a_caret_sized_change_stays_refused(fs):
    """canvas-editor: every first changed frame is 24 pixels, a caret."""
    run = Path('/runs/campaign')
    _launch(run, 'canvas', 'C05', _arm(12.0, [4.0, 60.0, 70.0], pixels=24) + _arm(11.0, [5.0, 61.0, 71.0], pixels=24))
    cell = cells.build_run_cell(run, 'canvas', 'C05', measure='warm_steady')
    assert cell['kept_ms'] == [] and cell['refusals'] == {'not_applicable': 1}
    assert cell['unwitnessed']['keystrokes'] == 8 and cell.get('witness') != 'changed_pixels'


def test_one_key_press_under_the_bound_keeps_the_whole_launch_refused(fs):
    run = Path('/runs/campaign')
    warm = _arm(30.0, [20.0, 26.0, 22.0])
    warm[2]['witness']['changed_pixels'] = 99
    _launch(run, 'docen', 'C05', COLD + warm)
    for measure in ('warm_steady', 'process_cold_fs_warm'):
        assert cells.build_run_cell(run, 'docen', 'C05', measure=measure)['refusals'] == {'not_applicable': 1}


def test_a_key_press_the_editor_did_not_confirm_keeps_the_launch_refused(fs):
    """WordCraft: the edit was confirmed on a quarter of the key presses."""
    run = Path('/runs/campaign')
    warm = _arm(30.0, [20.0, 26.0, 22.0])
    warm[1]['edit_confirmation']['adapter']['confirmed'] = False
    _launch(run, 'wordcraft', 'C05', COLD + warm)
    assert cells.build_run_cell(run, 'wordcraft', 'C05', measure='warm_steady')['refusals'] == {'not_applicable': 1}


def test_a_launch_that_does_not_have_both_cache_states_whole_stays_refused(fs):
    run = Path('/runs/campaign')
    _launch(run, 'docen', 'C05', WARM)
    assert cells.build_run_cell(run, 'docen', 'C05', measure='warm_steady')['refusals'] == {'not_applicable': 1}


def test_a_frame_the_clock_check_did_not_accept_keeps_the_launch_refused(fs):
    run = Path('/runs/campaign')
    _launch(run, 'docen', 'C05', COLD + _arm(30.0, [20.0, 26.0, 22.0], acceptable=False))
    assert cells.build_run_cell(run, 'docen', 'C05', measure='warm_steady')['refusals'] == {'not_applicable': 1}


def test_a_host_that_is_not_publishable_stays_unpublished(fs):
    run = Path('/runs/campaign')
    _launch(run, 'docen', 'C05', COLD + WARM, publishable=False)
    assert cells.build_run_cell(run, 'docen', 'C05', measure='warm_steady')['kept_ms'] == []


def test_a_diagnostic_run_stays_refused(fs, monkeypatch):
    run = Path('/runs/campaign')
    monkeypatch.setitem(ENV, 'run_kind', 'diagnostic')
    _launch(run, 'docen', 'C05', COLD + WARM)
    assert cells.build_run_cell(run, 'docen', 'C05', measure='warm_steady')['refusals'] == {'not_applicable': 1}


def test_a_time_under_one_redraw_is_flagged_as_the_glyph_path_flags_it(fs):
    run = Path('/runs/campaign')
    _launch(run, 'docen', 'C05', COLD + _arm(9.0, [20.0, 26.0, 22.0]))
    cell = cells.build_run_cell(run, 'docen', 'C05', measure='warm_steady')
    assert cell['kept_ms'] == [9.0] and cell['sub_frame'] == [True]


def test_another_refusal_is_never_read_on_the_pixel_witness(fs):
    run = Path('/runs/campaign')
    job = run / 'benchmark_warm_cold' / 'run-001'
    _launch(run, 'docen', 'C05', COLD + WARM)
    path = job / 'cells' / '0000-docen' / 'attempts' / 'c05.json'
    row = json.loads(path.read_text()); row['failure_reason'] = 'document_content_unverifiable'
    path.write_text(json.dumps(row))
    assert cells.build_run_cell(run, 'docen', 'C05', measure='warm_steady')['refusals'] == {'not_applicable': 1}
