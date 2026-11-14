"""Report E2's publication campaign is registered from a committed manifest.

`perf/container/e2_publication.json` names the 20 first-pass run ids and the
20 re-run run ids of the publish1 campaign, plus the 32 first-pass jobs that
issues #173, #174 and #175 superseded. `build/e2_publication_roots.py` turns
a local mirror of the sealed jobs into the roots tree `report_e2_runs.json`
points at — the step the interim `.scratch/e2-interim/farm.py` did by hand.

Run: python -m pytest build/test_e2_publication_roots.py
"""

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "build"))
sys.path.insert(0, str(ROOT))

import e2_publication_roots as e2r  # noqa: E402
import facts as facts_mod  # noqa: E402

MANIFEST_PATH = ROOT / "perf" / "container" / "e2_publication.json"
RUN_ID = re.compile(r"^\d{8}T\d{12}Z-\d{5,6}-\d{6}$")

RID_A = "20261112T180000000000Z-10000-000001"
RID_B = "20261112T180000000000Z-10000-000002"
RID_RERUN = "20261113T010000000000Z-20000-000003"


def job(run_dir, rid, index, *, lane="benchmark_document", sealed=True):
    """A mirrored job directory; a sealed one carries JOB-DONE."""
    path = Path(run_dir) / lane / f"{rid}-{index:03d}"
    path.mkdir(parents=True)
    if sealed:
        (path / "JOB-DONE").write_text("")
    return path


def synthetic_manifest():
    return {
        "campaign": "publish1",
        "harness": {"first_pass": "4488f9b6", "rerun": "78249e7c"},
        "first_pass": {"space-a": RID_A, "space-b": RID_B},
        "rerun": {"space-a": [{"run_id": RID_RERUN, "jobs": [10]}]},
        "superseded": {
            "issues": {"999": {"title": "synthetic", "lane": "benchmark_document", "jobs": [10]}}
        },
    }


def write_manifest(tmp_path, manifest):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    return path


def build_data(tmp_path):
    """Two first-pass runs and one re-run run, mirrored under <space>/runs/<run id>."""
    data = tmp_path / "data"
    kept = job(data / "space-a" / "runs" / RID_A, RID_A, 4)
    job(data / "space-a" / "runs" / RID_A, RID_A, 10)  # superseded by the manifest
    job(data / "space-a" / "runs" / RID_A, RID_A, 11, sealed=False)  # unsealed
    (data / "space-a" / "runs" / RID_A / "RUN.log").write_text("x")
    (data / "space-a" / "runs" / RID_A / "benchmark_document" / "not-a-job").mkdir()
    rerun_job = job(data / "space-a" / "runs" / RID_RERUN, RID_RERUN, 10, lane="benchmark_input")
    space_b_job = job(data / "space-b" / "runs" / RID_B, RID_B, 50, lane="benchmark_typing")
    # A Space and a run outside the manifest are ignored.
    stray = "20261112T190000000000Z-10000-000099"
    job(data / "space-z" / "runs" / stray, stray, 1)
    job(data / "space-a" / "runs" / stray, stray, 1)
    return data, kept, rerun_job, space_b_job


def run_roots(data, roots_dir, manifest, *extra):
    return e2r.main([str(data), str(roots_dir), "--manifest", str(manifest), *extra])


def test_sealed_jobs_are_linked_and_the_counts_are_written(tmp_path):
    data, kept, rerun_job, space_b_job = build_data(tmp_path)
    manifest = write_manifest(tmp_path, synthetic_manifest())
    roots_dir = tmp_path / "roots"
    assert run_roots(data, roots_dir, manifest) == 0

    payload = json.loads((roots_dir / "report_e2_runs.json").read_text())
    assert payload["roots"] == [
        str((roots_dir / f"space-a--{RID_A}").resolve()),
        str((roots_dir / f"space-a--{RID_RERUN}").resolve()),
        str((roots_dir / f"space-b--{RID_B}").resolve()),
    ]
    root = roots_dir / f"space-a--{RID_A}" / "benchmark_document"
    assert (root / f"{RID_A}-004").resolve() == kept
    assert not (root / f"{RID_A}-010").exists()  # superseded
    assert not (root / f"{RID_A}-011").exists()  # unsealed
    assert (roots_dir / f"space-a--{RID_RERUN}" / "benchmark_input" / f"{RID_RERUN}-010").resolve() == rerun_job
    assert (roots_dir / f"space-b--{RID_B}" / "benchmark_typing" / f"{RID_B}-050").resolve() == space_b_job

    campaign = payload["campaign"]
    assert campaign["first_pass_kept"] == 2
    assert campaign["first_pass_superseded"] == 1
    assert campaign["first_pass_unsealed"] == 1
    assert campaign["rerun_kept"] == 1
    assert campaign["rerun_unsealed"] == 0
    assert campaign["missing_runs"] == []


