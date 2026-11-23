"""A viewer's resources cell: load and C17 measured, the edit burst not applicable (not refused)."""
from perf.runner.benchmark_resources import EDIT_BURST, collect_phases
from perf.tests.test_resources import SHORT_QUIESCENCE, ManualClock, PhaseSession, World, make_sampler

META = {"sha256": "c" * 64, "byte_size": 10, "paragraph_count": 1, "word_count": 1}


def _trial(editor_id):
    world = World()
    clock = ManualClock(world, disturb=False)
    sampler = make_sampler(world, clock=clock)
    session = PhaseSession(world, mode="measure")
    trial = collect_phases(sampler, session, clock, quiescence=SHORT_QUIESCENCE, edit_burst=EDIT_BURST,
                           editor_id=editor_id, workload_id="prose-500w", workload_meta=META,
                           execution_profile="ci_broad", host_class="ci_coarse")
    return trial, session


def test_nutrient_is_measured_without_an_edit():
    trial, session = _trial("nutrient")
    assert session.edited is None, "a viewer is never typed into"
    assert trial["outcome"] == "measured"
    assert trial["edit_oracle"]["status"] == "not_applicable"
    assert "viewer" in trial["edit_oracle"]["reason"]
    assert "C17" in trial["criteria"] and "C19" not in trial["criteria"]


def test_an_editor_still_gets_its_edit_burst():
    trial, session = _trial("plate")
    assert trial["edit_oracle"]["status"] != "not_applicable"
    assert "C19" in trial["criteria"]
