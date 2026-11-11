from perf.runner.refusals import refusal_code


def test_dependency_refusal_survives_report_ingestion():
    assert refusal_code({'outcome': 'refused', 'refusal_code': 'dependency_missing',
                         'missing_module': 'playwright'}) == 'dependency_missing'


def test_unknown_refusal_still_fails_closed():
    assert refusal_code({'refusal_code': 'made_up_success'}) == 'crash'
