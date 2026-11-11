"""Legacy facts snapshots contain no E2 measurements; render explicit absence."""
import pytest
from build import reportgen


def test_legacy_snapshot_renders_explicit_unmeasured_status():
    try:
        rendered = reportgen.render('{{perf.e2.status}}', {'checks.total': 99})
    except KeyError as error:
        rendered = f'missing fact: {error}'
    assert rendered == 'This report is not yet measured.'


def test_partial_e2_facts_are_not_silently_filled():
    with pytest.raises(KeyError, match='perf.e2.status'):
        reportgen.render('{{perf.e2.status}}', {'perf.e2.intro': 'measured'})


def test_unknown_measurement_remains_an_error():
    with pytest.raises(KeyError, match='rt.missing'):
        reportgen.render('{{rt.missing}}', {})