def test_a_rerun_job_the_manifest_does_not_name_is_an_error(tmp_path):
    data, *_ = build_data(tmp_path)
    job(data / "space-a" / "runs" / RID_RERUN, RID_RERUN, 99, lane="benchmark_input")
    manifest = write_manifest(tmp_path, synthetic_manifest())
    assert run_roots(data, tmp_path / "roots", manifest) != 0
    assert run_roots(data, tmp_path / "roots2", manifest, "--partial") != 0


def test_a_rerun_job_not_yet_sealed_or_mirrored_counts_unsealed(tmp_path):
    data, *_ = build_data(tmp_path)
    manifest_data = synthetic_manifest()
    manifest_data["rerun"]["space-a"][0]["jobs"] = [10, 11]
    unsealed = job(data / "space-a" / "runs" / RID_RERUN, RID_RERUN, 11, lane="benchmark_input", sealed=False)
    manifest = write_manifest(tmp_path, manifest_data)
    roots_dir = tmp_path / "roots"
    assert run_roots(data, roots_dir, manifest) == 0
    campaign = json.loads((roots_dir / "report_e2_runs.json").read_text())["campaign"]
    assert campaign["rerun_kept"] == 1
    assert campaign["rerun_unsealed"] == 1

    import shutil
    shutil.rmtree(unsealed)
    manifest_data["rerun"]["space-a"][0]["jobs"] = [10, 12]  # declared, absent entirely
    manifest.write_text(json.dumps(manifest_data))
    roots_dir = tmp_path / "roots-2"  # a used roots dir is refused
    assert run_roots(data, roots_dir, manifest) == 0
    campaign = json.loads((roots_dir / "report_e2_runs.json").read_text())["campaign"]
    assert campaign["rerun_unsealed"] == 1


def test_a_missing_manifest_run_fails_unless_partial(tmp_path):
    data, *_ = build_data(tmp_path)
    manifest_data = synthetic_manifest()
    manifest_data["first_pass"]["space-c"] = "20261112T180000000000Z-10000-000003"
    manifest = write_manifest(tmp_path, manifest_data)
    assert run_roots(data, tmp_path / "roots", manifest) != 0

    roots_dir = tmp_path / "roots-partial"
    assert run_roots(data, roots_dir, manifest, "--partial") == 0
    campaign = json.loads((roots_dir / "report_e2_runs.json").read_text())["campaign"]
    assert campaign["missing_runs"] == ["space-c/20261112T180000000000Z-10000-000003"]


