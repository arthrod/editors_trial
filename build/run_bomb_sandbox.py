#!/usr/bin/env python3
"""Run the bomb suite where a sandbox actually confines it.

LibreOffice, the comparison, runs in Docker: no network, 2 GB memory cap,
read-only root. The editors are macOS binaries, so a Linux container cannot
run them. They run under seatbelt. External network stays denied. Localhost
and unix sockets inside the work directory stay open, because that is how
these editors' own tooling binds. Writes stay inside the work directory,
except the canvas vitest config-bundle cache, which Vite has no switch for.
The unsandboxed `run_bombs.py` entry still builds nothing.
"""
from __future__ import annotations

import os
import resource
import shutil
import signal
import subprocess
import sys
from pathlib import Path

import bomb_score
import make_bombs

ROOT = Path(__file__).resolve().parents[1]
IMAGE = "editors-trial-bombs:local"
BUN = "/Users/arthrod/.bun/bin/bun"
NODE = shutil.which("node") or "/opt/homebrew/bin/node"
WALL = 40
CPU = 30
CANARY_URI = "file:///tmp/xxe-canary.txt"
WC = os.environ.get(
    "WORDCRAFT_BIN",
    str(ROOT / "harness" / "wordcraft" / "target" / "release" / "wc-harness"),
)


def _tools(in_path: Path, out_dir: Path):
    out_docx = out_dir / "out.docx"
    return [
        ("plate", ROOT / "harness" / "plate", [BUN, "--preload", "./aliases.ts", "roundtrip.ts", str(in_path), str(out_docx)], {}),
        ("eigenpal", ROOT / "repos" / "eigenpal-docx-editor", [BUN, str(ROOT / "harness" / "eigenpal.ts"), str(in_path), str(out_docx), "store"], {}),
        ("eigenpal-editor", ROOT / "repos" / "eigenpal-docx-editor", [BUN, str(ROOT / "harness" / "eigenpal.ts"), str(in_path), str(out_docx), "editor"], {}),
        ("folio", ROOT / "repos" / "folio", [BUN, str(ROOT / "harness" / "folio.ts"), str(in_path), str(out_docx), "model"], {}),
        ("folio-editor", ROOT / "repos" / "folio", [BUN, str(ROOT / "harness" / "folio.ts"), str(in_path), str(out_docx), "editor"], {}),
        (
            "genoffice",
            ROOT / "repos" / "genoffice",
            [
                NODE,
                "--import",
                str(ROOT / "harness" / "css-stub.mjs"),
                "--import",
                str(ROOT / "repos" / "genoffice" / "node_modules" / "tsx" / "dist" / "loader.mjs"),
                str(ROOT / "harness" / "genoffice.cts"),
                str(in_path),
                str(out_docx),
            ],
            {},
        ),
        ("superdoc", ROOT, [NODE, str(ROOT / "harness" / "superdoc.mjs"), str(in_path), str(out_docx)], {}),
        (
            "officeopen",
            ROOT / "repos" / "office-open",
            [
                str(ROOT / "repos" / "office-open" / "node_modules" / ".bin" / "tsx"),
                "--tsconfig",
                str(ROOT / "repos" / "office-open" / "packages" / "docx" / "tsconfig.json"),
                str(ROOT / "harness" / "officeopen" / "roundtrip.mts"),
                str(in_path),
                str(out_docx),
            ],
            {},
        ),
        (
            "docen",
            ROOT / "repos" / "docen",
            [str(ROOT / "repos" / "docen" / "node_modules" / ".bin" / "tsx"), str(ROOT / "harness" / "docen" / "roundtrip.mts"), str(in_path), str(out_docx)],
            {},
        ),
        (
            "fidus",
            ROOT / "repos" / "fiduswriter-document-ts",
            [str(ROOT / "repos" / "fiduswriter-document-ts" / "node_modules" / ".bin" / "tsx"), "--no-cache", str(ROOT / "harness" / "fidus" / "roundtrip.mts")],
            {"IN_DOCX": str(in_path), "OUT_DOCX": str(out_docx), "TEMPLATE": "generated"},
        ),
        (
            "wordcraft",
            ROOT / "harness" / "wordcraft",
            [WC, str(in_path), str(out_docx)],
            {},
        ),
        (
            "canvas",
            ROOT / "repos" / "canvas-editor",
            [str(ROOT / "repos" / "canvas-editor" / "node_modules" / ".bin" / "vitest"), "run", "--root", str(ROOT / "harness" / "canvas")],
            {"IN_DOCX": str(in_path), "OUT_DIR": str(out_dir)},
        ),
        (
            "docsplus",
            ROOT / "harness" / "docsplus" / "repo-copy",
            [BUN, str(ROOT / "harness" / "docsplus" / "roundtrip.ts"), str(in_path), str(out_docx)],
            {},
        ),
        (
            "docxodus",
            ROOT / "harness" / "ui" / "docxodus",
            [NODE, "roundtrip.mjs", str(in_path), str(out_docx)],
            {},
        ),
    ]


