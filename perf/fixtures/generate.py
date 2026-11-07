import hashlib
import random


def build_workload(profile):
    paragraphs = int(profile["paragraphs"])
    width = int(profile["paragraph_chars"])
    if paragraphs < 1 or width < 1:
        raise ValueError("workload shape")
    unicode_class = profile["unicode_class"]
    if unicode_class not in ("ascii", "mixed"):
        raise ValueError("unicode_class")
    match_count = int(profile["match_count"])
    if match_count < 0:
        raise ValueError("match_count")
    term = profile.get("search_term", "NEEDLE")
    needle = term.encode("utf-8")
    if match_count and (not term or needle in b" \n" or b"\n" in needle):
        raise ValueError("search_term")
    capacity = paragraphs * width
    if match_count and len(needle) * match_count > capacity:
        raise ValueError("match_count")
    if unicode_class == "mixed":
        marker = "e\u0301\U0002000b"
        lines = []
        for _ in range(paragraphs):
            chunk = ""
            while len(chunk) < width:
                chunk += marker
            lines.append(chunk[:width].encode("utf-8"))
    elif match_count:
        per_line, remainder = divmod(match_count, paragraphs)
        lines = []
        for index in range(paragraphs):
            count = per_line + (1 if index < remainder else 0)
            packed = needle * count
            if len(packed) > width:
                raise ValueError("match_count")
            lines.append(packed + b" " * (width - len(packed)))
    else:
        rng = random.Random(int(profile.get("seed", 0)))
        alphabet = "abcdefghijklmnopqrstuvwxyz "
        lines = []
        for _ in range(paragraphs):
            text = "".join(rng.choice(alphabet) for _ in range(width))
            lines.append(text.encode("ascii"))
    body = b"\n".join(lines) + b"\n"
    if match_count and body.count(needle) != match_count:
        raise ValueError("match_count")
    return {
        "workload_id": profile["workload_id"],
        "sha256": hashlib.sha256(body).hexdigest(),
        "body": body,
        "paragraphs": paragraphs,
        "unicode_class": unicode_class,
        "match_count": match_count,
        "search_term": term if match_count else None,
    }


def correctness_fixtures():
    return {
        "unicode": "cafe\u0301 \U0002000b\n".encode("utf-8"),
        "emoji": "family \U0001f468\u200d\U0001f469\u200d\U0001f467\u200d\U0001f466 tone \U0001f44d\U0001f3fb\n".encode("utf-8"),
        "bidi": "Hello مرحبا\n".encode("utf-8"),
        "ime_committed": "地\n".encode("utf-8"),
    }