def test_the_committed_manifest_names_the_publish1_campaign():
    manifest = json.loads(MANIFEST_PATH.read_text())
    assert manifest["harness"]["first_pass"] == "4488f9b6"
    assert manifest["harness"]["rerun"] == "78249e7c"

    first_pass = manifest["first_pass"]
    assert len(first_pass) == 20
    assert all(RUN_ID.match(rid) for rid in first_pass.values())

    entries = [entry for space in manifest["rerun"].values() for entry in space]
    rids = [entry["run_id"] for entry in entries]
    assert len(rids) == 20
    assert len(set(rids)) == 20
    assert all(RUN_ID.match(rid) for rid in rids)
    assert set(rids).isdisjoint(first_pass.values())
    assert set(manifest["rerun"]) <= set(first_pass)

    job_sets = [set(entry["jobs"]) for entry in entries]
    union = set().union(*job_sets)
    assert sum(len(s) for s in job_sets) == len(union) == 32

    superseded = set()
    for issue in manifest["superseded"]["issues"].values():
        superseded.update(issue["jobs"])
    assert superseded == union
    assert set(manifest["superseded"]["issues"]) == {"173", "174", "175"}

    # The second round (#181): every superseded re-run job is measured again, once.
    assert manifest["harness"]["rerun2"] == "c0015f83"
    retired = e2r.rerun_superseded_jobs(manifest)
    assert retired == {20, 21, 100, 101} and retired <= union
    second = [entry for space in manifest["rerun2"].values() for entry in space]
    assert all(RUN_ID.match(entry["run_id"]) for entry in second)
    assert {entry["run_id"] for entry in second}.isdisjoint(set(rids) | set(first_pass.values()))
    assert sorted(job for entry in second for job in entry["jobs"]) == sorted(retired)
    assert set(manifest["rerun2"]) <= set(first_pass)

    # The third round (#183, #184): every second-round job is measured again, once.
    assert manifest["harness"]["rerun3"] == "3ffb21a5"
    retired2 = e2r.rerun_superseded_jobs(manifest, "rerun2_superseded")
    assert retired2 == {20, 21, 100, 101}
    third = [entry for space in manifest["rerun3"].values() for entry in space]
    third_rids = [entry["run_id"] for entry in third]
    assert all(RUN_ID.match(rid) for rid in third_rids) and len(set(third_rids)) == len(third_rids)
    second_rids = {entry["run_id"] for entry in second}
    assert set(third_rids).isdisjoint(set(rids) | set(first_pass.values()) | second_rids)
    assert sorted(job for entry in third for job in entry["jobs"]) == sorted(retired2)
    assert set(manifest["rerun3"]) <= set(first_pass)


def test_campaign_counts_become_perf_e2_facts(tmp_path):
    payload = {
        "campaign": {
            "first_pass_kept": 2,
            "first_pass_superseded": 1,
            "first_pass_unsealed": 1,
            "rerun_kept": 1,
            "rerun_unsealed": 1,
            "missing_runs": ["space-c/20261112T180000000000Z-10000-000003"],
        }
    }
    runs_file = tmp_path / "report_e2_runs.json"
    runs_file.write_text(json.dumps(payload))
    out = {}
    facts_mod.perf_e2_facts(runs_file, out)
    assert out["perf.e2.campaign.first_pass_kept"] == 2
    assert out["perf.e2.campaign.first_pass_superseded"] == 1
    assert out["perf.e2.campaign.rerun_kept"] == 1
    assert out["perf.e2.campaign.missing_runs"] == ["space-c/20261112T180000000000Z-10000-000003"]
    import perf_e2_tables
    assert out["perf.e2.reruns"] == perf_e2_tables.reruns_text(payload["campaign"])


# A second re-run round (#181) ---------------------------------------------------------------------

RID_RERUN2 = "20261113T170000000000Z-30000-000004"


def second_round_manifest():
    manifest = synthetic_manifest()
    manifest["rerun"]["space-a"][0]["jobs"] = [10, 12]
    manifest["rerun_superseded"] = {
        "issues": {"998": {"title": "synthetic round 2", "lane": "benchmark_document", "jobs": [12]}}
    }
    manifest["rerun2"] = {"space-b": [{"run_id": RID_RERUN2, "jobs": [12]}]}
    return manifest


def test_a_second_round_replaces_the_rerun_jobs_it_supersedes(tmp_path):
    data, kept, rerun_job, _ = build_data(tmp_path)
    old = job(data / "space-a" / "runs" / RID_RERUN, RID_RERUN, 12)
    new = job(data / "space-b" / "runs" / RID_RERUN2, RID_RERUN2, 12)
    manifest = write_manifest(tmp_path, second_round_manifest())
    roots_dir = tmp_path / "roots"
    assert run_roots(data, roots_dir, manifest) == 0

    payload = json.loads((roots_dir / "report_e2_runs.json").read_text())
    assert str((roots_dir / f"space-b--{RID_RERUN2}").resolve()) in payload["roots"]
    assert (roots_dir / f"space-b--{RID_RERUN2}" / "benchmark_document" / f"{RID_RERUN2}-012").resolve() == new
    assert not (roots_dir / f"space-a--{RID_RERUN}" / "benchmark_document" / old.name).exists()
    assert (roots_dir / f"space-a--{RID_RERUN}" / "benchmark_input" / f"{RID_RERUN}-010").resolve() == rerun_job
    campaign = payload["campaign"]
    assert campaign["rerun_kept"] == 1
    assert campaign["rerun_superseded"] == 1
    assert campaign["rerun2_kept"] == 1
    assert campaign["rerun2_unsealed"] == 0


