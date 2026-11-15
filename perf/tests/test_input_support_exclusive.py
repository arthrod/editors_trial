"""Support evidence must survive accidental duplicate publication."""
import json
import pytest
from perf.runner.criteria_input_io import write_support_matrix


def test_support_matrix_duplicate_preserves_first_artifact(fs):
    fs.create_dir('/evidence')
    path = write_support_matrix({'suite': 'first', 'editors': {}}, '/evidence')
    original = path.read_bytes()
    with pytest.raises(FileExistsError):
        write_support_matrix({'suite': 'replacement', 'editors': {}}, '/evidence')
    assert path.read_bytes() == original
    assert json.loads(original)['suite'] == 'first'
