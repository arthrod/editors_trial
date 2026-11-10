"""Pure validation and command planning for the HF-only container workflow."""
import re

EDITORS = ('plate eigenpal-docx-editor folio genoffice superdoc canvas-editor '
           'canvas-editor-plugin wordcraft docxodus docen office-open office-open-upstream '
           'docs-plus fiduswriter fiduswriter-document-ts fiduswriter-cli-ts '
           'fiduswriter-pandoc-plugin-ts').split()
INSTALLS = {
    'plate': ['pnpm', 'install', '--no-frozen-lockfile', '--ignore-scripts'],
    'eigenpal-docx-editor': ['bun', 'install'], 'folio': ['bun', 'install'],
    'genoffice': ['npm', 'install', '--no-audit', '--no-fund'],
    'canvas-editor': ['pnpm', 'install', '--no-frozen-lockfile'],
    'canvas-editor-plugin': ['pnpm', 'install', '--no-frozen-lockfile'],
}
RUNNERS = ('benchmark_warm_cold', 'benchmark_document', 'benchmark_input', 'adversarial_c10_scroll')
NPM = (
    ('superdoc_sdk', 'harness/superdoc-sdk', '@superdoc/sdk'),
    ('superdoc_engine', 'harness/superdoc-sdk', '@superdoc/docx-engine'),
    ('docxodus', 'harness/ui/docxodus', 'docxodus'),
    ('docxodus', 'harness/ui/docxodus', '@docxodus/export'),
    ('apryse', 'harness/apryse', '@pdftron/webviewer'),
)


def git_pins(facts, required=EDITORS):
    result = []
    for name in required:
        pin, slug = facts.get(f'ver.{name}.commit'), facts.get(f'ver.{name}.slug')
        if not isinstance(pin, str) or not re.fullmatch(r'[0-9a-f]{7,40}', pin):
            raise ValueError(f'missing or invalid commit: {name}')
        if not isinstance(slug, str) or not re.fullmatch(r'[\w-]+/[\w.-]+', slug):
            raise ValueError(f'missing or invalid slug: {name}')
        result.append((name, slug, pin))
    return result


def verify_commit(pin, full):
    if not re.fullmatch(r'[0-9a-f]{40}', full) or not full.startswith(pin):
        raise ValueError(f'commit mismatch: {pin} / {full}')
    return full


def verify_version(expected, actual):
    if not expected or expected != actual:
        raise ValueError(f'version mismatch: {expected} / {actual}')
    return actual


def npm_pins(facts):
    result = []
    for key, directory, package in NPM:
        version = facts.get('ver.npm.' + key)
        if not isinstance(version, str) or not re.fullmatch(r'\d+\.\d+\.\d+(?:-[\w.-]+)?', version):
            raise ValueError(f'missing or invalid npm pin: {key}')
        result.append((directory, package, version))
    return result


def publication_jobs(editors, seed, seed2, host_class):
    if not editors or seed == seed2 or host_class != 'shared_guarded':
        raise ValueError('publication requires editors, distinct seeds and shared_guarded')
    jobs = []
    for value in (seed, seed2):
        for runner in RUNNERS:
            base = ['--execution-profile', 'dedicated_publish', '--host-class', host_class, '--seed', str(value)]
            # C10 has a singular CLI; run_cli still interleaves its 30 repetitions.
            if runner == 'adversarial_c10_scroll':
                jobs.extend((runner, base + ['--editor', editor]) for editor in editors)
            else:
                jobs.append((runner, base + ['--editors', *editors]))
    return jobs


def verify_run(data):
    rendering = data.get('rendering') or {}
    if not data.get('run_id') or not rendering.get('renderer') or data.get('failure_reason'):
        raise ValueError('run evidence incomplete or failed')
    if any(row.get('outcome') == 'failed' for row in data.get('samples', [])):
        raise ValueError('run contains failed samples; inspect evidence before continuing')
    if rendering.get('headless') is not True:
        raise ValueError('headless rendering was not established')
    return data