def test_a_second_round_job_not_yet_sealed_counts_unsealed(tmp_path):
    data, *_ = build_data(tmp_path)
    job(data / "space-a" / "runs" / RID_RERUN, RID_RERUN, 12)
    job(data / "space-b" / "runs" / RID_RERUN2, RID_RERUN2, 12, sealed=False)
    manifest = write_manifest(tmp_path, second_round_manifest())
    roots_dir = tmp_path / "roots"
    assert run_roots(data, roots_dir, manifest) == 0
    campaign = json.loads((roots_dir / "report_e2_runs.json").read_text())["campaign"]
    assert campaign["rerun2_kept"] == 0 and campaign["rerun2_unsealed"] == 1


def test_a_second_round_job_that_supersedes_nothing_is_an_error(tmp_path):
    data, *_ = build_data(tmp_path)
    manifest_data = second_round_manifest()
    manifest_data["rerun2"]["space-b"][0]["jobs"] = [12, 13]
    job(data / "space-b" / "runs" / RID_RERUN2, RID_RERUN2, 12)
    manifest = write_manifest(tmp_path, manifest_data)
    assert run_roots(data, tmp_path / "roots", manifest) != 0


def test_a_missing_second_round_run_fails_unless_partial(tmp_path):
    data, *_ = build_data(tmp_path)
    manifest = write_manifest(tmp_path, second_round_manifest())
    assert run_roots(data, tmp_path / "roots", manifest) != 0
    roots_dir = tmp_path / "roots-partial"
    assert run_roots(data, roots_dir, manifest, "--partial") == 0
    campaign = json.loads((roots_dir / "report_e2_runs.json").read_text())["campaign"]
    assert campaign["missing_runs"] == [f"space-b/{RID_RERUN2}"]
    assert campaign["rerun2_unsealed"] == 1


# A third round (#183, #184) -----------------------------------------------------------------------

RID_RERUN3 = "20261113T190000000000Z-40000-000005"


def third_round_manifest():
    manifest = second_round_manifest()
    manifest["rerun2_superseded"] = {
        "issues": {"997": {"title": "synthetic round 3", "lane": "benchmark_document", "jobs": [12]}}
    }
    manifest["rerun3"] = {"space-a": [{"run_id": RID_RERUN3, "jobs": [12]}]}
    return manifest


def test_a_third_round_replaces_the_second_round_jobs_it_supersedes(tmp_path):
    data, *_ = build_data(tmp_path)
    job(data / "space-a" / "runs" / RID_RERUN, RID_RERUN, 12)
    second = job(data / "space-b" / "runs" / RID_RERUN2, RID_RERUN2, 12)
    third = job(data / "space-a" / "runs" / RID_RERUN3, RID_RERUN3, 12)
    manifest = write_manifest(tmp_path, third_round_manifest())
    roots_dir = tmp_path / "roots"
    assert run_roots(data, roots_dir, manifest) == 0

    payload = json.loads((roots_dir / "report_e2_runs.json").read_text())
    assert (roots_dir / f"space-a--{RID_RERUN3}" / "benchmark_document" / third.name).resolve() == third
    assert not (roots_dir / f"space-b--{RID_RERUN2}" / "benchmark_document" / second.name).exists()
    assert str((roots_dir / f"space-b--{RID_RERUN2}").resolve()) not in payload["roots"]
    campaign = payload["campaign"]
    assert campaign["rerun_superseded"] == 1
    assert campaign["rerun2_kept"] == 0 and campaign["rerun2_superseded"] == 1
    assert campaign["rerun3_kept"] == 1 and campaign["rerun3_unsealed"] == 0


