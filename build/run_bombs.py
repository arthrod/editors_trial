#!/usr/bin/env python3
"""Record the ten hostile vectors without building or opening one.

The suite is scheduled to run later, inside a sandbox. This process does not
build a bomb. setrlimit(RLIMIT_AS) cannot lower the address-space limit on
this macOS, and a lowered limit is still not permission to build one. Each
vector, and the Word and LibreOffice reference rows, has its own fidelity
field and its own safety field. Both are not-run.
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
    """Describe a temporary address-space limit attempt without running the suite.

    The original limit is restored after a successful attempt. A ValueError from
    setting the limit becomes a not-run reason; other resource errors propagate.
    """
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


REFERENCES = ("Word", "LibreOffice")


def lines() -> list[str]:
    """Return not-run records for each vector and reference application.

    The records include the result of the temporary address-space limit attempt.
    """
    reason = cap_reason()
    out = [
        f"platform: {platform.platform()}",
        reason,
        "scheduled: run later, sandboxed. This session did not build or open a hostile package.",
        (
            "taxonomy: preserving a hostile payload is not the same single result "
            "as a crash. This run recorded neither, because no vector was executed."
        ),
        (
            "defect_survival.py classifies structural defects in outputs of "
            "fixture/complex_broken.docx. It is not this suite, and it did not run B1-B10."
        ),
    ]
    for name in REFERENCES:
        out.append(
            f"reference {name} fidelity: not-run safety: not-run "
            f"{name} was not opened on a hostile package. {reason}"
        )
    for vid, title in VECTORS:
        extra = ""
        if vid == "B7":
            extra = " NTLM credential leak cannot be measured on macOS."
        out.append(
            f"{vid} SKIP not-run: {title}.{extra} fidelity: not-run safety: not-run {reason}"
        )
    return out


def main() -> None:
    """Print not-run records and optionally write them to the first CLI path."""
    text = "\n".join(lines()) + "\n"
    if len(sys.argv) > 1:
        with open(sys.argv[1], "w", encoding="utf-8") as fh:
            fh.write(text)
    sys.stdout.write(text)


if __name__ == "__main__":
    main()
