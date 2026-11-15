"""Integration handoff: B2 attempts carry their measurement identity and interval."""
from perf.tests.test_b2_paint import WriterIntegration, frame_record


def test_cache_state_distinguishes_cold_and_warm_measurements():
    row = WriterIntegration().write()
    assert row.get('measure') == 'process_cold_fs_warm'


def test_measured_attempt_exports_its_witnessed_interval():
    row = WriterIntegration().write()
    assert row['outcome'] == 'measured'
    interval = frame_record()['clock_check']['frame_interval_ms']
    assert row['diagnostic'].get('frame_interval_ms') == interval
    assert row.get('sub_frame_samples') == [False]


def test_ready_attempt_exports_accepted_clock_interval(tmp_path):
    import json
    from perf.runner.benchmark_warm_cold import _write_measured_attempt
    from perf.tests.test_schema import _env
    clock = frame_record()['clock_check']
    path = _write_measured_attempt(attempt_dir=tmp_path, criterion_id='C03',
        layer='browser_visible', boundary='first_usable', editor_id='plate', lane='browser',
        env=_env(), samples_ms=[25], cache_state='process_cold_fs_warm',
        diagnostic={'clock_skew': [clock]})
    row = json.loads(path.read_text())
    assert row['diagnostic'].get('frame_interval_ms') == clock['frame_interval_ms']
    assert row.get('sub_frame_samples') == [False]


def _write_burst(tmp_path, intervals):
    import json
    from perf.runner.benchmark_warm_cold import _write_measured_attempt
    from perf.tests.test_schema import _env
    from perf.tests.witness_records import publishable_witness_record
    observations = []
    for latency, interval in zip([5, 12, 20], intervals):
        witness = publishable_witness_record(100 + latency, 100)
        witness['clock_check']['frame_interval_ms'] = interval
        observations.append({'edit_ms': latency, 'outcome': 'measured', 'witness': witness,
            'clock_skew': witness['clock_check'],
            'edit_confirmation': {'confirmed': True, 'changed_pixels': 20,
                'visible_rects': [{'x': 10, 'y': 10, 'width': 20, 'height': 30}]}})
    try:
        path = _write_measured_attempt(attempt_dir=tmp_path, criterion_id='C06',
            layer='browser_visible', boundary='presented_frame', editor_id='plate', lane='browser',
            env=_env(), samples_ms=[12], cache_state='process_cold_fs_warm',
            diagnostic={'mechanism': 'cdp_screencast_changed_frame', 'observations': [observations]})
    except (TypeError, KeyError) as error:
        return {'writer_exception': str(error)}
    return json.loads(path.read_text())


def test_burst_median_uses_its_corresponding_witness_interval(tmp_path):
    row = _write_burst(tmp_path, [8.3, 16.7, 16.7])
    assert row['diagnostic'].get('frame_interval_ms') == 16.7
    assert row.get('sub_frame_samples') == [True]


def test_nullable_witness_interval_refuses_without_writer_exception(tmp_path):
    row = _write_burst(tmp_path, [8.3, None, 16.7])
    assert row.get('outcome') == 'failed', row
    assert row.get('failure_reason') == 'frame_interval_unavailable'
    assert row.get('samples_ms') == []
