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


def test_the_committed_manifest_names_its_editor_and_late_rounds():
    manifest = json.loads(MANIFEST_PATH.read_text())
    issues = manifest["editor_superseded"]["issues"]
    entries = [entry for space in manifest["editor_rerun"].values() for entry in space]
    assert all(RUN_ID.match(entry["run_id"]) for entry in entries)
    assert len({entry["run_id"] for entry in entries}) == len(entries)
    # Each editor round is measured again exactly once per (editor, job), by runs naming only that editor.
    for number, issue in issues.items():
        editor = issue["editor"]
        measured = sorted(job for entry in entries if editor in entry["editors"] for job in entry["jobs"]
                          if job in issue["jobs"])
        assert measured == sorted(issue["jobs"]), number
    # #193: Docen's document jobs below the 500k rung, at the fixed surface clock (1e1393b9), C14 jobs untouched.
    docen = issues["193"]
    assert docen["editor"] == "docen" and docen["lane"] == "benchmark_document"
    assert docen["jobs"] == [*range(10, 20), *range(90, 100)]
    assert "prose-500kw" not in docen["workloads"]
    assert {entry["harness"] for entry in entries if entry["editors"] == ["docen"]
            and set(entry["jobs"]) <= set(docen["jobs"])} == {"1e1393b9"}
    # #192: the late round re-measures C10 on the complex document for every editor.
    late = [entry for space in manifest["late_rerun"].values() for entry in space]
    assert sorted(job for entry in late for job in entry["jobs"]) == [40, 41, 120, 121]
    assert manifest["harness"]["late_rerun"] == "653b9471"
    # #190: Plate.js's 250,000-word document jobs, at the 600 s load wait (6885707b).
    plate = issues["190"]
    assert (plate["editor"], plate["workload"], plate["jobs"]) == ("plate", "prose-250kw", [16, 17, 96, 97])
    assert {entry["harness"] for entry in entries if entry["editors"] == ["plate"]} == {"6885707b"}
    # #194: Docen's and canvas-editor's 250,000-word memory jobs, one run per job for both editors.
    for key, editor in (("194", "docen"), ("194-canvas", "canvas")):
        memory = issues[key]
        assert (memory["editor"], memory["lane"], memory["jobs"]) == (editor, "benchmark_memory", [66, 67, 146, 147])
        assert str(memory.get("issue", key)) == "194"
    assert {entry["harness"] for entry in entries if entry["editors"] == ["docen", "canvas"]} == {"6885707b"}
    # #196-#198: WordCraft's warm/cold, document (below and at 500k), input and C10 jobs, at 93498491.
    wordcraft = sorted(job for issue in issues.values() if issue["editor"] == "wordcraft" for job in issue["jobs"])
    assert wordcraft == sorted([*range(0, 20), *range(22, 42), *range(80, 100), *range(102, 122),
                                *range(160, 168)])
    rounds = [entry for entry in entries if entry["editors"] == ["wordcraft"]]
    assert {entry["harness"] for entry in rounds} == {"93498491", "6a037a84"}
    # Its 500k C14 jobs, at a later commit, only so that one harness measures all its 500k cells.
    c14 = issues["196-c14"]
    assert (c14["issue"], c14["extension"], c14["workload"], c14["jobs"]) == ("196", True, "prose-500kw",
                                                                             [162, 163, 166, 167])
    assert sorted(job for entry in rounds if entry["harness"] == "6a037a84" for job in entry["jobs"]) == c14["jobs"]
    # The two jobs stopped part-way when their work moved to e2-plate are measured whole there.
    stopped = sorted(job for entry in rounds for job in entry.get("stopped", []))
    assert stopped == [27, 102]
    plate_runs = {entry["run_id"] for entry in manifest["editor_rerun"]["e2-plate"]}
    for job in stopped:
        keepers = [entry["run_id"] for entry in rounds if job in entry["jobs"]]
        assert len(keepers) == 1 and keepers[0] in plate_runs, job
    # #202: the recorder's 1,200-frame cap froze every frame cursor. Canvas-editor's 250,000-word input jobs
    # and Docen's eight 500,000-word jobs are measured again at the fixed witness (52ff8990).
    cap = issues["202"]
    assert (cap["editor"], cap["lane"], cap["workload"], cap["jobs"]) == (
        "canvas", "benchmark_input", "prose-250kw", [28, 29, 108, 109])
    rung = issues["202-extension"]
    assert (rung["issue"], rung["editor"], rung["lane"], rung["extension"], rung["jobs"]) == (
        "202", "docen", "benchmark_document", True, list(range(160, 168)))
    cap_runs = [entry for entry in entries if entry.get("harness") == "52ff8990"]
    assert sorted(job for entry in cap_runs for job in entry["jobs"]) == [28, 29, 108, 109, *range(160, 168)]
    assert all(len(entry["editors"]) == 1 for entry in cap_runs)
    # #203: C14's damage window accepted frames minutes late; GenOffice's four 500,000-word C14 jobs are
    # measured again at the strict window (936e526b), one run per job pair.
    window = issues["203"]
    assert (window["editor"], window["lane"], window["extension"], window["workload"], window["jobs"]) == (
        "genoffice", "benchmark_document", True, "prose-500kw", [162, 163, 166, 167])
    window_runs = [entry for entry in entries if entry.get("harness") == "936e526b"]
    assert sorted(job for entry in window_runs for job in entry["jobs"]) == [162, 163, 166, 167]
    assert all(entry["editors"] == ["genoffice"] for entry in window_runs)
    # #188: the 500k rung's eight new jobs, each once; its harness names both commits.
    extension = sorted(job for space in manifest["extension"].values() for entry in space for job in entry["jobs"])
    assert extension == list(range(160, 168))
    assert "d697b98e" in manifest["harness"]["extension"] and "6885707b" in manifest["harness"]["extension"]


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


