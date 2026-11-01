#!/usr/bin/env python3
"""
Choose the version of each editor a release measures (AGENTS.md, "Releases").

The rule: the newest version that is at least COOLDOWN_DAYS old on the release
date, and never a version older than the one currently pinned.

    python3 build/pin_versions.py git <repo> <branch> [--date YYYY-MM-DD]   # prints a commit
    python3 build/pin_versions.py npm <package> <channel> [--current V] [--date YYYY-MM-DD]

``channel`` is ``latest`` (stable versions only) or a prerelease tag such as
``next`` (versions containing ``-next.``).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

COOLDOWN_DAYS = 5


def cutoff(release: date) -> date:
    return release - timedelta(days=COOLDOWN_DAYS)


def release_record(release: date) -> dict:
    """What the reports cite as the release date, and the cutoff the pins obey."""
    return {"date": release.isoformat(), "cutoff": cutoff(release).isoformat()}


def _end_of(day: date) -> str:
    return f"{day.isoformat()}T23:59:59+00:00"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


def git_pin(repo: Path, ref: str, cut: date, current: str | None) -> str:
    """Newest commit on ``ref`` committed on or before ``cut``; never behind ``current``."""
    r = _git(repo, "log", "-1", "--format=%H", f"--before={_end_of(cut)}", ref)
    candidate = r.stdout.strip()
    if not candidate:
        if current:
            return _git(repo, "rev-parse", current).stdout.strip()
        raise SystemExit(f"no commit on {ref} before {cut} in {repo}")
    if current:
        current = _git(repo, "rev-parse", current).stdout.strip()
        # The candidate is older than (an ancestor of) the current pin: keep the pin.
        if _git(repo, "merge-base", "--is-ancestor", candidate, current).returncode == 0:
            return current
    return candidate


def _channel(version: str, channel: str) -> bool:
    if channel == "latest":
        return "-" not in version
    return f"-{channel}." in version


def _when(stamp: str) -> datetime:
    return datetime.fromisoformat(stamp.replace("Z", "+00:00"))


def npm_pin(times: dict, cut: date, channel: str, current: str | None) -> str:
    """Newest version of ``channel`` published on or before ``cut``; never behind ``current``."""
    limit = datetime.fromisoformat(_end_of(cut))
    versions = {v: _when(t) for v, t in times.items() if v not in ("created", "modified")}
    eligible = [v for v, t in versions.items() if _channel(v, channel) and t <= limit]
    candidate = max(eligible, key=lambda v: versions[v]) if eligible else None
    if current and current in versions:
        if candidate is None or versions[candidate] <= versions[current]:
            return current
    if candidate is None:
        raise SystemExit(f"no {channel} version published before {cut}")
    return candidate


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="kind", required=True)
    g = sub.add_parser("git")
    g.add_argument("repo")
    g.add_argument("ref")
    g.add_argument("--current", default="HEAD")
    g.add_argument("--date")
    n = sub.add_parser("npm")
    n.add_argument("package")
    n.add_argument("channel")
    n.add_argument("--current")
    n.add_argument("--date")
    r = sub.add_parser("release", help="print the release record (date, cutoff) as JSON")
    r.add_argument("--date")
    a = ap.parse_args()
    release = date.fromisoformat(a.date) if a.date else datetime.now(timezone.utc).date()
    cut = cutoff(release)
    if a.kind == "release":
        print(json.dumps(release_record(release)))
    elif a.kind == "git":
        print(git_pin(Path(a.repo), a.ref, cut, a.current))
    else:
        out = subprocess.run(["npm", "view", a.package, "time", "--json"], capture_output=True, text=True, check=True)
        print(npm_pin(json.loads(out.stdout), cut, a.channel, a.current))
    return 0


if __name__ == "__main__":
    sys.exit(main())
