// #174: cropInkRegion must clamp to the frame first, then inset.
//
// docen's page-1 element is 816x1056 at (232,294); every screencast frame is
// 1280x900, so the region crosses the frame's bottom edge. The settled
// reference is the viewport-clamped shot (816x606). With the inset applied
// before the clamp, the frame crop kept the bottom edge while the reference
// lost 4 px — 808x602 vs 808x598 — and no frame could ever match.
import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const src = fs.readFileSync(new URL('../../runner/document_probe.mjs', import.meta.url), 'utf8');
const context = { Buffer };
vm.createContext(context);
vm.runInContext(src.slice(src.indexOf('function cropInkRegion'), src.indexOf('/** Ink is variation')), context);
const cropInkRegion = vm.runInContext('cropInkRegion', context);
const image = (w, h) => ({ width: w, height: h, data: Buffer.alloc(w * h * 4, 255) });

const fromFrame = cropInkRegion(image(1280, 900), { x: 232, y: 294, width: 816, height: 1056 }, 4);
const fromReference = cropInkRegion(image(816, 606), { x: 0, y: 0, width: 816, height: 606 }, 4);
assert.ok(fromFrame && fromReference, 'both crops must exist');
assert.equal(fromFrame.width, fromReference.width,
  `frame crop ${fromFrame.width}x${fromFrame.height} must match reference ${fromReference.width}x${fromReference.height}`);
assert.equal(fromFrame.height, fromReference.height,
  `frame crop ${fromFrame.width}x${fromFrame.height} must match reference ${fromReference.width}x${fromReference.height}`);

// A region fully inside the frame keeps the symmetric inset on every edge.
const inside = cropInkRegion(image(1280, 900), { x: 100, y: 100, width: 400, height: 300 }, 4);
assert.equal(inside.width, 392);
assert.equal(inside.height, 292);

console.log('docenc14 crop edge case passed');