# A criteria-scoped editor round (#203) ----------------------------------------------------------------
# The fixed harness changed only C14's damage witness: GenOffice's C14 jobs at
# 500,000 words were measured again; its C11/C12/C15 jobs of that workload,
# which never run C14, keep their cells.

def _attempts(path, editor, *criteria):
    attempts = path / "cells" / f"0000-{editor}" / "attempts"
    attempts.mkdir(parents=True, exist_ok=True)
    for cid in criteria:
        (attempts / f"{cid.lower()}-{editor}-0123456789.json").write_text(
            json.dumps({"criterion_id": cid, "editor_id": editor, "outcome": "measured"}))


def criteria_round(tmp_path, *, old_12_criteria, round_criteria=("C14",), round_measured=("C14",)):
    data, manifest = workload_round(tmp_path, old_12=("prose-250kw", "micro-search"))
    third = next(data.glob(f"space-a/runs/{RID_RERUN3}/benchmark_document/*-012"))
    _attempts(third, "canvas", *old_12_criteria)
    round_job = next(data.glob(f"space-b/runs/{RID_CANVAS}/benchmark_document/*-004"))
    _attempts(round_job, "canvas", *round_measured)
    manifest["editor_superseded"]["issues"]["185"]["criteria"] = list(round_criteria)
    return data, manifest


def test_a_criteria_round_leaves_jobs_that_never_measured_its_criteria(tmp_path):
    data, manifest = criteria_round(tmp_path, old_12_criteria=("C11", "C12", "C15"))
    assert run_roots(data, tmp_path / "roots", write_manifest(tmp_path, manifest)) == 0


def test_a_criteria_round_that_leaves_a_job_measuring_its_criteria_is_refused(tmp_path):
    data, manifest = criteria_round(tmp_path, old_12_criteria=("C11", "C14"))
    assert run_roots(data, tmp_path / "roots", write_manifest(tmp_path, manifest)) != 0


def test_a_criteria_round_with_an_old_job_recording_no_criteria_is_refused(tmp_path):
    data, manifest = criteria_round(tmp_path, old_12_criteria=())
    assert run_roots(data, tmp_path / "roots", write_manifest(tmp_path, manifest)) != 0


def test_a_round_without_criteria_on_the_same_workload_still_needs_every_job(tmp_path):
    """Another issue on the same editor and workload, not criteria-scoped, keeps the full rule."""
    data, manifest = criteria_round(tmp_path, old_12_criteria=("C11",))
    issues = manifest["editor_superseded"]["issues"]
    issues["186"] = dict(issues["185"], title="synthetic unscoped round")
    del issues["186"]["criteria"]
    assert run_roots(data, tmp_path / "roots", write_manifest(tmp_path, manifest)) != 0


# Review of the criteria-scoped round (GLM, octo) ------------------------------------------------------

def _cell_summary(path, editor, *criteria, cell="0000"):
    cell_dir = path / "cells" / f"{cell}-{editor}"
    cell_dir.mkdir(parents=True, exist_ok=True)
    (cell_dir / "summary.json").write_text(json.dumps({"criteria": list(criteria)}))


def _old_12(data):
    return next(data.glob(f"space-a/runs/{RID_RERUN3}/benchmark_document/*-012"))


def test_a_scheduled_criterion_whose_attempt_is_missing_still_counts(tmp_path):
    """F1: C14 scheduled in the cell summary, its attempt never written: the job ran C14."""
    data, manifest = criteria_round(tmp_path, old_12_criteria=("C11",))
    _cell_summary(_old_12(data), "canvas", "C11", "C14")
    assert run_roots(data, tmp_path / "roots", write_manifest(tmp_path, manifest)) != 0


def test_the_cell_summary_alone_is_evidence(tmp_path):
    data, manifest = criteria_round(tmp_path, old_12_criteria=())
    _cell_summary(_old_12(data), "canvas", "C11", "C12", "C15")
    assert run_roots(data, tmp_path / "roots", write_manifest(tmp_path, manifest)) == 0


def test_criterion_names_are_compared_without_case(tmp_path):
    """F2: an attempt recording c14 ran C14."""
    data, manifest = criteria_round(tmp_path, old_12_criteria=("C11", "c14"))
    assert run_roots(data, tmp_path / "roots", write_manifest(tmp_path, manifest)) != 0


def test_criteria_must_be_a_list_of_criterion_ids(tmp_path):
    """F3: "C14" as a string would read as {C, 1, 4}."""
    for bad in ("C14", ["C14", ""], [14], ["X99"]):
        data, manifest = criteria_round(tmp_path / str(len(str(bad))) / str(abs(hash(str(bad)))), old_12_criteria=("C11",))
        manifest["editor_superseded"]["issues"]["185"]["criteria"] = bad
        assert run_roots(data, tmp_path / "roots", write_manifest(tmp_path, manifest)) != 0, bad


def test_another_editor_whose_name_ends_the_same_is_not_read(tmp_path):
    """F4: cells/0000-flat-canvas is not canvas's cell."""
    data, manifest = criteria_round(tmp_path, old_12_criteria=())
    _attempts(_old_12(data), "flat-canvas", "C11")
    assert run_roots(data, tmp_path / "roots", write_manifest(tmp_path, manifest)) != 0


def test_the_rounds_own_jobs_must_have_measured_its_criteria(tmp_path):
    """F5: a C14 round whose job for the editor ran no C14 is refused."""
    data, manifest = criteria_round(tmp_path, old_12_criteria=("C11",), round_measured=("C11",))
    round_job = next(data.glob(f"space-b/runs/{RID_CANVAS}/benchmark_document/*-004"))
    assert run_roots(data, tmp_path / "roots", write_manifest(tmp_path, manifest)) != 0
    _attempts(round_job, "canvas", "C14")
    assert run_roots(data, tmp_path / "roots2", write_manifest(tmp_path, manifest)) == 0


