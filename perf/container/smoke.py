"""Explicitly nonpublication fake-host adapter, without editing the runners.

The three multi-editor runners require a catalogued editor. Their plate driver
is exercised against a fake page; every run labels this substitution. No result
from this adapter is evidence about Plate or eligible for publication.
"""
import importlib
from pathlib import Path
import sys
from perf.runner.browser_run import BrowserRun, run_cli

FAKE = Path(__file__).parent / 'fake'


class SmokeRun(BrowserRun):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hosts['plate'] = {
            'host_build': 'fake_host', 'build_directory': str(FAKE.resolve()),
            'publishable': False, 'publication_block_reason': 'B6 fake page using plate driver, not Plate',
        }

    def finish(self, metadata):
        return super().finish({**metadata, 'smoke_fake_host': True,
                               'editor_identity_note': 'fake page; plate is only the driver alias', 'publishable': False})


def main():
    name = sys.argv.pop(1)
    from .policy import RUNNERS
    if name not in RUNNERS or '--execution-profile' not in sys.argv or sys.argv[sys.argv.index('--execution-profile') + 1] != 'ci_contract':
        raise ValueError('fake hosts are only allowed in ci_contract')
    from .run import read_run, verify_lane_profiles
    from .policy import verify_run
    # Save wrapper flags before the runner's parsers rewrite argv.
    options = list(sys.argv)
    directory = Path(options[options.index('--out-root') + 1]) / name / options[options.index('--run-id') + 1]
    profile = options[options.index('--execution-profile') + 1]
    host_class = options[options.index('--host-class') + 1] if '--host-class' in options else 'ci_coarse'
    module = importlib.import_module('perf.runner.' + name)
    if name == 'adversarial_c10_scroll':
        sys.argv += ['--fake-host', str(FAKE), '--fake-page', 'index.html']
        status = module.main()
        verify_lane_profiles(directory, profile, host_class)
        verify_run(read_run(directory))
        return status
    target = dict(module.BROWSER_TARGETS['plate'])
    target.update(url='http://127.0.0.1:5208/', ready_selector='.status-ok',
                  edit_selector='[contenteditable="true"]', ready_js='window.b6Ready === true')
    module.BROWSER_TARGETS['plate'] = target
    sys.argv += ['--editors', 'plate']
    flag = {'benchmark_warm_cold': '--pairs', 'benchmark_document': '--samples', 'benchmark_input': None}[name]
    status = run_cli(module._main, name, module.BROWSER_TARGETS, count_flag=flag, default_count=1, run_factory=SmokeRun)
    verify_lane_profiles(directory, profile, host_class)
    verify_run(read_run(directory))
    return status


if __name__ == '__main__':
    raise SystemExit(main())
