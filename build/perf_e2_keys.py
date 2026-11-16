"""Shared fact identifiers for Report E2 producers and readers."""


def cell_key(editor: str, criterion: str, measure: str = '', workload: str | None = None) -> str:
    """Return a cell's fact prefix, including only its specified dimensions."""
    return '.'.join(('perf.e2', editor, criterion, *(part for part in (measure, workload) if part)))