def test_two_scoped_rounds_on_one_workload_need_the_union(tmp_path):
    """F6: rounds scoped to C14 and to C11: a job that ran C11 must be superseded."""
    data, manifest = criteria_round(tmp_path, old_12_criteria=("C11",))
    issues = manifest["editor_superseded"]["issues"]
    issues["186"] = dict(issues["185"], title="synthetic C11 round", criteria=["C11"])
    assert run_roots(data, tmp_path / "roots", write_manifest(tmp_path, manifest)) != 0


def test_a_job_kept_by_a_criteria_scope_is_reported(tmp_path, capsys):
    """F7: the carve-out is never silent."""
    data, manifest = criteria_round(tmp_path, old_12_criteria=("C11", "C12", "C15"))
    assert run_roots(data, tmp_path / "roots", write_manifest(tmp_path, manifest)) == 0
    out = capsys.readouterr()
    assert "kept by the criteria scope" in out.out + out.err


# A late round (#192) ---------------------------------------------------------------------------------
# C10 scrolled the protected complex package; GenOffice and eigenpal opened it
# read-only and C10 never started. Whole first-pass jobs, never re-run before,
# are measured again for every editor, at a later harness commit.

RID_LATE = "20261114T050000000000Z-70000-000013"


def late_manifest():
    manifest = synthetic_manifest()
    manifest["harness"]["late_rerun"] = "c0ffee00"
    manifest["late_superseded"] = {
        "issues": {"192": {"title": "synthetic late round", "lane": "benchmark_typing", "jobs": [50]}}
    }
    manifest["late_rerun"] = {"space-b": [{"run_id": RID_LATE, "jobs": [50]}]}
    return manifest


def late_data(tmp_path):
    data, kept, rerun_job, space_b_job = build_data(tmp_path)
    late_job = job(data / "space-b" / "runs" / RID_LATE, RID_LATE, 50, lane="benchmark_typing")
    return data, kept, space_b_job, late_job


def test_a_late_round_replaces_the_first_pass_jobs_it_supersedes(tmp_path):
    data, kept, old, new = late_data(tmp_path)
    roots_dir = tmp_path / "roots"
    assert run_roots(data, roots_dir, write_manifest(tmp_path, late_manifest())) == 0
    campaign = json.loads((roots_dir / "report_e2_runs.json").read_text())["campaign"]
    assert (roots_dir / f"space-b--{RID_LATE}" / "benchmark_typing" / new.name).resolve() == new
    assert not (roots_dir / f"space-b--{RID_B}" / "benchmark_typing" / old.name).exists()
    assert campaign["late_superseded"] == 1 and campaign["late_rerun_kept"] == 1
    assert campaign["late_rerun_unsealed"] == 0
    # The first round's counters do not absorb the late round.
    assert campaign["first_pass_superseded"] == 1


def test_a_late_round_job_nobody_superseded_is_an_error(tmp_path):
    data, *_ = late_data(tmp_path)
    job(data / "space-b" / "runs" / RID_LATE, RID_LATE, 51, lane="benchmark_typing")
    manifest = late_manifest()
    manifest["late_rerun"]["space-b"][0]["jobs"] = [50, 51]
    assert run_roots(data, tmp_path / "roots", write_manifest(tmp_path, manifest)) != 0


def test_a_late_superseded_job_nobody_measured_again_is_an_error(tmp_path):
    data, *_ = late_data(tmp_path)
    manifest = late_manifest()
    manifest["late_superseded"]["issues"]["192"]["jobs"] = [4, 50]
    assert run_roots(data, tmp_path / "roots", write_manifest(tmp_path, manifest)) != 0


RID_LATE2 = "20261114T050000000000Z-70000-000014"


def test_a_late_round_cannot_retire_a_job_the_first_round_already_replaced(tmp_path, capsys):
    # Job 10 was re-run by the first round; retiring it again would drop the re-run's cell.
    data, *_ = late_data(tmp_path)
    job(data / "space-a" / "runs" / RID_LATE2, RID_LATE2, 10)
    manifest = late_manifest()
    manifest["late_superseded"]["issues"]["192"]["jobs"] = [10, 50]
    manifest["late_rerun"]["space-a"] = [{"run_id": RID_LATE2, "jobs": [10]}]
    assert run_roots(data, tmp_path / "roots", write_manifest(tmp_path, manifest)) != 0
    assert "already measured again by an earlier round" in capsys.readouterr().err


def test_a_late_round_needs_its_harness_commit(tmp_path):
    data, *_ = late_data(tmp_path)
    manifest = late_manifest()
    del manifest["harness"]["late_rerun"]
    assert run_roots(data, tmp_path / "roots", write_manifest(tmp_path, manifest)) != 0


def test_a_late_round_run_listed_elsewhere_is_an_error(tmp_path):
    data, *_ = late_data(tmp_path)
    manifest = late_manifest()
    manifest["rerun"]["space-b"] = [{"run_id": RID_LATE, "jobs": [50]}]
    assert run_roots(data, tmp_path / "roots", write_manifest(tmp_path, manifest)) != 0


def test_a_round_may_name_several_workloads(tmp_path):
    # #193: Docen's C11 is re-measured on every document workload, never on the C14 rung jobs.
    data, manifest = workload_round(tmp_path, old_12=("prose-5kw", "micro-search"))
    issue = manifest["editor_superseded"]["issues"]["185"]
    del issue["workload"]
    issue["workloads"] = ["prose-250kw", "prose-50kw"]
    assert run_roots(data, tmp_path / "roots", write_manifest(tmp_path, manifest)) == 0
    issue["workloads"] = ["prose-250kw", "prose-5kw"]  # old job 12 (prose-5kw) is left: refused
    assert run_roots(data, tmp_path / "roots2", write_manifest(tmp_path, manifest)) != 0