def _vite_temp() -> Path:
    """Vite bundles an ESM config into the nearest node_modules/.vite-temp.

    There is no environment variable for that path. EPERM there is this
    sandbox, not canvas-editor. The directory is created by us before the
    profile is applied.
    """
    path = ROOT / "harness" / "canvas" / "node_modules" / ".vite-temp"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _profile(work: Path) -> str:
    real = os.path.realpath(work)
    # tsx binds its IPC pipe on the path we hand it, which may be /tmp while
    # the seatbelt check uses the /private/tmp realpath. Allow both.
    socket_roots = {real, str(Path(work))}
    socket_rules = []
    for root in sorted(socket_roots):
        # network* with a filter allowed outbound to the public internet on
        # this Mac. Name the operation. Default deny then blocks everything else.
        socket_rules.append(f'(allow network-bind (local unix-socket (subpath "{root}")))')
        socket_rules.append(f'(allow network-inbound (local unix-socket (subpath "{root}")))')
        socket_rules.append(f'(allow network-outbound (remote unix-socket (subpath "{root}")))')
    vite_temp = os.path.realpath(_vite_temp())
    return (
        "(version 1)\n"
        "(deny default)\n"
        "(allow process*)\n"
        "(allow signal)\n"
        "(allow sysctl-read)\n"
        "(allow mach-lookup)\n"
        "(allow ipc*)\n"
        "(allow system-socket)\n"
        "(allow file-ioctl (literal \"/dev/null\"))\n"
        "(allow file-ioctl (literal \"/dev/dtracehelper\"))\n"
        "(allow file-write-data (literal \"/dev/null\"))\n"
        "(allow file-read*)\n"
        f'(allow file-write* (subpath "{real}"))\n'
        f'(allow file-write* (subpath "{vite_temp}"))\n'
        # Seatbelt accepts only "*" or "localhost" as the host. A numeric
        # loopback is rejected at profile compile time. These three operations
        # are what let a tool bind its own loopback stub. network* is not used:
        # on this Mac that wildcard allowed a connection to a public address.
        "(allow network-bind (local ip \"localhost:*\"))\n"
        "(allow network-inbound (local ip \"localhost:*\"))\n"
        "(allow network-outbound (remote ip \"localhost:*\"))\n"
        + "\n".join(socket_rules)
        + "\n"
    )


def _limit():
    resource.setrlimit(resource.RLIMIT_CPU, (CPU, CPU + 5))


def _newest_docx(work: Path, source: Path) -> bytes | None:
    found = []
    for path in work.rglob("*.docx"):
        if path.resolve() == source.resolve() or not path.is_file():
            continue
        found.append(path)
    if not found:
        return None
    found.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return found[0].read_bytes()


def _leak(work: Path, out_dir: Path, data: bytes | None) -> bool:
    text = data.decode("utf-8", "replace") if data else ""
    if bomb_score.leaked_text(text):
        return True
    out_real = out_dir.resolve()
    for path in work.rglob("*"):
        if not path.is_file() or path.name != make_bombs.SLIP_NAME:
            continue
        try:
            path.resolve().relative_to(out_real)
        except ValueError:
            return True
    tmp = Path("/tmp") / make_bombs.SLIP_NAME
    return tmp.exists()


LOG_ROOT = ROOT / "logs" / "bombs"


def _text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return str(value)


