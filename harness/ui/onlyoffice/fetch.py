#!/usr/bin/env python3
"""Fetch the pinned OnlyOffice (CryptPad build) release archives and unpack the document editor.

usage: python3 -I harness/ui/onlyoffice/fetch.py

Two archives, as CryptPad publishes them:
  cryptpad/onlyoffice-editor    the editor (web-apps + sdkjs), co-editing socket replaced by page messages
  cryptpad/onlyoffice-x2t-wasm  OnlyOffice's converter (x2t) compiled to WebAssembly

Each is downloaded once into vendor/_archives/, checked against the SHA-512 its
release publishes (recorded below, so a pin is its bytes and not only its tag),
and unpacked unmodified into vendor/editor/ and vendor/x2t/. The spreadsheet,
presentation, PDF and Visio editors are left in the archive: the trial opens a
.docx. vendor/ is git-ignored; vendor/SOURCE.txt says what is in it.
"""
import hashlib
import sys
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
VENDOR = HERE / "vendor"

# The pin (AGENTS.md section 1: the newest release at least 5 days old).
PINS = {
    "editor": {
        "repo": "cryptpad/onlyoffice-editor",
        "tag": "v9.3.2+3",
        "published": "2026-09-29",
        "asset": "onlyoffice-editor.zip",
        "sha512": "181978176e443b9ff9cce127e6aa9668a4ee8e81473cb0c0c4cf0d83dea9b6636c730d40e704ebe8fdf313498a3106bafe5c4021ae937b269d05a07b7be6bbb4",
        # The other editors in the archive, not used to open a .docx.
        "skip": ("web-apps/apps/spreadsheeteditor/", "web-apps/apps/presentationeditor/", "web-apps/apps/pdfeditor/",
                 "web-apps/apps/visioeditor/", "sdkjs/cell/", "sdkjs/slide/", "sdkjs/pdf/", "sdkjs/visio/"),
    },
    "x2t": {
        "repo": "cryptpad/onlyoffice-x2t-wasm",
        "tag": "v9.3.2+4",
        "published": "2026-11-03",
        "asset": "x2t.zip",
        "sha512": "8fa965d86ef81c8615f2cc7c67eb0da270f88c573d137dcf82bb5b54d7ffacd66adb0e29f16b46a537279fc1c9ddf13ebc2b6e2f491c08cc4f266e6669763af6",
        "skip": (),
    },
}


def sha512(path: Path) -> str:
    h = hashlib.sha512()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def archive(name: str, pin: dict) -> Path:
    path = VENDOR / "_archives" / f"{name}-{pin['tag']}.zip"
    if not (path.exists() and sha512(path) == pin["sha512"]):
        path.parent.mkdir(parents=True, exist_ok=True)
        url = f"https://github.com/{pin['repo']}/releases/download/{urllib.parse.quote(pin['tag'])}/{pin['asset']}"
        print(f"downloading {url}", flush=True)
        urllib.request.urlretrieve(url, path)
        got = sha512(path)
        if got != pin["sha512"]:
            path.unlink()
            raise SystemExit(f"{name}: SHA-512 {got} is not the pinned {pin['sha512']}")
    return path


def unpack(name: str, pin: dict, path: Path) -> int:
    out = VENDOR / name
    stamp = out / ".unpacked"
    if stamp.exists() and stamp.read_text() == pin["sha512"]:
        # The stamp says the unpack finished, not that its files are still there: each member of
        # the archive must be in place at its size, or the whole archive is unpacked again.
        with zipfile.ZipFile(path) as z:
            members = [i for i in z.infolist() if not (i.is_dir() or i.filename.startswith(pin["skip"]))]
        lost = [i.filename for i in members if not ((out / i.filename).is_file() and (out / i.filename).stat().st_size == i.file_size)]
        if not lost:
            return -1
        print(f"{name}: {len(lost)} unpacked files missing or changed in size (first: {lost[0]}); unpacking again", flush=True)
    n = 0
    with zipfile.ZipFile(path) as z:
        for info in z.infolist():
            if info.is_dir() or info.filename.startswith(pin["skip"]):
                continue
            target = (out / info.filename).resolve()
            if out.resolve() not in target.parents:
                raise SystemExit(f"{name}: {info.filename} leaves the archive's folder")
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as src, target.open("wb") as dst:
                while block := src.read(1 << 20):
                    dst.write(block)
            n += 1
    stamp.write_text(pin["sha512"])
    return n


def main() -> int:
    lines = []
    for name, pin in PINS.items():
        n = unpack(name, pin, archive(name, pin))
        print(f"{name}: {pin['repo']} {pin['tag']} " + ("already unpacked" if n < 0 else f"{n} files unpacked"))
        lines.append(f"{name}: https://github.com/{pin['repo']} release {pin['tag']} (published {pin['published']}), "
                     f"{pin['asset']} sha512 {pin['sha512']}")
    (VENDOR / "SOURCE.txt").write_text("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
