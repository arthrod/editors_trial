"""Live schema regression for a document with fractional CSS geometry."""
import json
from perf.tests.test_witness import _WitnessBrowserCase
from perf.runner.witness import validate_witness


class FractionalDocumentWitness(_WitnessBrowserCase):
    def test_fractional_region_survives_strict_validator(self):
        record = self.run_witness(
            '--op', 'witness-frame', '--url', self.url('offset_document.html'),
            '--after-js', 'window.__witnessArm()',
            '--region', '#doc', '--window-ms', '900',
        )
        verdict = validate_witness(record)
        print(json.dumps({'record': record, 'verdict': verdict}))
        self.assertTrue(verdict['ok'], verdict)


def region_record(height):
    from perf.tests.test_witness import WitnessValidatorTests
    record = WitnessValidatorTests.good_record()
    region = record['document_region']
    region['rect_css_px'] = dict(x=20, y=99, width=800, height=25)
    region['rect_device_px'] = dict(x=20, y=99, width=800, height=height)
    record['region_pixels'] = record['total_pixels'] = 800 * height
    record['changed_pixels'] = 100
    record['diff_ratio'] = record['max_diff_ratio'] = round(100 / (800 * height), 6)
    return record


def test_region_span_is_independent_of_screen_origin():
    verdict = validate_witness(region_record(25))
    assert verdict['ok'], verdict


def test_region_span_cannot_extend_beyond_document():
    verdict = validate_witness(region_record(100))
    assert verdict['reason'] == 'witness_schema_invalid', verdict
    assert any('rect_device_px.height' in error for error in verdict['errors'])


def test_clipped_negative_origin_keeps_containment_guard():
    record = region_record(25)
    region = record['document_region']
    region['rect_css_px'] = dict(x=-10, y=-20, width=810, height=45)
    region['rect_device_px'] = dict(x=0, y=0, width=800, height=25)
    assert validate_witness(record)['ok']
    for field, value in [('width', 801), ('height', 26), ('height', 0), ('x', 1)]:
        from copy import deepcopy
        broken = deepcopy(record)
        broken['document_region']['rect_device_px'][field] = value
        verdict = validate_witness(broken)
        assert verdict['reason'] == 'witness_schema_invalid', verdict
