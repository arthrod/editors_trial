"""Storage Bucket upload of every sealed job (issue #162, r3bucket).

A fake in-memory bucket client is injected through mirror.BUCKET_CLIENT_FACTORY;
no test touches the network.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest


def sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


class FakeBucketClient:
    """Stand-in for the HfApi calls mirror.py uses."""

    def __init__(self):
        self.files: dict[str, bytes] = {}
        self.calls: list[tuple] = []
        self.fail_on_batch = False
        self.fail_on_list = False
        self.drop_dests: set[str] = set()

    def list_bucket_tree(self, bucket_id, prefix=None, *, recursive=None, token=None):
        self.calls.append(('list', prefix))
        if self.fail_on_list:
            raise RuntimeError('simulated list failure')
        for path in sorted(self.files):
            if prefix is None or path.startswith(prefix):
                data = self.files[path]
                yield SimpleNamespace(type='file', path=path, size=len(data))

    def batch_bucket_files(self, bucket_id, *, add=None, copy=None, delete=None, token=None):
        self.calls.append(('batch', sorted(dest for _s, dest in (add or []))))
        if self.fail_on_batch:
            raise RuntimeError('simulated upload failure')
        for src, dest in add or []:
            if dest in self.drop_dests:
                continue
            self.files[dest] = Path(src).read_bytes()

    def download_bucket_files(self, bucket_id, *, files=None, token=None):
        self.calls.append(('download', sorted(r for r, _l in (files or []))))
        for remote_path, local in files or []:
            local = Path(local)
            local.parent.mkdir(parents=True, exist_ok=True)
            local.write_bytes(self.files[remote_path])


def seal_job(remote: Path, run_id: str, runner: str, job_id: str, files: dict[str, str], status: int = 0) -> Path:
    job = remote / 'runs' / run_id / runner / job_id
    job.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        path = job / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    from perf.container import artifacts

    artifacts.finalize_job(job, status)
    return job


@pytest.fixture
def bucket_env(tmp_path, monkeypatch):
    from perf.container import mirror

    client = FakeBucketClient()
    monkeypatch.setattr(mirror, 'BUCKET_CLIENT_FACTORY', lambda token: client)
    monkeypatch.setenv('HF_BUCKET_TOKEN', 'unit-test-token')
    monkeypatch.setenv('SPACE_ID', 'arthrod/e2-publish')
    monkeypatch.setenv('HF_MIRROR_ROOT', str(tmp_path / 'mirror'))
    monkeypatch.delenv('HF_BUCKET_ID', raising=False)
    return client


def campaign_root(remote: Path, run_id: str) -> Path:
    return remote / 'runs' / run_id


def bucket_lines(run_log: Path, job: str | None = None):
    lines = [
        line for line in run_log.read_text().splitlines()
        if line.startswith(('BUCKET-OK ', 'BUCKET-ERROR '))
    ]
    if job is not None:
        lines = [line for line in lines if line.split(' ', 2)[1] == job]
    return lines


class TestUploadOnSeal:
    def test_sealed_job_uploads_under_space_run_prefix(self, tmp_path, bucket_env):
        from perf.container import mirror

        remote = tmp_path / 'remote'
        run_id = 'camp-1'
        job_dir = seal_job(
            remote, run_id, 'benchmark_warm_cold', f'{run_id}-000',
            {'summary.json': '{"samples": []}', 'cells/c1/attempts/a.json': '{}'},
        )
        campaign = campaign_root(remote, run_id)
        run_log = campaign / 'RUN.log'
        mirror.mirror_job_directory(run_id, 'benchmark_warm_cold', f'{run_id}-000', job_dir, run_log)
        prefix = 'runs/arthrod/e2-publish/camp-1/benchmark_warm_cold/camp-1-000'
        for name in ('summary.json', 'cells/c1/attempts/a.json', 'MANIFEST.sha256', 'JOB-DONE'):
            assert bucket_env.files[f'{prefix}/{name}'] == (job_dir / name).read_bytes(), name

    def test_campaign_level_files_upload_to_run_prefix(self, tmp_path, bucket_env):
        from perf.container import mirror

        remote = tmp_path / 'remote'
        run_id = 'camp-2'
        campaign = campaign_root(remote, run_id)
        job_dir = seal_job(remote, run_id, 'benchmark_input', f'{run_id}-000', {'summary.json': '{}'})
        run_log = campaign / 'RUN.log'
        run_log.write_text('first line\n')
        (campaign / 'RUN-DONE').write_text('exit_status=0\n')
        out_dir = campaign / 'out'
        out_dir.mkdir()
        (out_dir / 'e2-publication.json').write_text('{"runs": []}')
        mirror.mirror_job_directory(run_id, 'benchmark_input', f'{run_id}-000', job_dir, run_log)
        prefix = 'runs/arthrod/e2-publish/camp-2'
        assert (run_log.read_bytes()) == bucket_env.files[f'{prefix}/RUN.log']
        assert bucket_env.files[f'{prefix}/RUN-DONE'] == b'exit_status=0\n'
        assert bucket_env.files[f'{prefix}/out/e2-publication.json'] == b'{"runs": []}'

    def test_tail_uploads_jobs_and_campaign_files(self, tmp_path, bucket_env):
        from perf.container import mirror

        remote = tmp_path / 'remote'
        run_id = 'camp-3'
        campaign = campaign_root(remote, run_id)
        seal_job(remote, run_id, 'runner_a', f'{run_id}-000', {'summary.json': '{}'})
        seal_job(remote, run_id, 'runner_b', f'{run_id}-001', {'summary.json': '{}'})
        run_log = campaign / 'RUN.log'
        run_log.write_text('tail\n')
        (campaign / 'RUN-DONE').write_text('exit_status=0\n')
        mirror.mirror_campaign_tail(campaign, run_id, run_log)
        prefix = f'runs/arthrod/e2-publish/{run_id}'
        assert f'{prefix}/runner_a/{run_id}-000/summary.json' in bucket_env.files
        assert f'{prefix}/runner_b/{run_id}-001/summary.json' in bucket_env.files
        assert bucket_env.files[f'{prefix}/RUN-DONE'] == b'exit_status=0\n'
        assert bucket_env.files[f'{prefix}/RUN.log'] == run_log.read_bytes()

    def test_space_name_falls_back_to_hostname(self, tmp_path, bucket_env, monkeypatch):
        import socket

        from perf.container import mirror

        monkeypatch.delenv('SPACE_ID')
        monkeypatch.setattr(socket, 'gethostname', lambda: 'mac-box-9')
        remote = tmp_path / 'remote'
        run_id = 'camp-4'
        job_dir = seal_job(remote, run_id, 'runner_a', f'{run_id}-000', {'summary.json': '{}'})
        mirror.mirror_job_directory(run_id, 'runner_a', f'{run_id}-000', job_dir,
                                    campaign_root(remote, run_id) / 'RUN.log')
        assert f'runs/mac-box-9/{run_id}/runner_a/{run_id}-000/summary.json' in bucket_env.files

    def test_unsealed_job_is_not_uploaded(self, tmp_path, bucket_env):
        from perf.container import mirror

        remote = tmp_path / 'remote'
        run_id = 'camp-5'
        campaign = campaign_root(remote, run_id)
        inflight = campaign / 'runner_a' / f'{run_id}-000'
        inflight.mkdir(parents=True)
        (inflight / 'summary.json').write_text('{"partial": true}')
        run_log = campaign / 'RUN.log'
        mirror.mirror_campaign_tail(campaign, run_id, run_log)
        assert not any(f'{run_id}-000' in path for path in bucket_env.files)


class TestExclusions:
    def test_exclusion_constant_matches_only_non_generated_paths(self):
        from perf.container import mirror

        for rel in (
            'fixtures/w1-abcdef0123456789.docx', 'cells/c1/fixtures/in.docx',
            'builds/plate/abc123/dist/assets/index.js', 'builds/plate/abc123/build.json',
            'benchmark_input/job/builds/editor/x.js',
            'dist/app.js', 'job/dist/app.js',
            'node_modules/pkg/index.js', 'job/node_modules/pkg/index.js',
            'repos/plate/README.md', 'a/repos/x',
            'input.docx', 'cells/c1/input.docx', 'fixtures/nested/dir/in.docx',
        ):
            assert mirror.bucket_excluded(rel), rel
        for rel in (
            'summary.json', 'cells/c1/attempts/a.json', 'samples/s1.json',
            'evidence/e.json', 'rejected-evidence/r/cell/x.json',
            'MANIFEST.sha256', 'JOB-DONE', 'campaign-meta.json',
            'out/e2-publication.json', 'RUN.log', 'RUN-DONE', 'RUN.pid',
            'traces/t1.zip', 'distance.txt',
        ):
            assert not mirror.bucket_excluded(rel), rel

    def test_fixture_build_dist_and_docx_files_never_upload(self, tmp_path, bucket_env):
        from perf.container import mirror

        remote = tmp_path / 'remote'
        run_id = 'camp-6'
        campaign = campaign_root(remote, run_id)
        job_dir = seal_job(
            remote, run_id, 'runner_a', f'{run_id}-000',
            {
                'summary.json': '{}',
                'fixtures/w1-aaaa.docx': 'INPUT-DOCX',
                'input.docx': 'INPUT-DOCX-2',
                'builds/plate/abc/dist/app.js': 'CODE',
                'node_modules/pkg/index.js': 'CODE',
                'repos/plate/f.py': 'CODE',
                'evidence/e.json': '{}',
            },
        )
        dist = campaign / 'builds' / 'plate' / 'abc' / 'dist'
        dist.mkdir(parents=True)
        (dist / 'index.js').write_text('CODE')
        (campaign / 'builds' / 'plate' / 'abc' / 'build.json').write_text('{}')
        run_log = campaign / 'RUN.log'
        mirror.mirror_job_directory(run_id, 'runner_a', f'{run_id}-000', job_dir, run_log)
        mirror.mirror_campaign_tail(campaign, run_id, run_log)
        leaked = [
            path for path, data in bucket_env.files.items()
            if data in (b'INPUT-DOCX', b'INPUT-DOCX-2', b'CODE')
        ]
        assert leaked == []
        prefix = f'runs/arthrod/e2-publish/{run_id}'
        assert not any('builds/' in path or 'fixtures/' in path or 'node_modules/' in path
                       or '/repos/' in path or path.endswith('.docx') or '/dist/' in path
                       for path in bucket_env.files)
        assert f'{prefix}/runner_a/{run_id}-000/evidence/e.json' in bucket_env.files

    def test_job_with_excluded_trees_uploads_generated_json_and_logs(self, tmp_path, bucket_env):
        from perf.container import mirror

        remote = tmp_path / 'remote'
        run_id = 'camp-7'
        campaign = campaign_root(remote, run_id)
        generated = {
            'summary.json': '{"samples": 1}',
            'samples/s1.json': '{"n": 1}',
            'evidence/e.json': '{}',
            'logs/job.log': 'measured ok\n',
        }
        excluded = {
            'builds/editor/app.js': 'BUILD',
            'dist/bundle.js': 'DIST',
            'node_modules/pkg/index.js': 'MODULES',
            'fixtures/case/in.txt': 'FIXTURE',
            'input.docx': 'DOCX-INPUT',
        }
        job_dir = seal_job(
            remote, run_id, 'runner_a', f'{run_id}-000',
            {**generated, **excluded},
        )
        run_log = campaign / 'RUN.log'
        run_log.write_text('campaign start\n')
        mirror.mirror_job_directory(run_id, 'runner_a', f'{run_id}-000', job_dir, run_log)
        prefix = f'runs/arthrod/e2-publish/{run_id}'
        job_prefix = f'{prefix}/runner_a/{run_id}-000/'
        uploaded = {
            path[len(job_prefix):] for path in bucket_env.files if path.startswith(job_prefix)
        }
        assert uploaded == set(generated) | {'MANIFEST.sha256', 'JOB-DONE'}
        for rel, text in generated.items():
            assert bucket_env.files[f'{job_prefix}{rel}'] == text.encode(), rel
        assert bucket_env.files[f'{prefix}/RUN.log'] == run_log.read_bytes()
        banned = {b'BUILD', b'DIST', b'MODULES', b'FIXTURE', b'DOCX-INPUT'}
        leaked = [path for path, data in bucket_env.files.items() if data in banned]
        assert leaked == []
        for rel in excluded:
            assert (job_dir / rel).is_file(), rel


class TestVerifyAndLogLines:
    def test_bucket_ok_line_counts_files_and_bytes(self, tmp_path, bucket_env):
        from perf.container import mirror

        remote = tmp_path / 'remote'
        run_id = 'camp-10'
        job_dir = seal_job(
            remote, run_id, 'runner_a', f'{run_id}-000',
            {'summary.json': '12345', 'cells/c1/attempts/a.json': 'x' * 20},
        )
        run_log = campaign_root(remote, run_id) / 'RUN.log'
        mirror.mirror_job_directory(run_id, 'runner_a', f'{run_id}-000', job_dir, run_log)
        expected = 4  # summary.json, cells/..., MANIFEST.sha256, JOB-DONE
        manifest_bytes = (job_dir / 'MANIFEST.sha256').stat().st_size
        done_bytes = (job_dir / 'JOB-DONE').stat().st_size
        total = 5 + 20 + manifest_bytes + done_bytes
        assert bucket_lines(run_log, 'runner_a/camp-10-000') == [
            f'BUCKET-OK runner_a/{run_id}-000 {expected} {total}'
        ]

    def test_upload_failure_logs_one_error_line_and_returns(self, tmp_path, bucket_env):
        from perf.container import mirror

        remote = tmp_path / 'remote'
        run_id = 'camp-11'
        job_dir = seal_job(remote, run_id, 'runner_a', f'{run_id}-000', {'summary.json': '{}'})
        run_log = campaign_root(remote, run_id) / 'RUN.log'
        bucket_env.fail_on_batch = True
        mirror.mirror_job_directory(run_id, 'runner_a', f'{run_id}-000', job_dir, run_log)
        lines = bucket_lines(run_log, f'runner_a/{run_id}-000')
        assert len(lines) == 1 and lines[0].startswith('BUCKET-ERROR ')
        assert 'simulated upload failure' in lines[0]

    def test_remote_mismatch_after_upload_logs_error(self, tmp_path, bucket_env):
        from perf.container import mirror

        remote = tmp_path / 'remote'
        run_id = 'camp-12'
        job_dir = seal_job(remote, run_id, 'runner_a', f'{run_id}-000', {'summary.json': '{}'})
        run_log = campaign_root(remote, run_id) / 'RUN.log'
        prefix = f'runs/arthrod/e2-publish/{run_id}/runner_a/{run_id}-000'
        bucket_env.drop_dests.add(f'{prefix}/summary.json')
        mirror.mirror_job_directory(run_id, 'runner_a', f'{run_id}-000', job_dir, run_log)
        lines = bucket_lines(run_log, f'runner_a/{run_id}-000')
        assert len(lines) == 1
        assert lines[0].startswith('BUCKET-ERROR ') and 'mismatch' in lines[0]

    def test_failed_upload_retried_on_the_next_seal(self, tmp_path, bucket_env):
        from perf.container import mirror

        remote = tmp_path / 'remote'
        run_id = 'camp-13'
        campaign = campaign_root(remote, run_id)
        run_log = campaign / 'RUN.log'
        job1 = seal_job(remote, run_id, 'runner_a', f'{run_id}-000', {'summary.json': '{"a": 1}'})
        bucket_env.fail_on_batch = True
        mirror.mirror_job_directory(run_id, 'runner_a', f'{run_id}-000', job1, run_log)
        assert bucket_lines(run_log, f'runner_a/{run_id}-000')[0].startswith('BUCKET-ERROR ')
        assert f'runs/arthrod/e2-publish/{run_id}/runner_a/{run_id}-000/summary.json' not in bucket_env.files
        bucket_env.fail_on_batch = False
        job2 = seal_job(remote, run_id, 'runner_b', f'{run_id}-001', {'summary.json': '{"b": 2}'})
        mirror.mirror_job_directory(run_id, 'runner_b', f'{run_id}-001', job2, run_log)
        prefix = f'runs/arthrod/e2-publish/{run_id}'
        assert f'{prefix}/runner_a/{run_id}-000/summary.json' in bucket_env.files
        ok_lines = [
            line for line in bucket_lines(run_log)
            if line.startswith('BUCKET-OK ')
        ]
        assert f'BUCKET-OK runner_a/{run_id}-000 3 {sum(p.stat().st_size for p in job1.rglob("*") if p.is_file())}' in ok_lines
        assert any(line.startswith(f'BUCKET-OK runner_b/{run_id}-001 ') for line in ok_lines)

    def test_tail_rechecks_every_job_and_logs_one_line_each(self, tmp_path, bucket_env):
        from perf.container import mirror

        remote = tmp_path / 'remote'
        run_id = 'camp-14'
        campaign = campaign_root(remote, run_id)
        run_log = campaign / 'RUN.log'
        jobs = [
            seal_job(remote, run_id, 'runner_a', f'{run_id}-000', {'summary.json': '{}'}),
            seal_job(remote, run_id, 'runner_b', f'{run_id}-001', {'summary.json': '{}'}),
        ]
        mirror.mirror_campaign_tail(campaign, run_id, run_log)
        for job in jobs:
            rel = job.relative_to(campaign).as_posix()
            assert len(bucket_lines(run_log, rel)) == 1
            assert bucket_lines(run_log, rel)[0].startswith('BUCKET-OK ')

    def test_tail_reuploads_files_missing_from_remote(self, tmp_path, bucket_env):
        from perf.container import mirror

        remote = tmp_path / 'remote'
        run_id = 'camp-15'
        campaign = campaign_root(remote, run_id)
        run_log = campaign / 'RUN.log'
        job_dir = seal_job(remote, run_id, 'runner_a', f'{run_id}-000', {'summary.json': 'data'})
        mirror.mirror_job_directory(run_id, 'runner_a', f'{run_id}-000', job_dir, run_log)
        gone = f'runs/arthrod/e2-publish/{run_id}/runner_a/{run_id}-000/summary.json'
        del bucket_env.files[gone]
        mirror.mirror_campaign_tail(campaign, run_id, run_log)
        assert bucket_env.files[gone] == b'data'
        assert bucket_lines(run_log, f'runner_a/{run_id}-000')[-1].startswith('BUCKET-OK ')

    def test_unexpected_remote_file_is_a_verify_mismatch(self, tmp_path, bucket_env):
        from perf.container import mirror

        remote = tmp_path / 'remote'
        run_id = 'camp-16'
        campaign = campaign_root(remote, run_id)
        run_log = campaign / 'RUN.log'
        job_dir = seal_job(remote, run_id, 'runner_a', f'{run_id}-000', {'summary.json': '{}'})
        mirror.mirror_job_directory(run_id, 'runner_a', f'{run_id}-000', job_dir, run_log)
        bucket_env.files[f'runs/arthrod/e2-publish/{run_id}/runner_a/{run_id}-000/stale.txt'] = b'x'
        mirror.mirror_campaign_tail(campaign, run_id, run_log)
        last = bucket_lines(run_log, f'runner_a/{run_id}-000')[-1]
        assert last.startswith('BUCKET-ERROR ') and 'mismatch' in last

    def test_seal_pass_does_not_relog_complete_jobs(self, tmp_path, bucket_env):
        from perf.container import mirror

        remote = tmp_path / 'remote'
        run_id = 'camp-17'
        campaign = campaign_root(remote, run_id)
        run_log = campaign / 'RUN.log'
        job1 = seal_job(remote, run_id, 'runner_a', f'{run_id}-000', {'summary.json': '{}'})
        mirror.mirror_job_directory(run_id, 'runner_a', f'{run_id}-000', job1, run_log)
        job2 = seal_job(remote, run_id, 'runner_b', f'{run_id}-001', {'summary.json': '{}'})
        mirror.mirror_job_directory(run_id, 'runner_b', f'{run_id}-001', job2, run_log)
        assert len(bucket_lines(run_log, f'runner_a/{run_id}-000')) == 1
        assert len(bucket_lines(run_log, f'runner_b/{run_id}-001')) == 1


class TestToken:
    def test_no_token_logs_bucket_skip_once_per_run(self, tmp_path, monkeypatch):
        from perf.container import mirror

        monkeypatch.delenv('HF_BUCKET_TOKEN', raising=False)
        monkeypatch.setattr(mirror, 'PROC1_ENVIRON', str(tmp_path / 'absent-environ'))
        client = FakeBucketClient()
        monkeypatch.setattr(mirror, 'BUCKET_CLIENT_FACTORY', lambda token: client)
        remote = tmp_path / 'remote'
        run_id = 'camp-20'
        campaign = campaign_root(remote, run_id)
        run_log = campaign / 'RUN.log'
        job1 = seal_job(remote, run_id, 'runner_a', f'{run_id}-000', {'summary.json': '{}'})
        mirror.mirror_job_directory(run_id, 'runner_a', f'{run_id}-000', job1, run_log)
        job2 = seal_job(remote, run_id, 'runner_b', f'{run_id}-001', {'summary.json': '{}'})
        mirror.mirror_job_directory(run_id, 'runner_b', f'{run_id}-001', job2, run_log)
        mirror.mirror_campaign_tail(campaign, run_id, run_log)
        text = run_log.read_text() if run_log.exists() else ''
        assert text.count('BUCKET-SKIP no_token') == 1
        assert 'BUCKET-OK' not in text and 'BUCKET-ERROR' not in text
        assert client.files == {} and not any(c[0] == 'batch' for c in client.calls)

    def test_proc1_environ_supplies_token_when_env_missing(self, tmp_path, monkeypatch):
        from perf.container import mirror

        environ = tmp_path / 'environ'
        environ.write_bytes(b'PATH=/usr/bin\0HF_BUCKET_TOKEN=proc1-test-token\0OTHER=1\0')
        monkeypatch.delenv('HF_BUCKET_TOKEN', raising=False)
        monkeypatch.setattr(mirror, 'PROC1_ENVIRON', str(environ))
        assert mirror._bucket_token() == 'proc1-test-token'

    def test_env_token_wins_over_proc1_environ(self, tmp_path, monkeypatch):
        from perf.container import mirror

        environ = tmp_path / 'environ'
        environ.write_bytes(b'HF_BUCKET_TOKEN=proc1-test-token\0')
        monkeypatch.setenv('HF_BUCKET_TOKEN', 'env-test-token')
        monkeypatch.setattr(mirror, 'PROC1_ENVIRON', str(environ))
        assert mirror._bucket_token() == 'env-test-token'

    def test_unreadable_proc1_environ_means_no_token(self, tmp_path, monkeypatch):
        from perf.container import mirror

        monkeypatch.delenv('HF_BUCKET_TOKEN', raising=False)
        monkeypatch.setattr(mirror, 'PROC1_ENVIRON', str(tmp_path / 'not-there'))
        assert mirror._bucket_token() is None

    def test_upload_runs_on_proc1_token(self, tmp_path, bucket_env, monkeypatch):
        from perf.container import mirror

        environ = tmp_path / 'environ'
        environ.write_bytes(b'HF_BUCKET_TOKEN=proc1-test-token\0')
        monkeypatch.delenv('HF_BUCKET_TOKEN')
        monkeypatch.setattr(mirror, 'PROC1_ENVIRON', str(environ))
        remote = tmp_path / 'remote'
        run_id = 'camp-21'
        job_dir = seal_job(remote, run_id, 'runner_a', f'{run_id}-000', {'summary.json': '{}'})
        mirror.mirror_job_directory(run_id, 'runner_a', f'{run_id}-000', job_dir,
                                    campaign_root(remote, run_id) / 'RUN.log')
        assert f'runs/arthrod/e2-publish/{run_id}/runner_a/{run_id}-000/summary.json' in bucket_env.files

    def test_missing_library_logs_skip_once(self, tmp_path, monkeypatch):
        from perf.container import mirror

        monkeypatch.setenv('HF_BUCKET_TOKEN', 'test-token-x')
        monkeypatch.setattr(mirror, 'BUCKET_CLIENT_FACTORY', None)
        monkeypatch.setitem(sys.modules, 'huggingface_hub', None)
        remote = tmp_path / 'remote'
        run_id = 'camp-22'
        campaign = campaign_root(remote, run_id)
        run_log = campaign / 'RUN.log'
        job1 = seal_job(remote, run_id, 'runner_a', f'{run_id}-000', {'summary.json': '{}'})
        mirror.mirror_job_directory(run_id, 'runner_a', f'{run_id}-000', job1, run_log)
        mirror.mirror_campaign_tail(campaign, run_id, run_log)
        text = run_log.read_text() if run_log.exists() else ''
        assert text.count('BUCKET-SKIP no_huggingface_hub') == 1

    def test_token_never_appears_in_log_stderr_or_run_files(self, tmp_path, monkeypatch, capsys):
        from perf.container import mirror

        token = 'test-token-neverlogged-0001'
        monkeypatch.setenv('HF_BUCKET_TOKEN', token)

        def leaky_batch(bucket_id, *, add=None, copy=None, delete=None, token=None):
            raise RuntimeError(f'401 Unauthorized: token {token} rejected')

        client = FakeBucketClient()
        client.batch_bucket_files = leaky_batch
        monkeypatch.setattr(mirror, 'BUCKET_CLIENT_FACTORY', lambda t: client)
        remote = tmp_path / 'remote'
        run_id = 'camp-23'
        campaign = campaign_root(remote, run_id)
        run_log = campaign / 'RUN.log'
        job_dir = seal_job(remote, run_id, 'runner_a', f'{run_id}-000', {'summary.json': '{}'})
        mirror.mirror_job_directory(run_id, 'runner_a', f'{run_id}-000', job_dir, run_log)
        text = run_log.read_text()
        assert token not in text
        assert 'BUCKET-ERROR' in text and '<redacted>' in text
        for path in campaign.rglob('*'):
            if path.is_file():
                assert token.encode() not in path.read_bytes(), path
        captured = capsys.readouterr()
        assert token not in captured.out and token not in captured.err

    def test_mirror_main_sanitizes_token_in_exception_text(self, tmp_path, monkeypatch, capsys):
        from perf.container import mirror

        token = 'test-token-in-exc-0002'
        monkeypatch.setenv('HF_BUCKET_TOKEN', token)

        def boom(run_log, line):
            raise RuntimeError(f'log append failed with {token}')

        monkeypatch.setattr(mirror, '_append_run_log', boom)
        remote = tmp_path / 'remote'
        run_id = 'camp-24'
        campaign = campaign_root(remote, run_id)
        run_log = campaign / 'RUN.log'
        job_dir = seal_job(remote, run_id, 'runner_a', f'{run_id}-000', {'summary.json': '{}'})
        rc = mirror.main(['job', run_id, 'runner_a', f'{run_id}-000', str(job_dir), str(run_log)])
        captured = capsys.readouterr()
        assert token not in captured.err and token not in captured.out


class TestBounded:
    def test_budget_is_inside_mirror_timeout(self, monkeypatch):
        from perf.container import mirror

        monkeypatch.delenv('HF_BUCKET_TIMEOUT_S', raising=False)
        monkeypatch.setenv('HF_MIRROR_TIMEOUT_S', '100')
        budget = mirror._bucket_budget_s()
        assert 0 < budget < 100
        monkeypatch.setenv('HF_BUCKET_TIMEOUT_S', '5')
        assert mirror._bucket_budget_s() == 5.0

    def test_stuck_upload_deadline_logs_per_job_timeout(self, tmp_path, bucket_env, monkeypatch):
        from perf.container import mirror

        def stuck(bucket_id, *, add=None, copy=None, delete=None, token=None):
            raise mirror._BucketDeadline('bucket timeout')

        bucket_env.batch_bucket_files = stuck
        remote = tmp_path / 'remote'
        run_id = 'camp-30'
        campaign = campaign_root(remote, run_id)
        run_log = campaign / 'RUN.log'
        seal_job(remote, run_id, 'runner_a', f'{run_id}-000', {'summary.json': '{}'})
        seal_job(remote, run_id, 'runner_b', f'{run_id}-001', {'summary.json': '{}'})
        mirror.mirror_campaign_tail(campaign, run_id, run_log)
        text = run_log.read_text()
        assert f'BUCKET-ERROR runner_a/{run_id}-000 bucket timeout' in text
        assert f'runner_b/{run_id}-001' not in text

    def test_deadline_mid_verify_is_logged_not_raised(self, tmp_path, bucket_env):
        from perf.container import mirror

        calls = {'n': 0}

        def lister(bucket_id, *, prefix='', recursive=False, token=None):
            calls['n'] += 1
            if calls['n'] > 1:
                raise mirror._BucketDeadline('bucket timeout')
            return iter(())

        bucket_env.list_bucket_tree = lister
        remote = tmp_path / 'remote'
        run_id = 'camp-31'
        campaign = campaign_root(remote, run_id)
        run_log = campaign / 'RUN.log'
        seal_job(remote, run_id, 'runner_a', f'{run_id}-000', {'summary.json': '{}'})
        mirror.mirror_campaign_tail(campaign, run_id, run_log)
        text = run_log.read_text()
        assert 'bucket timeout' in text

    def test_one_bad_job_does_not_block_the_next(self, tmp_path, bucket_env):
        from perf.container import mirror

        def picky(bucket_id, *, add=None, copy=None, delete=None, token=None):
            for src, _ in (add or []):
                if f'{run_id}-000' in str(src):
                    raise RuntimeError('upload rejected')
            for src, dst in (add or []):
                bucket_env_put(bucket_env.files, src, dst)

        def bucket_env_put(files, src, dst):
            files[dst] = Path(src).read_bytes()

        bucket_env.batch_bucket_files = picky
        remote = tmp_path / 'remote'
        run_id = 'camp-32'
        campaign = campaign_root(remote, run_id)
        run_log = campaign / 'RUN.log'
        seal_job(remote, run_id, 'runner_a', f'{run_id}-000', {'summary.json': '{}'})
        seal_job(remote, run_id, 'runner_b', f'{run_id}-001', {'summary.json': '{}'})
        mirror.mirror_campaign_tail(campaign, run_id, run_log)
        text = run_log.read_text()
        assert f'BUCKET-ERROR runner_a/{run_id}-000' in text
        assert f'BUCKET-OK runner_b/{run_id}-001' in text

    def test_unreadable_job_dir_does_not_block_the_next(self, tmp_path, bucket_env, monkeypatch):
        from perf.container import mirror

        real_local_sizes = mirror._local_sizes

        def flaky(root):
            if f'{run_id}-000' in str(root):
                raise OSError('job dir vanished')
            return real_local_sizes(root)

        monkeypatch.setattr(mirror, '_local_sizes', flaky)
        remote = tmp_path / 'remote'
        run_id = 'camp-35'
        campaign = campaign_root(remote, run_id)
        run_log = campaign / 'RUN.log'
        seal_job(remote, run_id, 'runner_a', f'{run_id}-000', {'summary.json': '{}'})
        seal_job(remote, run_id, 'runner_b', f'{run_id}-001', {'summary.json': '{}'})
        mirror.mirror_campaign_tail(campaign, run_id, run_log)
        text = run_log.read_text()
        assert f'BUCKET-ERROR runner_a/{run_id}-000' in text
        assert f'BUCKET-OK runner_b/{run_id}-001' in text

    def test_bucket_sync_failure_never_fails_mirror_or_local_copy(self, tmp_path, bucket_env):
        from perf.container import mirror

        def broken(bucket_id, *, add=None, copy=None, delete=None, token=None):
            raise RuntimeError('bucket down')

        bucket_env.batch_bucket_files = broken
        bucket_env.list_bucket_tree = lambda *a, **k: iter(())
        remote = tmp_path / 'remote'
        run_id = 'camp-33'
        campaign = campaign_root(remote, run_id)
        run_log = campaign / 'RUN.log'
        job_dir = seal_job(remote, run_id, 'runner_a', f'{run_id}-000', {'summary.json': '{}'})
        mirror.mirror_job_directory(run_id, 'runner_a', f'{run_id}-000', job_dir, run_log)
        dest = Path(os.environ['HF_MIRROR_ROOT']) / run_id / 'runner_a' / f'{run_id}-000'
        assert (dest / 'summary.json').is_file()
        assert (dest / 'MIRROR-OK').is_file()
        assert f'BUCKET-ERROR runner_a/{run_id}-000' in run_log.read_text()

    def test_stuck_mirror_child_killed_at_mirror_timeout(self, tmp_path, monkeypatch):
        from perf.container import run

        stub = tmp_path / 'stub_mirror.py'
        stub.write_text('import time\ntime.sleep(600)\n')
        run_log_dir = tmp_path / 'runs' / 'camp-34'
        run_log_dir.mkdir(parents=True)
        run_log = run_log_dir / 'RUN.log'
        monkeypatch.setenv('HF_MIRROR_PY', str(stub))
        monkeypatch.setenv('HF_MIRROR_TIMEOUT_S', '1')
        started = time.monotonic()
        ok, alive = run.run_mirror_subprocess(['job', 'camp-34'], run_log, label='sleepy')
        elapsed = time.monotonic() - started
        assert ok is False
        assert alive is None
        assert elapsed < 30
        assert 'MIRROR-ERROR sleepy timeout' in run_log.read_text()


class TestSetup:
    def test_dockerfile_installs_huggingface_hub_into_runtime(self):
        from perf.container.mirror import HUGGINGFACE_HUB_VERSION, RUNTIME_PIP
        image = Path('perf/container/Dockerfile').read_text()
        pip_line = next(text for text in image.splitlines() if 'pip install' in text)
        assert f'huggingface_hub=={HUGGINGFACE_HUB_VERSION}' in pip_line
        assert RUNTIME_PIP in pip_line
        assert 'playwright==1.64.1' in pip_line and 'psutil==' in pip_line

    def test_mirror_subprocess_interpreter_gets_huggingface_hub(self):
        # mirror.py runs under `sys.executable -I`; the Dockerfile installs the
        # runtime deps into /home/user/python-runtime and puts it on PATH, so
        # the child's interpreter carries huggingface_hub. The Dockerfile check
        # above is the contract; here the import inside mirror.py must be the
        # late import (not a top-level one) so a missing library degrades to
        # BUCKET-SKIP rather than an import crash.
        source = Path('perf/container/mirror.py').read_text()
        head = source.split('def ', 1)[0]
        assert 'import huggingface_hub' not in head

    def test_setup_sh_dry_run_lists_pinned_huggingface_hub(self):
        import subprocess
        from perf.container.mirror import HUGGINGFACE_HUB_VERSION, RUNTIME_PIP
        spec = f'huggingface_hub=={HUGGINGFACE_HUB_VERSION}'
        image = Path('perf/container/Dockerfile').read_text()
        pip_line = next(text for text in image.splitlines() if 'python-runtime/bin/pip install' in text)
        assert spec in pip_line and RUNTIME_PIP in pip_line
        result = subprocess.run(['bash', 'perf/container/setup.sh', '--dry-run'], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        assert f'{RUNTIME_PIP} install --no-cache-dir {spec}' in result.stdout

    def test_setup_dry_run_prints_runtime_pip_and_does_not_execute(self, monkeypatch, capsys):
        from perf.container import setup
        from perf.container.mirror import HUGGINGFACE_HUB_VERSION, RUNTIME_PIP
        calls = []

        def forbid(cmd, **kwargs):
            calls.append(cmd)
            raise AssertionError('dry-run executed a command')

        monkeypatch.setattr(setup.subprocess, 'run', forbid)
        monkeypatch.setattr(sys, 'argv', ['setup', '--dry-run'])
        setup.main()
        out = capsys.readouterr().out
        assert calls == []
        assert f'{RUNTIME_PIP} install --no-cache-dir huggingface_hub=={HUGGINGFACE_HUB_VERSION}' in out

    def test_runtime_pip_install_failure_fails_setup(self, monkeypatch):
        import subprocess
        from perf.container import setup
        from perf.container.mirror import HUGGINGFACE_HUB_VERSION, RUNTIME_PIP

        def run(cmd, **kwargs):
            if any(str(part).startswith('huggingface_hub==') for part in cmd):
                raise subprocess.CalledProcessError(1, cmd)
            raise AssertionError('setup ran a command before the runtime pip install')

        monkeypatch.setattr(setup.subprocess, 'run', run)
        monkeypatch.setattr(sys, 'argv', ['setup', '--facts', 'out/facts.json'])
        with pytest.raises(subprocess.CalledProcessError) as caught:
            setup.main()
        assert list(caught.value.cmd) == [
            RUNTIME_PIP, 'install', '--no-cache-dir', f'huggingface_hub=={HUGGINGFACE_HUB_VERSION}',
        ]


def _quiet_host(monkeypatch):
    from perf.container import check_host
    monkeypatch.setattr(check_host, 'host_record', lambda: {'os': 'linux', 'python': '3.12'})
    monkeypatch.setattr(check_host, 'quiet_machine_check', lambda: {
        'quiet': True, 'reasons': [], 'load_average': [0.0, 0.0, 0.0],
    })


def _isolate_space(monkeypatch, tmp_path):
    """Point the PID-1 environ read at an empty file and drop campaign flags."""
    from perf.container import mirror
    monkeypatch.delenv('HF_BUCKET_TOKEN', raising=False)
    monkeypatch.delenv('SPACE_ID', raising=False)
    monkeypatch.delenv('HF_BUCKET_REQUIRED', raising=False)
    path = tmp_path / 'environ'
    path.write_bytes(b'')
    monkeypatch.setattr(mirror, 'PROC1_ENVIRON', str(path))
    return path


def _secret():
    import secrets
    return 't' + secrets.token_hex(24)


def _write_proc1(path, fields):
    raw = b''.join(f'{key}={value}'.encode() + b'\0' for key, value in fields.items())
    path.write_bytes(raw)


def _hub(monkeypatch, version):
    import types
    if version is None:
        monkeypatch.setitem(sys.modules, 'huggingface_hub', None)
        return
    module = types.ModuleType('huggingface_hub')
    module.__version__ = version
    monkeypatch.setitem(sys.modules, 'huggingface_hub', module)


def _run_check():
    from perf.container import check_host
    try:
        check_host.main()
    except SystemExit as exc:
        return str(exc)
    return None


def _refuse_leak(text, secret):
    if secret and secret in text:
        raise AssertionError('check_host output contains the bucket token')


def _bucket_has_no_length(bucket, secret):
    import json
    blob = json.dumps(bucket)
    if 'length' in bucket or str(len(secret)) in blob:
        raise AssertionError('check_host bucket report contains the token length')


class TestCheckHostBucket:
    def test_refuses_when_library_missing(self, monkeypatch, tmp_path, capsys):
        import json
        _quiet_host(monkeypatch)
        path = _isolate_space(monkeypatch, tmp_path)
        secret = _secret()
        _write_proc1(path, {'SPACE_ID': 'arthrod/e2-publish', 'HF_BUCKET_TOKEN': secret})
        _hub(monkeypatch, None)
        message = _run_check()
        out = capsys.readouterr().out
        _refuse_leak(out + (message or ''), secret)
        assert message is not None and 'no_huggingface_hub' in message
        payload = json.loads(out)
        assert payload['bucket']['expected'] is True
        assert payload['bucket']['ready'] is False
        assert payload['bucket']['huggingface_hub'] == 'missing'
        assert payload['bucket']['token'] == 'present'
        assert 'no_huggingface_hub' in payload['quiet_machine_check']['reasons']
        _bucket_has_no_length(payload['bucket'], secret)

    def test_refuses_when_version_is_not_the_pin(self, monkeypatch, tmp_path, capsys):
        import json
        _quiet_host(monkeypatch)
        path = _isolate_space(monkeypatch, tmp_path)
        secret = _secret()
        _write_proc1(path, {'HF_BUCKET_TOKEN': secret})
        monkeypatch.setenv('SPACE_ID', 'arthrod/e2-publish')
        _hub(monkeypatch, '9.9.9')
        message = _run_check()
        out = capsys.readouterr().out
        _refuse_leak(out + (message or ''), secret)
        assert message is not None and 'huggingface_hub_version' in message
        payload = json.loads(out)
        assert payload['bucket']['huggingface_hub'] == '9.9.9'
        assert payload['bucket']['token'] == 'present'
        from perf.container.mirror import HUGGINGFACE_HUB_VERSION
        assert any(item.startswith('huggingface_hub_version') and HUGGINGFACE_HUB_VERSION in item
                   for item in payload['quiet_machine_check']['reasons'])
        _bucket_has_no_length(payload['bucket'], secret)

    def test_refuses_when_token_absent(self, monkeypatch, tmp_path, capsys):
        import json
        _quiet_host(monkeypatch)
        _isolate_space(monkeypatch, tmp_path)
        monkeypatch.setenv('SPACE_ID', 'arthrod/e2-publish')
        from perf.container.mirror import HUGGINGFACE_HUB_VERSION
        _hub(monkeypatch, HUGGINGFACE_HUB_VERSION)
        message = _run_check()
        out = capsys.readouterr().out
        assert message is not None and 'no_token' in message
        payload = json.loads(out)
        assert payload['bucket']['token'] == 'absent'
        assert payload['bucket']['huggingface_hub'] == HUGGINGFACE_HUB_VERSION
        assert payload['bucket']['ready'] is False
        assert 'no_token' in payload['quiet_machine_check']['reasons']
        assert 'length' not in payload['bucket']

    def test_passes_when_proc1_token_and_pinned_library_present(self, monkeypatch, tmp_path, capsys):
        import json
        _quiet_host(monkeypatch)
        path = _isolate_space(monkeypatch, tmp_path)
        secret = _secret()
        from perf.container.mirror import HUGGINGFACE_HUB_VERSION
        _write_proc1(path, {'SPACE_ID': 'arthrod/e2-publish', 'HF_BUCKET_TOKEN': secret})
        _hub(monkeypatch, HUGGINGFACE_HUB_VERSION)
        message = _run_check()
        captured = capsys.readouterr()
        _refuse_leak(captured.out + captured.err + (message or ''), secret)
        assert message is None
        payload = json.loads(captured.out)
        assert payload['bucket']['expected'] is True
        assert payload['bucket']['ready'] is True
        assert payload['bucket']['token'] == 'present'
        assert payload['bucket']['huggingface_hub'] == HUGGINGFACE_HUB_VERSION
        assert payload['bucket']['blocking'] == []
        assert payload['quiet_machine_check']['quiet'] is True
        _bucket_has_no_length(payload['bucket'], secret)

    def test_environment_token_is_reported_present_without_its_value(self, monkeypatch, tmp_path, capsys):
        import json
        _quiet_host(monkeypatch)
        _isolate_space(monkeypatch, tmp_path)
        secret = _secret()
        from perf.container.mirror import HUGGINGFACE_HUB_VERSION
        monkeypatch.setenv('HF_BUCKET_TOKEN', secret)
        monkeypatch.setenv('HF_BUCKET_REQUIRED', '1')
        _hub(monkeypatch, HUGGINGFACE_HUB_VERSION)
        message = _run_check()
        captured = capsys.readouterr()
        _refuse_leak(captured.out + captured.err + (message or ''), secret)
        assert message is None
        payload = json.loads(captured.out)
        assert payload['bucket']['token'] == 'present'
        assert payload['bucket']['expected'] is True
        _bucket_has_no_length(payload['bucket'], secret)

    def test_not_expected_without_space_id_or_flag(self, monkeypatch, tmp_path, capsys):
        import json
        _quiet_host(monkeypatch)
        _isolate_space(monkeypatch, tmp_path)
        _hub(monkeypatch, None)
        message = _run_check()
        payload = json.loads(capsys.readouterr().out)
        assert message is None
        assert payload['bucket']['expected'] is False
        assert payload['bucket']['ready'] is False
        assert payload['quiet_machine_check']['quiet'] is True
        assert payload['quiet_machine_check']['reasons'] == []

    def test_expected_when_space_id_is_only_in_proc1(self, monkeypatch, tmp_path, capsys):
        import json
        _quiet_host(monkeypatch)
        path = _isolate_space(monkeypatch, tmp_path)
        _write_proc1(path, {'SPACE_ID': 'arthrod/e2-publish'})
        _hub(monkeypatch, None)
        message = _run_check()
        payload = json.loads(capsys.readouterr().out)
        assert payload['bucket']['expected'] is True
        assert message is not None and 'no_huggingface_hub' in message
        assert 'no_token' in payload['quiet_machine_check']['reasons']

    def test_flag_expects_a_bucket_copy_without_space_id(self, monkeypatch, tmp_path, capsys):
        import json
        _quiet_host(monkeypatch)
        _isolate_space(monkeypatch, tmp_path)
        from perf.container.mirror import HUGGINGFACE_HUB_VERSION
        monkeypatch.setenv('HF_BUCKET_REQUIRED', '1')
        _hub(monkeypatch, HUGGINGFACE_HUB_VERSION)
        message = _run_check()
        payload = json.loads(capsys.readouterr().out)
        assert payload['bucket']['expected'] is True
        assert message is not None and 'no_token' in message

    def test_zero_flag_does_not_skip_the_check_on_a_space(self, monkeypatch, tmp_path, capsys):
        import json
        from perf.container.mirror import HUGGINGFACE_HUB_VERSION
        _quiet_host(monkeypatch)
        _isolate_space(monkeypatch, tmp_path)
        monkeypatch.setenv('SPACE_ID', 'arthrod/e2-publish')
        monkeypatch.setenv('HF_BUCKET_REQUIRED', '0')
        _hub(monkeypatch, HUGGINGFACE_HUB_VERSION)
        message = _run_check()
        payload = json.loads(capsys.readouterr().out)
        assert payload['bucket']['expected'] is True
        assert message is not None and 'no_token' in message


def fill_bucket(client: FakeBucketClient, remote: Path, run_id: str, *,
                space: str = 'arthrod/e2-publish') -> None:
    """Push the sealed campaign tree into the fake bucket as mirror.py would."""
    campaign = campaign_root(remote, run_id)
    run_log = campaign / 'RUN.log'
    if not run_log.exists():
        run_log.write_text('run log\n')
    for path in sorted(campaign.rglob('*')):
        if path.is_file():
            rel = path.relative_to(campaign).as_posix()
            client.files[f'runs/{space}/{run_id}/{rel}'] = path.read_bytes()


class TestBucketPull:
    def test_downloads_run_and_verifies_manifest(self, tmp_path, bucket_env, monkeypatch, capsys):
        from perf.container import bucket_pull

        remote = tmp_path / 'remote'
        run_id = 'camp-40'
        campaign_root(remote, run_id)
        seal_job(remote, run_id, 'runner_a', f'{run_id}-000', {'summary.json': '{}', 'cells/c.json': '{}'})
        fill_bucket(bucket_env, remote, run_id)
        monkeypatch.setattr(bucket_pull, 'CLIENT_FACTORY', lambda token: bucket_env)
        dest = tmp_path / 'pulled'
        rc = bucket_pull.main(['--dest', str(dest), '--space', 'arthrod/e2-publish', '--run', run_id])
        assert rc == 0
        job = dest / 'runs' / 'arthrod/e2-publish' / run_id / 'runner_a' / f'{run_id}-000'
        assert (job / 'summary.json').is_file()
        assert (job / 'cells/c.json').is_file()
        assert (job / 'JOB-DONE').is_file()
        assert (dest / 'runs' / 'arthrod/e2-publish' / run_id / 'RUN.log').is_file()
        summary = capsys.readouterr().out.strip().splitlines()[-1]
        assert summary.startswith(f'BUCKET-PULL arthrod/e2-publish/{run_id}')
        assert 'ok=1' in summary and 'failed=0' in summary

    def test_corrupt_remote_file_fails_and_is_not_installed(self, tmp_path, bucket_env, monkeypatch, capsys):
        from perf.container import bucket_pull

        remote = tmp_path / 'remote'
        run_id = 'camp-41'
        campaign_root(remote, run_id)
        seal_job(remote, run_id, 'runner_a', f'{run_id}-000', {'summary.json': '{"ok":1}'})
        fill_bucket(bucket_env, remote, run_id)
        key = f'runs/arthrod/e2-publish/{run_id}/runner_a/{run_id}-000/summary.json'
        bucket_env.files[key] = b'{"corrupted":true}'
        monkeypatch.setattr(bucket_pull, 'CLIENT_FACTORY', lambda token: bucket_env)
        dest = tmp_path / 'pulled'
        rc = bucket_pull.main(['--dest', str(dest), '--space', 'arthrod/e2-publish', '--run', run_id])
        assert rc == 1
        bad = dest / 'runs' / 'arthrod/e2-publish' / run_id / 'runner_a' / f'{run_id}-000' / 'summary.json'
        assert not bad.exists() or bad.read_text() == '{"ok":1}'
        assert 'BUCKET-PULL' in capsys.readouterr().out

    def test_downloads_all_runs_of_space(self, tmp_path, bucket_env, monkeypatch):
        from perf.container import bucket_pull

        remote = tmp_path / 'remote'
        for idx, run_id in enumerate(('camp-42a', 'camp-42b')):
            campaign_root(remote, run_id)
            seal_job(remote, run_id, 'runner_a', f'{run_id}-000', {'summary.json': '{}'})
            fill_bucket(bucket_env, remote, run_id)
        monkeypatch.setattr(bucket_pull, 'CLIENT_FACTORY', lambda token: bucket_env)
        dest = tmp_path / 'pulled'
        rc = bucket_pull.main(['--dest', str(dest), '--space', 'arthrod/e2-publish'])
        assert rc == 0
        for run_id in ('camp-42a', 'camp-42b'):
            job = dest / 'runs' / 'arthrod/e2-publish' / run_id / 'runner_a' / f'{run_id}-000'
            assert (job / 'summary.json').is_file()

    def test_manifest_file_missing_remote_is_error(self, tmp_path, bucket_env, monkeypatch):
        from perf.container import bucket_pull

        remote = tmp_path / 'remote'
        run_id = 'camp-43'
        campaign_root(remote, run_id)
        seal_job(remote, run_id, 'runner_a', f'{run_id}-000', {'summary.json': '{}', 'cells/c.json': '{}'})
        fill_bucket(bucket_env, remote, run_id)
        del bucket_env.files[f'runs/arthrod/e2-publish/{run_id}/runner_a/{run_id}-000/cells/c.json']
        monkeypatch.setattr(bucket_pull, 'CLIENT_FACTORY', lambda token: bucket_env)
        rc = bucket_pull.main(['--dest', str(tmp_path / 'pulled'), '--space', 'arthrod/e2-publish', '--run', run_id])
        assert rc == 1

    def test_extra_remote_job_file_is_mismatch(self, tmp_path, bucket_env, monkeypatch):
        from perf.container import bucket_pull

        remote = tmp_path / 'remote'
        run_id = 'camp-44'
        campaign_root(remote, run_id)
        seal_job(remote, run_id, 'runner_a', f'{run_id}-000', {'summary.json': '{}'})
        fill_bucket(bucket_env, remote, run_id)
        bucket_env.files[f'runs/arthrod/e2-publish/{run_id}/runner_a/{run_id}-000/stray.txt'] = b'stray'
        monkeypatch.setattr(bucket_pull, 'CLIENT_FACTORY', lambda token: bucket_env)
        rc = bucket_pull.main(['--dest', str(tmp_path / 'pulled'), '--space', 'arthrod/e2-publish', '--run', run_id])
        assert rc == 1

    def test_never_deletes_local_files(self, tmp_path, bucket_env, monkeypatch):
        from perf.container import bucket_pull

        remote = tmp_path / 'remote'
        run_id = 'camp-45'
        campaign_root(remote, run_id)
        seal_job(remote, run_id, 'runner_a', f'{run_id}-000', {'summary.json': '{"v":2}'})
        fill_bucket(bucket_env, remote, run_id)
        monkeypatch.setattr(bucket_pull, 'CLIENT_FACTORY', lambda token: bucket_env)
        dest = tmp_path / 'pulled'
        keep = dest / 'runs' / 'arthrod/e2-publish' / run_id / 'runner_a' / f'{run_id}-000'
        keep.mkdir(parents=True)
        old = keep / 'summary.json'
        old.write_text('{"v":1}')
        extra = dest / 'notes.txt'
        extra.write_text('local note')
        rc = bucket_pull.main(['--dest', str(dest), '--space', 'arthrod/e2-publish', '--run', run_id])
        assert rc == 0
        assert extra.read_text() == 'local note'
        prev = list(keep.glob('summary.json.prev-*'))
        assert prev and prev[0].read_text() == '{"v":1}'
        assert old.read_text() == '{"v":2}'

    def test_no_token_exits_nonzero_without_network(self, tmp_path, monkeypatch, capsys):
        from perf.container import bucket_pull

        monkeypatch.delenv('HF_BUCKET_TOKEN', raising=False)
        monkeypatch.setattr(bucket_pull, 'PROC1_ENVIRON', str(tmp_path / 'nope'))
        called = []

        def factory(token):
            called.append(token)
            return FakeBucketClient()

        monkeypatch.setattr(bucket_pull, 'CLIENT_FACTORY', factory)
        rc = bucket_pull.main(['--dest', str(tmp_path / 'pulled'), '--space', 'arthrod/e2-publish'])
        assert rc != 0
        assert called == []
        out = capsys.readouterr().out
        assert 'no_token' in out

    def test_token_never_printed_on_error(self, tmp_path, monkeypatch, capsys):
        from perf.container import bucket_pull

        token = 'test-pull-token-0003'
        monkeypatch.setenv('HF_BUCKET_TOKEN', token)
        client = FakeBucketClient()

        def leaky(bucket_id, *, prefix=None, recursive=None, token=None):
            raise RuntimeError(f'auth failed for {token}')

        client.list_bucket_tree = leaky
        monkeypatch.setattr(bucket_pull, 'CLIENT_FACTORY', lambda t: client)
        rc = bucket_pull.main(['--dest', str(tmp_path / 'p'), '--space', 'arthrod/e2-publish'])
        captured = capsys.readouterr()
        assert rc != 0
        assert token not in captured.out and token not in captured.err
