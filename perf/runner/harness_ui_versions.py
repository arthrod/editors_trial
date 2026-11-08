"""Npm/git versions actually served by harness/ui browser hosts."""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
UI = REPO / "harness" / "ui"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def superdoc_served() -> dict[str, str]:
    """Return npm ``superdoc`` and ``@superdoc/docx-engine`` resolved in the UI host."""
    root = UI / "superdoc"
    pkg = _read_json(root / "package.json")
    superdoc_ver = str((pkg.get("dependencies") or {}).get("superdoc", "")).strip()
    engine_ver = ""
    lock_path = root / "package-lock.json"
    if lock_path.is_file():
        lock = _read_json(lock_path)
        packages = lock.get("packages") or {}
        for key, meta in packages.items():
            if key.endswith("node_modules/@superdoc/docx-engine") or key == "node_modules/@superdoc/docx-engine":
                engine_ver = str(meta.get("version", "")).strip()
                break
        if not engine_ver:
            deps = (lock.get("dependencies") or {}).get("superdoc") or {}
            engine_ver = str(deps.get("@superdoc/docx-engine", "")).strip()
    return {"superdoc": superdoc_ver, "docx_engine": engine_ver}


def docxodus_served() -> dict[str, str]:
    pkg = _read_json(UI / "docxodus" / "package.json")
    return {
        "docxodus": str((pkg.get("dependencies") or {}).get("docxodus", "")).strip(),
    }


def browser_harness_editor_version(editor_id: str, trial_pin: str) -> tuple[str, dict | None]:
    """
    ``editor_version`` for warm_cold browser attempts: trial pin when it matches served bits,
    otherwise the served npm label plus trial-pin metadata for the summary.
    """
    if editor_id == "docxodus":
        served = docxodus_served()["docxodus"]
        parts = [p.strip() for p in trial_pin.split(";") if p.strip()]
        commit = parts[0] if parts else ""
        trial_npm = parts[1] if len(parts) > 1 else ""
        label = "; ".join(p for p in (commit, served) if p)
        meta = None
        if trial_npm and served and trial_npm != served:
            meta = {
                "harness_served": {"docxodus": served},
                "trial_pin": trial_pin,
                "trial_pin_mismatch": "npm docxodus %s served as %s" % (trial_npm, served),
            }
        return label, meta

    if editor_id == "superdoc":
        served = superdoc_served()
        parts = [p.strip() for p in trial_pin.split(";") if p.strip()]
        commit = parts[0] if parts else ""
        trial_sdk = parts[1] if len(parts) > 1 else ""
        trial_engine = parts[2] if len(parts) > 2 else ""
        label = "; ".join(
            p
            for p in (
                commit,
                "superdoc@%s" % served["superdoc"] if served["superdoc"] else "",
                "@superdoc/docx-engine@%s" % served["docx_engine"] if served["docx_engine"] else "",
            )
            if p
        )
        mismatches = []
        if trial_sdk and served["superdoc"] and trial_sdk != served["superdoc"]:
            mismatches.append(
                "trial @superdoc/sdk pin %s; browser host serves npm superdoc@%s (no superdoc@%s on npm)"
                % (trial_sdk, served["superdoc"], trial_sdk)
            )
        if trial_engine and served["docx_engine"] and trial_engine != served["docx_engine"]:
            mismatches.append(
                "trial engine pin %s; harness serves @superdoc/docx-engine@%s"
                % (trial_engine, served["docx_engine"])
            )
        meta = {
            "harness_served": served,
            "trial_pin": trial_pin,
        }
        if mismatches:
            meta["trial_pin_mismatch"] = "; ".join(mismatches)
        return label, meta

    if editor_id == "genoffice":
        return trial_pin, None

    return trial_pin, None
