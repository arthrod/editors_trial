"""E2 later campaign: the container setup installs every later editor's page.

react-docx, BetterOffice and Nutrient install through their pnpm locks (the
manifest walk). OnlyOffice's page needs its pinned release trees
(harness/ui/onlyoffice/fetch.py) and OpenDoc's needs its pinned checkout
(repos/opendoc, facts ver.opendoc.commit) plus the engine build
(harness/ui/opendoc/fetch_engine.py). Before this, setup did neither, so both
pages would have refused on a fresh Space.
"""
import subprocess


def _dry_run():
    result = subprocess.run(['bash', 'perf/container/setup.sh', '--dry-run'], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result.stdout


def test_setup_clones_opendoc_at_its_pin():
    out = _dry_run()
    assert 'clone opendoc https://github.com/CasualOffice/opendoc.git pin=' in out


def test_setup_fetches_both_vendor_trees_after_the_clones():
    out = _dry_run()
    for script in ('harness/ui/onlyoffice/fetch.py', 'harness/ui/opendoc/fetch_engine.py'):
        line = '(cd . && python3 -I %s)' % script
        assert line in out, script
        assert out.index('clone opendoc') < out.index(line)


def test_setup_installs_the_pnpm_pages():
    out = _dry_run()
    for page in ('harness/ui/react-docx', 'harness/ui/betteroffice', 'harness/ui/nutrient'):
        assert '(cd %s && pnpm install --frozen-lockfile)' % page in out, page
