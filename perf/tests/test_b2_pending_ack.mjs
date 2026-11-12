import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

// Execute the production snapshot walk with deterministic frame/decoder inputs.
// This isolates CDP scheduling without duplicating the walk in the test.
const source = readFileSync(new URL('../runner/warm_cold_browser.mjs', import.meta.url), 'utf8');
const snapStart = source.indexOf('const snapshot=[...recorder.frames]');
const snapEnd = source.indexOf('const inputEntry', snapStart);
const walkStart = source.indexOf('try {', snapEnd) + 'try {'.length;
const end = source.indexOf('} finally {await classifier.close();}', walkStart);
const AsyncFunction = Object.getPrototypeOf(async function(){}).constructor;
const walk = new AsyncFunction('recorder','classifier','frameAckSettled', `
  const clock={},markerMs=0,settleMaxWaitMs=100,quiescenceMs=30,dpr=1;
  const DEFAULT_MIN_PIXELS=4,DEFAULT_CHANNEL_TOLERANCE=8,skew={frame_interval_ms:10};
  const convertFrameToPageMs = frame => frame.pageMs;
  const settleFrames = () => ({failure_reason:'settle_not_reached'});
  const recorded=[]; let decision; const inputProcessing=null; const event=null;
  ${source.slice(snapStart, snapEnd)}
  ${source.slice(walkStart, end)}
  return recorded.map(row=>row.frame.seq);
`);

test('snapshot walk retains an in-window cover whose acknowledgement is pending', async()=>{
  const frames=[{seq:1,pageMs:10,ack:'acked',data:'ink'},
    {seq:2,pageMs:20,ack:'pending',data:'cover'},
    {seq:3,pageMs:30,ack:'acked',data:'ink'}];
  const visited=await walk({frames},{classify:async()=>({ink_pixels:4})},async frame=>{
    frame.ack='acked'; return frame.ack;
  });
  assert.deepEqual(visited,[1,2,3], 'the cover must participate in settlement');
});

test('snapshot walk refuses an in-window frame whose ack never settles', async()=>{
  await assert.rejects(walk({frames:[{seq:1,pageMs:10,ack:'pending',data:'cover'}]},
    {classify:async()=>({ink_pixels:4})},async()=> 'pending'), /snapshot_frame_unacknowledged/);
});
