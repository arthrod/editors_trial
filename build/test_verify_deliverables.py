"""The Word-open step of the release gate must fail when Word does not open a deliverable (#231)."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verify_deliverables  # noqa: E402 - the build folder is put on sys.path just above


def _deliverables(tmp_path, names=('one', 'two')):
    out = []
    for name in names:
        path = tmp_path / ('%s.docx' % name)
        path.write_bytes(b'PK')
        out.append((str(path), 'report %s' % name))
    return out


def _word(verdicts):
    def run(targets, work):
        return {label: verdicts[label] for label in targets if label in verdicts}
    return run


def test_every_deliverable_opened_is_a_pass(tmp_path, capsys):
    code = verify_deliverables.main(_deliverables(tmp_path), _word({'report-one': 'OPENED', 'report-two': 'OPENED'}), tmp_path)
    assert code == 0
    assert 'ALL DELIVERABLES OPEN IN MICROSOFT WORD' in capsys.readouterr().out


def test_a_deliverable_word_did_not_open_cleanly_fails_the_step(tmp_path, capsys):
    code = verify_deliverables.main(_deliverables(tmp_path), _word({'report-one': 'OPENED', 'report-two': 'REPAIR-PROMPT'}), tmp_path)
    assert code == 1
    assert 'SOME DELIVERABLE FAILED' in capsys.readouterr().out


def test_a_deliverable_with_no_verdict_fails_the_step(tmp_path, capsys):
    code = verify_deliverables.main(_deliverables(tmp_path), _word({'report-one': 'OPENED'}), tmp_path)
    assert code == 1
    assert 'NO-VERDICT' in capsys.readouterr().out


def test_a_missing_deliverable_fails_the_step(tmp_path):
    deliverables = _deliverables(tmp_path) + [(str(tmp_path / 'absent.docx'), 'report three')]
    code = verify_deliverables.main(deliverables, _word({'report-one': 'OPENED', 'report-two': 'OPENED'}), tmp_path)
    assert code == 1


def test_the_script_exits_with_the_verdict():
    """The gate reads the exit code: the script must hand main()'s result to sys.exit."""
    source = Path(verify_deliverables.__file__).read_text(encoding='utf-8')
    assert 'sys.exit(main(' in source
    # Run for real with a folder that holds no deliverable: every one is missing, so the step fails.
    probe = ('import sys; sys.path.insert(0, %r); import verify_deliverables as v; '
             'sys.exit(v.main([(%r, "report x")], lambda targets, work: {}, %r))'
             % (os.path.dirname(verify_deliverables.__file__), '/nonexistent/x.docx', '/nonexistent'))
    assert subprocess.run([sys.executable, '-c', probe], capture_output=True).returncode == 1
