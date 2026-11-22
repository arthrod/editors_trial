"""The published E2 campaign keeps its editors; later editors get a campaign of their own.

A job's global index names its cell (plan.py, --jobs, #185), so wiring a new
editor into the lanes must never renumber the published campaign's jobs.
"""
import pytest

from perf.container import policy
from perf.runner.benchmark_warm_cold import BROWSER_TARGETS
from perf.runner.browser_hosts import host_policy

PUBLISHED = ['plate', 'docxodus', 'superdoc', 'genoffice', 'canvas', 'docen', 'wordcraft', 'eigenpal', 'folio']


def test_the_published_campaign_keeps_its_nine_editors_in_order():
    assert policy.campaign_editors('e2') == PUBLISHED
    assert len(policy.publication_jobs(PUBLISHED, 1, 2, 'shared_guarded')) == 594


def test_the_later_campaign_measures_only_editors_added_after_it():
    later = policy.campaign_editors('later')
    assert later, 'the later campaign has wired editors'
    assert not set(later) & set(PUBLISHED)
    assert set(later) <= set(policy.LATER_CAMPAIGN_EDITORS)
    assert set(later) <= set(BROWSER_TARGETS)


def test_every_browser_target_is_in_exactly_one_campaign():
    for name in BROWSER_TARGETS:
        if name == 'apryse' or not host_policy(name)['publishable']:
            continue
        homes = [c for c in policy.CAMPAIGNS if name in policy.campaign_editors(c)]
        assert len(homes) == 1, (name, homes)


def test_an_unknown_campaign_is_refused():
    with pytest.raises(ValueError):
        policy.campaign_editors('e3')
