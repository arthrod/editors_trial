"""A relative TRIAL_ROOT reaches run_trial.sh's children as the same checkout (CodeAnt on PR #291).

run_trial.sh changes into the checkout and then starts run_all.sh, run_second_pass.sh, score_all.py
and score_extra.py, which read TRIAL_ROOT again from there. A relative value then pointed below
the checkout ("trial/trial")."""
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).with_name("run_trial.sh")


def prologue() -> str:
    lines = SCRIPT.read_text().splitlines()
    end = next(i for i, l in enumerate(lines) if l.startswith("export TRIAL_ROOT="))
    return "\n".join(lines[: end + 1])


def test_children_see_the_checkout_from_a_relative_trial_root(tmp_path):
    (tmp_path / "trial").mkdir()
    probe = prologue() + '\n[ "$(cd "$TRIAL_ROOT" 2>/dev/null && pwd -P)" = "$(pwd -P)" ] && echo same || echo "other: $TRIAL_ROOT"\n'
    out = subprocess.run(["bash", "-c", probe], cwd=tmp_path, env={"TRIAL_ROOT": "trial", "PATH": "/usr/bin:/bin"},
                         capture_output=True, text=True)
    assert out.stdout.strip() == "same", out.stdout + out.stderr