# A memory-lane editor round (#194) -------------------------------------------------------------------
# The memory pair's deadline was too short at prose-250kw: Docen's and
# canvas-editor's cells of those memory jobs are measured again. Memory job
# summaries list no fixtures; the attempts record the workload.

RID_MEM = "20261114T060000000000Z-80000-000015"


def _attempt(path, editor, workload):
    attempts = path / "cells" / f"0000-{editor}" / "attempts"
    attempts.mkdir(parents=True, exist_ok=True)
    (attempts / f"c17-{editor}-0.json").write_text(json.dumps(
        {"editor_id": editor, "criterion_id": "C17", "environment": {"workload_id": workload}}))


def memory_round(tmp_path, *, other_workload):
    data, kept, third, canvas = editor_round_data(tmp_path)
    old66 = summarize(job(data / "space-a" / "runs" / RID_A, RID_A, 66, lane="benchmark_memory"), 1, 1,
                      ["canvas", "docen"])
    _attempt(old66, "canvas", "prose-250kw")
    old64 = summarize(job(data / "space-a" / "runs" / RID_A, RID_A, 64, lane="benchmark_memory"), 1, 1,
                      ["canvas", "docen"])
    _attempt(old64, "canvas", other_workload)
    new66 = summarize(job(data / "space-b" / "runs" / RID_MEM, RID_MEM, 66, lane="benchmark_memory"), 1, 1,
                      ["canvas"])
    manifest = editor_round_manifest()
    manifest["editor_superseded"]["issues"]["194"] = {
        "title": "synthetic memory round", "lane": "benchmark_memory", "editor": "canvas", "jobs": [66],
        "workload": "prose-250kw"}
    manifest["editor_rerun"]["space-b"].append({"run_id": RID_MEM, "jobs": [66], "editors": ["canvas"]})
    return data, manifest, new66


def test_a_memory_round_supersedes_that_workloads_memory_jobs(tmp_path):
    data, manifest, new66 = memory_round(tmp_path, other_workload="prose-50kw")
    roots_dir = tmp_path / "roots"
    assert run_roots(data, roots_dir, write_manifest(tmp_path, manifest)) == 0
    assert (roots_dir / f"space-b--{RID_MEM}" / "benchmark_memory" / new66.name).resolve() == new66


def test_a_memory_round_that_leaves_a_job_of_its_workload_is_refused(tmp_path):
    data, manifest, _ = memory_round(tmp_path, other_workload="prose-250kw")
    assert run_roots(data, tmp_path / "roots", write_manifest(tmp_path, manifest)) != 0


def test_a_document_rounds_workloads_do_not_reach_the_memory_lane(tmp_path):
    # canvas's document round (#185) covers every document job; its memory jobs are another lane.
    data, manifest, _ = memory_round(tmp_path, other_workload="prose-50kw")
    assert "workload" not in manifest["editor_superseded"]["issues"]["185"]
    assert run_roots(data, tmp_path / "roots", write_manifest(tmp_path, manifest)) == 0


def test_one_issue_may_name_several_editors_rounds(tmp_path):
    data, manifest, _ = memory_round(tmp_path, other_workload="prose-50kw")
    issues = manifest["editor_superseded"]["issues"]
    issues["194-canvas"] = {**issues.pop("194"), "issue": "194"}
    roots_dir = tmp_path / "roots"
    assert run_roots(data, roots_dir, write_manifest(tmp_path, manifest)) == 0
    rounds = json.loads((roots_dir / "report_e2_runs.json").read_text())["campaign"]["editor_rounds"]
    assert {(r["issue"], r["editor"]) for r in rounds} == {("185", "canvas"), ("194", "canvas")}


def test_a_late_round_must_retire_a_first_pass_job(tmp_path):
    # octo review of the late round: an index no first-pass run carries would link a job nobody replaced.
    data, *_ = late_data(tmp_path)
    job(data / "space-b" / "runs" / RID_LATE, RID_LATE, 77, lane="benchmark_typing")
    manifest = late_manifest()
    manifest["late_superseded"]["issues"]["192"]["jobs"] = [50, 77]
    manifest["late_rerun"]["space-b"][0]["jobs"] = [50, 77]
    assert run_roots(data, tmp_path / "roots", write_manifest(tmp_path, manifest)) != 0


# An editor round over extension jobs (#193 at 500k) ----------------------------------------------------
# The 500k rung (#188) ran before Docen's C11 clock fix: Docen's cells of its
# prose-500kw document jobs are measured again. Only a round flagged
# "extension" reaches extension jobs; canvas's #185 round never does.

RID_EXT_ROUND = "20261114T070000000000Z-90000-000016"


def extension_round(tmp_path, *, supersede=(160, 161)):
    data, new = extension_data(tmp_path)
    for path in new:
        _fixtures(path, "prose-500kw", "micro-search")
    redo = [summarize(job(data / "space-b" / "runs" / RID_EXT_ROUND, RID_EXT_ROUND, index), 1, block, ["plate"])
            for index, block in ((160, 1), (161, 2)) if index in supersede]
    manifest = extension_manifest()
    manifest["editor_superseded"]["issues"]["193-500k"] = {
        "issue": "193", "title": "synthetic", "lane": "benchmark_document", "editor": "plate",
        "jobs": list(supersede), "workload": "prose-500kw", "extension": True}
    manifest["editor_rerun"]["space-b"].append({"run_id": RID_EXT_ROUND, "jobs": list(supersede),
                                                "editors": ["plate"]})
    return data, manifest, redo


