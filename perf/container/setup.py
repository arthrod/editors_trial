"""Install in the HF writable checkout only; dry-run performs no mutation/network."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shlex
import subprocess
from .policy import INSTALLS, harness_install, git_pins, npm_pins, verify_commit, verify_version


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--facts', type=Path, default=Path('out/facts.json'))
    args = parser.parse_args()
    facts = json.loads(args.facts.read_text())
    if not args.dry_run and Path('repos').is_symlink():
        raise ValueError('repos must be a writable private directory, not a symlink')
    pins, packages = git_pins(facts), npm_pins(facts)  # validate ALL before mutating
    record = {'commits': {}, 'npm': {}, 'tools': {}, 'apryse': {'not_run': 'licence key not exported'}}

    def command(cmd, cwd=Path('.'), capture=False):
        print(f'(cd {shlex.quote(str(cwd))} && {shlex.join(cmd)})', flush=True)
        if args.dry_run:
            return ''
        result = subprocess.run(cmd, cwd=cwd, check=True, text=True, capture_output=capture)
        return result.stdout.strip() if capture else ''

    for name, slug, pin in pins:
        path = Path('repos') / name
        print(f'clone {name} https://github.com/{slug}.git pin={pin} (resolve full SHA after fetch)')
        if not args.dry_run and path.is_symlink():
            raise ValueError(f'refusing shared checkout symlink: {path}')
        if not path.exists():
            command(['git', 'clone', '--no-checkout', f'https://github.com/{slug}.git', str(path)])
        else:
            if not args.dry_run and command(['git', 'status', '--porcelain'], path, True):
                raise ValueError(f'dirty checkout: {path}')
            command(['git', 'fetch', '--tags', 'origin'], path)
        full = command(['git', 'rev-parse', '--verify', pin + '^{commit}'], path, True)
        if not args.dry_run:
            full = verify_commit(pin, full)
        command(['git', 'checkout', '--detach', full or pin], path)
        if not args.dry_run:
            record['commits'][name] = verify_commit(pin, command(['git', 'rev-parse', 'HEAD'], path, True))
        if name in INSTALLS:
            command(INSTALLS[name], path)
    # Traverse tracked package manifests, never node_modules or editor symlinks.
    manifests = []
    for directory, children, files in os.walk('harness', followlinks=False):
        children[:] = sorted(name for name in children if name not in ('node_modules', '.git') and not (Path(directory) / name).is_symlink())
        if 'package.json' in files:
            manifests.append(str(Path(directory) / 'package.json'))
    for manifest in manifests:
        directory = Path(manifest).parent
        command(harness_install({path.name for path in directory.iterdir()}), directory)
    for directory, package, version in packages:
        command(['pnpm', 'add', '--save-exact', f'{package}@{version}'], Path(directory))
        actual = command(['node', '-p', f'JSON.parse(require("fs").readFileSync("node_modules/{package}/package.json")).version'], Path(directory), True)
        if not args.dry_run:
            record['npm'][package] = verify_version(version, actual)
    # harness/ui's frozen pnpm lock already pins Playwright 1.64.1.
    playwright = command(['node', '-p', 'require("playwright/package.json").version'], Path('harness/ui'), True)
    if not args.dry_run:
        record['npm']['playwright'] = verify_version('1.64.1', playwright)
    command(['cargo', 'build', '--release'], Path('harness/wordcraft'))
    command(['trunk', 'build', '--release'], Path('repos/wordcraft/apps/wordcraft-web'))
    for tool in ('git', 'node', 'npm', 'pnpm', 'bun', 'rustc', 'cargo', 'trunk', 'uv', 'python3'):
        record['tools'][tool] = command([tool, '--version'], capture=True)
    print('apryse: not_run: licence key not exported')
    if not args.dry_run:
        dest = Path('perf/container/out')
        dest.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        (dest / f'setup-{stamp}.json').write_text(json.dumps(record, indent=2) + '\n')


if __name__ == '__main__':
    main()
