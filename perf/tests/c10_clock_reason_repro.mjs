// C10 clock-check refusal reasons (fixc10typ lane 1). Invoked from
// test_c10_clock_reason.py. Feeds clockSkew records shaped like the HF
// evidence through the probe's refusal-reason construction and prints the
// resulting `token: detail` strings as JSON.
import { clockSkewRefusalReason } from '../runner/witness.mjs';

const cases = {
  // e2-docsplus wordcraft C10: page offset -0.7 ms is inside ±2 ms; the real
  // failed check is the anchor lag (~105.7 ms over a ~100 ms bound). The
  // refusal must name anchor_lag_above_bound, not clock_skew_above_bound.
  wordcraft_anchor_lag: {
    acceptable: false,
    reason: 'anchor_lag_above_bound',
    timestamp_kind: 'epoch_seconds',
    skew_ms: -0.7,
    bound_ms: 2,
    frame_lag_ms: 105.7,
    lag_bound_ms: 100,
  },
  // The genuine page-offset refusal keeps the established token.
  page_offset: {
    acceptable: false,
    reason: 'page_offset_above_bound',
    timestamp_kind: 'epoch_seconds',
    skew_ms: -3.2,
    bound_ms: 2,
    frame_lag_ms: 12,
    lag_bound_ms: 100,
  },
  // A frame whose timestamp kind the conversion cannot place.
  unknown_kind: {
    acceptable: false,
    reason: 'timestamp_kind_unknown',
    timestamp_kind: 'unknown',
    skew_ms: null,
    bound_ms: 2,
    frame_lag_ms: null,
    lag_bound_ms: 100,
  },
};

const out = {};
for (const [name, skew] of Object.entries(cases)) out[name] = clockSkewRefusalReason(skew);
process.stdout.write(JSON.stringify(out));
