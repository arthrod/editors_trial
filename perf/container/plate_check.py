"""HF-only production Plate readiness check, using B1's build adapter."""
from pathlib import Path
import subprocess
from perf.runner.benchmark_warm_cold import BROWSER_TARGETS
from perf.runner.browser_hosts import build_host, StaticHost


def main():
    target = dict(BROWSER_TARGETS['plate'])
    meta = build_host('plate', target, Path('perf/container/out/plate-check'))
    from perf.fixtures.generate import docx_zip_bytes
    fixture = Path(meta['build_directory']).parent / 'ready.docx'
    fixture.write_bytes(docx_zip_bytes(b'<w:p><w:r><w:t>Production readiness check</w:t></w:r></w:p>'))
    host = StaticHost(meta['build_directory'], fixture=fixture)
    try:
        subprocess.run(['node', 'perf/container/plate_ready.mjs', host.url,
                        target.get('ready_selector', ''), target.get('ready_js', '')], check=True)
    finally:
        host.stop()


if __name__ == '__main__':
    main()
