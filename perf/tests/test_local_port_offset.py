"""Several local sessions can run lanes at once: PERF_PORT_OFFSET moves every host port.

A publication run never sets it. Two agents proving a fix on the same Mac used to
collide on the fixed host ports and read each other's failures.
"""
from __future__ import annotations

import os
import re

from perf.runner.benchmark_warm_cold import BROWSER_TARGETS, offset_targets

# 98cd7544 applies the ambient PERF_PORT_OFFSET at import time, so a session
# that exports it (parallel local runs) sees the declared ports moved by it.
AMBIENT = int(os.environ.get("PERF_PORT_OFFSET") or 0)


def _port(url):
    return int(re.search(r':(\d+)/', url).group(1))


def test_no_offset_leaves_every_target_as_declared():
    assert offset_targets(BROWSER_TARGETS, 0) == BROWSER_TARGETS


def test_the_declared_ports_are_the_ambient_offset_away_from_the_statics():
    assert int(re.search(r':(\d+)/', BROWSER_TARGETS['plate']['url']).group(1)) == 5208 + AMBIENT


def test_offset_moves_url_port_and_keeps_everything_else():
    moved = offset_targets(BROWSER_TARGETS, 1000)
    for editor, target in BROWSER_TARGETS.items():
        assert _port(moved[editor]['url']) == _port(target['url']) + 1000
        assert moved[editor]['url'].split('/', 3)[3:] == target['url'].split('/', 3)[3:]
        assert moved[editor]['edit_selector'] == target['edit_selector']
    assert BROWSER_TARGETS['plate']['url'] == 'http://127.0.0.1:%d/' % (5208 + AMBIENT)
    # the WordCraft host server takes its port from PORT
    assert moved['wordcraft']['env']['PORT'] == str(_port(BROWSER_TARGETS['wordcraft']['url']) + 1000)
