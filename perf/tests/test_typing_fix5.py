"""#128 step2c: the per-key clock check reuses the load-time frame interval.

A bare ``clockSkew(page, cdp)`` on every sampled key pays the full
calibration — a fresh 60-frame rAF interval measurement, a 200 ms settle,
nine offset samples 20 ms apart, and a 600 ms anchor wait — about 1.5 s per
key. The session already measured its frame interval at load; the per-key
check takes it plus the fast sampling options.
"""

import re
from pathlib import Path

SOURCE = Path(__file__).parents[1] / 'runner/typing_session.mjs'


def test_per_key_clock_check_reuses_load_interval_and_fast_options():
    source = SOURCE.read_text()
    branch = source[source.index("command.op === 'key'"):source.index("command.op === 'close'")]
    rest = branch[branch.index('clockSkew('):]
    assert rest.index('{') < rest.index(')'), 'per-key clockSkew passes no options'
    options = re.sub(r'\s+', '', rest[rest.index('{'):rest.index('}') + 1])
    for entry in ('frameIntervalMs:interval.median_ms', 'settleMs:0',
                  'samples:9', 'sampleGapMs:5', 'changeWaitMs:150'):
        assert entry in options, f'per-key clockSkew missing {entry}'
