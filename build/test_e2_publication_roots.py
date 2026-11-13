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
