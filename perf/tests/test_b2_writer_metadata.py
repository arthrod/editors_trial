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
