#!/usr/bin/env python3
"""Read logs/bombs and name the protection level of every cell.

Writes logs/bombs/protection.txt. Does not delete the bomb logs. A line has
no percentage and no byte size, so a report can quote it.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import protection

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "logs" / "bombs"

# First match wins. Specific tool phrases come before broad ones.
PHRASES = (
    ("compression_ratio_limit_exceeded", "named ceiling on compression ratio"),
    ("xml_depth_limit_exceeded", "named ceiling on element depth"),
    ("maxEntryBytes", "named ceiling on the size of one part"),
    ("exceeds maxEntries", "named ceiling on the number of parts"),
    ("maxXmlDepth", "named ceiling on element depth"),
    ("too-large", "named ceiling: too-large"),
    ("too-many-entries", "named ceiling: too-many-entries"),
    ("too-deep", "named ceiling: too-deep"),
    ("zip.maxRatio", "named ceiling: zip.maxRatio"),
    ("zip.maxEntries", "named ceiling: zip.maxEntries"),
    ("xml.maxDepth", "named ceiling: xml.maxDepth"),
    ("maximum compression ratio", "named ceiling on compression ratio"),
    ("too many entries", "named ceiling on the number of parts"),
    ("nested deeper than", "named ceiling on element depth"),
    ("Maximum nested tags exceeded", "named ceiling on nested tags"),
    ("XML nesting too deep", "named ceiling on element depth"),
    ("too many attributes", "named ceiling on attributes of one element"),
    ("parts exceeds the", "named ceiling on the number of parts"),
    ("INPUT_LIMIT", "named input limit"),
    ("document type declaration", "rejected a document type declaration"),
    ("DtdIsProhibited", "rejected a document type declaration"),
    ("External entities are not supported", "rejected an external entity"),
    ("unsupported or malformed entity", "rejected a malformed entity"),
    ("entity not found", "an entity was not found"),
    ("an entity is not defined", "an entity is not defined"),
    ("dtd-forbidden", "named rejection: dtd-forbidden"),
    ("bad-name", "named rejection: bad-name"),
    ("decode-failed", "the editor schema could not decode the package"),
    ("not valid UTF-8", "rejected XML that is not UTF-8"),
    ("limit exceeded", "named ceiling"),
    ("unsafe entry path", "rejected an unsafe entry path"),
    ("could not safely scan malformed markup", "preflight rejected malformed markup"),
    ("InvalidArgument", "the editor rejected the input and did not name a ceiling"),
    ("not one this API accepts", "the editor rejected the input and did not name a ceiling"),
    ("invalid-package", "rejected the package"),
    ("parse-error", "named rejection: parse-error"),
    ("Maximum call stack size exceeded", "the call stack ran out"),
    ("unterminated-child", "the opener reported unterminated markup"),
    ("malformed-start-tag", "the opener reported a malformed start tag"),
    ("no-document-root", "the opener reported no document root"),
    ("source loading is not applicable", "the opener said source loading does not apply"),
    ("source file could not be loaded", "soffice said the source file could not be loaded"),
    ("invalid tagName", "the xml parser rejected a tag"),
    ("styles.xml unparseable", "a styles part could not be parsed"),
    ("source-unavailable", "a source was unavailable"),
    ("element parse error", "the xml parser rejected the markup"),
)

_LIMIT = re.compile(r'limit: "([^"]+)"')


def usable_text(stdout: str, stderr: str) -> str:
    """Drop loader dumps and source listings.

    A stack frame prints the function source, and that source names every
    ceiling the function knows about. Those names are not the error.
    """
    kept = []
    for src in (stdout, stderr):
        for line in src.splitlines():
            if len(line) > 500 or " | " in line:
                continue
            kept.append(line)
    return "\n".join(kept)


def phrase_for(text: str, level: str) -> str:
    found = _LIMIT.search(text)
    if found and level == "bounded-refusal":
        return f"named ceiling: {found.group(1)}"
    for needle, phrase in PHRASES:
        if needle in text:
            return phrase
    if level == "sanitation":
        return "the written package does not carry the weapon"
    if level == "preserved":
        return "the weapon is still in the written package"
    if level == "hang":
        return "the run did not finish"
    if level == "crash":
        return "the process died"
    if level == "leak":
        return "file contents or a slipped file came out"
    if level == "failed-load-exit-zero":
        return "no document was written and the process exited zero"
    if level == "stack-exhaustion":
        return "the call stack ran out"
    if level == "not-in-view":
        return "the text view does not carry this weapon"
    if level == "not-run":
        return "no measurement"
    return "the cell log does not name a ceiling"


def main() -> int:
    rows = []
    for score_path in sorted(LOG.rglob("score.txt")):
        score = score_path.read_text(encoding="utf-8").strip().splitlines()
        if not score:
            continue
        line = score[0]
        parts = line.split()
        if len(parts) < 7 or parts[0] not in {"tool", "comparison"}:
            continue
        name, bid = parts[1], parts[2]
        fidelity = line.split("fidelity: ", 1)[1].split()[0]
        safety = line.split("safety: ", 1)[1].split()[0]
        folder = score_path.parent
        stdout = (folder / "stdout.txt").read_text(encoding="utf-8", errors="replace") if (folder / "stdout.txt").exists() else ""
        stderr = (folder / "stderr.txt").read_text(encoding="utf-8", errors="replace") if (folder / "stderr.txt").exists() else ""
        text = usable_text(stdout, stderr)
        level = protection.classify(fidelity, safety, text)
        detail = phrase_for(text, level)
        rows.append((name, bid, level, detail, fidelity, safety))
    order = [
        "libreoffice",
        "plate",
        "eigenpal",
        "eigenpal-editor",
        "folio",
        "folio-editor",
        "genoffice",
        "superdoc",
        "officeopen",
        "docen",
        "fidus",
        "wordcraft",
        "canvas",
        "docsplus",
        "docxodus",
    ]
    bombs = [f"B{n}" for n in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10)]
    by = {(name, bid): (level, detail) for name, bid, level, detail, _f, _s in rows}
    lines = [
        "protection: a named ceiling that refuses the package is bounded-refusal.",
        "protection: a clean exit whose output does not carry the weapon is sanitation.",
        "protection: a non-zero exit with no named ceiling is erroring.",
        "protection: a call stack that ran out is stack-exhaustion, not a ceiling.",
        "protection: a weapon still in the output is preserved.",
        "protection: hang, crash, and leak are separate.",
        "protection: failed-load-exit-zero wrote nothing and still exited zero.",
        "protection: the safety word bounded-reject is not a resource bound.",
    ]
    missing = []
    for name in order:
        for bid in bombs:
            item = by.get((name, bid))
            if item is None:
                missing.append(f"{name} {bid}")
                continue
            level, detail = item
            lines.append(f"protection {name} {bid} level: {level} detail: {detail}")
    text = "\n".join(lines) + "\n"
    out = LOG / "protection.txt"
    out.write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    if missing:
        sys.stderr.write("missing " + ", ".join(missing) + "\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
