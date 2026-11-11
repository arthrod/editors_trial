"""Report E2 reader: withheld figures in facts, seed pooling, host wording (#154)."""

import json
from pathlib import Path

import pytest

from build import perf_e2_tables as report
from perf.analysis import e2_cells as cells

DISTINCTIVE_MEDIAN = 54321.987


def _summary(run_id, seed, **extra):
    base = dict(
        run_id=run_id,
        seed=seed,
        execution_profile='dedicated_publish',
        host_class='shared_guarded',
        publishable=True,
        order=[[i, 'plate'] for i in range(30)],
        host=dict(
            cpu_model='fixture CPU',
            cpu_cores_logical=16,
            os='Linux',
            os_version='fixture',
            power_source='ac',
            container=True,
            cpu_quota=8,
        ),
        rendering=dict(headless=True, browser_version='130', playwright_version='1.64', vendor='Google Inc.', renderer='SwiftShader'),
        versions=dict(tools=dict(playwright='1.64'), editors=dict(plate=dict(pin='p'))),
    )
    base.update(extra)
    return base


def _trial(samples):
    return dict(
        schema_version=1,
        editor_id='plate',
        criterion_id='C07',
        outcome='measured',
        publishable=True,
        refusal_code=None,
        layer='browser_visible',
        boundary='input_to_next_paint',
        environment=dict(host_class='shared_guarded', execution_profile='dedicated_publish', editor_id='plate'),
        samples_ms=samples,
        sub_frame_samples=[False],
        diagnostic=dict(frame_interval_ms=16.7),
        host_provenance=dict(host_build='production', publishable=True, tree_sha256='tree-a'),
    )


def _write_run(root: Path, *, run_id: str, seed: int, **summary_kw):
    root.mkdir(parents=True, exist_ok=True)
    (root / 'summary.json').write_text(json.dumps(_summary(run_id, seed, **summary_kw)))
    for i in range(30):
        cell = root / 'cells' / f'{i:04d}-plate' / 'attempts'
        cell.mkdir(parents=True)
        (cell / 'c07.json').write_text(json.dumps(_trial([DISTINCTIVE_MEDIAN])))


def test_blocked_run_stores_no_median_in_facts(tmp_path):
  repro = tmp_path / 'repro'
  _write_run(tmp_path / 'primary', run_id='a', seed=1)
  _write_run(repro, run_id='b', seed=2, shakedown=True, publishable=False,
             publication_block_reason='shakedown: few repetitions to find bugs; never a publication run')
  facts = report.facts_from_runs(tmp_path / 'primary', repro)
  blob = json.dumps(facts)
  assert str(DISTINCTIVE_MEDIAN) not in blob
  assert facts['perf.e2.plate.C07.reproduced'] is False
  primary = facts['perf.e2.plate.C07.primary']
  assert primary.get('stats') is None
  assert 'blocked' in facts['perf.e2.table.C07']


def test_under_n_stores_no_median_in_facts(tmp_path):
  primary, repro = tmp_path / 'primary', tmp_path / 'repro'
  _write_run(primary, run_id='a', seed=1)
  _write_run(repro, run_id='b', seed=2)
  for i in range(25):
      (primary / 'cells' / f'{i:04d}-plate' / 'attempts' / 'c07.json').unlink()
  facts = report.facts_from_runs(primary, repro)
  assert str(DISTINCTIVE_MEDIAN) not in json.dumps(facts)
  assert '5 of 30' in facts['perf.e2.table.C07']


def test_pooled_spaces_group_criterion_launches_by_seed(tmp_path):
  def job(space, job_id, seed, reps):
      root = tmp_path / space / 'runs' / 'camp' / 'benchmark_input' / job_id
      root.mkdir(parents=True)
      (root / 'summary.json').write_text(json.dumps(_summary(job_id, seed, order=[[i, 'plate'] for i in reps])))
      for i in reps:
          cell = root / 'cells' / f'{i:04d}-plate' / 'attempts'
          cell.mkdir(parents=True)
          (cell / 'c07.json').write_text(json.dumps(_trial([20.0])))
      return tmp_path / space / 'runs' / 'camp'

  roots = [
      job('space-a', 'j1', 1, range(0, 15)),
      job('space-b', 'j2', 1, range(15, 30)),
      job('space-c', 'j3', 2, range(30)),
  ]
  cell = cells.read_criterion_cell(roots, 'plate', 'C07')
  assert cell['published'] is True
  assert [group['stats']['n'] for group in cell['groups']] == [30, 30]


def test_host_note_names_spaces_not_same_machine(tmp_path):
  primary, repro = tmp_path / 'space-3' / 'runs' / 'c1', tmp_path / 'space-7' / 'runs' / 'c1'
  _write_run(primary, run_id='a', seed=1)
  _write_run(repro, run_id='b', seed=2)
  facts = report.facts_from_roots([primary.parent.parent, repro.parent.parent])
  note = facts['perf.e2.host_note']
  assert 'same machine' not in note.casefold()
  assert 'hardware class' in note
  assert 'virtual machine' in note.casefold()
  assert 'space-3' in note and 'space-7' in note


def test_facts_config_accepts_roots_list(fs):
  from build import facts as generator

  root = Path('/evidence/space-a/runs/campaign-a')
  job = root / 'benchmark_input' / 'j1'
  job.mkdir(parents=True)
  (job / 'summary.json').write_text(json.dumps(_summary('j1', 1)))
  config = Path('/report_e2_runs.json')
  config.write_text(json.dumps({'roots': [str(root.parent.parent.resolve())]}))
  result = {}
  generator.perf_e2_facts(config, result)
  assert 'space-a' in result.get('perf.e2.host_note', '') or 'space-a' in result.get('perf.e2.provenance', '')
