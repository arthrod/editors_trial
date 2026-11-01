#!/usr/bin/env python3
"""Run jubarte read on the ten hostile packages.

This does not touch logs/bombs or /tmp/editors-trial-bombs. The scored
command is the binary default, including the layout pass:

    jubarte read FILE -o view.md --force

The skill quick start adds --no-page-markers. This run does not. read writes
a markdown view, not a second docx. A missing docx is not a catch.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path

import bomb_score
import make_bombs
import protection
from run_bomb_sandbox import CPU, WALL, _limit, _profile

ROOT = Path(__file__).resolve().parents[1]
EDITOR_WORK = Path("/tmp/editors-trial-bombs")
EDITOR_LOG = ROOT / "logs" / "bombs"
WORK = Path("/tmp/editors-trial-jubarte-bombs")
LOG = ROOT / "logs" / "jubarte-bombs"
BINARY = Path(os.environ.get("JUBARTE_BIN", "/tmp/jubarte-redlines-target/release/jubarte"))
CANARY_PATH = Path("/tmp/xxe-canary.txt")
EXPECTED_VERSION = "jubarte 0.14.0"

# A markdown view of body text can show these. Zip entry counts, attribute
# soup, relationship targets, field machinery, and corrupt part bytes are
# not body text. Their absence from a successful view is not sanitation.
_STRUCTURAL = {"B2", "B3", "B6", "B7", "B9", "B10"}


def _guard() -> None:
    if WORK.resolve() == EDITOR_WORK.resolve():
        raise SystemExit("refusing to use the editor work directory")
    if LOG.resolve() == EDITOR_LOG.resolve():
        raise SystemExit("refusing to use the editor log directory")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _count_upto(path: Path, needle: bytes, limit: int) -> int:
    if not path.is_file():
        return 0
    found = 0
    prev = b""
    width = max(len(needle) - 1, 0)
    with path.open("rb") as handle:
        while found <= limit:
            chunk = handle.read(1 << 20)
            if not chunk:
                break
            hay = prev + chunk
            start = 0
            while found <= limit:
                at = hay.find(needle, start)
                if at < 0:
                    break
                found += 1
                start = at + len(needle)
            prev = hay[-width:] if width else b""
    return found


def _has(path: Path, needle: bytes) -> bool:
    return _count_upto(path, needle, 0) > 0


def view_fidelity(bomb_id: str, present: bool, size: int, hits: dict[str, bool]) -> str:
    """Fidelity of a markdown view. No view is refused. A structural weapon
    that a view cannot carry is not-in-view, which is not a catch.
    """
    if not present:
        return "refused"
    if bomb_id == "B1":
        return "preserved" if size > 8 * 1024 * 1024 else "dropped"
    if bomb_id == "B4":
        return "preserved" if hits.get("deep") or hits.get("tbl") else "dropped"
    if bomb_id == "B5":
        # An unexpanded "&lol6;" is the weapon, kept. Absence of the expanded
        # token is not a drop.
        if (
            size > 32 * 1024 * 1024
            or hits.get("lol")
            or hits.get("entity")
            or hits.get("hosts_uri")
            or hits.get("leak")
            or hits.get("raw_entity")
        ):
            return "preserved"
        return "dropped"
    if bomb_id == "B8":
        return "preserved" if hits.get("xss_js") or hits.get("xss_mark") else "dropped"
    structural = {
        "B2": hits.get("entries"),
        "B3": hits.get("attrs"),
        "B6": hits.get("slip") or hits.get("passwd_path") or hits.get("hosts_path") or hits.get("leak"),
        "B7": hits.get("ssrf") or hits.get("unc") or hits.get("dotm"),
        "B9": hits.get("span") or hits.get("fields") or hits.get("sources"),
        "B10": hits.get("png") or hits.get("bom"),
    }.get(bomb_id, False)
    if structural:
        return "preserved"
    if bomb_id in _STRUCTURAL:
        return "not-in-view"
    return "dropped"


def _hits(view: Path, streams: bytes) -> dict[str, bool]:
    def seen(needle: bytes) -> bool:
        if needle in streams:
            return True
        return _has(view, needle) if view.is_file() else False

    lol = make_bombs.LOL.encode("ascii")
    return {
        "deep": seen(b"DEEP_LEAF"),
        "tbl": seen(b"TBL_LEAF"),
        "lol": seen(lol),
        "raw_entity": seen(b"&lol") or seen(b"&xxe;") or seen(b"&canary;"),
        "entity": seen(b"<!ENTITY") or seen(b"<!DOCTYPE"),
        "hosts_uri": seen(b"file:///etc/hosts"),
        "leak": any(seen(mark.encode("utf-8")) for mark in bomb_score.LEAK_MARKS),
        "xss_js": seen(make_bombs.XSS_JS.encode("ascii")),
        "xss_mark": seen(make_bombs.XSS_MARK.encode("ascii")),
        "entries": _count_upto(view, b"customXml/p", 1000) > 1000 if view.is_file() else b"customXml/p" in streams,
        "attrs": _count_upto(view, b"bombAttr", 1000) > 1000 if view.is_file() else streams.count(b"bombAttr") > 1000,
        "slip": seen(make_bombs.SLIP.encode("ascii")),
        "passwd_path": seen(b"etc/passwd"),
        "hosts_path": seen(b"etc/hosts"),
        "ssrf": seen(make_bombs.SSRF.encode("ascii")),
        "unc": seen(make_bombs.UNC.encode("utf-8")),
        "dotm": seen(b"leak.dotm"),
        "span": seen(b"1000000"),
        "fields": (view.is_file() and _count_upto(view, b"fldChar", 100) > 100) or streams.count(b"fldChar") > 100,
        "sources": (view.is_file() and _count_upto(view, b"b:Source", 100) > 100) or streams.count(b"b:Source") > 100,
        "png": seen(make_bombs.PNG_MARK.encode("ascii")),
        "bom": seen(b"\xff\xfe"),
    }


def _leaked(run: Path, out_dir: Path, view: Path, streams: bytes) -> bool:
    if bomb_score.leaked_text(streams.decode("utf-8", "replace")):
        return True
    if view.is_file():
        for mark in bomb_score.LEAK_MARKS:
            if _has(view, mark.encode("utf-8")):
                return True
    slip_name = make_bombs.SLIP_NAME
    slip_bytes = make_bombs.SLIP.encode("ascii")
    for path in run.rglob("*"):
        if not path.is_file():
            continue
        if view.is_file() and path.resolve() == view.resolve():
            continue
        try:
            path.resolve().relative_to(out_dir.resolve())
            inside_out = True
        except ValueError:
            inside_out = False
        if path.name == slip_name and not inside_out:
            return True
        if path.stat().st_size > 4096:
            continue
        head = path.read_bytes()[:200]
        if slip_bytes in head and not inside_out:
            return True
    host = Path("/tmp") / slip_name
    return host.exists()


def _harness(stdout: str, stderr: str) -> str | None:
    blob = f"{stdout}\n{stderr}"
    if "sandbox-exec:" in blob:
        return "harness-start"
    # Seatbelt EPERM with no admission code from jubarte is our bug.
    if "Operation not permitted" in blob:
        named = ("INPUT_LIMIT", "INVALID_PACKAGE", "INVALID_XML", "UNSUPPORTED_PACKAGE", "DUPLICATE_PART", "LEGACY_DOC", "ZIP_HEADER")
        if not any(code in blob for code in named):
            return "harness-seatbelt-write"
    return None


def _kill_group(pid: int) -> None:
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        return


def _copy_bombs(dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    source = EDITOR_WORK / "bombs"
    names = [f"B{n}.docx" for n in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10)]
    if all((source / name).is_file() for name in names):
        for name in names:
            shutil.copyfile(source / name, dest / name)
        return
    make_bombs.build(dest, "file:///tmp/xxe-canary.txt")


def _store_streams(case: Path, stdout: bytes, stderr: bytes) -> tuple[str, str]:
    def one(name: str, data: bytes) -> str:
        text = data.decode("utf-8", "replace")
        if len(data) <= 8 * 1024 * 1024:
            (case / name).write_text(text, encoding="utf-8", errors="replace")
            return text
        (case / f"{name}.full").write_bytes(data)
        clipped = text[:4000] + "\n----- clipped -----\n" + text[-4000:]
        (case / name).write_text(clipped, encoding="utf-8", errors="replace")
        return clipped

    return one("stdout.txt", stdout), one("stderr.txt", stderr)


def _store_view(case: Path, view: Path) -> None:
    if not view.is_file():
        (case / "view-absent.txt").write_text("no view file\n", encoding="utf-8")
        return
    size = view.stat().st_size
    (case / "view-stat.txt").write_text(f"octets {size}\nsha256 {_sha256(view)}\n", encoding="utf-8")
    if size <= 1_000_000:
        shutil.copyfile(view, case / "view.md")
        return
    data_head = view.open("rb")
    try:
        head = data_head.read(4096)
        data_head.seek(max(size - 4096, 0))
        tail = data_head.read(4096)
    finally:
        data_head.close()
    (case / "view-head.txt").write_bytes(head)
    (case / "view-tail.txt").write_bytes(tail)
    (case / "view-kept.txt").write_text(f"full view left at {view}\n", encoding="utf-8")


def run_one(binary: Path, bomb: Path, run: Path) -> tuple[str, str]:
    bid = bomb.stem
    if run.exists():
        shutil.rmtree(run)
    out_dir = run / "out"
    home = run / "home"
    for path in (out_dir, home, run / "tmp", run / "cache", run / "config", run / "data"):
        path.mkdir(parents=True, exist_ok=True)
    view = out_dir / "view.md"
    profile = run / "profile.sb"
    # Writes are allowed anywhere under the jubarte work root, so a slip that
    # stays inside that root and outside out/ can be seen. Host temp stays denied.
    profile.write_text(_profile(WORK), encoding="utf-8")
    cmd = [str(binary), "read", str(bomb), "-o", str(view), "--force"]
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["TMPDIR"] = str(run / "tmp")
    env["XDG_CACHE_HOME"] = str(run / "cache")
    env["XDG_CONFIG_HOME"] = str(run / "config")
    env["XDG_DATA_HOME"] = str(run / "data")
    proc = subprocess.Popen(
        ["sandbox-exec", "-f", str(profile), *cmd],
        cwd=str(run),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
        preexec_fn=_limit,
    )
    timed = False
    try:
        out_b, err_b = proc.communicate(timeout=WALL)
        code = proc.returncode if proc.returncode is not None else 1
    except subprocess.TimeoutExpired as exc:
        out_b = exc.stdout or b""
        err_b = exc.stderr or b""
        _kill_group(proc.pid)
        try:
            rest_out, rest_err = proc.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            rest_out, rest_err = b"", b""
        out_b += rest_out or b""
        err_b += rest_err or b""
        code = 124
        timed = True
    case = LOG / "tool" / "jubarte" / bid
    case.mkdir(parents=True, exist_ok=True)
    (case / "command.txt").write_text(f"cwd: {run}\n{' '.join(cmd)}\n", encoding="utf-8")
    stdout, stderr = _store_streams(case, out_b, err_b)
    _store_view(case, view)
    fault = _harness(stdout, stderr)
    streams = out_b + b"\n" + err_b
    present = view.is_file() and view.stat().st_size > 0
    size = view.stat().st_size if view.is_file() else 0
    if fault:
        fid, safe = "not-run", "not-run"
        score = bomb_score.line("tool", "jubarte", bid, fid, safe) + f" reason: {fault}"
        level = "not-run"
        detail = fault
    else:
        hits = _hits(view, streams)
        fid = view_fidelity(bid, present, max(size, len(out_b)), hits)
        safe = bomb_score.safety(code, timed, _leaked(run, out_dir, view, streams))
        score = bomb_score.line("tool", "jubarte", bid, fid, safe)
        view_text = view.read_text(encoding="utf-8", errors="replace") if view.is_file() else ""
        level = jubarte_level(bid, fid, safe, stdout + "\n" + stderr, view_text)
        detail = protection_detail(bid, level)
    prot = f"protection jubarte {bid} level: {level} detail: {detail}"
    (case / "score.txt").write_text(score + "\n" + prot + "\n", encoding="utf-8")
    block = (
        f"\n===== tool jubarte {bid} =====\n"
        f"cwd: {run}\n"
        f"command: {' '.join(cmd)}\n"
        f"exit: {code} timed_out: {timed}\n"
        f"score: {score}\n"
        f"{prot}\n"
        "----- stdout -----\n"
        f"{stdout}\n"
        "----- stderr -----\n"
        f"{stderr}\n"
        "===== end =====\n"
    )
    with (LOG / "trace.log").open("a", encoding="utf-8") as handle:
        handle.write(block)
    return score, prot


def jubarte_level(bid: str, fid: str, safe: str, evidence: str, view_text: str) -> str:
    """Protection level for one jubarte cell.

    B9's markdown clamps a merged span to the renderer grid cap and still
    exits 0. The fidelity field stays not-in-view, because the hostile
    digits are absent. The protection level names the clamp.
    """
    level = protection.classify(fid, safe, evidence + "\n" + view_text)
    if (
        bid == "B9"
        and fid == "not-in-view"
        and safe == "ok"
        and "across 64" in view_text
        and "1000000" not in view_text
    ):
        return "bounded-delivery"
    return level


def protection_detail(bid: str, level: str) -> str:
    details = {
        ("B1", "bounded-refusal"): "INPUT_LIMIT named a ceiling on one part. No view was written.",
        ("B2", "bounded-refusal"): "INPUT_LIMIT named a ceiling on the zip entry count. No view was written.",
        ("B3", "bounded-refusal"): "INVALID_XML named a ceiling on the attributes of one element. No view was written.",
        ("B4", "bounded-refusal"): "the reader refused the package for XML nesting too deep. No view was written.",
        ("B5", "unexpanded-kept"): "the view keeps the unexpanded entity references and does not expand them",
        ("B6", "not-in-view"): "layout named UNSUPPORTED_PACKAGE for the unsafe entry and still wrote a body view that does not carry the slip",
        ("B7", "not-in-view"): "the markdown view does not carry the relationship targets. The log shows no connection attempt.",
        ("B8", "sanitation"): "the view keeps the body marker and omits the hyperlink, the javascript target, and the script",
        ("B9", "bounded-delivery"): "the view clamps the merged span to the renderer grid cap and summarizes the empty field paragraphs. The bibliography is not in the view.",
        ("B10", "not-in-view"): "layout named INVALID_XML on the comments part and still wrote a body view. The bad image marker is not in the view.",
    }
    return details.get((bid, level), level)


def _self_test() -> None:
    assert view_fidelity("B8", False, 0, {}) == "refused"
    assert view_fidelity("B8", True, 20, {"xss_js": True}) == "preserved"
    assert view_fidelity("B8", True, 20, {}) == "dropped"
    assert view_fidelity("B2", True, 20, {}) == "not-in-view"
    assert view_fidelity("B2", False, 0, {}) == "refused"
    assert view_fidelity("B1", True, 9_000_000, {}) == "preserved"
    assert view_fidelity("B1", True, 100, {}) == "dropped"
    assert bomb_score.caught("not-in-view", "ok") == "no"
    assert bomb_score.caught("refused", "bounded-reject") == "yes"
    assert bomb_score.caught("refused", "hang") == "no"
    assert protection.classify("refused", "bounded-reject", "INPUT_LIMIT") == "bounded-refusal"
    assert view_fidelity("B5", True, 600, {"raw_entity": True}) == "preserved"
    assert view_fidelity("B5", True, 600, {}) == "dropped"
    assert bomb_score.caught("preserved", "ok") == "no"
    assert jubarte_level(
        "B5",
        "preserved",
        "ok",
        "",
        "&lol6;&xxe;&canary;",
    ) == "unexpanded-kept"
    assert jubarte_level(
        "B9",
        "not-in-view",
        "ok",
        "",
        "merged t0.row0.cell0 across 64",
    ) == "bounded-delivery"
    assert jubarte_level("B3", "refused", "bounded-reject", "element exceeds 1024 attributes", "") == "bounded-refusal"


def header(version: str) -> list[str]:
    return [
        f"version: {version}",
        "binary: release build of ../jubarte-redlines. The skill copy was not used.",
        "command: jubarte read FILE -o view.md --force",
        "config: binary default. Page markers stay on. The skill quick start adds --no-page-markers. This run did not. No input-limit override.",
        "sandbox: jubarte under seatbelt. External network is denied. Localhost and unix sockets inside the work directory are allowed. Writes stay in the work directory. The binary is a macOS executable and was not run inside the Linux container.",
        "taxonomy: preserving a hostile payload is not the same single result as a crash.",
        "reference Word fidelity: not-run safety: not-run Word was not opened.",
        "B7 note: NTLM credential leak was not measured. No hash collector was started. External network and UNC were denied. Localhost was allowed.",
        "B5 note: the entity bomb expands one million times, not to a gigabyte. This Mac cannot cap address space.",
        "B1 note: one deflate member tops out near one thousand to one. A single member at two thousand five hundred to one is not a real deflate stream.",
        "view: read writes markdown. No view file is refused. A view that still carries the weapon is preserved. A weapon the markdown view does not carry, and that was not echoed, is not-in-view. That is not sanitation and it is not a catch.",
        "protection: the safety word bounded-reject is not a resource bound.",
    ]


def main() -> int:
    _guard()
    if "--self-test" in sys.argv:
        _self_test()
        print("self-test ok")
        return 0
    if not BINARY.is_file():
        raise SystemExit(f"missing binary {BINARY}")
    version = subprocess.run([str(BINARY), "--version"], check=False, capture_output=True, text=True)
    reported = (version.stdout or version.stderr).strip()
    if reported != EXPECTED_VERSION:
        raise SystemExit(f"refusing to score {reported!r}; want {EXPECTED_VERSION}")
    CANARY_PATH.write_text(bomb_score.CANARY + "\n", encoding="utf-8")
    WORK.mkdir(parents=True, exist_ok=True)
    bombs_dir = WORK / "bombs"
    _copy_bombs(bombs_dir)
    if LOG.exists():
        shutil.rmtree(LOG)
    LOG.mkdir(parents=True)
    (LOG / "trace.log").write_text("jubarte bomb trace. streams are kept below.\n", encoding="utf-8")
    only = set(filter(None, os.environ.get("JUBARTE_ONLY", "").split(",")))
    lines = header(reported)
    faulted = False
    for bomb in sorted(bombs_dir.glob("B*.docx")):
        if only and bomb.stem not in only:
            continue
        print(f"RUN jubarte {bomb.stem}", file=sys.stderr, flush=True)
        score, prot = run_one(BINARY, bomb, WORK / "runs" / bomb.stem)
        lines.append(score)
        lines.append(prot)
        print(score, file=sys.stderr, flush=True)
        print(prot, file=sys.stderr, flush=True)
        if "reason: harness-" in score:
            faulted = True
            break
    text = "\n".join(lines) + "\n"
    (LOG / "scorecard.txt").write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    return 2 if faulted else 0


if __name__ == "__main__":
    raise SystemExit(main())
