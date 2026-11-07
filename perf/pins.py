"""Release pins for performance harnesses — read from ``out/facts.json``."""

from __future__ import annotations

import json
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_FACTS = _REPO_ROOT / "out" / "facts.json"

# Keys aligned with ``out/facts.json`` (``ver.*`` namespace from the release pipeline).
_FACTS_KEYS = {
    "plate": ("ver.plate.commit",),
    "docxodus": ("ver.docxodus.commit", "ver.npm.docxodus"),
    "apryse": ("ver.npm.apryse",),
    "superdoc": ("ver.superdoc.commit", "ver.npm.superdoc_sdk", "ver.npm.superdoc_engine"),
    "folio": ("ver.folio.commit",),
    "genoffice": ("ver.genoffice.commit",),
    "eigenpal": ("ver.eigenpal-docx-editor.commit",),
    "office-open": ("ver.office-open.commit",),
    "docen": ("ver.docen.commit",),
    "wordcraft": ("ver.wordcraft.commit",),
    "fidus": ("ver.fiduswriter.commit", "ver.fiduswriter-document-ts.commit"),
    "canvas": ("ver.canvas-editor.commit", "ver.canvas-editor-plugin.commit"),
    "docsplus": ("ver.docs-plus.commit",),
    "libreoffice": (),
}

_LIBREOFFICE_FALLBACK = "system soffice"


def load_editor_pins(facts_path: Path | None = None) -> dict[str, str]:
    """Return ``editor_id`` -> human-readable version string from release facts."""
    path = facts_path or _DEFAULT_FACTS
    data = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    for editor_id, keys in _FACTS_KEYS.items():
        label = None
        parts = []
        for key in keys:
            val = data.get(key)
            if isinstance(val, str) and val.strip():
                parts.append(val.strip())
        if parts:
            label = "; ".join(parts)
        elif editor_id == "libreoffice":
            label = _LIBREOFFICE_FALLBACK
        else:
            raise ValueError("missing facts pin for editor %r (tried %s)" % (editor_id, keys))
        out[editor_id] = label
    return out
