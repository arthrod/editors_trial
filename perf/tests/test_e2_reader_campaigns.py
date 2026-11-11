"""Shard provenance is a list: no overwriting jobs from other Spaces."""

import json
from pathlib import Path
from build import perf_e2_tables as report


def campaign(fs, space, campaign_id, job_id='same-job'):
    root = Path('/evidence') / space / 'runs' / campaign_id
    job = root / 'benchmark_memory' / job_id
    job.mkdir(parents=True)
    (root / 'RUN.log').write_text('start\ncpu_affinity_pinned=0,1 cpu.max=200000 100000 visible=64\n')
    (job / 'summary.json').write_text(
        json.dumps({
            'run_id': job_id,
            'seed': 1,
            'runner': 'benchmark_memory',
            'cpu_accounting': {
                'samples_total': 30,
                'samples_unavailable': 2,
                'samples_refused': 3,
                'steal_percent': 0.5,
            },
        })
    )
    return root


def test_multiple_campaigns_retain_space_and_accounting(fs):
    roots = [campaign(fs, 'space-a', 'campaign-a'), campaign(fs, 'space-b', 'campaign-b')]
    assert callable(getattr(report, 'facts_from_campaigns', None)), 'multi-campaign reader absent'
    facts = report.facts_from_campaigns(roots)
    records = facts['perf.e2.campaigns']
    assert len(records) == 2
    assert {r['space'] for r in records} == {'space-a', 'space-b'}
    for row in records:
        assert row['cpu_affinity_pinned'] == ['cpu_affinity_pinned=0,1 cpu.max=200000 100000 visible=64']
        assert row['jobs'][0]['space'] == row['space']
        assert row['jobs'][0]['cpu_accounting']['samples_unavailable'] == 2
    text = facts['perf.e2.provenance']
    assert 'space-a' in text and 'space-b' in text and 'unavailable' in text and '0.5' in text


def test_missing_log_and_partial_job_are_explicit(fs):
    root = campaign(fs, 'space-a', 'campaign-a')
    (root / 'RUN.log').unlink()
    job = root / 'benchmark_typing' / 'running'
    job.mkdir(parents=True)
    (job / 'cells').mkdir()
    assert callable(getattr(report, 'facts_from_campaigns', None)), 'multi-campaign reader absent'
    facts = report.facts_from_campaigns([root, root])
    assert len(facts['perf.e2.campaigns']) == 1
    assert len(facts['perf.e2.campaigns'][0]['jobs']) == 2
    assert 'not recorded' in facts['perf.e2.provenance'] and 'incomplete' in facts['perf.e2.provenance']


def test_campaign_roots_from_facts_config(fs):
    from build import facts as generator

    root = campaign(fs, 'space-a', 'campaign-a')
    config = Path('/config.json')
    config.write_text(json.dumps({'campaigns': [str(root)]}))
    result = {}
    # The assertion is the RED rather than a KeyError from the old config parser.
    assert callable(getattr(report, 'facts_from_campaigns', None)), 'multi-campaign reader absent'
    generator.perf_e2_facts(config, result)
    assert 'space-a' in result['perf.e2.provenance']


def test_space_root_and_corrupt_summary(fs):
    root = campaign(fs, 'space-a', 'campaign-a')
    (root / 'benchmark_memory/same-job/summary.json').write_text('[]')
    (root / 'unrelated/empty').mkdir(parents=True)
    facts = report.facts_from_campaigns([root.parent.parent])
    assert facts['perf.e2.campaigns'][0]['jobs'][0]['status'] == 'incomplete'
    assert len(facts['perf.e2.campaigns'][0]['jobs']) == 1


def test_missing_campaign_is_rejected(fs):
    import pytest

    with pytest.raises(ValueError, match='does not exist'):
        report.facts_from_campaigns(['/missing'])


def test_space_directory_without_runs_is_rejected(fs):
    import pytest

    # A nested pull directory (shard0/, publish-3/, snapshots) is not a
    # campaign; a silent 0-job record would hide the misconfiguration.
    space = Path('/evidence/space-without-runs')
    (space / 'shard0' / 'runs').mkdir(parents=True)
    (space / 'publish-3').mkdir()
    with pytest.raises(ValueError, match='no runs/ and no campaign jobs'):
        report.facts_from_campaigns([space])


def test_nested_pull_uses_explicit_space_identity(fs):
    root = campaign(fs, 'space-a/shard0', 'campaign-a')
    # Nested pull directory names must not masquerade as HF Space names.
    facts = report.facts_from_campaigns([root])
    assert facts['perf.e2.campaigns'][0]['space'] == 'space-a'
