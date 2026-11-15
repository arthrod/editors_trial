"""A C14-only benchmark_document job builds only the ladder rungs; the C11
workload's fixture is absent and must not crash every editor (shakedown 3:
KeyError 'micro-paragraphs' on every C14 job)."""
from pathlib import Path

from perf.runner import benchmark_document as bd


def test_content_meta_without_the_c11_fixture_is_not_applicable():
    specs = {'C11': {'workload': 'micro-paragraphs'}}
    fixtures = {'prose-5kw': {'path': Path('/nonexistent/prose-5kw.docx')}}
    meta = bd._editor_content_meta(fixtures, specs)
    assert meta == {'length_check': 'not_applicable', 'length_check_reason': None}


def test_content_meta_uses_the_c11_fixture_when_it_was_built(tmp_path, monkeypatch):
    path = tmp_path / 'prose-500w.docx'
    path.write_bytes(b'x')
    seen = []
    monkeypatch.setattr(bd, 'corpus_content_expectations', lambda p: seen.append(p) or {'length_check': 'band'})
    meta = bd._editor_content_meta({'prose-500w': {'path': path}}, {'C11': {'workload': 'prose-500w'}})
    assert meta == {'length_check': 'band'} and seen == [path]


def test_main_has_no_unconditional_c11_fixture_lookup():
    source = Path(bd.__file__).read_text()
    assert 'fixtures[specs["C11"]["workload"]]\n        editor_content_meta' not in source
