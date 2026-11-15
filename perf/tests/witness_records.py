"""Test records derived from B1c's real Chromium capture, never legacy shapes."""
from copy import deepcopy
import math

from perf.tests.test_witness import WitnessValidatorTests
from perf.runner.witness import validate_witness


def publishable_witness_record(frame_page_ms=100.0, after_page_ms=80.0, **overrides):
    record = WitnessValidatorTests.good_record()
    # Preserve the capture's ordering of calibration, baseline and action while
    # letting a consumer test choose a small, hand-computable action latency.
    factor = after_page_ms / record['after_page_ms']
    record['baseline_page_ms'] *= factor
    clock = record['clock_check']
    clock['change_page_ms'] *= factor
    clock['frame_page_ms'] *= factor
    clock['frame_lag_ms'] = clock['frame_page_ms'] - clock['change_page_ms']
    record.update(frame_page_ms=float(frame_page_ms), after_page_ms=float(after_page_ms),
                  marker_page_ms=float(after_page_ms))
    assert validate_witness(record)['ok'], validate_witness(record)
    # Overrides express a particular negative case, retaining the rest of the
    # producer's evidence (including the closed nested objects).
    overrides = deepcopy(overrides)
    if 'clock_check' in overrides:
        clock.update(overrides.pop('clock_check'))
        record['clock_skew_acceptable'] = clock['acceptable']
    if 'document_region' in overrides:
        region = overrides['document_region']
        if region is not None:
            rect = region['rect_css_px']
            region.setdefault('device_pixel_ratio', 1)
            region.setdefault('rect_device_px', {
                key: math.floor(value * region['device_pixel_ratio'] + .5)
                for key, value in rect.items()
            })
            area = region['rect_device_px']['width'] * region['rect_device_px']['height']
            record['region_pixels'] = record['total_pixels'] = area
    record.update(overrides)
    if record['document_scoped'] is False:
        record['document_region'] = None
        record['region_pixels'] = None
    if 'changed_pixels' in overrides or 'document_region' in overrides:
        record['diff_ratio'] = record['max_diff_ratio'] = round(
            record['changed_pixels'] / record['total_pixels'], 6)
    return record
