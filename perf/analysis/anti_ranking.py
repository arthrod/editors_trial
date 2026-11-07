"""Reject prose that ranks editors by speed without required context."""

from __future__ import annotations

import re

# e.g. "3x faster than", "2× faster than Editor"
_SPEED_RANK = re.compile(
    r"\b\d+(\.\d+)?\s*[x×]\s*faster\s+than\b",
    re.IGNORECASE,
)


def assert_markdown_no_editor_speed_ranking(text: str) -> None:
    if _SPEED_RANK.search(text):
        raise ValueError(
            "faster-than comparison between editors without context: name "
            "workload, layer, cache state, and host or remove the comparison"
        )
