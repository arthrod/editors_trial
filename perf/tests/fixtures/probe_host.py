"""Probe a scratch host through the real reflow probe, then score it."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HOSTS = REPO / "perf" / "tests" / "fixtures" / "hosts"
SCRATCH_HOSTS = Path(__file__).resolve().parent / "hosts"
PROBE = REPO / "perf" / "runner" / "document_probe.mjs"

sys.path.insert(0, str(REPO))
spec_server = REPO / "perf" / "tests" / "fixtures" / "witness" / "server.py"
import importlib.util

mod_spec = importlib.util.spec_from_file_location("witness_server", spec_server)
server_mod = importlib.util.module_from_spec(mod_spec)
mod_spec.loader.exec_module(server_mod)


def run(host_file: str, out: str, timeout_ms: int = 20000) -> dict:
    (REPO / ".scratch" / "tmp").mkdir(parents=True, exist_ok=True)
    server, _thread, base = server_mod.serve(SCRATCH_HOSTS if (SCRATCH_HOSTS / host_file).exists() else HOSTS)
    tmp = tempfile.TemporaryDirectory(dir=REPO / ".scratch" / "tmp")
    try:
        corpus = Path(tmp.name) / "corpus.docx"
        corpus.write_bytes(b"PK\x03\x04r3c12h")
        cmd = [
            "node", str(PROBE),
            "--mode", "reflow",
            "--url", "%s/%s" % (base, host_file),
            "--corpus", str(corpus),
            "--doc-selector", ".doc-paragraph",
            "--page-model", "continuous_flow",
            "--edit-selector", ".doc-paragraph",
            "--timeout-ms", str(timeout_ms),
        ]
        proc = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True, timeout=90)
    finally:
        server.shutdown()
        server.server_close()
        tmp.cleanup()
    if proc.returncode != 0:
        raise SystemExit("probe failed rc=%d\n%s\n%s" % (proc.returncode, proc.stdout, proc.stderr))
    payload = json.loads(proc.stdout)
    Path(out).write_text(json.dumps(payload, indent=2))
    return payload


if __name__ == "__main__":
    import perf.runner.benchmark_document as bd

    for host in sys.argv[1:]:
        payload = run(host, REPO / ".scratch" / "review" / ("%s.json" % host.replace("/", "_")))
        try:
            sample = bd.c12_measured_sample(payload)
            print("%s: MEASURED %r ms" % (host, sample))
        except bd.ProbeRefusal as refusal:
            print("%s: REFUSED %s (code=%r)" % (host, refusal.reason, refusal.refusal_code))
        print(
            "  moved=%r shift_at=%r input=%r presented=%r matched_by=%r reads=%r frames=%r"
            % (
                payload.get("moved"),
                payload.get("observed_shift_page_ms"),
                payload.get("input_page_ms"),
                payload.get("presented_frame_ms"),
                payload.get("matched_by"),
                payload.get("layout_reads_during_window"),
                payload.get("anchor_frames"),
            )
        )
