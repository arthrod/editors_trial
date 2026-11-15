"""Integration: fake-page content must match the supplied DOCX, never canned prose."""
from pathlib import Path
from playwright.sync_api import sync_playwright
from perf.fixtures.generate import docx_zip_bytes
from perf.runner.browser_hosts import StaticHost


def test_input_smoke_renders_the_supplied_corpus():
    host = StaticHost(Path(__file__).resolve().parents[1])
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            try:
                page = browser.new_page()
                page.route('**/corpus.docx', lambda route: route.fulfill(
                    body=docx_zip_bytes('first line\nUnicode café\n'.encode()),
                    content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'))
                page.goto(host.url + '/container/fake/index.html?lane=input')
                page.wait_for_function('window.b6Ready === true')
                assert page.locator('#doc').inner_text() == 'first lineUnicode café'
            finally:
                browser.close()
    finally:
        host.stop()


def test_c10_smoke_explicitly_reports_its_profile_cap(tmp_path):
    import json
    import subprocess
    import sys
    result = subprocess.run([sys.executable, '-m', 'perf.container.smoke',
        'adversarial_c10_scroll', '--out-root', str(tmp_path), '--run-id', 'cap',
        '--execution-profile', 'ci_contract', '--host-class', 'ci_coarse', '--seed', '1'],
        capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    data = json.loads((tmp_path/'adversarial_c10_scroll/cap/smoke-summary.json').read_text())
    assert data['cells_measured'] == 0
    assert data['by_design_refusals'] == {
        'execution_profile: workload cap for ci_contract: prose-50kw': 3}


def test_smoke_does_not_excuse_arbitrary_empty_runs(tmp_path):
    import json
    import pytest
    from perf.container.smoke import finish_smoke
    cell = tmp_path/'cells/one'
    (cell/'attempts').mkdir(parents=True)
    (cell/'attempts/c10.json').write_text(json.dumps({
        'criterion_id':'C10', 'editor_id':'fake', 'outcome':'failed',
        'failure_reason':'unexpected probe error'}))
    (tmp_path/'summary.json').write_text(json.dumps({
        'execution_profile':'ci_contract', 'rendering':{'renderer':'test'},
        'samples':[{'cell_directory':str(cell),'outcome':'ok'}]}))
    with pytest.raises(ValueError, match='nothing_measured'):
        finish_smoke(tmp_path,'adversarial_c10_scroll')


def test_input_smoke_accepts_measured_criteria_and_retains_refusals(tmp_path):
    import json
    import subprocess
    import sys
    result = subprocess.run([sys.executable, '-m', 'perf.container.smoke',
        'benchmark_input', '--out-root', str(tmp_path), '--run-id', 'input',
        '--execution-profile', 'ci_contract', '--host-class', 'ci_coarse', '--seed', '1'],
        capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    data = json.loads((tmp_path/'benchmark_input/input/smoke-summary.json').read_text())
    assert data['cells_measured'] >= 1
    assert data['attempt_counts']['measured'] >= 1
    assert data['publishable'] is False