def _run_captured(argv, cwd, env, timeout, work: Path, preexec_fn=None):
    """Run a child with its stdout and stderr written to files, not pipes.

    Node writes to a pipe asynchronously on macOS: when it dies on an uncaught
    exception, whatever lies past the 64 KB pipe buffer is lost. That is the
    message naming a ceiling, printed after a long runtime dump. A file is
    written synchronously, so the whole stream survives.
    """
    out_path, err_path = work / "child.stdout", work / "child.stderr"
    with out_path.open("wb") as out_fh, err_path.open("wb") as err_fh:
        proc = subprocess.Popen(argv, cwd=cwd, env=env, stdout=out_fh, stderr=err_fh,
                                start_new_session=True, preexec_fn=preexec_fn)
        timed = False
        try:
            proc.wait(timeout=timeout)
            code = proc.returncode if proc.returncode is not None else 1
        except subprocess.TimeoutExpired:
            _kill_group(proc.pid)
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass
            code, timed = 124, True
    out = out_path.read_bytes().decode("utf-8", "replace")
    err = err_path.read_bytes().decode("utf-8", "replace")
    return code, timed, out, err


def _save_case(kind: str, name: str, bid: str, cwd, command, code, timed: bool, stdout: str, stderr: str, score: str) -> None:
    """Keep the full streams. Nothing here is truncated."""
    case = LOG_ROOT / kind / name / bid
    case.mkdir(parents=True, exist_ok=True)
    command_text = " ".join(command) if isinstance(command, (list, tuple)) else str(command)
    (case / "command.txt").write_text(f"cwd: {cwd}\n{command_text}\n", encoding="utf-8")
    (case / "stdout.txt").write_text(stdout, encoding="utf-8", errors="replace")
    (case / "stderr.txt").write_text(stderr, encoding="utf-8", errors="replace")
    (case / "score.txt").write_text(score + "\n", encoding="utf-8")
    block = (
        f"\n===== {kind} {name} {bid} =====\n"
        f"cwd: {cwd}\n"
        f"command: {command_text}\n"
        f"exit: {code} timed_out: {timed}\n"
        f"score: {score}\n"
        f"stdout-chars: {len(stdout)} stderr-chars: {len(stderr)}\n"
        "----- stdout -----\n"
        f"{stdout}"
        "----- stderr -----\n"
        f"{stderr}"
        "===== end =====\n"
    )
    with (LOG_ROOT / "trace.log").open("a", encoding="utf-8") as fh:
        fh.write(block)
    print(block, file=sys.stderr, flush=True)


def _kill_group(pid: int) -> None:
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        return


def run_tool(name, cwd, cmd, env_extra, bomb_path: Path, work: Path) -> str:
    bid = bomb_path.stem
    if not cwd.is_dir() or not Path(cmd[0]).exists():
        score = bomb_score.line("tool", name, bid, "not-run", "not-run") + " reason: missing-toolchain"
        _save_case("tool", name, bid, cwd, cmd, "missing", False, "", "missing toolchain\n", score)
        return score
    out_dir = work / "out"
    home = work / "home"
    for path in (out_dir, home, work / "tmp", work / "cache", work / "config", work / "data"):
        path.mkdir(parents=True, exist_ok=True)
    profile = work / "profile.sb"
    profile.write_text(_profile(work), encoding="utf-8")
    env = os.environ.copy()
    env.update(env_extra)
    env["HOME"] = str(home)
    env["TMPDIR"] = str(work / "tmp")
    env["XDG_CACHE_HOME"] = str(work / "cache")
    env["XDG_CONFIG_HOME"] = str(work / "config")
    env["XDG_DATA_HOME"] = str(work / "data")
    env["BUN_INSTALL_CACHE_DIR"] = str(work / "cache" / "bun")
    env["npm_config_cache"] = str(work / "cache" / "npm")
    env["EDITOR_CONFIG"] = "suggested"
    env["EVIDENCE_DIR"] = str(work / "evidence")
    env["VITEST_CACHE_DIR"] = str(work / "cache" / "vite")
    (work / "evidence").mkdir(parents=True, exist_ok=True)
    (work / "cache" / "vite").mkdir(parents=True, exist_ok=True)
    code, timed, out, err = _run_captured(
        ["sandbox-exec", "-f", str(profile), *cmd], cwd=cwd, env=env, timeout=WALL,
        work=work, preexec_fn=_limit)
    out = _text(out)
    err = _text(err)
    data = _newest_docx(work, bomb_path)
    fault = _harness_fault(out, err)
    if fault:
        # A seatbelt or loader failure before the editor runs is our bug.
        # Do not record it as the editor catching, crashing, or hanging.
        fid, safe = "not-run", "not-run"
        score = bomb_score.line("tool", name, bid, fid, safe) + f" reason: {fault}"
    else:
        fid = bomb_score.fidelity(bid, data)
        safe = bomb_score.safety(code, timed, _leak(work, out_dir, data))
        score = bomb_score.line("tool", name, bid, fid, safe)
    _save_case("tool", name, bid, cwd, cmd, code, timed, out, err, score)
    return score


