"""C12's not-applicable reasons: Wordcraft's stays as it was; Nutrient (a viewer) has one; nobody else."""
from perf.runner.benchmark_document import DOCUMENT_TARGETS, c12_refusal

WORDCRAFT = ("wordcraft exposes no document text or block geometry at this pin "
             "(one WebGL canvas; correctness is only the modified window-title bullet)")


def test_wordcraft_keeps_its_reason():
    assert c12_refusal("wordcraft", DOCUMENT_TARGETS["wordcraft"]) == WORDCRAFT


def test_nutrient_is_a_viewer_with_nothing_to_edit():
    reason = c12_refusal("nutrient", DOCUMENT_TARGETS["nutrient"])
    assert reason and "viewer" in reason


def test_every_other_editor_runs_c12():
    for editor_id, cfg in DOCUMENT_TARGETS.items():
        if editor_id in ("wordcraft", "nutrient"):
            continue
        assert c12_refusal(editor_id, cfg) is None, editor_id