def test_an_editor_round_may_replace_extension_jobs(tmp_path):
    data, manifest, redo = extension_round(tmp_path)
    roots_dir = tmp_path / "roots"
    assert run_roots(data, roots_dir, write_manifest(tmp_path, manifest)) == 0
    for path in redo:
        assert (roots_dir / f"space-b--{RID_EXT_ROUND}" / "benchmark_document" / path.name).resolve() == path
    cells = json.loads((roots_dir / "report_e2_runs.json").read_text())["superseded_cells"]
    assert any(c["editor"] == "plate" and c["jobs"] == [160, 161] and RID_EXT_ROUND in c["kept_runs"]
               for c in cells)


def test_an_extension_round_that_leaves_a_job_of_its_workload_is_refused(tmp_path):
    data, manifest, _ = extension_round(tmp_path, supersede=(160,))
    assert run_roots(data, tmp_path / "roots", write_manifest(tmp_path, manifest)) != 0


def test_an_extension_flagged_round_must_name_extension_jobs(tmp_path):
    data, manifest, _ = extension_round(tmp_path)
    manifest["editor_superseded"]["issues"]["193-500k"]["jobs"] = [4, 160, 161]
    assert run_roots(data, tmp_path / "roots", write_manifest(tmp_path, manifest), "--partial") != 0



# octo review of the rounds (2026-11-14) ----------------------------------------------------------------

def test_a_late_job_in_another_lane_than_its_first_pass_job_is_refused(tmp_path, capsys):
    data, *_ = late_data(tmp_path)
    import shutil
    shutil.rmtree(data / "space-b" / "runs" / RID_LATE)
    job(data / "space-b" / "runs" / RID_LATE, RID_LATE, 50, lane="adversarial_c10_scroll")
    assert run_roots(data, tmp_path / "roots", write_manifest(tmp_path, late_manifest())) != 0
    assert "lane" in capsys.readouterr().err


def test_an_editor_round_job_in_another_lane_than_its_issue_is_refused(tmp_path, capsys):
    data, manifest, new66 = memory_round(tmp_path, other_workload="prose-50kw")
    manifest["editor_superseded"]["issues"]["194"]["lane"] = "benchmark_document"
    manifest["editor_superseded"]["issues"]["194"].pop("workload")
    assert run_roots(data, tmp_path / "roots", write_manifest(tmp_path, manifest)) != 0
    assert "lane" in capsys.readouterr().err


def test_a_memory_workload_is_read_from_the_editors_own_attempts(tmp_path):
    # canvas's attempt in old job 64 says prose-250kw; Docen's says prose-50kw: job 64 is canvas's prose-250kw.
    data, manifest, _ = memory_round(tmp_path, other_workload="prose-250kw")
    old64 = next((data / "space-a" / "runs" / RID_A / "benchmark_memory").glob("*-064"))
    _attempt(old64, "docen", "prose-50kw")
    assert run_roots(data, tmp_path / "roots", write_manifest(tmp_path, manifest)) != 0


def test_a_memory_job_whose_editor_attempts_name_no_workload_is_refused(tmp_path, capsys):
    data, manifest, _ = memory_round(tmp_path, other_workload="prose-50kw")
    old64 = next((data / "space-a" / "runs" / RID_A / "benchmark_memory").glob("*-064"))
    for path in old64.glob("cells/*canvas/attempts/*.json"):
        path.write_text(json.dumps({"editor_id": "canvas", "environment": {}}))
    assert run_roots(data, tmp_path / "roots", write_manifest(tmp_path, manifest)) != 0
    assert "workload" in capsys.readouterr().err


def test_mixed_workloads_in_one_memory_job_are_refused(tmp_path):
    data, manifest, _ = memory_round(tmp_path, other_workload="prose-50kw")
    old64 = next((data / "space-a" / "runs" / RID_A / "benchmark_memory").glob("*-064"))
    (old64 / "cells" / "0000-canvas" / "attempts" / "c19-canvas-1.json").write_text(json.dumps(
        {"editor_id": "canvas", "environment": {"workload_id": "prose-250kw"}}))
    assert run_roots(data, tmp_path / "roots", write_manifest(tmp_path, manifest)) != 0


@pytest.mark.parametrize("bad", ["prose-250kw", [], [""], [3]])
def test_workloads_must_be_a_list_of_names(tmp_path, bad):
    data, manifest, _ = memory_round(tmp_path, other_workload="prose-50kw")
    issue = manifest["editor_superseded"]["issues"]["194"]
    issue.pop("workload")
    issue["workloads"] = bad
    assert run_roots(data, tmp_path / "roots", write_manifest(tmp_path, manifest)) != 0


def test_an_editor_round_issue_must_be_an_issue_number(tmp_path, capsys):
    data, manifest, _ = memory_round(tmp_path, other_workload="prose-50kw")
    issues = manifest["editor_superseded"]["issues"]
    issues["194-canvas"] = issues.pop("194")  # no "issue": "194"
    assert run_roots(data, tmp_path / "roots", write_manifest(tmp_path, manifest)) != 0
    assert "issue number" in capsys.readouterr().err


# The WordCraft round (#196-#198) ---------------------------------------------------------------------
# Its content gate, its C08/C09 and its C10 scroll were refused by our harness, not by WordCraft: an
# editor round re-measures WordCraft alone in the warm/cold, input and C10 lanes too, including the C10
# jobs the late round (#192) already measured again.

RID_WC = "20261114T090000000000Z-90000-000017"


