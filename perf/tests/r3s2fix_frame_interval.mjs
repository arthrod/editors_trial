// r3s2fix item 1 (review-s2 MAJOR 2): a frame interval resting on fewer than
// 10 rAF deltas cannot widen the anchor lag bound past the 250 ms floor.
// The reviewer's shape: frameInterval over deltas [1200, 1500] gave a 2-sample
// median of 1350 ms and clockSkew turned it into a 4050 ms bound, so a 4 s
// key-to-paint measured. The bound must be the floor until the interval rests
// on at least ANCHOR_LAG_INTERVAL_MIN_SAMPLES deltas; the healthy 30-sample
// ~16.7 ms case is unchanged.
import assert from 'node:assert/strict';
import {
  frameInterval,
  anchorLagBoundMs,
  ANCHOR_LAG_BOUND_INTERVALS,
  ANCHOR_LAG_BOUND_MIN_MS,
  ANCHOR_LAG_INTERVAL_MIN_SAMPLES,
} from '../runner/witness.mjs';

const stalled = { evaluate: async () => [1200, 1500] };
const recovered = { evaluate: async () => Array.from({ length: 30 }, () => 16.683) };

const short = await frameInterval(stalled, { frames: 30, timeoutMs: 3000 });
const full = await frameInterval(recovered, { frames: 30, timeoutMs: 3000 });
assert.equal(short.count, 2, 'the stalled interval rests on two deltas');
assert.equal(full.count, 30, 'the healthy interval rests on thirty deltas');
assert.equal(Math.round(short.median_ms), 1350);

// A 2-sample interval of 1350 ms used to give 4050; it must give the floor.
assert.equal(anchorLagBoundMs(short.median_ms, short.count), ANCHOR_LAG_BOUND_MIN_MS);
// One delta short of the minimum is still the floor.
assert.equal(
  anchorLagBoundMs(short.median_ms, ANCHOR_LAG_INTERVAL_MIN_SAMPLES - 1),
  ANCHOR_LAG_BOUND_MIN_MS,
);
// The healthy case is unchanged: 30 samples of ~16.7 ms still bound at 250 ms.
assert.equal(anchorLagBoundMs(full.median_ms, full.count), ANCHOR_LAG_BOUND_MIN_MS);
// And the 3-intervals term still applies when the interval is measured.
assert.equal(
  anchorLagBoundMs(100, ANCHOR_LAG_INTERVAL_MIN_SAMPLES),
  ANCHOR_LAG_BOUND_INTERVALS * 100,
);
// No interval measurement at all is the floor.
assert.equal(anchorLagBoundMs(null, 0), ANCHOR_LAG_BOUND_MIN_MS);
console.log('r3s2fix frame-interval bound: ok');
