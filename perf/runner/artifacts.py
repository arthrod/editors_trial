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
        os.unlink(path)
        raise
    os.close(fd)
    return path
