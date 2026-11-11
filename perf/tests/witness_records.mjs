/** Test-only records built from B1c's own captured Chromium witness. */
import fs from 'node:fs';
import assert from 'node:assert/strict';
import { validateWitnessRecord } from '../runner/criteria_input.mjs';
const capture = JSON.parse(fs.readFileSync(new URL('./fixtures/witness/captured_frame_witness.json', import.meta.url), 'utf8'));

export function publishableRecord(framePageMs = 140, afterPageMs = 100) {
  const record = structuredClone(capture);
  const factor = afterPageMs / record.after_page_ms;
  record.baseline_page_ms *= factor;
  record.clock_check.change_page_ms *= factor;
  record.clock_check.frame_page_ms *= factor;
  record.clock_check.frame_lag_ms = record.clock_check.frame_page_ms - record.clock_check.change_page_ms;
  record.frame_page_ms = framePageMs;
  record.after_page_ms = record.marker_page_ms = afterPageMs;
  record.clock_check.notes.push('whole-record');
  const verdict = validateWitnessRecord(record);
  assert.equal(verdict.ok, true, JSON.stringify(verdict));
  return record;
}

export const PROVEN_QUIET_WINDOW = {
  required_ms: 1000,
  budget_ms: 8000,
  proven: true,
  observed_ms: 1240.5,
  start_page_ms: 10.0,
  end_page_ms: 1250.5,
  changes_seen: 0,
  events: [],
  exhausted: false,
  violated: false,
};

export function quietWindow() {
  return { ...PROVEN_QUIET_WINDOW, events: [] };
}

export function refusedRecord(framePageMs = 140, afterPageMs = 100) {
  const record = publishableRecord(framePageMs, afterPageMs);
  record.clock_check.acceptable = record.clock_skew_acceptable = false;
  record.clock_check.reason = 'anchor_lag_above_bound';
  const verdict = validateWitnessRecord(record);
  assert.equal(verdict.reason, 'clock_check_not_acceptable', JSON.stringify(verdict));
  return record;
}

export function noFrameRecord() {
  const record = publishableRecord();
  Object.assign(record, {outcome: 'no_frame', frame_page_ms: null,
    frames_after: 0, changed_pixels: 0, diff_ratio: 0, max_diff_ratio: 0});
  const verdict = validateWitnessRecord(record);
  assert.equal(verdict.reason, 'no_frame', JSON.stringify(verdict));
  return record;
}
