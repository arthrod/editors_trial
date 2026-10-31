#!/usr/bin/env python3
"""Record the ten hostile vectors without building or opening one.

A resource cap is required before any bomb runs. On this macOS,
resource.setrlimit(RLIMIT_AS) cannot lower the address-space limit, so each
vector is an explicit skip. A skip is not a crash, a leak, a reject, or a
preserved payload.
"""
from __future__ import annotations

import platform
import resource
import sys

VECTORS = (
    ("B1", "Zip decompression bomb (ratio / total size)"),
    ("B2", "Zip entry flood"),
    ("B3", "XML attribute compression bomb"),
    ("B4", "Deep nesting of w:sdt and w:tbl"),
    ("B5", "Billion Laughs and XXE"),
    ("B6", "Zip-Slip path traversal"),
    ("B7", "SSRF / NTLM credential leak via external relationships"),
    ("B8", "XSS / active content"),
    ("B9", "Layout and combinatorial bombs (gridSpan, fields, bibliography)"),
    ("B10", "Corrupt secondary parts and bad PNG magic"),
)


def cap_reason() -> str:
    soft, hard = resource.getrlimit(resource.RLIMIT_AS)
    try:
        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, hard))
    except ValueError as exc:
        return (
            "not-run: resource.setrlimit(RLIMIT_AS) raised ValueError: "
            f"{exc}. platform={platform.platform()} "
            f"RLIMIT_AS soft={soft} hard={hard}. "
            "The hostile suite was not executed."
        )
    resource.setrlimit(resource.RLIMIT_AS, (soft, hard))
    return (
        "not-run: setrlimit(RLIMIT_AS) succeeded unexpectedly; "
        "the suite was still not executed, because this recorder does not build bombs. "
        f"platform={platform.platform()} RLIMIT_AS soft={soft} hard={hard}."
    )


def lines() -> list[str]:
    reason = cap_reason()
    out = [
        f"platform: {platform.platform()}",
        reason,
        (
            "taxonomy: preserving a hostile payload is not the same single result "
            "as a crash. This run recorded neither, because no vector was executed."
        ),
        (
            "defect_survival.py classifies structural defects in outputs of "
            "fixture/complex_broken.docx. It is not this suite, and it did not run B1-B10."
        ),
    ]
    for vid, title in VECTORS:
        extra = ""
        if vid == "B7":
            extra = " NTLM credential leak cannot be measured on macOS."
        out.append(f"{vid} SKIP not-run: {title}.{extra} {reason}")
    return out


def main() -> None:
    text = "\n".join(lines()) + "\n"
    if len(sys.argv) > 1:
        with open(sys.argv[1], "w", encoding="utf-8") as fh:
            fh.write(text)
    sys.stdout.write(text)


if __name__ == "__main__":
    main()
