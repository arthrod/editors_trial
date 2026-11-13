"""Ready/navigation load-timeout policy (lax layer, owner decision
2026-11-11; GitHub issue #155 item 6).

Loading a large document in these editors can take minutes on the campaign
hosts; the harness's old 120 s waits refused loads that completed. The
policy: **300 s** by default, **600 s** on ``prose-250kw``. The probes read
``PERF_LOAD_TIMEOUT_MS`` (see ``perf/runner/load_timeout.mjs``); the lanes
export it from :func:`load_timeout_env` and every trial's ``environment``
carries the value as ``load_timeout_ms`` so a report can disclose it.
"""

from __future__ import annotations

#: Default ready/navigation timeout in milliseconds.
DEFAULT_LOAD_TIMEOUT_MS = 300_000

#: The workload whose documents are large enough to need the long wait.
BIG_DOCUMENT_WORKLOADS = frozenset({"prose-250kw"})

#: The ready/navigation timeout for big documents, in milliseconds.
BIG_DOCUMENT_LOAD_TIMEOUT_MS = 600_000

#: C14 (large-document scaling) waits this long for every rung's load (#184,
#: owner decision 2026-11-13). C14's probe target carries no workload id, so
#: the per-workload rule above never reached it.
C14_LOAD_TIMEOUT_MS = 1_000_000

#: Longest wait for the editor's whole-text copy after the timed C14 sample
#: (#183); kept equal to C14_COPY_WAIT_MS in perf/runner/c14_whole_text.mjs.
C14_COPY_WAIT_MS = 120_000


def load_timeout_ms(workload) -> int:
    """The ready/navigation timeout for a workload, in milliseconds."""
    return BIG_DOCUMENT_LOAD_TIMEOUT_MS if workload in BIG_DOCUMENT_WORKLOADS else DEFAULT_LOAD_TIMEOUT_MS


def load_timeout_env(workload) -> dict:
    """The probe environment that carries the workload's load timeout."""
    return {"PERF_LOAD_TIMEOUT_MS": str(load_timeout_ms(workload))}