def run_libreoffice_one(bid: str, bombs_dir: Path) -> str:
    name = f"bomb-lo-{bid}-{os.getpid()}"
    cmd = [
        "docker", "run", "--rm", "--name", name,
        "--network", "none",
        "--memory", "2g",
        "--memory-swap", "2g",
        "--cpus", "1",
        "--pids-limit", "256",
        "--read-only",
        "--tmpfs", "/tmp:rw,exec,size=1024m",
        "--tmpfs", "/home:rw,size=256m",
        "--tmpfs", "/run:rw,size=32m",
        "--tmpfs", "/var/tmp:rw,size=32m",
        "-e", "HOME=/home",
        "-e", "SAL_USE_VCLPLUGIN=svp",
        "-v", f"{bombs_dir}:/bombs:ro",
        "-v", f"{ROOT}/build/make_bombs.py:/opt/make_bombs.py:ro",
        "-v", f"{ROOT}/build/bomb_score.py:/opt/bomb_score.py:ro",
        "-v", f"{ROOT}/build/lo_run.py:/opt/lo_run.py:ro",
        IMAGE,
        "python3", "/opt/lo_run.py", bid,
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        out, err = proc.communicate(timeout=90)
        code = proc.returncode if proc.returncode is not None else 1
        timed = False
    except subprocess.TimeoutExpired as exc:
        out = _text(exc.stdout)
        err = _text(exc.stderr) + "\nreason: docker-timeout\n"
        _kill_group(proc.pid)
        subprocess.run(["docker", "kill", name], capture_output=True, check=False)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass
        code = 124
        timed = True
    out = _text(out)
    err = _text(err)
    found = [ln for ln in out.splitlines() if ln.startswith("comparison ")]
    if found:
        score = found[-1]
    elif timed:
        score = bomb_score.line("comparison", "libreoffice", bid, "not-run", "hang") + " reason: docker-timeout"
    elif code == 137 or code < 0:
        score = bomb_score.line("comparison", "libreoffice", bid, "not-run", "crash") + " reason: container-killed"
    else:
        tail = ((err or out or "docker failed").strip().splitlines() or ["docker failed"])[-1][:160]
        score = bomb_score.line("comparison", "libreoffice", bid, "not-run", "not-run") + f" reason: {tail}"
    _save_case("comparison", "libreoffice", bid, "/", cmd, code, timed, out, err, score)
    return score


def header() -> list[str]:
    return [
        "sandbox: libreoffice in docker, network none, memory 2g, read-only root. "
        "editors under seatbelt. External network is denied. Localhost and unix sockets "
        "inside the work directory are allowed, because the editors' own tooling binds them. "
        "Writes stay in the work directory, plus the canvas vitest config cache. "
        "The editors are macOS binaries and were not run inside the Linux container.",
        "taxonomy: preserving a hostile payload is not the same single result as a crash.",
        "reference Word fidelity: not-run safety: not-run Word was not opened. LibreOffice is the comparison.",
        "B7 note: NTLM credential leak was not measured. No hash collector was started. External network and UNC were denied. Localhost was allowed so a tool loopback stub and the 127.0.0.1 probe are not blocked by the seatbelt.",
        "B5 note: the entity bomb expands one million times, not to a gigabyte. This Mac cannot cap address space.",
        "B1 note: one deflate member tops out near one thousand to one. A single member at two thousand five hundred to one is not a real deflate stream.",
        "config: each editor used that project's documented import and export. Plate used BaseEditorKit, retainSource, and the default reject policy, and a refused import wrote no second permissive file. Canvas did not replace a thrown import with the blank starter document. docs.plus stopped at its own importDocx and exportDocx. docen, officeopen and fidus were started with their own tsx.",
    ]


def _harness_fault(stdout: str, stderr: str) -> str | None:
    """Startup failures that belong to this harness, not to the editor."""
    blob = f"{stdout}\n{stderr}"
    if "listen EPERM" in blob and ".pipe" in blob:
        return "harness-tsx-socket"
    if ".vite-temp" in blob and "EPERM" in blob:
        return "harness-vite-temp"
    if "Failed to start server" in blob or "sandbox-exec:" in blob:
        return "harness-start"
    if "Cannot access 'show' before initialization" in blob:
        return "harness-plate"
    # A missing package while loading the editor's own kit is this checkout,
    # not the editor refusing the bomb.
    if "Cannot find package" in blob or "Cannot find module" in blob:
        return "harness-missing-module"
    return None


def _record(path: Path, line: str) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def _done(path: Path) -> dict[tuple[str, str], str]:
    found = {}
    if not path.exists():
        return found
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0] in {"tool", "comparison"}:
            found[(parts[1], parts[2])] = line
    return found


