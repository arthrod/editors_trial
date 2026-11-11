"""#129: the campaign runs on as many CPUs as the cgroup quota grants.

HF cpu-upgrade grants cpu.max 800000/100000 (8 CPUs) but schedules the
container on 64; browsers spread over 64 CPUs, exceed the quota inside a
period and every such sample is rejected as cpu_throttled.
"""
import pytest

from perf.container import run


@pytest.mark.parametrize("text,affinity,expected", [
    ("800000 100000", set(range(64)), set(range(8))),
    ("800000 100000\n", {3, 9, 11, 40, 41, 42, 50, 51, 60, 63}, {3, 9, 11, 40, 41, 42, 50, 51}),
    ("250000 100000", set(range(64)), {0, 1}),       # 2.5 CPUs: never more CPUs than quota
    ("50000 100000", set(range(64)), {0}),           # below one CPU still keeps one
    ("max 100000", set(range(64)), None),            # no quota: no pin
    ("800000 100000", set(range(8)), None),          # already within quota
    ("", set(range(64)), None),                      # unreadable: no pin
])
def test_quota_cpus(text, affinity, expected):
    assert run.quota_cpus(text, affinity) == expected


def test_pin_applies_and_reports(monkeypatch):
    applied = {}
    monkeypatch.setattr(run.os, "sched_getaffinity", lambda pid: set(range(64)), raising=False)
    monkeypatch.setattr(run.os, "sched_setaffinity", lambda pid, cpus: applied.setdefault("cpus", set(cpus)), raising=False)
    line = run.pin_to_quota(read=lambda: "800000 100000")
    assert applied["cpus"] == set(range(8))
    assert line == "cpu_affinity_pinned=0,1,2,3,4,5,6,7 cpu.max=800000 100000 visible=64"


def test_pin_noop_without_quota(monkeypatch):
    monkeypatch.setattr(run.os, "sched_getaffinity", lambda pid: set(range(64)), raising=False)
    monkeypatch.setattr(run.os, "sched_setaffinity", lambda pid, cpus: pytest.fail("must not pin"), raising=False)
    assert run.pin_to_quota(read=lambda: "max 100000") == "cpu_affinity_pinned=none cpu.max=max 100000 visible=64"