def test_a_third_round_job_that_supersedes_nothing_is_an_error(tmp_path):
    data, *_ = build_data(tmp_path)
    manifest_data = third_round_manifest()
    manifest_data["rerun3"]["space-a"][0]["jobs"] = [12, 14]
    job(data / "space-b" / "runs" / RID_RERUN2, RID_RERUN2, 12)
    job(data / "space-a" / "runs" / RID_RERUN3, RID_RERUN3, 12)
    manifest = write_manifest(tmp_path, manifest_data)
    assert run_roots(data, tmp_path / "roots", manifest) != 0


def test_a_missing_third_round_run_fails_unless_partial(tmp_path):
    data, *_ = build_data(tmp_path)
    job(data / "space-b" / "runs" / RID_RERUN2, RID_RERUN2, 12)
    manifest = write_manifest(tmp_path, third_round_manifest())
    assert run_roots(data, tmp_path / "roots", manifest) != 0
    roots_dir = tmp_path / "roots-partial"
    assert run_roots(data, roots_dir, manifest, "--partial") == 0
    campaign = json.loads((roots_dir / "report_e2_runs.json").read_text())["campaign"]
    assert campaign["missing_runs"] == [f"space-a/{RID_RERUN3}"]
    assert campaign["rerun3_unsealed"] == 1


def test_a_superseded_second_round_job_nobody_measured_again_is_an_error(tmp_path):
    # Review of d509c234, M1: a retired job with no third-round job would drop its cell silently.
    data, *_ = build_data(tmp_path)
    manifest_data = third_round_manifest()
    manifest_data["rerun2_superseded"]["issues"]["997"]["jobs"] = [12, 13]
    job(data / "space-b" / "runs" / RID_RERUN2, RID_RERUN2, 12)
    job(data / "space-a" / "runs" / RID_RERUN3, RID_RERUN3, 12)
    manifest = write_manifest(tmp_path, manifest_data)
    assert run_roots(data, tmp_path / "roots", manifest) != 0


def test_a_run_listed_twice_in_a_round_is_an_error(tmp_path):
    data, *_ = build_data(tmp_path)
    manifest_data = third_round_manifest()
    manifest_data["rerun3"]["space-a"].append({"run_id": RID_RERUN3, "jobs": [12]})
    job(data / "space-b" / "runs" / RID_RERUN2, RID_RERUN2, 12)
    job(data / "space-a" / "runs" / RID_RERUN3, RID_RERUN3, 12)
    manifest = write_manifest(tmp_path, manifest_data)
    assert run_roots(data, tmp_path / "roots", manifest) != 0


def test_a_used_roots_dir_is_refused(tmp_path):
    # Review of d509c234, M2: links left by an earlier manifest would feed the tables superseded jobs.
    data, *_ = build_data(tmp_path)
    job(data / "space-b" / "runs" / RID_RERUN2, RID_RERUN2, 12)
    job(data / "space-a" / "runs" / RID_RERUN, RID_RERUN, 12)
    roots_dir = tmp_path / "roots"
    assert run_roots(data, roots_dir, write_manifest(tmp_path, second_round_manifest())) == 0
    job(data / "space-a" / "runs" / RID_RERUN3, RID_RERUN3, 12)
    assert run_roots(data, roots_dir, write_manifest(tmp_path, third_round_manifest())) != 0
    # An empty directory is fine.
    empty = tmp_path / "empty-roots"
    empty.mkdir()
    assert run_roots(data, empty, write_manifest(tmp_path, third_round_manifest())) == 0


# An editor-scoped round (#185) ------------------------------------------------------------------
# canvas-editor's C11 and C14 timed its empty page. Its cells of the document
# jobs are measured again by canvas-only runs that keep the job indices; the
# old jobs stay linked for every other editor.

RID_CANVAS = "20261114T010000000000Z-50000-000009"


