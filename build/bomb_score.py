#!/usr/bin/env python3
"""Classify one tool run. Fidelity and safety stay separate fields.

catch is yes only when the hostile marker was refused or dropped and the
process did not crash, hang, or leak. Preserving the marker is not a catch.
A crash is not a catch either.
"""
from __future__ import annotations

import zipfile
from pathlib import Path

from make_bombs import BODY, LOL, PNG_MARK, SLIP, SSRF, UNC, XSS_JS, XSS_MARK

PASSWD_MARK = "Unprivileged User"
PASSWD_LINUX = "root:x:0:0"
HOSTS_MARK = "broadcasthost"
HOSTS_LINUX = "ip6-localhost"
CANARY = "XXE_CANARY_editors_trial"
LEAK_MARKS = (CANARY, PASSWD_MARK, PASSWD_LINUX, HOSTS_MARK, HOSTS_LINUX)


def _text(data: bytes | None) -> str:
    if not data:
        return ""
    return data.decode("utf-8", "replace")


def leaked_text(text: str) -> bool:
    return any(mark in text for mark in LEAK_MARKS)


def _document_size(data: bytes) -> int:
    try:
        with zipfile.ZipFile(io_bytes(data)) as zf:
            info = zf.getinfo("word/document.xml")
            return info.file_size
    except (KeyError, zipfile.BadZipFile):
        return len(data)


def io_bytes(data: bytes):
    import io

    return io.BytesIO(data)


def _names(data: bytes) -> list[str]:
    try:
        with zipfile.ZipFile(io_bytes(data)) as zf:
            return zf.namelist()
    except zipfile.BadZipFile:
        return []


def _inside(data: bytes, limit: int = 2_000_000) -> str:
    """Text of the file and of modest zip members. A huge member is not inflated."""
    parts = [data[:limit]]
    try:
        with zipfile.ZipFile(io_bytes(data)) as zf:
            for info in zf.infolist():
                if info.is_dir() or info.file_size > 8 * 1024 * 1024:
                    continue
                with zf.open(info) as handle:
                    parts.append(handle.read(limit))
    except zipfile.BadZipFile:
        pass
    return b"\n".join(parts).decode("utf-8", "replace")


def fidelity(bomb_id: str, data: bytes | None) -> str:
    """preserved means the hostile construct is still in the output.

    A package that forwards the bomb unchanged is preserved. That is not a
    catch. dropped means an output exists and the construct is gone. refused
    means there was no output.
    """
    if not data:
        return "refused"
    # An output this large already failed to contain the bomb.
    if bomb_id in {"B3", "B5", "B9"} and len(data) > 32 * 1024 * 1024:
        return "preserved"
    if bomb_id == "B5" and data.count(LOL.encode("ascii")) > 20:
        return "preserved"
    text = _inside(data)
    if bomb_id == "B1":
        return "preserved" if _document_size(data) > 8 * 1024 * 1024 else "dropped"
    if bomb_id == "B2":
        extra = [n for n in _names(data) if n.startswith("customXml/p")]
        return "preserved" if len(extra) > 1000 else "dropped"
    if bomb_id == "B3":
        return "preserved" if text.count("bombAttr") > 1000 else "dropped"
    if bomb_id == "B4":
        return "preserved" if "DEEP_LEAF" in text or "TBL_LEAF" in text else "dropped"
    if bomb_id == "B5":
        forwarded = LOL in text or "<!ENTITY" in text or "file:///etc/hosts" in text
        expanded = text.count(LOL) > 20 or leaked_text(text)
        return "preserved" if forwarded or expanded else "dropped"
    if bomb_id == "B6":
        traversal = any(".." in name for name in _names(data))
        forwarded = (
            SLIP in text
            or "etc/passwd" in text
            or "etc/hosts" in text
            or traversal
            or leaked_text(text)
        )
        return "preserved" if forwarded else "dropped"
    if bomb_id == "B7":
        return "preserved" if SSRF in text or "leak.dotm" in text or UNC in text else "dropped"
    if bomb_id == "B8":
        return "preserved" if XSS_JS in text or XSS_MARK in text else "dropped"
    if bomb_id == "B9":
        kept = "1000000" in text or text.count("fldChar") > 100 or text.count("b:Source") > 100
        return "preserved" if kept else "dropped"
    if bomb_id == "B10":
        raw_parts = [data]
        try:
            with zipfile.ZipFile(io_bytes(data)) as zf:
                for info in zf.infolist():
                    if info.is_dir() or info.file_size > 8 * 1024 * 1024:
                        continue
                    raw_parts.append(zf.read(info))
        except zipfile.BadZipFile:
            pass
        if any(PNG_MARK.encode("ascii") in part or b"\xff\xfe" in part for part in raw_parts):
            return "preserved"
        return "dropped"
    return "refused"


def safety(returncode: int, timed_out: bool, leak: bool) -> str:
    if timed_out or returncode == 124:
        return "hang"
    if returncode < 0 or returncode >= 128:
        return "crash"
    if leak:
        return "leak"
    if returncode != 0:
        return "bounded-reject"
    return "ok"


def caught(fid: str, safe: str) -> str:
    if fid == "not-run" or safe == "not-run":
        return "no"
    if safe in {"crash", "hang", "leak"}:
        return "no"
    if fid in {"refused", "dropped"}:
        return "yes"
    return "no"


def line(role: str, name: str, bomb_id: str, fid: str, safe: str) -> str:
    return (
        f"{role} {name} {bomb_id} fidelity: {fid} safety: {safe} "
        f"catch: {caught(fid, safe)}"
    )


def escaped(root: Path, out_dir: Path, slip_name: str) -> list[Path]:
    """Files written outside the designated output directory."""
    found = []
    root = root.resolve()
    out_dir = out_dir.resolve()
    if not root.exists():
        return found
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.name != slip_name and SLIP not in path.read_bytes()[:200].decode("utf-8", "replace"):
            continue
        try:
            path.resolve().relative_to(out_dir)
        except ValueError:
            found.append(path)
    return found
