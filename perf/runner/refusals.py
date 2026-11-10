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
