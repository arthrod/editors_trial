"""Editor lane capability registry (design overrides + unverified default)."""

from functools import lru_cache

from perf.pins import load_editor_pins

LANES = {
    "plate": ("headless_docx", "browser_slate"),
    "docxodus": ("session", "wasm_editor"),
    "apryse": ("webviewer",),
    "superdoc": ("sdk", "browser"),
    "folio": ("model", "editor"),
    "genoffice": ("editor",),
    "eigenpal": ("store", "server", "browser"),
    "office-open": ("library",),
    "docen": ("editor",),
    "wordcraft": ("docx_crate", "native_ui", "wasm_ui"),
    "fidus": ("document", "app"),
    "canvas": ("editor",),
    "docsplus": ("conversion", "app"),
    "libreoffice": ("headless", "gui"),
}

OVERRIDES = {
    ("plate", "headless_docx", "pagination"): "not_applicable",
    ("plate", "headless_docx", "hit_testing"): "not_applicable",
    ("plate", "headless_docx", "collaboration"): "not_applicable",
    ("plate", "headless_docx", "wasm"): "not_applicable",
    ("plate", "headless_docx", "typing"): "not_applicable",
    ("plate", "headless_docx", "visible_paint"): "not_applicable",
    ("plate", "headless_docx", "ime"): "not_applicable",
    ("plate", "headless_docx", "save"): "supported",
    ("plate", "browser_slate", "pagination"): "not_applicable",
    ("plate", "browser_slate", "collaboration"): "supported",
    ("plate", "browser_slate", "wasm"): "not_applicable",
    ("plate", "browser_slate", "typing"): "supported",
    ("plate", "browser_slate", "visible_paint"): "supported",
    ("office-open", "library", "pagination"): "not_applicable",
    ("office-open", "library", "hit_testing"): "not_applicable",
    ("office-open", "library", "typing"): "not_applicable",
    ("office-open", "library", "visible_paint"): "not_applicable",
    ("office-open", "library", "ime"): "not_applicable",
    ("office-open", "library", "wasm"): "not_applicable",
    ("office-open", "library", "collaboration"): "unverified",
    ("office-open", "library", "save"): "supported",
    ("docsplus", "app", "collaboration"): "supported",
    ("docsplus", "app", "pagination"): "not_applicable",
    ("docsplus", "conversion", "collaboration"): "not_applicable",
    ("docsplus", "conversion", "visible_paint"): "not_applicable",
    ("docsplus", "conversion", "typing"): "not_applicable",
    ("canvas", "editor", "collaboration"): "unverified",
    ("canvas", "editor", "hit_testing"): "supported",
    ("canvas", "editor", "wasm"): "not_applicable",
    ("wordcraft", "native_ui", "ime"): "supported",
    ("wordcraft", "native_ui", "undo"): "supported",
    ("docxodus", "session", "undo"): "supported",
    ("plate", "browser_slate", "undo"): "supported",
    ("wordcraft", "native_ui", "collaboration"): "unverified",
    ("wordcraft", "native_ui", "hit_testing"): "supported",
    ("wordcraft", "native_ui", "pagination"): "supported",
    ("wordcraft", "native_ui", "wasm"): "not_applicable",
    ("wordcraft", "docx_crate", "visible_paint"): "not_applicable",
    ("wordcraft", "docx_crate", "typing"): "not_applicable",
    ("wordcraft", "docx_crate", "pagination"): "not_applicable",
    ("wordcraft", "wasm_ui", "wasm"): "supported",
    ("docxodus", "wasm_editor", "wasm"): "supported",
    ("docxodus", "session", "visible_paint"): "not_applicable",
    ("docxodus", "session", "save"): "supported",
    ("apryse", "webviewer", "wasm"): "supported",
    ("apryse", "webviewer", "save"): "supported",
    ("superdoc", "sdk", "visible_paint"): "not_applicable",
    ("superdoc", "sdk", "save"): "supported",
    ("superdoc", "browser", "pagination"): "supported",
    ("folio", "model", "visible_paint"): "not_applicable",
    ("folio", "model", "save"): "supported",
    ("genoffice", "editor", "pagination"): "supported",
    ("eigenpal", "store", "visible_paint"): "not_applicable",
    ("eigenpal", "store", "save"): "supported",
    ("eigenpal", "server", "visible_paint"): "not_applicable",
    ("docen", "editor", "pagination"): "supported",
    ("fidus", "document", "collaboration"): "not_applicable",
    ("fidus", "document", "pagination"): "not_applicable",
    ("fidus", "document", "visible_paint"): "not_applicable",
    ("fidus", "app", "collaboration"): "unverified",
    ("fidus", "app", "pagination"): "not_applicable",
    ("libreoffice", "headless", "typing"): "not_applicable",
    ("libreoffice", "headless", "visible_paint"): "not_applicable",
    ("libreoffice", "headless", "save"): "supported",
    ("libreoffice", "gui", "typing"): "unverified",
}

FEATURES = (
    "pagination",
    "hit_testing",
    "collaboration",
    "wasm",
    "typing",
    "visible_paint",
    "ime",
    "save",
    "undo",
)

EVIDENCE = {
    ("plate", "browser_slate", "collaboration"): "optional Yjs plugin; not probed on pin 64123fe51",
    ("plate", "browser_slate", "visible_paint"): "available surface, not a verified measurement hook",
    ("canvas", "editor", "collaboration"): "feature/CRDT is not pin 68f1a4175",
    ("apryse", "webviewer", "wasm"): "closed source at npm 12.2.1; host-visible init only",
    ("superdoc", "browser", "pagination"): "current docs, not re-read on pin 71961c61f",
    ("fidus", "document", "collaboration"): "document package pin dc0981db4 has no collab surface",
    ("fidus", "app", "collaboration"): "full app was not the measured pin",
}


@lru_cache(maxsize=1)
def editor_pins():
    return load_editor_pins()


def pin_label(editor_id: str) -> str:
    return editor_pins()[editor_id]


def lanes():
    return dict(LANES)


def capability(editor_id, lane, feature):
    if feature not in FEATURES:
        raise ValueError("unknown feature %r" % (feature,))
    known = LANES.get(editor_id)
    if known is None or lane not in known:
        raise ValueError("unknown lane %s/%s" % (editor_id, lane))
    return OVERRIDES.get((editor_id, lane, feature), "unverified")


def capability_evidence(editor_id, lane, feature):
    state = capability(editor_id, lane, feature)
    note = EVIDENCE.get(
        (editor_id, lane, feature),
        "no probe recorded for pin %s" % (pin_label(editor_id),),
    )
    if feature == "visible_paint" and state == "supported" and "measurement hook" not in note:
        note = "available surface, not a verified measurement hook"
    return {"pin": pin_label(editor_id), "state": state, "note": note}


def default_lane(editor_id: str) -> str:
    lane_list = LANES.get(editor_id)
    if not lane_list:
        raise ValueError("unknown editor %r" % (editor_id,))
    return lane_list[0]
