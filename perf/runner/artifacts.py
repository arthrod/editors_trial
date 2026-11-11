import os
import re
from pathlib import Path

from perf.schema import dump_trial

_ATTEMPT = re.compile(r"^[a-z0-9][a-z0-9._-]{0,80}$")


def write_attempt(directory, attempt_id, trial):
    if _ATTEMPT.fullmatch(attempt_id) is None:
        raise ValueError("attempt_id")
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (attempt_id + ".json")
    from perf.runner.browser_run import ACTIVE, CELL
    run = ACTIVE.get()
    if run is not None:
        trial = {**trial, "run_id": run.run_id, "seed": run.seed, **(CELL.get() or {})}
        host = run.hosts.get(trial.get("editor_id"), {})
        trial["host_build"] = host.get("host_build")
        trial["host_provenance"] = host
        env_block = run.publication_block_from_environment()
        if env_block:
            trial["publishable"] = False
            trial["publication_block_reason"] = env_block
        elif host.get("publishable") is False:
            trial["publishable"] = False
            trial["publication_block_reason"] = host["publication_block_reason"]
    from perf.runner.refusals import refusal_code
    trial = dict(trial)
    if 'refusal_code' not in trial:
        outcome = trial.get('outcome')
        trial['refusal_code'] = (None if outcome == 'measured' else
                                 outcome if outcome in ('unsupported', 'not_applicable', 'unverified', 'not_run') else 'crash')
    trial['refusal_code'] = refusal_code(trial)
    payload = dump_trial(trial).encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(path, flags, 0o644)
    try:
        view = memoryview(payload)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise OSError("short write")
            view = view[written:]
    except Exception:
        os.close(fd)
        try:
            os.unlink(path)
        except OSError:
            pass
        raise
    os.close(fd)
    return path