def wordcraft_round(tmp_path, lane, *, also_unsuperseded=False):
    data, *_ = editor_round_data(tmp_path)
    old = summarize(job(data / "space-a" / "runs" / RID_A, RID_A, 30, lane=lane), 1, 1, ["plate", "wordcraft"])
    if also_unsuperseded:
        summarize(job(data / "space-a" / "runs" / RID_A, RID_A, 31, lane=lane), 1, 2, ["plate", "wordcraft"])
    new = summarize(job(data / "space-b" / "runs" / RID_WC, RID_WC, 30, lane=lane), 1, 1, ["wordcraft"])
    manifest = editor_round_manifest()
    manifest["editor_superseded"]["issues"]["197"] = {
        "title": "synthetic WordCraft round", "lane": lane, "editor": "wordcraft", "jobs": [30]}
    manifest["editor_rerun"]["space-b"].append({"run_id": RID_WC, "jobs": [30], "editors": ["wordcraft"]})
    return data, manifest, old, new


@pytest.mark.parametrize("lane", ["benchmark_warm_cold", "benchmark_input", "adversarial_c10_scroll"])
def test_an_editor_round_in_the_wordcraft_lanes_is_accepted(tmp_path, lane):
    data, manifest, old, new = wordcraft_round(tmp_path, lane)
    roots_dir = tmp_path / "roots"
    assert run_roots(data, roots_dir, write_manifest(tmp_path, manifest)) == 0
    assert (roots_dir / f"space-a--{RID_A}" / lane / old.name).resolve() == old
    assert (roots_dir / f"space-b--{RID_WC}" / lane / new.name).resolve() == new
    rounds = json.loads((roots_dir / "report_e2_runs.json").read_text())["campaign"]["editor_rounds"]
    assert {"issue": "197", "editor": "wordcraft", "lane": lane} in [
        {k: r[k] for k in ("issue", "editor", "lane")} for r in rounds]


@pytest.mark.parametrize("lane", ["benchmark_warm_cold", "benchmark_input", "adversarial_c10_scroll"])
def test_a_lane_round_that_leaves_a_job_of_its_lane_is_refused(tmp_path, lane, capsys):
    data, manifest, _, _ = wordcraft_round(tmp_path, lane, also_unsuperseded=True)
    assert run_roots(data, tmp_path / "roots", write_manifest(tmp_path, manifest)) != 0
    assert "is not superseded" in capsys.readouterr().err


def test_an_editor_round_replaces_wordcrafts_cells_of_a_late_round_job(tmp_path):
    lane = "adversarial_c10_scroll"
    data, *_ = editor_round_data(tmp_path)
    first = summarize(job(data / "space-a" / "runs" / RID_A, RID_A, 40, lane=lane), 1, 1, ["plate", "wordcraft"])
    late = summarize(job(data / "space-b" / "runs" / RID_LATE, RID_LATE, 40, lane=lane), 1, 1,
                     ["plate", "wordcraft"])
    new = summarize(job(data / "space-b" / "runs" / RID_WC, RID_WC, 40, lane=lane), 1, 1, ["wordcraft"])
    manifest = editor_round_manifest()
    manifest["harness"]["late_rerun"] = "c0ffee00"
    manifest["late_superseded"] = {"issues": {"192": {"title": "late", "lane": lane, "jobs": [40]}}}
    manifest["late_rerun"] = {"space-b": [{"run_id": RID_LATE, "jobs": [40]}]}
    manifest["editor_superseded"]["issues"]["198"] = {
        "title": "synthetic WordCraft C10", "lane": lane, "editor": "wordcraft", "jobs": [40]}
    manifest["editor_rerun"]["space-b"].append({"run_id": RID_WC, "jobs": [40], "editors": ["wordcraft"]})
    roots_dir = tmp_path / "roots"
    assert run_roots(data, roots_dir, write_manifest(tmp_path, manifest)) == 0
    # The late job stays for every other editor; the first-pass job is retired by the late round.
    assert (roots_dir / f"space-b--{RID_LATE}" / lane / late.name).resolve() == late
    assert not (roots_dir / f"space-a--{RID_A}" / lane / first.name).exists()
    assert (roots_dir / f"space-b--{RID_WC}" / lane / new.name).resolve() == new


def test_an_editor_round_before_the_late_round_cannot_touch_its_jobs(tmp_path, capsys):
    # The late round re-measured every editor of job 40 after this editor round: the editor round's cells
    # would override a newer measurement.
    lane = "adversarial_c10_scroll"
    early = "20261114T040000000000Z-90000-000016"  # before RID_LATE
    data, *_ = editor_round_data(tmp_path)
    summarize(job(data / "space-a" / "runs" / RID_A, RID_A, 40, lane=lane), 1, 1, ["plate", "wordcraft"])
    summarize(job(data / "space-b" / "runs" / RID_LATE, RID_LATE, 40, lane=lane), 1, 1, ["plate", "wordcraft"])
    summarize(job(data / "space-b" / "runs" / early, early, 40, lane=lane), 1, 1, ["wordcraft"])
    manifest = editor_round_manifest()
    manifest["harness"]["late_rerun"] = "c0ffee00"
    manifest["late_superseded"] = {"issues": {"192": {"title": "late", "lane": lane, "jobs": [40]}}}
    manifest["late_rerun"] = {"space-b": [{"run_id": RID_LATE, "jobs": [40]}]}
    manifest["editor_superseded"]["issues"]["198"] = {
        "title": "synthetic WordCraft C10", "lane": lane, "editor": "wordcraft", "jobs": [40]}
    manifest["editor_rerun"]["space-b"].append({"run_id": early, "jobs": [40], "editors": ["wordcraft"]})
    assert run_roots(data, tmp_path / "roots", write_manifest(tmp_path, manifest)) != 0
    assert "already measured again by an earlier round" in capsys.readouterr().err