def editor_round_manifest():
    manifest = third_round_manifest()
    manifest["editor_superseded"] = {
        "issues": {"185": {"title": "synthetic editor round", "lane": "benchmark_document", "editor": "canvas",
                           "jobs": [4, 12]}}
    }
    manifest["editor_rerun"] = {"space-b": [{"run_id": RID_CANVAS, "jobs": [4, 12], "editors": ["canvas"]}]}
    return manifest


def summarize(path, seed, block, editors):
    """A job's summary.json: its seed, its block and the editors its schedule names."""
    (path / "summary.json").write_text(json.dumps({
        "run_id": path.name, "seed": seed, "block": {"index": block, "of": 2, "repetitions": 5},
        "order": [[rep, editor] for rep in range(5) for editor in editors]}))
    return path


def editor_round_data(tmp_path, *, canvas_seeds=(1, 1), canvas_editors=("canvas",)):
    data, kept, *_ = build_data(tmp_path)
    summarize(kept, 1, 1, ["plate", "canvas"])
    job(data / "space-b" / "runs" / RID_RERUN2, RID_RERUN2, 12)
    third = summarize(job(data / "space-a" / "runs" / RID_RERUN3, RID_RERUN3, 12), 1, 2, ["plate", "canvas"])
    canvas = [summarize(job(data / "space-b" / "runs" / RID_CANVAS, RID_CANVAS, index), seed, block,
                        list(canvas_editors))
              for index, seed, block in ((4, canvas_seeds[0], 1), (12, canvas_seeds[1], 2))]
    return data, kept, third, canvas


def test_an_editor_round_links_its_jobs_and_keeps_the_old_jobs_for_other_editors(tmp_path):
    data, kept, third, canvas = editor_round_data(tmp_path)
    roots_dir = tmp_path / "roots"
    assert run_roots(data, roots_dir, write_manifest(tmp_path, editor_round_manifest())) == 0
    payload = json.loads((roots_dir / "report_e2_runs.json").read_text())
    # The old jobs stay: only canvas-editor's cells of them are superseded.
    assert (roots_dir / f"space-a--{RID_A}" / "benchmark_document" / kept.name).resolve() == kept
    assert (roots_dir / f"space-a--{RID_RERUN3}" / "benchmark_document" / third.name).resolve() == third
    for path in canvas:
        assert (roots_dir / f"space-b--{RID_CANVAS}" / "benchmark_document" / path.name).resolve() == path
    assert str((roots_dir / f"space-b--{RID_CANVAS}").resolve()) in payload["roots"]
    assert payload["superseded_cells"] == [
        {"issue": "185", "editor": "canvas", "jobs": [4, 12], "kept_runs": [RID_CANVAS]}
    ]
    campaign = payload["campaign"]
    assert campaign["editor_rerun_kept"] == 2 and campaign["editor_rerun_unsealed"] == 0
    assert campaign["editor_superseded"] == {"canvas": 2}


def test_an_editor_round_entry_must_name_its_editors(tmp_path):
    data, *_ = editor_round_data(tmp_path)
    manifest = editor_round_manifest()
    del manifest["editor_rerun"]["space-b"][0]["editors"]
    assert run_roots(data, tmp_path / "roots", write_manifest(tmp_path, manifest)) != 0


def test_an_editor_round_job_that_supersedes_nothing_is_an_error(tmp_path):
    data, *_ = editor_round_data(tmp_path)
    job(data / "space-b" / "runs" / RID_CANVAS, RID_CANVAS, 14)
    manifest = editor_round_manifest()
    manifest["editor_rerun"]["space-b"][0]["jobs"] = [4, 12, 14]
    assert run_roots(data, tmp_path / "roots", write_manifest(tmp_path, manifest)) != 0


def test_a_superseded_editor_job_nobody_measured_again_is_an_error(tmp_path):
    data, *_ = editor_round_data(tmp_path)
    manifest = editor_round_manifest()
    manifest["editor_superseded"]["issues"]["185"]["jobs"] = [4, 12, 13]
    assert run_roots(data, tmp_path / "roots", write_manifest(tmp_path, manifest)) != 0


