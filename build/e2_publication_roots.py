#!/usr/bin/env python3
"""Register Report E2's publication runs as a farm of symlinks to sealed jobs.

`perf/container/e2_publication.json` names the publish1 campaign: the 20
first-pass run ids (harness 4488f9b6), the 20 re-run run ids (harness
78249e7c) with the job indexes each re-ran, and the first-pass job indexes
superseded by issues #173, #174 and #175; then the second round: the re-run
job indexes issue #181 superseded (`rerun_superseded`) and the runs that
measured them again (`rerun2`); then the third round: the second-round job
indexes issues #183 and #184 superseded (`rerun2_superseded`) and the runs
that measured them again (`rerun3`); then an editor-scoped round: the
editor whose cells of some jobs an issue superseded (`editor_superseded`,
#185) and the runs that measured that editor's cells again under the same
job indices (`editor_rerun`); an extension round of new job indices
(`extension`, #188); and a late round: first-pass jobs an issue retired
after the first round, whole jobs for every editor (`late_superseded`,
#192), and the runs that measured them again (`late_rerun`). The editor
round's old jobs stay linked for every other
editor; `report_e2_runs.json` lists the superseded cells
(`superseded_cells`) and `build/facts.py` reads around them. This script walks a local mirror
of the campaign bucket — `<space>/runs/<run id>/<lane>/<job>` — and links
every sealed job (`JOB-DONE`) that counts into `<roots dir>/<space>--<run id>/`,
leaving the superseded first-pass jobs out, then writes
`<roots dir>/report_e2_runs.json` for `build/facts.py` `perf_e2_facts`.

usage: python3 build/e2_publication_roots.py <data dir> <roots dir>
           [--manifest perf/container/e2_publication.json] [--partial]

Exits non-zero when a manifest run is absent from the data dir, unless
`--partial` — then the campaign block of the runs file lists the missing
runs. A re-run job whose index the manifest does not name is always an
error: the re-run schedule is fixed.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "perf" / "container" / "e2_publication.json"


def superseded_jobs(manifest: dict) -> set[int]:
    """Every first-pass job index the superseding issues retire."""
    jobs: set[int] = set()
    for issue in manifest["superseded"]["issues"].values():
        jobs.update(issue["jobs"])
    return jobs


def rerun_superseded_jobs(manifest: dict, key: str = "rerun_superseded") -> set[int]:
    """Every job index of a re-run round a later issue retires (measured again in the next round).

    ``rerun_superseded`` retires re-run jobs (second round); ``rerun2_superseded``
    retires second-round jobs (third round).
    """
    jobs: set[int] = set()
    for issue in manifest.get(key, {}).get("issues", {}).values():
        jobs.update(issue["jobs"])
    return jobs


def late_superseded_jobs(manifest: dict) -> set[int]:
    """First-pass job indexes a late issue retired after the first round (#192), whole jobs for every editor."""
    jobs: set[int] = set()
    for issue in manifest.get("late_superseded", {}).get("issues", {}).values():
        jobs.update(issue["jobs"])
    return jobs


def _check_late_round(manifest: dict, errors: list[str]) -> None:
    """A late round re-measures first-pass jobs no earlier round touched, each exactly once.

    A job the first round already replaced lives in a re-run run, not in the
    first pass; retiring its index here would drop the re-run's cell too.
    """
    late = late_superseded_jobs(manifest)
    entries = [entry for space_entries in manifest.get("late_rerun", {}).values() for entry in space_entries]
    if not late and not entries:
        return
    if entries and not manifest.get("harness", {}).get("late_rerun"):
        errors.append("the manifest's late round names no harness commit (harness.late_rerun)")
    already = superseded_jobs(manifest)
    for key in ("rerun", "rerun2", "rerun3", "extension"):
        already.update(index for space_entries in manifest.get(key, {}).values()
                       for entry in space_entries for index in entry["jobs"])
    # An editor round may re-measure one editor's cells of a late-round job only after the late round
    # (#198 after #192); run ids start with their UTC launch time, so the order is in the ids.
    late_run = {index: entry["run_id"] for entry in entries for index in entry["jobs"]}
    for space_entries in manifest.get("editor_rerun", {}).values():
        for entry in space_entries:
            for index in entry["jobs"]:
                if index in late and not entry["run_id"] > late_run.get(index, ""):
                    already.add(index)
    overlap = sorted(late & already)
    if overlap:
        errors.append(f"late_superseded jobs {overlap} were already measured again by an earlier round")
    measured = [index for entry in entries for index in entry["jobs"]]
    if sorted(measured) != sorted(late):
        errors.append(f"late_superseded jobs {sorted(late)} are not measured again exactly once by "
                      f"late-round jobs {sorted(measured)}")


def editor_superseded(manifest: dict) -> dict[str, set[int]]:
    """Per editor, the job indexes whose cells of that editor an issue superseded (#185)."""
    out: dict[str, set[int]] = {}
    for issue in manifest.get("editor_superseded", {}).get("issues", {}).values():
        out.setdefault(issue["editor"], set()).update(issue["jobs"])
    return out


def superseded_cells(manifest: dict) -> list[dict]:
    """The editor-scoped supersedes `build/facts.py` reads around (#185)."""
    kept = sorted(entry["run_id"] for entries in manifest.get("editor_rerun", {}).values() for entry in entries)
    return [
        {"issue": number, "editor": issue["editor"], "jobs": sorted(issue["jobs"]), "kept_runs": kept}
        for number, issue in sorted(manifest.get("editor_superseded", {}).get("issues", {}).items())
    ]


def _check_editor_round(manifest: dict, errors: list[str]) -> None:
    """Every superseded (editor, job) is measured again exactly once, by an entry naming that editor."""
    wanted = editor_superseded(manifest)
    extension_jobs = {index for entries in manifest.get("extension", {}).values() for entry in entries
                      for index in entry["jobs"]}
    for number, issue in sorted(manifest.get("editor_superseded", {}).get("issues", {}).items()):
        stray = sorted(set(issue["jobs"]) - extension_jobs) if issue.get("extension") else []
        if stray:
            errors.append(f"editor_superseded issue {number} is flagged extension but jobs {stray} are not "
                          f"extension jobs")
    measured: dict[str, list[int]] = {}
    for space, entries in sorted(manifest.get("editor_rerun", {}).items()):
        for entry in entries:
            editors = entry.get("editors")
            if not editors:
                errors.append(f"editor-round run {space}/{entry['run_id']} names no editors")
                continue
            for editor in editors:
                stray = sorted(set(entry["jobs"]) - wanted.get(editor, set()))
                if stray:
                    errors.append(f"editor-round jobs {stray} of {space}/{entry['run_id']} supersede no {editor} cells")
                measured.setdefault(editor, []).extend(entry["jobs"])
    for editor, jobs in sorted(wanted.items()):
        if sorted(measured.get(editor, [])) != sorted(jobs):
            errors.append(f"editor_superseded {editor} jobs {sorted(jobs)} are not measured again exactly once by "
                          f"editor-round jobs {sorted(measured.get(editor, []))}")


# The document lane (#185, #190, #193, #196), the memory lane (#194), and WordCraft's warm/cold (#196),
# input (#197) and C10 scroll (#198) lanes.
EDITOR_ROUND_LANES = ("benchmark_document", "benchmark_memory", "benchmark_warm_cold", "benchmark_input",
                      "adversarial_c10_scroll")


def _summary_of(job: Path) -> dict | None:
    try:
        value = json.loads((job / "summary.json").read_text())
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _scheduled_editors(summary: dict) -> set[str]:
    return {pair[1] for pair in summary.get("order") or [] if isinstance(pair, (list, tuple)) and len(pair) == 2}


def _editor_round_scope(issues: dict) -> dict:
    """Per (editor, lane, extension?), the workloads its rounds were scoped to (#190, several for #193, the
    memory lane for #194, extension jobs for #193 at 500k); None when a round covers every job of that lane."""
    scope: dict = {}
    for issue in issues.values():
        # An issue flagged "extension" re-measures extension jobs (#193 at 500k); any other round never
        # reaches them, since they were measured after the fixes of the rounds before them.
        key = (issue["editor"], issue["lane"], bool(issue.get("extension")))
        workloads = issue.get("workloads") or ([issue["workload"]] if issue.get("workload") else None)
        if workloads is None or (key in scope and scope[key] is None):
            scope[key] = None
        else:
            scope.setdefault(key, set()).update(workloads)
    return scope


def _job_workload(summary: dict, job: Path | None = None, editor: str | None = None):
    """The workload a job loaded: a document job's fixture names, else its attempts' workload_id.

    C15's micro-search fixtures ride along in every document job; a C14 job
    loads several rungs and so names no single workload. A memory job's
    summary lists no fixtures; its attempts record the workload (#194), read from
    the editor's own attempts when an editor is named (octo review).
    """
    fixtures = summary.get("fixtures") or []
    if fixtures:
        names = {Path(str(f)).name.rsplit("-", 1)[0] for f in fixtures} - {"micro-search"}
    elif job is not None:
        names = set()
        pattern = f"cells/*-{editor}/attempts/*.json" if editor else "cells/*/attempts/*.json"
        for attempt in sorted(job.glob(pattern)):
            try:
                workload = json.loads(attempt.read_text()).get("environment", {}).get("workload_id")
            except (OSError, json.JSONDecodeError, AttributeError):
                continue
            if workload:
                names.add(workload)
    else:
        names = set()
    if not names:
        return None
    return next(iter(names)) if len(names) == 1 else "(several: %s)" % ", ".join(sorted(names))


def _check_editor_round_data(roots_dir: Path, manifest: dict, errors: list[str]) -> None:
    """Read the linked jobs themselves (glm-5.3 review of 31805ef7, findings 4-7).

    - an editor round is for the lanes of EDITOR_ROUND_LANES only;
    - every linked job of that lane whose schedule names the editor is superseded,
      so no cell pools the new runs with the retired measurement;
    - each editor-round job measures only the editors its entry names, with the
      seed and block of the one job it replaces.
    """
    issues = manifest.get("editor_superseded", {}).get("issues", {})
    if not issues:
        return
    for number, issue in sorted(issues.items()):
        if issue.get("lane") not in EDITOR_ROUND_LANES:
            errors.append(f"editor_superseded issue {number}: lane {issue.get('lane')!r} is not one of "
                          f"{list(EDITOR_ROUND_LANES)}")
        if not str(issue.get("issue", number)).isdigit():
            errors.append(f"editor_superseded issue {number}: {issue.get('issue', number)!r} is not an issue number; "
                          f"a key naming several rounds of one issue carries \"issue\"")
        if "workloads" in issue:
            names = issue["workloads"]
            if not (isinstance(names, list) and names and all(isinstance(n, str) and n for n in names)):
                errors.append(f"editor_superseded issue {number}: workloads {names!r} is not a list of workload names")
    wanted = editor_superseded(manifest)
    new_runs = {entry["run_id"]: set(entry.get("editors") or ())
                for entries in manifest.get("editor_rerun", {}).values() for entry in entries}
    # Extension jobs (#188) were measured after the earlier rounds' fixes: only a round flagged
    # "extension" supersedes them (#193 at 500k).
    later = {entry["run_id"] for entries in manifest.get("extension", {}).values() for entry in entries}
    old: dict[int, list[tuple[str, Path, bool]]] = {}
    new: list[tuple[str, int, Path, str]] = []
    issue_lane = {(issue["editor"], index): issue.get("lane") for issue in issues.values() for index in issue["jobs"]}
    for root in sorted(p for p in roots_dir.iterdir() if p.is_dir()):
        for lane in EDITOR_ROUND_LANES:
            for job in sorted((root / lane).glob("*")) if (root / lane).is_dir() else ():
                run_id, _, tail = job.name.rpartition("-")
                if not tail.isdigit():
                    continue
                if run_id in new_runs:
                    new.append((run_id, int(tail), job, lane))
                else:
                    old.setdefault(int(tail), []).append((lane, job, run_id in later))
    scope = _editor_round_scope(issues)
    for (editor, round_lane, extension), workloads in sorted(scope.items(), key=lambda item: item[0]):
        jobs = wanted.get(editor, set())
        for index, entries in sorted(old.items()):
            if index in jobs:
                continue
            for lane, path, is_extension in entries:
                if lane != round_lane or is_extension != extension:
                    continue
                summary = _summary_of(path)
                if summary is None or editor not in _scheduled_editors(summary):
                    continue
                if workloads is not None:
                    workload = _job_workload(summary, path, editor)
                    if workload is None:
                        errors.append(f"job {path.name} measured {editor} and records no workload: the "
                                      f"workload-scoped round cannot tell whether it measured {sorted(workloads)}")
                    elif workload.startswith("(several") and lane != "benchmark_document":
                        errors.append(f"job {path.name} measured {editor} on {workload}: a {lane} job "
                                      f"loads one workload")
                    elif workload in workloads:
                        errors.append(f"job {path.name} measured {editor} on {workload} and is not superseded: "
                                      f"the round must supersede all of {editor}'s {workload} jobs")
                    continue
                errors.append(f"job {path.name} measured {editor} and is not superseded: an editor round "
                              f"must supersede all of {editor}'s {round_lane} jobs")
    for run_id, index, path, lane in new:
        for editor in sorted(new_runs[run_id]):
            wanted_lane = issue_lane.get((editor, index))
            if wanted_lane is not None and wanted_lane != lane:
                errors.append(f"editor-round job {path.name} is in lane {lane}; its issue supersedes {editor}'s "
                              f"job {index} in lane {wanted_lane}")
        summary = _summary_of(path)
        if summary is None:
            errors.append(f"editor-round job {path.name} has no readable summary.json")
            continue
        extra = sorted(_scheduled_editors(summary) - new_runs[run_id])
        if extra:
            errors.append(f"editor-round job {path.name} measured {extra} beyond its entry's editors "
                          f"{sorted(new_runs[run_id])}")
        replaced = old.get(index, [])
        if len(replaced) != 1:
            errors.append(f"editor-round job {path.name} replaces {len(replaced)} linked jobs with index {index}, "
                          f"not exactly one")
            continue
        before = _summary_of(replaced[0][1])
        if before is None:
            errors.append(f"job {replaced[0][1].name} has no readable summary.json to compare seeds with")
            continue
        for key in ("seed", "block"):
            if summary.get(key) != before.get(key):
                errors.append(f"editor-round job {path.name} has {key} {summary.get(key)!r}; the job it replaces, "
                              f"{replaced[0][1].name}, has {before.get(key)!r}")


def _check_extension(data: Path, manifest: dict, errors: list[str]) -> None:
    """An extension round (#188) adds jobs the campaign never had: each index is new and measured once.

    Its jobs supersede nothing, so an index that a first-pass run also carries
    would put two measurements in one job's place; a harness commit must name
    the code that measured them.
    """
    entries = [entry for space_entries in manifest.get("extension", {}).values() for entry in space_entries]
    if not entries:
        return
    if not manifest.get("harness", {}).get("extension"):
        errors.append("the manifest's extension round names no harness commit (harness.extension)")
    listed = [index for entry in entries for index in entry["jobs"]]
    twice = sorted({index for index in listed if listed.count(index) > 1})
    if twice:
        errors.append(f"extension jobs listed more than once: {twice}")
    campaign: set[int] = set()
    for space, run_id in manifest["first_pass"].items():
        run_dir = data / space / "runs" / run_id
        if run_dir.is_dir():
            campaign.update(index for _, _, index in run_jobs(run_dir, run_id))
    for key in ("rerun", "rerun2", "rerun3", "late_rerun"):
        campaign.update(index for space_entries in manifest.get(key, {}).values()
                        for entry in space_entries for index in entry["jobs"])
    # An editor round may re-measure an editor's cells of extension jobs (#193 at 500k); any other
    # editor-round index is a campaign index.
    extension_rounds = {index for issue in manifest.get("editor_superseded", {}).get("issues", {}).values()
                        if issue.get("extension") for index in issue["jobs"]}
    campaign.update(index for space_entries in manifest.get("editor_rerun", {}).values()
                    for entry in space_entries for index in entry["jobs"] if index not in extension_rounds)
    reused = sorted(set(listed) & campaign)
    if reused:
        errors.append(f"extension jobs {reused} reuse campaign job indexes; an extension adds new jobs only")


ROUND_KEYS = ("rerun", "rerun2", "rerun3", "editor_rerun", "extension", "late_rerun")


def _check_stopped(manifest: dict, errors: list[str]) -> None:
    """A stopped job is never also kept by its entry, and another entry of its round measured it whole."""
    for key in ROUND_KEYS:
        entries = [(space, entry) for space, space_entries in sorted(manifest.get(key, {}).items())
                   for entry in space_entries]
        for space, entry in entries:
            for index in sorted(entry.get("stopped", [])):
                if index in entry["jobs"]:
                    errors.append(f"{key} job {index} of {space}/{entry['run_id']} is both kept and stopped")
                    continue
                whole = [other for _, other in entries if other is not entry and index in other["jobs"]
                         and set(other.get("editors", [])) >= set(entry.get("editors", []))]
                if not whole:
                    errors.append(f"{key} job {index} stopped in {space}/{entry['run_id']} is not measured whole "
                                  f"by another entry of the round")


def _link_round(data: Path, roots_dir: Path, space: str, entries: list, prefix: str, retired: set[int],
                campaign: dict, roots: list[str], errors: list[str]) -> None:
    """Link one re-run round's sealed jobs of a Space; jobs in ``retired`` are counted, never linked."""
    for entry in entries:
        run_id = entry["run_id"]
        run_dir = data / space / "runs" / run_id
        if not run_dir.is_dir():
            campaign["missing_runs"].append(f"{space}/{run_id}")
            campaign[f"{prefix}_unsealed"] += len(entry["jobs"])
            continue
        declared = set(entry["jobs"])
        # A job stopped part-way when its work moved to another Space (14 Nov rebalancing): counted, never
        # linked; _check_stopped proves another entry of the round measured it whole.
        stopped = set(entry.get("stopped", []))
        seen: set[int] = set()
        root = roots_dir / f"{space}--{run_id}"
        for lane, job, index in run_jobs(run_dir, run_id):
            if index in stopped and index not in declared:
                if (job / "JOB-DONE").exists():
                    errors.append(f"stopped job {job.name} of {space}/{run_id} is sealed: a sealed job is "
                                  f"measured, list it under jobs")
                campaign[f"{prefix}_stopped"] = campaign.get(f"{prefix}_stopped", 0) + 1
                continue
            if index not in declared:
                errors.append(
                    f"re-run job {job.name} of {space}/{run_id} is not in the manifest's job list {sorted(declared)}"
                )
                continue
            seen.add(index)
            if index in retired:
                campaign[f"{prefix}_superseded"] += 1
            elif not (job / "JOB-DONE").exists():
                campaign[f"{prefix}_unsealed"] += 1
            else:
                link_job(roots_dir, space, run_id, lane, job)
                campaign[f"{prefix}_kept"] += 1
        campaign[f"{prefix}_unsealed"] += len(declared - seen)
        if root.exists():
            roots.append(str(root))


def run_jobs(run_dir: Path, run_id: str):
    """(lane, job path, index) for each mirrored job directory of a run.

    A job directory is `<run id>-<index>` under a lane directory; anything
    else (run logs, non-job folders) is not a job.
    """
    for lane in sorted(run_dir.iterdir()):
        if not lane.is_dir():
            continue
        for job in sorted(lane.iterdir()):
            tail = job.name.rsplit("-", 1)[-1]
            if job.is_dir() and job.name.startswith(run_id + "-") and tail.isdigit():
                yield lane.name, job, int(tail)


def link_job(roots_dir: Path, space: str, run_id: str, lane: str, job: Path) -> None:
    link = roots_dir / f"{space}--{run_id}" / lane / job.name
    link.parent.mkdir(parents=True, exist_ok=True)
    if not link.is_symlink() and not link.exists():
        link.symlink_to(job)


def build_roots(data: Path, roots_dir: Path, manifest: dict) -> tuple[list[str], dict, list[str]]:
    """Link the campaign's sealed jobs; return (roots, counts, hard errors).

    A run absent from the data dir is not a hard error here: it lands in
    ``campaign["missing_runs"]`` and ``main`` decides against ``--partial``.
    """
    data, roots_dir = Path(data).resolve(), Path(roots_dir).resolve()
    superseded = superseded_jobs(manifest)
    late = late_superseded_jobs(manifest)
    campaign = {
        "first_pass_kept": 0,
        "first_pass_superseded": 0,
        "first_pass_unsealed": 0,
        "rerun_kept": 0,
        "rerun_unsealed": 0,
        "rerun_superseded": 0,
        "rerun2_kept": 0,
        "rerun2_unsealed": 0,
        "rerun2_superseded": 0,
        "rerun3_kept": 0,
        "rerun3_unsealed": 0,
        "editor_rerun_kept": 0,
        "editor_rerun_unsealed": 0,
        "extension_kept": 0,
        "extension_unsealed": 0,
        "late_superseded": 0,
        "late_rerun_kept": 0,
        "late_rerun_unsealed": 0,
        "editor_superseded": {editor: len(jobs) for editor, jobs in sorted(editor_superseded(manifest).items())},
        "editor_rounds": [
            # One issue may supersede several editors' cells: keys like "194-canvas" carry "issue": "194".
            {"issue": str(issue.get("issue", number)), "editor": issue["editor"], "jobs": len(issue["jobs"]),
             "lane": issue.get("lane"), "workload": issue.get("workload"), "workloads": issue.get("workloads"),
             "extension": bool(issue.get("extension"))}
            for number, issue in sorted(manifest.get("editor_superseded", {}).get("issues", {}).items())],
        "missing_runs": [],
    }
    roots: list[str] = []
    errors: list[str] = []
    first_pass_indices: set[int] = set()
    first_pass_lane: dict[int, str] = {}
    for space in sorted(manifest["first_pass"]):
        run_id = manifest["first_pass"][space]
        run_dir = data / space / "runs" / run_id
        if not run_dir.is_dir():
            campaign["missing_runs"].append(f"{space}/{run_id}")
        else:
            root = roots_dir / f"{space}--{run_id}"
            for lane, job, index in run_jobs(run_dir, run_id):
                first_pass_indices.add(index)
                first_pass_lane[index] = lane
                if not (job / "JOB-DONE").exists():
                    campaign["first_pass_unsealed"] += 1
                elif index in superseded:
                    campaign["first_pass_superseded"] += 1
                elif index in late:
                    campaign["late_superseded"] += 1
                else:
                    link_job(roots_dir, space, run_id, lane, job)
                    campaign["first_pass_kept"] += 1
            if root.exists():
                roots.append(str(root))
        retired = rerun_superseded_jobs(manifest)
        retired2 = rerun_superseded_jobs(manifest, "rerun2_superseded")
        _link_round(data, roots_dir, space, manifest["rerun"].get(space, []), "rerun", retired,
                    campaign, roots, errors)
        _link_round(data, roots_dir, space, manifest.get("rerun2", {}).get(space, []), "rerun2", retired2,
                    campaign, roots, errors)
        _link_round(data, roots_dir, space, manifest.get("rerun3", {}).get(space, []), "rerun3", set(),
                    campaign, roots, errors)
        _link_round(data, roots_dir, space, manifest.get("editor_rerun", {}).get(space, []), "editor_rerun",
                    set(), campaign, roots, errors)
        _link_round(data, roots_dir, space, manifest.get("extension", {}).get(space, []), "extension",
                    set(), campaign, roots, errors)
        _link_round(data, roots_dir, space, manifest.get("late_rerun", {}).get(space, []), "late_rerun",
                    set(), campaign, roots, errors)
        for round_key, earlier, name, of in (("rerun2", retired, "second-round", "re-run"),
                                             ("rerun3", retired2, "third-round", "second-round")):
            for entry in manifest.get(round_key, {}).get(space, []):
                stray = sorted(set(entry["jobs"]) - earlier)
                if stray:
                    errors.append(f"{name} jobs {stray} of {space}/{entry['run_id']} supersede no {of} job")
    # Every retired job is measured again exactly once, and no run is listed twice
    # (review of d509c234, M1): otherwise a cell would vanish with only a counter as trace.
    for retired_key, round_key, name in (("rerun_superseded", "rerun2", "second-round"),
                                         ("rerun2_superseded", "rerun3", "third-round")):
        if retired_key not in manifest:
            continue
        measured = [job for entries in manifest.get(round_key, {}).values() for entry in entries
                    for job in entry["jobs"]]
        wanted = rerun_superseded_jobs(manifest, retired_key)
        if sorted(measured) != sorted(wanted):
            errors.append(f"{retired_key} jobs {sorted(wanted)} are not measured again exactly once by "
                          f"{name} jobs {sorted(measured)}")
    _check_editor_round(manifest, errors)
    _check_stopped(manifest, errors)
    _check_extension(data, manifest, errors)
    _check_late_round(manifest, errors)
    # A late round retires first-pass jobs (octo review): an index no first-pass run carries would link a
    # job that replaces nothing. Only decidable when every first-pass run is mirrored.
    stray_late = sorted(late_superseded_jobs(manifest) - first_pass_indices)
    if stray_late and not campaign["missing_runs"]:
        errors.append(f"late_superseded jobs {stray_late} are not first-pass jobs")
    # ... and measures each in the lane of the job it retires (octo review).
    for space, entries in sorted(manifest.get("late_rerun", {}).items()):
        for entry in entries:
            run_dir = data / space / "runs" / entry["run_id"]
            if not run_dir.is_dir():
                continue
            for lane, job, index in run_jobs(run_dir, entry["run_id"]):
                if index in first_pass_lane and first_pass_lane[index] != lane:
                    errors.append(f"late-round job {job.name} is in lane {lane}; the first-pass job it retires "
                                  f"is in lane {first_pass_lane[index]}")
    run_ids = list(manifest["first_pass"].values()) + [
        entry["run_id"] for key in ("rerun", "rerun2", "rerun3", "editor_rerun", "extension", "late_rerun")
        for entries in manifest.get(key, {}).values() for entry in entries]
    duplicates = sorted({rid for rid in run_ids if run_ids.count(rid) > 1})
    if duplicates:
        errors.append(f"runs listed more than once in the manifest: {duplicates}")
    return roots, campaign, errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data_dir", type=Path, help="local bucket mirror: <space>/runs/<run id>/<lane>/<job>")
    parser.add_argument("roots_dir", type=Path, help="farm of symlinks this run builds")
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--partial", action="store_true",
                        help="tolerate manifest runs absent from the data dir and count them")
    args = parser.parse_args(argv)

    manifest = json.loads(args.manifest.read_text())
    # Links left by an earlier manifest would feed the tables superseded jobs (review of d509c234, M2).
    if args.roots_dir.exists() and any(args.roots_dir.iterdir()):
        print(f"error: roots dir {args.roots_dir} is not empty; build the roots into a fresh directory",
              file=sys.stderr)
        return 2
    roots, campaign, errors = build_roots(args.data_dir, args.roots_dir, manifest)
    if args.roots_dir.is_dir() and not campaign["missing_runs"]:
        _check_editor_round_data(args.roots_dir, manifest, errors)
    for line in errors:
        print(f"error: {line}", file=sys.stderr)
    if errors:
        return 2
    if campaign["missing_runs"] and not args.partial:
        for line in campaign["missing_runs"]:
            print(f"error: manifest run not in the data dir: {line}", file=sys.stderr)
        return 2
    campaign["partial"] = args.partial and bool(campaign["missing_runs"])
    args.roots_dir.mkdir(parents=True, exist_ok=True)
    payload = {"roots": roots, "campaign": campaign}
    if manifest.get("editor_superseded"):
        payload["superseded_cells"] = superseded_cells(manifest)
    (args.roots_dir / "report_e2_runs.json").write_text(json.dumps(payload, indent=1) + "\n")
    print(json.dumps(campaign))
    return 0


if __name__ == "__main__":
    sys.exit(main())