# A job stopped part-way when its work was moved to another Space (rebalancing, 14 Nov): the entry names it
# under "stopped"; it is counted, never linked, and another entry of the same round measures it whole.
RID_STOP = "20261114T005000000000Z-50000-000020"


def stopped_round(tmp_path, *, sealed=False):
    data, kept, third, canvas = editor_round_data(tmp_path)
    partial = job(data / "space-a" / "runs" / RID_STOP, RID_STOP, 12, sealed=sealed)
    manifest = editor_round_manifest()
    manifest["editor_rerun"]["space-a"] = [{"run_id": RID_STOP, "jobs": [], "stopped": [12], "editors": ["canvas"]}]
    return data, manifest, partial


def test_a_stopped_job_is_counted_and_never_linked(tmp_path):
    data, manifest, partial = stopped_round(tmp_path)
    roots_dir = tmp_path / "roots"
    assert run_roots(data, roots_dir, write_manifest(tmp_path, manifest)) == 0
    assert not (roots_dir / f"space-a--{RID_STOP}" / "benchmark_document" / partial.name).exists()
    campaign = json.loads((roots_dir / "report_e2_runs.json").read_text())["campaign"]
    assert campaign["editor_rerun_stopped"] == 1
    assert campaign["editor_rerun_kept"] == 2 and campaign["editor_rerun_unsealed"] == 0


def test_a_stopped_job_that_was_sealed_is_an_error(tmp_path, capsys):
    data, manifest, _ = stopped_round(tmp_path, sealed=True)
    assert run_roots(data, tmp_path / "roots", write_manifest(tmp_path, manifest)) != 0
    err = capsys.readouterr().err
    assert "stopped job" in err and "is sealed" in err


def test_a_stopped_job_nobody_measured_whole_is_an_error(tmp_path, capsys):
    data, manifest, _ = stopped_round(tmp_path)
    manifest["editor_rerun"]["space-a"][0]["stopped"] = [13]
    job(data / "space-a" / "runs" / RID_STOP, RID_STOP, 13, sealed=False)
    assert run_roots(data, tmp_path / "roots", write_manifest(tmp_path, manifest)) != 0
    assert "not measured whole by another entry" in capsys.readouterr().err


def test_a_job_both_kept_and_stopped_is_an_error(tmp_path, capsys):
    data, manifest, _ = stopped_round(tmp_path)
    manifest["editor_rerun"]["space-b"][0]["stopped"] = [12]
    assert run_roots(data, tmp_path / "roots", write_manifest(tmp_path, manifest)) != 0
    assert "both kept and stopped" in capsys.readouterr().err


# A lane round (#208) ---------------------------------------------------------------------------------
# #206 and #207 are harness bugs that touch every editor of a lane: every job of the lane is measured
# again, all editors interleaved. Earlier rounds had already replaced those jobs, whole or for one
# editor; for a lane-superseded index only the lane round's job is linked.
RID_LANE = "20261115T010000000000Z-70000-000021"
RID_LANE_EXT = "20261115T010000000000Z-70000-000022"
LANE_JOBS = ((RID_LANE, "space-a", 4, 1), (RID_LANE, "space-a", 12, 2),
             (RID_LANE_EXT, "space-b", 160, 1), (RID_LANE_EXT, "space-b", 161, 2))


def lane_manifest():
    manifest = extension_manifest()
    manifest["harness"]["lane_rerun"] = "3eaf8c9b"
    manifest["lane_superseded"] = {
        "issues": {"206": {"title": "synthetic lane round", "lane": "benchmark_document", "jobs": [4, 12, 160, 161]}}
    }
    manifest["lane_rerun"] = {"space-a": [{"run_id": RID_LANE, "jobs": [4, 12]}],
                              "space-b": [{"run_id": RID_LANE_EXT, "jobs": [160, 161], "extension": True}]}
    return manifest


def lane_data(tmp_path, *, seed=1, editors=("plate", "canvas"), lane="benchmark_document"):
    data, _ = extension_data(tmp_path)
    new = [summarize(job(data / space / "runs" / rid, rid, index, lane=lane), seed, block, list(editors))
           for rid, space, index, block in LANE_JOBS]
    return data, new


def linked(roots_dir):
    """{job index: [run id, ...]} of every linked job."""
    out = {}
    for path in sorted(roots_dir.glob("*/*/*")):
        run_id, _, tail = path.name.rpartition("-")
        if tail.isdigit():
            out.setdefault(int(tail), []).append(run_id)
    return out


def test_a_lane_round_replaces_every_earlier_job_of_its_indexes(tmp_path):
    data, new = lane_data(tmp_path)
    roots_dir = tmp_path / "roots"
    assert run_roots(data, roots_dir, write_manifest(tmp_path, lane_manifest())) == 0
    payload = json.loads((roots_dir / "report_e2_runs.json").read_text())
    jobs = linked(roots_dir)
    # First pass (4), third round (12), canvas-editor's round (4, 12) and the extension (160, 161) are gone.
    assert jobs[4] == [RID_LANE] and jobs[12] == [RID_LANE]
    assert jobs[160] == [RID_LANE_EXT] and jobs[161] == [RID_LANE_EXT]
    for path in new:
        rid = path.name.rpartition("-")[0]
        space = "space-a" if rid == RID_LANE else "space-b"
        assert (roots_dir / f"{space}--{rid}" / "benchmark_document" / path.name).resolve() == path
    # A job outside the lane round is untouched.
    assert jobs[50] == [RID_B]
    campaign = payload["campaign"]
    assert campaign["lane_rerun_kept"] == 4 and campaign["lane_rerun_unsealed"] == 0
    assert campaign["lane_superseded"] == 6
    # The earlier rounds' own counters do not absorb the lane round.
    assert campaign["editor_rerun_kept"] == 0 and campaign["extension_kept"] == 0
    assert campaign["lane_rounds"] == [{"issue": "206", "lane": "benchmark_document", "jobs": 4}]
    # The reader must not drop canvas-editor's cells of the lane round's jobs.
    assert payload["superseded_cells"] == [
        {"issue": "185", "editor": "canvas", "jobs": [4, 12], "kept_runs": sorted([RID_CANVAS, RID_LANE, RID_LANE_EXT])}
    ]
    for rid in (RID_LANE, RID_LANE_EXT):
        assert any(root.endswith(rid) for root in payload["roots"])
    assert not any(root.endswith(RID_CANVAS) or root.endswith(RID_EXT) for root in payload["roots"])


