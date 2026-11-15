"""#169 F5/F6: what list-item evidence may excuse, and what it must record.

Prefix markers require a non-null label of the same class. Marker-only
lines accept any rendered label, because the editor's number cannot equal
the typed marker, and the excuse records the class pair (``v.`` → ``i.``
is not ``v.`` → ``9.``). A null label is not a rendered label. A missing
``empty`` key means empty:false, so it cannot excuse a marker-only line;
a bare index is that plus a null marker and excuses nothing.
"""

from __future__ import annotations

from perf.tests.test_typing_fix167 import _type


def _pair(index, typed, rendered, typed_styles, rendered_styles):
    return {
        "index": index,
        "typed": typed,
        "rendered": rendered,
        "typed_styles": typed_styles,
        "rendered_styles": rendered_styles,
    }


def test_null_label_does_not_excuse_a_prefix_marker():
    result = _type(
        "3. body",
        "body",
        absorbed=[{"index": 0, "marker": None, "empty": False}],
    )
    assert result["failure_reason"] == "text_mismatch", result
    assert result["marker_only"]["missing"] == [{"index": 0, "marker": "3."}]
    assert not result.get("tolerated_class_pairs")


def test_same_class_prefix_label_measures_and_records_the_overlap():
    """'x.' is alpha and roman. The pair discloses that; 'b.' is alpha only."""
    result = _type(
        "b. body",
        "body",
        absorbed=[{"index": 0, "marker": "x.", "empty": False}],
    )
    assert result["failure_reason"] is None, result
    assert result["tolerated_list_markers"] == [{"index": 0, "marker": "b."}]
    assert set(result["tolerated_list_markers"][0]) == {"index", "marker"}
    assert result.get("tolerated_class_pairs") == [
        _pair(0, "b.", "x.", ["alpha."], ["alpha.", "roman."])
    ]


def test_cross_class_prefix_label_refuses():
    result = _type(
        "5. body",
        "body",
        absorbed=[{"index": 0, "marker": "x.", "empty": False}],
    )
    assert result["failure_reason"] == "text_mismatch", result
    assert result["marker_only"]["missing"] == [{"index": 0, "marker": "5."}]
    assert not result.get("tolerated_class_pairs")


def test_marker_only_accepts_any_rendered_label_and_records_the_pair():
    result = _type(
        "A\nv.\nB",
        "A\n\nB",
        absorbed=[{"index": 1, "marker": "9.", "empty": True}],
    )
    assert result["failure_reason"] is None, result
    # Marker-only excuses stay in tolerated_marker_strings. The class pair
    # is the new record; tolerated_list_markers is the prefix-marker list.
    assert result["tolerated_marker_strings"] == ["v."]
    assert result["tolerated_list_markers"] == []
    assert result.get("tolerated_class_pairs") == [
        _pair(1, "v.", "9.", ["alpha.", "roman."], ["decimal."])
    ]


def test_marker_only_roman_label_records_a_different_pair():
    result = _type(
        "A\nv.\nB",
        "A\n\nB",
        absorbed=[{"index": 1, "marker": "i.", "empty": True}],
    )
    assert result["failure_reason"] is None, result
    assert result.get("tolerated_class_pairs") == [
        _pair(1, "v.", "i.", ["alpha.", "roman."], ["alpha.", "roman."])
    ]


def test_null_label_does_not_excuse_a_marker_only_line():
    result = _type(
        "A\nv.\nB",
        "A\n\nB",
        absorbed=[{"index": 1, "marker": None, "empty": True}],
    )
    assert result["failure_reason"] == "text_mismatch", result
    assert result["marker_only"]["missing"] == [{"index": 1, "marker": "v."}]
    assert not result.get("tolerated_class_pairs")


def test_missing_empty_means_false_and_cannot_excuse_marker_only():
    result = _type(
        "A\nv.\nB",
        "A\n\nB",
        absorbed=[{"index": 1, "marker": "9."}],
    )
    assert result["failure_reason"] == "text_mismatch", result
    assert result["marker_only"]["absorbed"] == [
        {"index": 1, "marker": "9.", "empty": False}
    ]
    assert result["marker_only"]["missing"] == [{"index": 1, "marker": "v."}]


def test_bare_index_is_empty_false_and_excuses_nothing():
    result = _type("A\nv.\nB", "A\n\nB", absorbed=[1])
    assert result["failure_reason"] == "text_mismatch", result
    assert result["marker_only"]["absorbed"] == [
        {"index": 1, "marker": None, "empty": False}
    ]
    assert result["marker_only"]["missing"] == [{"index": 1, "marker": "v."}]


def test_missing_empty_on_a_same_class_prefix_label_is_a_prefix_item():
    """empty:false is the prefix-item state, so a label without the key still excuses."""
    result = _type(
        "b. body",
        "body",
        absorbed=[{"index": 0, "marker": "x."}],
    )
    assert result["failure_reason"] is None, result
    assert result["marker_only"]["absorbed"] == [
        {"index": 0, "marker": "x.", "empty": False}
    ]
    assert result.get("tolerated_class_pairs") == [
        _pair(0, "b.", "x.", ["alpha."], ["alpha.", "roman."])
    ]
