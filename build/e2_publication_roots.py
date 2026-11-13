#!/usr/bin/env python3
"""Register Report E2's publication runs as a farm of symlinks to sealed jobs.

`perf/container/e2_publication.json` names the publish1 campaign: the 20
first-pass run ids (harness 4488f9b6), the 20 re-run run ids (harness
78249e7c) with the job indexes each re-ran, and the first-pass job indexes
superseded by issues #173, #174 and #175; then the second round: the re-run
job indexes issue #181 superseded (`rerun_superseded`) and the runs that
measured them again (`rerun2`); then the third round: the second-round job
indexes issues #183 and #184 superseded (`rerun2_superseded`) and the runs
that measured them again (`rerun3`). This script walks a local mirror
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
        seen: set[int] = set()
        root = roots_dir / f"{space}--{run_id}"
        for lane, job, index in run_jobs(run_dir, run_id):
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
        "missing_runs": [],
    }
    roots: list[str] = []
    errors: list[str] = []
    for space in sorted(manifest["first_pass"]):
        run_id = manifest["first_pass"][space]
        run_dir = data / space / "runs" / run_id
        if not run_dir.is_dir():
            campaign["missing_runs"].append(f"{space}/{run_id}")
        else:
            root = roots_dir / f"{space}--{run_id}"
            for lane, job, index in run_jobs(run_dir, run_id):
                if not (job / "JOB-DONE").exists():
                    campaign["first_pass_unsealed"] += 1
                elif index in superseded:
                    campaign["first_pass_superseded"] += 1
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
        for round_key, earlier, name, of in (("rerun2", retired, "second-round", "re-run"),
                                             ("rerun3", retired2, "third-round", "second-round")):
            for entry in manifest.get(round_key, {}).get(space, []):
                stray = sorted(set(entry["jobs"]) - earlier)
                if stray:
                    errors.append(f"{name} jobs {stray} of {space}/{entry['run_id']} supersede no {of} job")
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
    roots, campaign, errors = build_roots(args.data_dir, args.roots_dir, manifest)
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
    (args.roots_dir / "report_e2_runs.json").write_text(json.dumps(payload, indent=1) + "\n")
    print(json.dumps(campaign))
    return 0


if __name__ == "__main__":
    sys.exit(main())