def main() -> int:
    work_root = Path(os.environ["BOMB_WORK"])
    work_root.mkdir(parents=True, exist_ok=True)
    Path("/tmp/xxe-canary.txt").write_text(bomb_score.CANARY + "\n", encoding="utf-8")
    bomb_dir = work_root / "bombs"
    resume = os.environ.get("BOMB_RESUME") == "1"
    if resume and (bomb_dir / "B1.docx").exists():
        bombs = {path.stem: path for path in sorted(bomb_dir.glob("B*.docx"))}
    else:
        bombs = make_bombs.build(bomb_dir, CANARY_URI)
    only_b = set(filter(None, os.environ.get("BOMB_ONLY", "").split(",")))
    only_t = set(filter(None, os.environ.get("TOOL_ONLY", "").split(",")))
    if only_b:
        bombs = {bid: path for bid, path in bombs.items() if bid in only_b}
    lines_path = work_root / "lines.log"
    done = _done(lines_path) if resume else {}
    if not resume:
        if lines_path.exists():
            lines_path.unlink()
        if LOG_ROOT.exists():
            shutil.rmtree(LOG_ROOT)
        LOG_ROOT.mkdir(parents=True, exist_ok=True)
        (LOG_ROOT / "trace.log").write_text(
            "bomb experiment trace. full stdout and stderr of every run are kept below.\n",
            encoding="utf-8",
        )
    lines = header()
    skip_lo = os.environ.get("BOMB_SKIP_LO") == "1"
    try:
        for bid in bombs:
            key = ("libreoffice", bid)
            if skip_lo:
                continue
            if key in done:
                lines.append(done[key])
                continue
            print(f"RUN libreoffice {bid}", file=sys.stderr, flush=True)
            line = run_libreoffice_one(bid, bomb_dir)
            _record(lines_path, line)
            lines.append(line)
            print(line, file=sys.stderr, flush=True)
        for bid, bomb_path in bombs.items():
            for name, cwd, cmd, extra in _tools(bomb_path, work_root / "unused"):
                if only_t and name not in only_t:
                    continue
                key = (name, bid)
                if key in done:
                    lines.append(done[key])
                    continue
                run_work = work_root / "runs" / name / bid
                if run_work.exists():
                    shutil.rmtree(run_work)
                run_work.mkdir(parents=True)
                spec = next(item for item in _tools(bomb_path, run_work / "out") if item[0] == name)
                print(f"RUN {name} {bid}", file=sys.stderr, flush=True)
                line = run_tool(spec[0], spec[1], spec[2], spec[3], bomb_path, run_work)
                _record(lines_path, line)
                lines.append(line)
                print(line, file=sys.stderr, flush=True)
    finally:
        try:
            Path("/tmp/xxe-canary.txt").unlink()
        except FileNotFoundError:
            pass
    text = "\n".join(lines) + "\n"
    (work_root / "stdout.txt").write_text(text, encoding="utf-8")
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    (LOG_ROOT / "scorecard.txt").write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