def test_without_a_lane_round_the_campaign_has_no_lane_counters(tmp_path):
    data, _ = extension_data(tmp_path)
    roots_dir = tmp_path / "roots"
    assert run_roots(data, roots_dir, write_manifest(tmp_path, extension_manifest())) == 0
    campaign = json.loads((roots_dir / "report_e2_runs.json").read_text())["campaign"]
    assert not [key for key in campaign if key.startswith("lane_")]


def lane_refused(tmp_path, capsys, change, expected, **data_kwargs):
    data, new = lane_data(tmp_path, **data_kwargs)
    manifest = lane_manifest()
    change(manifest, data, new)
    assert run_roots(data, tmp_path / "roots", write_manifest(tmp_path, manifest)) != 0
    assert expected in capsys.readouterr().err


def test_a_lane_superseded_job_nobody_measured_again_is_an_error(tmp_path, capsys):
    def change(manifest, data, new):
        manifest["lane_rerun"]["space-a"][0]["jobs"] = [4]
    lane_refused(tmp_path, capsys, change, "are not measured again exactly once")


def test_a_lane_round_job_nobody_superseded_is_an_error(tmp_path, capsys):
    def change(manifest, data, new):
        manifest["lane_superseded"]["issues"]["206"]["jobs"] = [4, 160, 161]
    lane_refused(tmp_path, capsys, change, "are not measured again exactly once")


def test_a_lane_round_needs_its_harness_commit(tmp_path, capsys):
    def change(manifest, data, new):
        del manifest["harness"]["lane_rerun"]
    lane_refused(tmp_path, capsys, change, "harness.lane_rerun")


def test_a_lane_round_job_in_another_lane_is_refused(tmp_path, capsys):
    lane_refused(tmp_path, capsys, lambda *_: None, "is in lane benchmark_input", lane="benchmark_input")


def test_a_lane_round_job_with_another_seed_is_refused(tmp_path, capsys):
    lane_refused(tmp_path, capsys, lambda *_: None, "has seed 2", seed=2)


def test_a_lane_round_job_that_drops_an_editor_is_refused(tmp_path, capsys):
    lane_refused(tmp_path, capsys, lambda *_: None, "does not schedule ['canvas']", editors=("plate",))


def test_a_lane_round_of_an_index_no_earlier_run_carries_is_refused(tmp_path, capsys):
    def change(manifest, data, new):
        manifest["lane_superseded"]["issues"]["206"]["jobs"].append(77)
        manifest["lane_rerun"]["space-a"][0]["jobs"].append(77)
        summarize(job(data / "space-a" / "runs" / RID_LANE, RID_LANE, 77), 1, 1, ["plate", "canvas"])
    lane_refused(tmp_path, capsys, change, "replaces no earlier job")


def test_extension_jobs_of_a_lane_round_sit_in_an_entry_flagged_extension(tmp_path, capsys):
    def change(manifest, data, new):
        del manifest["lane_rerun"]["space-b"][0]["extension"]
    lane_refused(tmp_path, capsys, change, "extension jobs [160, 161]")


def test_an_entry_flagged_extension_holds_extension_jobs_only(tmp_path, capsys):
    def change(manifest, data, new):
        manifest["lane_rerun"]["space-a"][0]["extension"] = True
    lane_refused(tmp_path, capsys, change, "campaign jobs [4, 12]")


def test_a_lane_round_job_the_manifest_does_not_name_is_an_error(tmp_path, capsys):
    def change(manifest, data, new):
        summarize(job(data / "space-a" / "runs" / RID_LANE, RID_LANE, 11), 1, 1, ["plate", "canvas"])
    lane_refused(tmp_path, capsys, change, "is not in the manifest's job list")


def test_a_lane_round_run_listed_elsewhere_is_an_error(tmp_path, capsys):
    def change(manifest, data, new):
        manifest["extension"]["space-a"][0]["run_id"] = RID_LANE
    lane_refused(tmp_path, capsys, change, "listed more than once")


def test_a_lane_round_job_not_yet_sealed_counts_unsealed(tmp_path):
    data, new = lane_data(tmp_path)
    (new[0] / "JOB-DONE").unlink()
    roots_dir = tmp_path / "roots"
    assert run_roots(data, roots_dir, write_manifest(tmp_path, lane_manifest())) == 0
    campaign = json.loads((roots_dir / "report_e2_runs.json").read_text())["campaign"]
    assert campaign["lane_rerun_kept"] == 3 and campaign["lane_rerun_unsealed"] == 1
    assert 4 not in linked(roots_dir)


def test_a_missing_lane_round_run_fails_unless_partial(tmp_path):
    data, _ = extension_data(tmp_path)
    manifest = write_manifest(tmp_path, lane_manifest())
    assert run_roots(data, tmp_path / "roots", manifest) != 0
    assert run_roots(data, tmp_path / "roots2", manifest, "--partial") == 0
    campaign = json.loads((tmp_path / "roots2" / "report_e2_runs.json").read_text())["campaign"]
    assert campaign["lane_rerun_unsealed"] == 4 and campaign["partial"] is True