def test_a_missing_editor_round_run_fails_unless_partial(tmp_path):
    data, *_ = build_data(tmp_path)
    job(data / "space-b" / "runs" / RID_RERUN2, RID_RERUN2, 12)
    job(data / "space-a" / "runs" / RID_RERUN3, RID_RERUN3, 12)
    manifest = write_manifest(tmp_path, editor_round_manifest())
    assert run_roots(data, tmp_path / "roots", manifest) != 0
    roots_dir = tmp_path / "roots-partial"
    assert run_roots(data, roots_dir, manifest, "--partial") == 0
    payload = json.loads((roots_dir / "report_e2_runs.json").read_text())
    assert payload["campaign"]["missing_runs"] == [f"space-b/{RID_CANVAS}"]
    assert payload["campaign"]["editor_rerun_unsealed"] == 2


def test_superseded_cells_reach_the_tables(tmp_path, monkeypatch):
    import perf_e2_tables
    seen = {}

    def fake_facts_from_roots(roots, superseded_cells=None):
        seen["superseded_cells"] = superseded_cells
        return {}

    monkeypatch.setattr(perf_e2_tables, "facts_from_roots", fake_facts_from_roots)
    entries = [{"issue": "185", "editor": "canvas", "jobs": [4], "kept_runs": [RID_CANVAS]}]
    runs_file = tmp_path / "report_e2_runs.json"
    runs_file.write_text(json.dumps({"roots": [str(tmp_path)], "superseded_cells": entries}))
    facts_mod.perf_e2_facts(runs_file, {})
    assert seen["superseded_cells"] == entries


def test_a_half_editor_round_is_refused(tmp_path):
    # glm-5.3 review of 31805ef7, finding 4: an editor round that leaves one of
    # the editor's jobs of the lane unsuperseded would publish a cell mixing the
    # new and the retired measurement.
    import shutil
    data, _kept, _third, canvas = editor_round_data(tmp_path)
    shutil.rmtree(canvas[1])  # the round measured job 4 only
    manifest = editor_round_manifest()
    manifest["editor_superseded"]["issues"]["185"]["jobs"] = [4]
    manifest["editor_rerun"]["space-b"][0]["jobs"] = [4]
    assert run_roots(data, tmp_path / "roots", write_manifest(tmp_path, manifest)) != 0


def test_an_editor_round_job_with_another_seed_is_refused(tmp_path):
    # Finding 5: the re-run keeps the job index; its seed and block must match too.
    data, *_ = editor_round_data(tmp_path, canvas_seeds=(3, 1))
    assert run_roots(data, tmp_path / "roots", write_manifest(tmp_path, editor_round_manifest())) != 0


def test_an_editor_round_job_that_measured_other_editors_is_refused(tmp_path):
    # Finding 6: a run launched without --only-editors re-measured every editor.
    data, *_ = editor_round_data(tmp_path, canvas_editors=("canvas", "plate"))
    assert run_roots(data, tmp_path / "roots", write_manifest(tmp_path, editor_round_manifest())) != 0


def test_an_editor_round_outside_the_document_lane_is_refused(tmp_path):
    # Finding 7: the facts and the report read editor-scoped supersedes for document jobs only.
    data, *_ = editor_round_data(tmp_path)
    manifest = editor_round_manifest()
    manifest["editor_superseded"]["issues"]["185"]["lane"] = "benchmark_typing"
    assert run_roots(data, tmp_path / "roots", write_manifest(tmp_path, manifest)) != 0


# An extension round (#188): new jobs appended after the campaign's own, for a
# rung the campaign did not measure. They supersede nothing and are linked whole.
RID_EXT = "20261114T030000000000Z-60000-000011"


def extension_manifest():
    manifest = editor_round_manifest()
    manifest["harness"]["extension"] = "deadbeef"
    manifest["extension"] = {"space-a": [{"run_id": RID_EXT, "jobs": [160, 161]}]}
    return manifest


def extension_data(tmp_path):
    data, kept, third, canvas = editor_round_data(tmp_path)
    new = [summarize(job(data / "space-a" / "runs" / RID_EXT, RID_EXT, index), 1, block,
                     ["plate", "canvas"])
           for index, block in ((160, 1), (161, 2))]
    return data, new


