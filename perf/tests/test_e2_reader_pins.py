"""Reader gates for built-editor identity and shakedown runs (#149).

``environment.editor_version`` is ``pin_label`` — the editor slug — so it
never identifies a build; ``host_provenance.tree_sha256`` does. A trial with
neither refuses as ``pin_not_recorded``, a pair across different trees
refuses, and a shakedown mark (summary or any trial) never publishes.
"""

import json

import pytest

from perf.tests import test_e2_report_fix3 as fixtures
from perf.tests.test_e2_report_fix3 import trial
from perf.tests.test_e2_reader_typing import typing_pair
from perf.analysis import e2_cells as cells
from build import perf_e2_tables as report

runs = fixtures.runs


def restamp(root, tree=..., editor_version=..., shakedown=...):
    """Rewrite every plate trial's built-editor identity in one run."""
    # 2x5 launches live under the block job, not the campaign root.
    for path in sorted(root.glob('**/cells/*/attempts/*.json')):
        row = json.loads(path.read_text())
        if tree is ...:
            pass
        elif tree is None:
            row.pop('host_provenance', None)
        else:
            row['host_provenance'] = {'host_build': 'production', 'publishable': True, 'tree_sha256': tree}
        if editor_version is not ...:
            row['environment'] = {**(row.get('environment') or {}), 'editor_version': editor_version}
        if shakedown is not ...:
            row['shakedown'] = shakedown
        path.write_text(json.dumps(row))


def test_pair_with_different_trees_refuses(runs):
    # The reviewer's scenario: same slug in environment.editor_version on
    # both sides, different built editors. The slug must not pair them.
    for root in runs:
        restamp(root, editor_version='plate')
    restamp(runs[1], tree='tree-rebuilt', editor_version='plate')
    with pytest.raises(ValueError, match='other editor pins'):
        report.facts_from_runs(*runs)


def test_matching_trees_publish(runs):
    for root in runs:
        restamp(root, tree='tree-a', editor_version='plate')
    facts = report.facts_from_runs(*runs)
    assert facts['perf.e2.plate.C07.reproduced'] is True


def test_trial_with_neither_tree_nor_pin_refuses_as_pin_not_recorded(runs):
    # environment.editor_version equal to the slug is not a pin; the trial
    # records no identity and refuses, without vetoing the whole pair.
    for root in runs:
        restamp(root, tree=None, editor_version='plate')
    facts = report.facts_from_runs(*runs)
    assert facts['perf.e2.plate.C07.reproduced'] is False
    cell = cells.build_run_cell(runs[0], 'plate', 'C07')
    assert cell['stats'] is None
    assert cell['refusals'] == {'pin_not_recorded': 10}
    assert 'pin_not_recorded' in facts['perf.e2.table.C07']


def test_pinned_editor_version_is_the_fallback_identity(runs):
    # Rows without a tree whose editor_version is a real pin (not the slug)
    # still identify the build — the shape of 7,050 rows in the HF pull.
    for root in runs:
        restamp(root, tree=None, editor_version='958c582cb')
    assert report.facts_from_runs(*runs)['perf.e2.plate.C07.reproduced'] is True
    restamp(runs[1], tree=None, editor_version='1890b15aa')
    with pytest.raises(ValueError, match='other editor pins'):
        report.facts_from_runs(*runs)


@pytest.mark.parametrize(
    'summary_updates',
    [
        {'shakedown': True, 'publishable': False},  # summary omits the reason
        {'publishable': False, 'publication_block_reason': 'shakedown: few repetitions to find bugs; never a publication run'},
        {'shakedown': True},  # even with publishable not false
    ],
)
def test_shakedown_summary_never_publishes(runs, summary_updates):
    # The mark is on the job the reader uses. Under 2x5 that is each block.
    for path in [runs[1] / 'summary.json', *sorted(runs[1].glob('*/*/summary.json'))]:
        path.write_text(json.dumps({**json.loads(path.read_text()), **summary_updates}))
    facts = report.facts_from_runs(*runs)
    assert facts['perf.e2.cells_reproduced'] == 0
    assert facts['perf.e2.plate.C07.reproduced'] is False
    assert 'unpublishable: shakedown' in facts['perf.e2.table.C07']


def test_shakedown_mark_on_one_trial_blocks_the_whole_run(runs):
    # One shakedown-marked trial, clean job summary: no cell of that run —
    # not even another editor's — may publish. A block job schedules every
    # editor for its five launches; a single extra file is not that schedule.
    trial(runs[1], 0, 'C07', shakedown=True)
    for root in runs:
        for summary_path in sorted(root.glob('*/*/summary.json')):
            summary = json.loads(summary_path.read_text())
            order = summary.get('order') or []
            reps = [rep for rep, editor in order if editor == 'plate' and isinstance(rep, int)]
            summary['order'] = order + [[rep, 'docen'] for rep in reps if [rep, 'docen'] not in order]
            summary_path.write_text(json.dumps(summary))
            job = summary_path.parent
            for rep in reps:
                src = job / 'cells' / f'{rep:04d}-plate' / 'attempts' / 'C07.json'
                row = json.loads(src.read_text())
                row['editor_id'] = 'docen'
                row.pop('shakedown', None)
                dest = job / 'cells' / f'{rep:04d}-docen' / 'attempts' / 'C07.json'
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(json.dumps(row))
    for editor in ('plate', 'docen'):
        cell = cells.build_run_cell(runs[1], editor, 'C07')
        assert cell['blocked'] and cell['block_reason'].startswith('shakedown')
        assert cells.publication_text(cell).startswith('run not publishable (shakedown')
    facts = report.facts_from_runs(*runs)
    assert facts['perf.e2.cells_reproduced'] == 0
    assert facts['perf.e2.plate.C07.reproduced'] is False
    assert 'unpublishable: shakedown' in facts['perf.e2.table.C07']


def test_blocked_reproduction_still_fails_the_guards(runs):
    # check_comparable runs host/seed/pin checks before the blocked
    # early-return: a blocked repro with the same seed is an operator error.
    path = runs[1] / 'summary.json'
    path.write_text(json.dumps({
        **json.loads(path.read_text()),
        'publishable': False,
        'publication_block_reason': 'cpu_accounting_unavailable',
        'seed': json.loads((runs[0] / 'summary.json').read_text())['seed'],
    }))
    with pytest.raises(ValueError, match='same seed'):
        report.facts_from_runs(*runs)


def test_typing_session_without_identity_refuses(runs):
    typing_pair(runs)
    for root in runs:  # strip the fixture's default tree from typing rows
        for path in sorted((root / 'cells').rglob('TYPING.json')):
            row = json.loads(path.read_text())
            row.pop('host_provenance', None)
            path.write_text(json.dumps(row))
    text = report.typing_table({}, list(runs), 'plate', 'throughput')
    assert 'pin_not_recorded' in text and 'chars/s' not in text


def test_typing_run_with_shakedown_trial_never_publishes(runs):
    typing_pair(runs)
    path = runs[1] / 'cells/0000-plate/attempts/TYPING.json'
    path.write_text(json.dumps({**json.loads(path.read_text()), 'shakedown': True}))
    text = report.typing_table({}, list(runs), 'plate', 'throughput')
    assert 'shakedown' in text and 'chars/s' not in text


def test_rule_prose_states_the_per_trial_model(runs):
    rule = report.facts_from_runs(*runs)['perf.e2.rule']
    assert 'per trial' in rule
    assert 'pin not recorded' in rule
    assert 'shakedown' in rule
    assert 'Both runs must be publishable' not in rule
