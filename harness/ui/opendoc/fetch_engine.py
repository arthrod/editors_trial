#!/usr/bin/env python3
"""Put OpenDoc's built engine (webapp/pkg) next to its pinned checkout.

usage: python3 -I harness/ui/opendoc/fetch_engine.py [<checkout, default repos/opendoc>]

OpenDoc's editor is a website (CasualOffice/opendoc, `webapp/`), not a package;
its engine is Rust compiled to WebAssembly by `webapp/build.sh` into
`webapp/pkg/`, which the repository does not carry (webapp/.gitignore). The
trial's pin is a commit; the engine for that commit is the one the vendor's own
Pages workflow built from it and published at opendoc.casualoffice.org.

This script takes that build, and only that build: it downloads the two engine
files and refuses them unless their SHA-256 are the ones recorded here, which
were read on 2026-11-21 while GitHub's deployments API reported the pinned
commit as the site's latest `github-pages` deployment. When the site has moved
on, the hashes no longer match and the engine has to be built from the checkout
instead (`webapp/build.sh`: Rust 1.96.0, wasm-pack, binaryen).
Nothing tracked in the checkout is changed: `webapp/pkg/` is build output.

OPENDOC_ENGINE_DIR names a folder holding a copy of those two files, read before
the site: a file there is taken only if its SHA-256 is the pinned one. The site
moved on on 2026-11-22, so the Spaces of the later campaign get the pinned build
copied from a machine that fetched it while the site still served it.
"""
import os
import shutil
import hashlib
import sys
import urllib.request
from pathlib import Path

PIN = "5ac261ceadbb0fa0bcbe729ce3c2e20721756949"  # CasualOffice/opendoc main, 2026-11-05
SITE = "https://opendoc.casualoffice.org/pkg/"
FILES = {
    "casual_doc_wasm.js": "b278eaa8a71f51544605cf7d0060797913c6e70427807f7c0d25482230a9a30e",
    "casual_doc_wasm_bg.wasm": "7b2904eceefd74188096d9f2ec56c17952a658c95efba52d80048fac706023ee",
}


def main() -> int:
    root = Path(__file__).resolve().parents[3]
    checkout = Path(sys.argv[1]) if len(sys.argv) > 1 else root / "repos" / "opendoc"
    head = (checkout / ".git").exists() and __import__("subprocess").run(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    if head != PIN:
        raise SystemExit(f"{checkout} is at {head or 'no commit'}, not the pin {PIN}")
    pkg = checkout / "webapp" / "pkg"
    pkg.mkdir(exist_ok=True)
    for name, want in FILES.items():
        path = pkg / name
        if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == want:
            print(f"{name}: present")
            continue
        copy = Path(os.environ["OPENDOC_ENGINE_DIR"]) / name if os.environ.get("OPENDOC_ENGINE_DIR") else None
        if copy is not None and copy.is_file() and hashlib.sha256(copy.read_bytes()).hexdigest() == want:
            shutil.copyfile(copy, path)
            print(f"{name}: copied from {copy.parent} (the pinned build, SHA-256 checked)")
            continue
        req = urllib.request.Request(SITE + name, headers={"User-Agent": "docx-benchmark-harness"})
        try:
            data = urllib.request.urlopen(req, timeout=120).read()
        except OSError as e:  # URLError, HTTPError and a stalled connection's timeout are all OSError
            raise SystemExit(f"{name}: could not download {SITE + name}: {e}")
        got = hashlib.sha256(data).hexdigest()
        if got != want:
            raise SystemExit(f"{name}: the site now serves {got}, not the pinned build {want}; "
                             f"build the engine from the checkout with webapp/build.sh")
        path.write_bytes(data)
        print(f"{name}: fetched, {len(data)} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