def test_an_extension_round_links_its_new_jobs(tmp_path):
    data, new = extension_data(tmp_path)
    roots_dir = tmp_path / "roots"
    assert run_roots(data, roots_dir, write_manifest(tmp_path, extension_manifest())) == 0
    payload = json.loads((roots_dir / "report_e2_runs.json").read_text())
    for path in new:
        assert (roots_dir / f"space-a--{RID_EXT}" / "benchmark_document" / path.name).resolve() == path
    campaign = payload["campaign"]
    assert campaign["extension_kept"] == 2 and campaign["extension_unsealed"] == 0


def test_an_extension_job_that_reuses_a_campaign_index_is_refused(tmp_path):
    data, _ = extension_data(tmp_path)
    job(data / "space-a" / "runs" / RID_EXT, RID_EXT, 4)
    manifest = extension_manifest()
    manifest["extension"]["space-a"][0]["jobs"] = [4, 160, 161]
    assert run_roots(data, tmp_path / "roots", write_manifest(tmp_path, manifest)) != 0


def test_an_extension_job_listed_twice_is_refused(tmp_path):
    data, _ = extension_data(tmp_path)
    manifest = extension_manifest()
    manifest["extension"]["space-b"] = [{"run_id": "20261114T040000000000Z-60000-000012", "jobs": [161]}]
    assert run_roots(data, tmp_path / "roots", write_manifest(tmp_path, manifest), "--partial") != 0


def test_an_extension_round_needs_its_harness_commit(tmp_path):
    data, _ = extension_data(tmp_path)
    manifest = extension_manifest()
    del manifest["harness"]["extension"]
    assert run_roots(data, tmp_path / "roots", write_manifest(tmp_path, manifest)) != 0


# A workload-scoped editor round (#190) -------------------------------------------------------------
# The document lane waited 300 s, not 600 s, for prose-250kw loads: only the
# editor's jobs of that workload are measured again.

def _fixtures(path, *workloads):
    summary = json.loads((path / "summary.json").read_text())
    summary["fixtures"] = [f"/app/out/{path.name}/fixtures/{w}-0123456789abcdef.docx" for w in workloads]
    (path / "summary.json").write_text(json.dumps(summary))


def workload_round(tmp_path, *, old_12):
    import shutil
    data, kept, third, canvas = editor_round_data(tmp_path)
    shutil.rmtree(canvas[1])  # the round measured job 4 only
    _fixtures(kept, "prose-250kw", "micro-search", "micro-search")
    _fixtures(third, *old_12)
    manifest = editor_round_manifest()
    manifest["editor_superseded"]["issues"]["185"].update(jobs=[4], workload="prose-250kw")
    manifest["editor_rerun"]["space-b"][0]["jobs"] = [4]
    return data, manifest


def test_a_workload_round_supersedes_only_that_workloads_jobs(tmp_path):
    data, manifest = workload_round(tmp_path, old_12=("prose-5kw", "micro-search"))
    assert run_roots(data, tmp_path / "roots", write_manifest(tmp_path, manifest)) == 0


def test_a_workload_round_that_leaves_a_job_of_its_workload_is_refused(tmp_path):
    data, manifest = workload_round(tmp_path, old_12=("prose-250kw", "micro-search"))
    assert run_roots(data, tmp_path / "roots", write_manifest(tmp_path, manifest)) != 0


def test_a_workload_round_counts_a_c14_job_as_another_workload(tmp_path):
    # A C14 job loads every rung; its prose-250kw rung is not the document lane's C11/C12 workload.
    rungs = ("prose-500w", "prose-5kw", "prose-50kw", "prose-250kw", "complex-corpus")
    data, manifest = workload_round(tmp_path, old_12=rungs)
    assert run_roots(data, tmp_path / "roots", write_manifest(tmp_path, manifest)) == 0


def test_a_workload_round_with_an_unreadable_old_job_is_refused(tmp_path):
    data, manifest = workload_round(tmp_path, old_12=())
    assert run_roots(data, tmp_path / "roots", write_manifest(tmp_path, manifest)) != 0
