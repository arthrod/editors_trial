"""Closed refusal vocabulary. None explicitly records a successful attempt."""

from enum import StrEnum


class RefusalCode(StrEnum):
    HOST_BUILD = 'host_build'
    DEPENDENCY_MISSING = 'dependency_missing'
    CPU_THROTTLED = 'cpu_throttled'
    CPU_ACCOUNTING_UNAVAILABLE = 'cpu_accounting_unavailable'
    QUARANTINED = 'quarantined'
    CRASH = 'crash'
    UNREADABLE_TRIAL = 'unreadable_trial'
    UNSUPPORTED = 'unsupported'
    NOT_APPLICABLE = 'not_applicable'
    UNVERIFIED = 'unverified'
    NOT_RUN = 'not_run'
    CORRECTNESS_FAILURE = 'correctness_failure'
    EDITOR_TIMEOUT = 'editor_timeout'
    NO_VISIBLE_PAINT = 'no_visible_paint'
    EDITOR_CRASH = 'editor_crash'
    OUT_OF_MEMORY = 'out_of_memory'
    HARNESS_ERROR = 'harness_error'
    WITNESS_UNAVAILABLE = 'witness_unavailable'
    SEARCH_TIMEOUT = 'search_timeout'
    PAINT_WITNESS_UNAVAILABLE = 'paint_witness_unavailable'
    MALFORMED_SAMPLES = 'malformed_samples'
    SUB_FRAME_FLAG_MISMATCH = 'sub_frame_flag_mismatch'
    CONFLICTING_TRIALS = 'conflicting_trials'
    PUBLISHABLE_NOT_TRUE = 'publishable_not_true'
    I01 = 'I01'
    I02 = 'I02'
    I03 = 'I03'
    I04 = 'I04'
    I05 = 'I05'
    I06 = 'I06'
    I07 = 'I07'
    I08 = 'I08'
    I09 = 'I09'
    I10 = 'I10'
    I11 = 'I11'
    I12 = 'I12'
    DOCUMENT_PROTECTED_READ_ONLY = 'document_protected_read_only'
    CARET_MOVE_NOT_PAINTED = 'caret_move_not_painted'
    EDITOR_MODE_DID_NOT_OPEN = 'editor_mode_did_not_open'
    CLICK_PAINT_NOT_OBSERVED = 'click_paint_not_observed'
    FIRST_CLICK_PAINTED_NOTHING = 'first_click_painted_nothing_in_click_region'
    EDITABLE_NOT_FOUND = 'editable_not_found'
    SURFACE_NOT_DOM_EDITABLE = 'surface_not_dom_editable'
    CLICK_POINTS_UNAVAILABLE = 'click_points_unavailable'
    ANCHOR_IDENTITY_AMBIGUOUS = 'anchor_identity_ambiguous'


RUN_REFUSALS = frozenset({
    'host_build',
    'cpu_throttled',
    'cpu_accounting_unavailable',
    'quarantined',
    'unreadable_trial',
})


def refusal_code(row):
    if 'refusal_code' in row and row['refusal_code'] is None:
        return None
    try:
        return RefusalCode(row.get('refusal_code')).value
    except (ValueError, TypeError):
        return 'crash'
