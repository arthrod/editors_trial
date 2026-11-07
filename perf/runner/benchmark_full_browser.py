#!/usr/bin/env python3
"""Orchestrate full-browser perf suites (ci_broad + laboratory dedicated_publish)."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from perf.schema import load_trial  # noqa: E402
from perf.runner.schedule import plan_attempts  # noqa: E402
from perf.scenarios.catalog import scenarios  # noqa: E402

DEFAULT_OUT = REPO / "perf/out/full_browser_2026_11_07"
DEFAULT_EDITORS = ["docxodus", "superdoc", "genoffice", "plate", "canvas"]


def _run(cmd: list[str]) -> None:
    env = {**dict(__import__("os").environ), "PYTHONPATH": str(REPO)}
    proc = subprocess.run(cmd, cwd=str(REPO), env=env)
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


def _aggregate(out_root: Path, commands: list[str], **meta) -> None:
    subs = []
    for name in ("ci_broad", "dedicated_publish", "load_unload", "wasm", "ci_broad_catalog"):
        sp = out_root / name / "summary.json"
        if sp.is_file():
            subs.append(json.loads(sp.read_text(encoding="utf-8")))
    summary = {
        "suite": "full_browser",
        "publishable": False,
        "commands": commands,
        "subsuites": subs,
        **meta,
    }
    c20 = out_root / "c20_full_soak" / "started.json"
    summary["c20_full_soak_started"] = c20.is_file()
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


def check_out(root: Path) -> int:
    roots = [
        root / "ci_broad",
        root / "dedicated_publish",
        root / "wasm",
        root / "load_unload",
    ]
    attempts = []
    for sub in roots:
        if sub.is_dir():
            attempts.extend(sub.rglob("attempts/*.json"))
    for path in attempts:
        load_trial(path.read_text(encoding="utf-8"))
    bad = []
    for path in attempts:
        text = path.read_text(encoding="utf-8")
        if "adapter-not-implemented" in text:
            data = json.loads(text)
            if data.get("editor_id") in DEFAULT_EDITORS:
                bad.append(str(path))
    if bad:
        print("adapter-not-implemented in browser attempts:", *bad, sep="\n")
        return 1
    if re.search(r"PERF\s+model_ready_ms\s*=", "".join(p.read_text() for p in attempts[:20])):
        print("forbidden PERF model_ready_ms line")
        return 1
    print("check-out: %d attempts, %d forbidden" % (len(attempts), len(bad)))
    return 0


def drop_page_cache(out_root: Path) -> dict:
    script = REPO / "perf/runner/page_cache_drop.sh"
    proc = subprocess.run(["bash", str(script)], capture_output=True, text=True)
    return {
        "page_cache_dropped": proc.returncode == 0,
        "cache_drop_command": "sync; echo 3 | sudo tee /proc/sys/vm/drop_caches",
        "stderr": proc.stderr,
        "stdout": proc.stdout,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--check-out", type=Path, default=None)
    parser.add_argument("--execution-profile", default="ci_broad")
    parser.add_argument("--host-class", default="ci_coarse")
    parser.add_argument("--out-root", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--pairs", type=int, default=3)
    parser.add_argument("--editors", nargs="*", default=None)
    parser.add_argument("--c20-preview-seconds", type=int, default=0)
    parser.add_argument("--start-c20-full-soak", action="store_true")
    parser.add_argument("--skip-run", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.editors and len(args.editors) == 1 and "," in args.editors[0]:
        args.editors = [e.strip() for e in args.editors[0].split(",") if e.strip()]

    if args.check_out:
        return check_out(args.check_out)

    editors = args.editors or DEFAULT_EDITORS
    profile_root = args.out_root / args.execution_profile.replace("_", "-") if args.execution_profile != "ci_broad" else args.out_root / "ci_broad"
    if args.execution_profile == "ci_broad":
        profile_root = args.out_root / "ci_broad"

    commands: list[str] = []

    if args.dry_run:
        _aggregate(
            args.out_root,
            commands,
            execution_profile=args.execution_profile,
            host_class=args.host_class,
            editors=editors,
        )
        print("dry-run wrote %s" % (args.out_root / "summary.json"))
        return 0

    if args.skip_run:
        _aggregate(args.out_root, commands, execution_profile=args.execution_profile, host_class=args.host_class)
        return 0

    warm_cmd = [
        sys.executable,
        str(REPO / "perf/runner/benchmark_warm_cold.py"),
        "--out-root",
        str(profile_root),
        "--pairs",
        str(args.pairs),
        "--execution-profile",
        args.execution_profile,
        "--host-class",
        args.host_class,
        "--editors",
        *editors,
    ]
    commands.append(" ".join(warm_cmd))
    _run(warm_cmd)

    interact_cmd = [
        sys.executable,
        str(REPO / "perf/runner/benchmark_browser_interactions.py"),
        "--out-root",
        str(profile_root),
        "--pairs",
        str(args.pairs),
        "--execution-profile",
        args.execution_profile,
        "--host-class",
        args.host_class,
        "--editors",
        *editors,
    ]
    commands.append(" ".join(interact_cmd))
    _run(interact_cmd)

    wasm_root = args.out_root / "wasm"
    wasm_cmd = [
        sys.executable,
        str(REPO / "perf/runner/benchmark_wasm_c24.py"),
        "--out-root",
        str(wasm_root),
        "--execution-profile",
        args.execution_profile,
        "--host-class",
        args.host_class,
    ]
    commands.append(" ".join(wasm_cmd))
    _run(wasm_cmd)

    if args.host_class == "laboratory" and args.execution_profile == "dedicated_publish":
        drop = drop_page_cache(profile_root)
        (profile_root / "cache_drop.json").write_text(json.dumps(drop, indent=2) + "\n", encoding="utf-8")

    load_root = args.out_root / "load_unload"
    load_cmd = [
        sys.executable,
        str(REPO / "perf/runner/benchmark_load_unload.py"),
        "--out-root",
        str(load_root),
        "--pairs",
        str(args.pairs),
    ]
    if (REPO / "perf/runner/benchmark_load_unload.py").is_file():
        commands.append(" ".join(load_cmd))
        _run(load_cmd)

    catalog_root = args.out_root / "ci_broad_catalog"
    catalog_cmd = [
        sys.executable,
        str(REPO / "perf/runner/benchmark_ci_contract.py"),
        "--execution-profile",
        "ci_broad",
        "--out-root",
        str(catalog_root),
    ]
    commands.append(" ".join(catalog_cmd))
    _run(catalog_cmd)

    gaps_cmd = [
        sys.executable,
        str(REPO / "perf/runner/benchmark_browser_gaps.py"),
        "--out-root",
        str(profile_root),
        "--execution-profile",
        args.execution_profile,
        "--host-class",
        args.host_class,
    ]
    commands.append(" ".join(gaps_cmd))
    _run(gaps_cmd)

    pixels_cmd = [
        sys.executable,
        str(REPO / "perf/runner/benchmark_pixels_lo.py"),
        "--out-root",
        str(args.out_root / "pixels"),
    ]
    commands.append(" ".join(pixels_cmd))
    _run(pixels_cmd)

    if args.c20_preview_seconds > 0:
        c20_cmd = [
            sys.executable,
            str(REPO / "perf/runner/benchmark_c20_soak.py"),
            "--seconds",
            str(args.c20_preview_seconds),
            "--out-root",
            str(profile_root / "c20_preview"),
            "--editor",
            "plate",
        ]
        if (REPO / "perf/runner/benchmark_c20_soak.py").is_file():
            commands.append(" ".join(c20_cmd))
            _run(c20_cmd)

    if args.start_c20_full_soak:
        soak_dir = args.out_root / "c20_full_soak"
        soak_dir.mkdir(parents=True, exist_ok=True)
        tmux_cmd = (
            "tmux -f /exec-daemon/tmux.portal.conf new-session -d -s c20-full-soak -c %s -- "
            "env PYTHONPATH=. python3 perf/runner/benchmark_c20_soak.py "
            "--seconds 3600 --out-root %s --editor plate"
            % (REPO, soak_dir)
        )
        subprocess.run(tmux_cmd, shell=True, cwd=str(REPO))
        started = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "tmux_session": "c20-full-soak",
            "command": tmux_cmd,
        }
        (soak_dir / "started.json").write_text(json.dumps(started, indent=2) + "\n", encoding="utf-8")
        commands.append(tmux_cmd)

    _aggregate(
        args.out_root,
        commands,
        execution_profile=args.execution_profile,
        host_class=args.host_class,
        fixture_sha256="",
        editors=editors,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
