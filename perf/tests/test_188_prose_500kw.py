"""#188: a 500,000-word rung for Report E2's load lanes (Arthur, 2026-11-13).

The rung is measured by the document lane (C11, C12, C15) and by C14, in new
jobs appended after the campaign's 160; no existing job is renumbered.
"""
import hashlib
import json

import pytest

from perf.container.policy import publication_jobs

# sha256 of json.dumps(publication_jobs(EDITORS, 1, 2, 'shared_guarded', blocks=2))
# taken at ad1ebf3a, before #188: the 160 jobs the campaign ran.
CAMPAIGN_JOBS_SHA256 = "2be299d0a82865f8bffd63909c0f4463948f88c9e156bc508e68d7d5b2a71863"
EDITORS = ['plate', 'docxodus', 'superdoc', 'genoffice', 'canvas', 'docen', 'wordcraft', 'eigenpal', 'folio']


def _jobs():
    return publication_jobs(EDITORS, 1, 2, 'shared_guarded', blocks=2)


def test_the_campaign_jobs_keep_their_indexes():
    jobs = _jobs()
    assert hashlib.sha256(json.dumps(jobs[:160]).encode()).hexdigest() == CAMPAIGN_JOBS_SHA256


def test_eight_500k_jobs_follow_the_campaign():
    jobs = _jobs()
    assert len(jobs) == 168
    head = ['--execution-profile', 'dedicated_publish', '--host-class', 'shared_guarded']
    expected = []
    for seed in ('1', '2'):
        for tail in (['--workload', 'prose-500kw', '--editors', *EDITORS, '--criteria', 'C11', 'C12', 'C15'],
                     ['--editors', *EDITORS, '--criteria', 'C14', '--c14-rungs', 'prose-500kw']):
            for block in (1, 2):
                expected.append(('benchmark_document', head + (['--chrome-profile'] if block == 1 else [])
                                 + ['--seed', seed, *tail, '--block', f'{block}/2', '--samples', '5']))
    assert jobs[160:] == expected


def test_the_prose_ladder_itself_is_unchanged():
    from perf.fixtures.docx_workload import PROSE_LADDER
    assert [row['workload_id'] for row in PROSE_LADDER] == ['prose-500w', 'prose-5kw', 'prose-50kw', 'prose-250kw']


def test_the_500k_rung_is_a_known_publishable_workload():
    from perf.fixtures.profiles import allowed_workloads, size_ladder
    row = next(r for r in size_ladder() if r['workload_id'] == 'prose-500kw')
    assert row['words'] == 500_000 and row['shape'] == 'prose'
    assert 'prose-500kw' in allowed_workloads('dedicated_publish')
    assert 'prose-500kw' not in allowed_workloads('ci_broad')


def test_the_500k_document_carries_the_correctness_lines():
    from perf.fixtures.docx_workload import EXTENSION_ROWS, SENTINEL_PREFIX, _correctness_lines, build_prose_docx
    row = next(r for r in EXTENSION_ROWS if r['workload_id'] == 'prose-500kw')
    built = build_prose_docx(dict(row))
    lines = built['text'].split('\n')
    assert lines[-1] == '%s prose-500kw' % SENTINEL_PREFIX
    assert lines[-1 - len(_correctness_lines()):-1] == _correctness_lines()
    assert len(built['text'].split()) > 500_000


def test_the_500k_load_wait_is_1000_s():
    from perf.runner.load_timeouts import load_timeout_ms, C14_LOAD_TIMEOUT_MS
    assert load_timeout_ms('prose-500kw') == C14_LOAD_TIMEOUT_MS == 1_000_000
    assert load_timeout_ms('prose-250kw') == 600_000
    assert load_timeout_ms('prose-5kw') == 300_000


def test_c14_rungs_default_and_narrowed():
    from perf.runner.benchmark_document import C14_RUNGS, resolve_c14_rungs
    assert resolve_c14_rungs(None) == C14_RUNGS
    assert resolve_c14_rungs(['prose-500kw']) == ('prose-500kw',)
    with pytest.raises(SystemExit):
        resolve_c14_rungs(['prose-9mw'])
    with pytest.raises(SystemExit):
        resolve_c14_rungs(['prose-5kw', 'prose-5kw'])


def test_the_planner_estimates_a_500k_job():
    from perf.container.plan import estimate
    jobs = _jobs()
    doc_500k = estimate(*jobs[160])
    doc_250k = estimate(*next(job for job in jobs if '--workload' in job[1]
                               and job[1][job[1].index('--workload') + 1] == 'prose-250kw'
                               and job[0] == 'benchmark_document' and '--chrome-profile' in job[1]))
    assert doc_500k > doc_250k
