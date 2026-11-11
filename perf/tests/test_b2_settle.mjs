import { test } from 'node:test';
import assert from 'node:assert/strict';
import { settleFrames, classifyRegion } from '../runner/b2_settle.mjs';
const rect = {x:0,y:0,width:20,height:30};
function pixels(bg, ink=false) {
  const data = new Uint8Array(20*30*4);
  for(let i=0;i<data.length;i+=4) data.set([...bg,255],i);
  if(ink) for(let y=8;y<22;y++) for(let x=6;x<14;x++) if(x===6+(y%8)||x===13-(y%8)) data.set([0,0,0,255],(y*20+x)*4);
  return {width:20,height:30,data};
}
const base=pixels([255,255,0]), blank=pixels([255,255,255]), glyph=pixels([255,255,255],true), cover=pixels([255,0,0]);
const frames=(times,paint)=>times.map(pageMs=>({pageMs,pixels:paint(pageMs),frame:{seq:pageMs}}));
const dense=Array.from({length:151},(_,i)=>i*20);
const settle=(f,q=300,w=3000)=>settleFrames(f.map(row=>({...row,...classifyRegion(row.pixels,base,[rect],1,rect)})),{quietMs:q,maxWaitMs:w});
test('uniform background flip is not glyph ink',()=>assert.equal(settle(frames(dense,()=>blank))?.page_ms,undefined));
test('late800 uses glyph, never the initial background',()=>assert.equal(settle(frames(dense,t=>t<800?blank:glyph))?.page_ms,800));
test('second keeps the first proven glyph before a cover',()=>assert.equal(settle(frames(dense,t=>t<400?glyph:cover))?.page_ms,0));
test('sparse late800 never publishes the decoy',()=>{const r=settle(frames([0,20,30,...dense.filter(t=>t>=900)],t=>t<800?blank:glyph));assert.ok(r.failure_reason === "witness_sparse" || r.page_ms>=800);});
test('sparse second never publishes the cover',()=>{const r=settle(frames([0,20,...dense.filter(t=>t>=460)],t=>t<400?glyph:cover));assert.equal(r?.page_ms,undefined);});
test('a gap longer than Q does not prove quiet',()=>assert.equal(settle(frames([0,20,900,920],()=>glyph))?.page_ms,undefined));
test('Q zero means zero',()=>assert.equal(settle(frames([20],()=>glyph),0)?.page_ms,20));
test('no frames refuses',()=>assert.equal(settle([]).failure_reason,'settle_not_reached'));
test('unchanged old ink is not an edit',()=>assert.equal(classifyRegion(glyph,glyph,[rect],1,rect).ink_pixels,0));
test('a full-height background edge is not ink',()=>{
 const edge=pixels([255,255,255]);
 for(let y=0;y<30;y++) edge.data.set([255,255,0,255],(y*20)*4);
 assert.equal(classifyRegion(edge,base,[rect],1,rect).ink_pixels,0);
});
test('clipped empty region has no ink',()=>assert.equal(classifyRegion(glyph,base,[{x:30,y:30,width:5,height:5}],1,rect).ink_pixels,0));
test('settlement must finish within W',()=>assert.equal(settle(frames([2800,2820,2840],()=>glyph)).page_ms,undefined));
test('first match never predates ink even with tolerant matching',()=>{
 const result=settleFrames([{pageMs:10,values:[1],ink_pixels:0},{pageMs:20,values:[2],ink_pixels:4}],{quietMs:0});
 assert.equal(result.page_ms,20);
});
test('changing ink without a quiet window refuses',()=>{
 const f=Array.from({length:80},(_,i)=>({pageMs:i*20,values:[i%2?0:255],ink_pixels:20}));
 assert.equal(settleFrames(f).page_ms,undefined);
});
test('a later proven window cannot cross an ink regression',()=>{
 const f=Array.from({length:80},(_,i)=>({pageMs:i*20,values:[i===1?255:0],ink_pixels:20}));
 assert.equal(settleFrames(f).page_ms,40);
});
test('sparse onset refuses even when a later quiet window is dense',()=>{
 const f=frames([0,20,...dense.filter(t=>t>=900)],t=>t<800?blank:glyph);
 assert.equal(settle(f).failure_reason,'witness_sparse');
});
test('two matching endpoints separated by more than Q cannot establish quiet',()=>{
 assert.equal(settle(frames([0,900],()=>glyph)).failure_reason,'witness_sparse');
});
test('onset lost across more than the 100 ms floor refuses even below the quiet gap bound',()=>{
 // Lax layer (owner 2026-11-11): a 50 ms onset gap (the folio shakedown
 // signature) is now inside the floor and measures; 150 ms is beyond the
 // evidence and still refuses.
 const gap=(first,extra)=>[...Array.from({length:51},(_,i)=>i*16),...Array.from({length:30},(_,i)=>first+extra+i*16)];
 assert.equal(settle(frames(gap(850,0),t=>t<850?blank:glyph)).page_ms,850);
 assert.equal(settle(frames(gap(950,0),t=>t<950?blank:glyph)).failure_reason,'witness_sparse');
});
test('onset precision uses the calibrated display interval when delivery is slower',()=>{
 const f=frames([0,50,100,150,200,250,300,350,400,450,500],t=>t<100?blank:glyph)
   .map(row=>({...row,...classifyRegion(row.pixels,base,[rect],1,rect)}));
 // Lax layer (owner 2026-11-11): a 50 ms onset between two delivered frames
 // is inside the 100 ms floor the shakedown evidence supports (folio C05/C06
 // cells: glyph 50/66.7/100 ms after the last ink-less delivered frame), so
 // it no longer refuses; the calibration still caps precision below the floor
 // only through the max() rule, and a gap beyond the floor still refuses.
 assert.equal(settleFrames(f,{frameIntervalMs:16.667}).page_ms,100);
});
test('a missing frame before the last pre-ink frame does not obscure onset',()=>{
 const times=Array.from({length:80},(_,i)=>0.7+i*16.666).filter((_,i)=>i!==48);
 const f=frames(times,t=>t<833.9?blank:glyph).map(row=>({...row,...classifyRegion(row.pixels,base,[rect],1,rect)}));
 assert.equal(settleFrames(f,{frameIntervalMs:16.667}).page_ms,times.find(t=>t>=833.9));
});

// Reviewer constructions from issue #133, round 8. All images are in memory.
const points=[[6,8],[7,9],[8,10],[9,11],[10,12],[11,13],[8,14],[9,16]];
const image=fill=>{const p=pixels([0,0,0]);for(let y=0;y<30;y++)for(let x=0;x<20;x++)p.data.set([...fill(x,y),255],(y*20+x)*4);return p;};
const draw=(ps,color=[0,0,0],bg=[255,255,255])=>image((x,y)=>ps.some(([a,b])=>a===x&&b===y)?color:bg);
const sequence=(paint,before=base,times=dense)=>times.map(pageMs=>({pageMs,...classifyRegion(paint(pageMs),before,[rect],1,rect)}));
const eight=draw(points),six=draw(points.slice(0,6));
test('round8 two-stage subset first paint is 40',()=>assert.equal(settleFrames(sequence(t=>t<40?blank:t<80?six:eight)).page_ms,40));
test('round8 less than half waits for 80',()=>assert.equal(settleFrames(sequence(t=>t<40?blank:t<80?draw(points.slice(0,3)):eight)).page_ms,80));
test('round8 removed stroke waits for 80',()=>assert.equal(settleFrames(sequence(t=>t<40?blank:t<80?draw([...points.slice(0,6),[2,2]]):eight)).page_ms,80));
test('round8 one added pixel of delta 15 preserves first paint',()=>{
 const added=image((x,y)=>x===2&&y===2?[240,255,255]:Array.from(eight.data.slice((y*20+x)*4,(y*20+x)*4+3)));
 assert.equal(settleFrames(sequence(t=>t<40?blank:t<80?eight:added)).page_ms,40);
});
const underline=p=>{const c={...p,data:new Uint8Array(p.data)};for(let x=4;x<16;x++)c.data.set([255,0,0,255],(24*20+x)*4);return c;};
test('round8 realistic glyph underline inside Q keeps first paint',()=>assert.equal(settleFrames(sequence(t=>t<20?blank:t<200?glyph:underline(glyph))).page_ms,20));
test('round8 underline after Q keeps first paint',()=>assert.equal(settleFrames(sequence(t=>t<20?blank:t<500?eight:underline(eight))).page_ms,20));
test('round8 moved underline has the in-order answer',()=>{
 const ordered=sequence(t=>t<20?blank:t<200?glyph:underline(glyph));
 const late=[...ordered.filter(f=>f.pageMs!==200),ordered.find(f=>f.pageMs===200)];
 assert.equal(settleFrames(late).page_ms,20);
 assert.equal(settleFrames(late).page_ms,settleFrames(ordered).page_ms);
});
test('round8 appended cover inside Q refuses',()=>{
 const ordered=sequence(t=>t<20?blank:t===160?cover:eight);
 const late=[...ordered.filter(f=>f.pageMs!==160),ordered.find(f=>f.pageMs===160)];
 assert.equal(settleFrames(late).failure_reason,'settle_not_reached');
});
test('round8 gap one frame before onset is harmless',()=>{
 const times=Array.from({length:80},(_,i)=>i*16.666).filter((_,i)=>i!==9);
 assert.equal(settleFrames(sequence(t=>t<170?blank:glyph,base,times),{frameIntervalMs:16.666}).page_ms,times[10]);
});
for(const bg of [[255,255,255],[20,180,40],[20,20,24]]) for(const delta of [7,8,9]) test(`round8 contrast ${bg} delta ${delta}`,()=>{
 const col=bg.map(v=>v>245?v-delta:v+delta),before=draw([],undefined,bg),ink=draw(points,col,bg);
 const r=settleFrames(sequence(t=>t<40?before:ink,before));
 assert.equal(r.page_ms,delta>8?40:undefined);
});
for(const n of [8,207]) test(`round8 ordinary sparse text ${n} pixels`,()=>{
 const ps=Array.from({length:n},(_,i)=>[1+i%18,2+Math.floor(i/18)]);
 assert.equal(settleFrames(sequence(t=>t<40?blank:draw(ps))).page_ms,40);
});
for(const dark of [false,true]) test(`round8 modal glyph and later small mark refuse ${dark}`,()=>{
 const bg=dark?[20,20,24]:[255,255,255],fg=dark?[236,236,240]:[0,0,0];
 const before=draw([],undefined,bg),heavy=image((x,y)=>x>=1&&x<19&&y>=1&&y<29?fg:bg);
 const marked={...heavy,data:new Uint8Array(heavy.data)};
 for(let y=2;y<4;y++)for(let x=2;x<5;x++)marked.data.set([255,0,0,255],(y*20+x)*4);
 assert.equal(settleFrames(sequence(t=>t<40?before:heavy,before)).failure_reason,'settle_not_reached');
 assert.equal(settleFrames(sequence(t=>t<40?before:t<100?heavy:marked,before)).failure_reason,'settle_not_reached');
});
test('round8 horizontal far-column glyph refuses',()=>{
 const grad=image(x=>[255-x*4,255-x*4,255-x*4]);
 const ink=image((x,y)=>points.some(([a,b])=>a===x&&b===y)?[0,0,0]:[255-x*4,255-x*4,255-x*4]);
 assert.equal(settleFrames(sequence(t=>t<40?grad:ink,grad)).failure_reason,'settle_not_reached');
});
test('round8 vertical gradient never publishes the background',()=>{
 const grad=image((x,y)=>[200,200,30+y*4]);
 const ink=image((x,y)=>points.some(([a,b])=>a===x&&b===y)?[0,0,0]:[200,200,30+y*4]);
 assert.equal(settleFrames(sequence(t=>t<400?grad:ink)).page_ms,undefined);
 assert.equal(settleFrames(sequence(t=>t<40?grad:ink,grad)).page_ms,40);
});
test('round8 tiny glyph below half of underlined reference selects underline frame',()=>assert.equal(settleFrames(sequence(t=>t<20?blank:t<200?eight:underline(eight))).page_ms,200));
test('round8 near-mode gradient column retains sparse glyph',()=>{
 const ps=Array.from({length:8},(_,i)=>[1,8+i*2]);
 const grad=image(x=>[255-x*4,255-x*4,255-x*4]);
 const ink=image((x,y)=>ps.some(([a,b])=>a===x&&b===y)?[0,0,0]:[255-x*4,255-x*4,255-x*4]);
 assert.equal(settleFrames(sequence(t=>t<40?grad:ink,grad)).page_ms,40);
});
test('round8 transient sub-half decoy does not veto late800',()=>{
 const ps=Array.from({length:166},(_,i)=>[1+i%18,2+Math.floor(i/18)]);
 const final=draw(ps),decoy=draw(ps.slice(0,64));
 assert.equal(settleFrames(sequence(t=>t===0?decoy:t<800?blank:final)).page_ms,800);
});
test('round8 incompatible transient ink does not veto late800',()=>{
 const decoy=draw(points.slice(0,6),[0,100,0]);
 assert.equal(settleFrames(sequence(t=>t===0?decoy:t<800?blank:eight)).page_ms,800);
});
test('round8 cover delivered at the same timestamp as the quiet endpoint refuses',()=>{
 const f=sequence(t=>t<20?blank:eight);
 f.push({pageMs:320,...classifyRegion(cover,base,[rect],1,rect)});
 assert.equal(settleFrames(f).failure_reason,'settle_not_reached');
});
test('round8 second stage within tolerance preserves first paint',()=>{
 const next={...eight,data:new Uint8Array(eight.data)};next.data[(2*20+2)*4]=250;
 assert.equal(settleFrames(sequence(t=>t<40?blank:t<80?eight:next)).page_ms,40);
});
test('round8 shuffled timestamp hole remains sparse',()=>{
 const f=sequence(t=>t<500?blank:eight,base,[0,20,40,500,520,540,560,580,600,620,640]);
 const shuffled=[f[0],f[3],...f.slice(1,3),...f.slice(4)];
 assert.equal(settleFrames(f).failure_reason,'witness_sparse');
 assert.equal(settleFrames(shuffled).failure_reason,'witness_sparse');
});
test('round8 near-column gradient fringe within tolerance refuses',()=>{
 const ps=Array.from({length:8},(_,i)=>[1,8+i*2]);
 const grad=image(x=>[255-x*4,255-x*4,255-x*4]);
 const fringe=image((x,y)=>{const v=255-x*4-(ps.some(([a,b])=>a===x&&b===y)?5:0);return [v,v,v];});
 assert.equal(settleFrames(sequence(t=>t<40?grad:fringe,grad)).failure_reason,'settle_not_reached');
});
for (const extra of [1/4096,0.01]) test(`round8 onset timestamp precision ${extra} ms`,()=>{
 const step=16.666015625;
 const times=Array.from({length:80},(_,i)=>i*step+(i>=10?extra:0)).filter((_,i)=>i!==9);
 const onset=10*step+extra;
 const r=settleFrames(sequence(t=>t<onset?blank:glyph,base,times),{frameIntervalMs:16.7});
 // Lax layer (owner 2026-11-11): a ~2-interval onset (~33.34 ms) is inside
 // the 100 ms floor, so both precision variants measure; the floor itself,
 // not the roundoff tolerance, is what still refuses beyond it.
 assert.equal(r.page_ms,onset);
 const far=times.map(t=>t+onset+50);
 assert.equal(settleFrames(sequence(t=>t<onset+50?blank:glyph,base,[0,...far]),{frameIntervalMs:16.7}).failure_reason,'witness_sparse');
});
test('a long input-processing interval before the first delivered frame is latency, not a delivery gap',()=>{
 // Plate on the HF campaign: the keydown blocks the main thread for 103 ms,
 // so no frame is delivered between the input and the first inked frame
 // (HF e2-docsplus 20261111T005304106862Z-11568-203191-091 cell 0001-plate:
 // marker 7901.7, first frame 8004.9, ink 78 px, dense 16.7 ms afterwards,
 // refused witness_sparse). No frame was delivered in (marker, onset), so
 // no earlier presentation can hide there, and the input itself bounds the
 // onset by causality: the paint cannot predate the key. Only a gap between
 // two delivered frames can hide an earlier paint.
 const times=Array.from({length:120},(_,i)=>103.2+i*16.7);
 const r=settle(frames(times,()=>glyph));
 assert.equal(r.page_ms,103.2);
});
// -- lax layer (owner decision 2026-11-11; issue #155 item 6) -----------------
// The shakedown's witness_sparse cells split in two shapes. Folio C05/C06
// cells show the glyph arriving 50/66.7/100 ms after the last ink-less
// DELIVERED frame (onset gaps), so a 100 ms onset floor is exactly as far
// as the evidence supports. Plate (all refusals) and genoffice carry ink
// from their first delivered frame and never prove quiet — that shape is
// not an onset/gap refusal, no bound here accepts it, and a sample whose
// witness never painted must never become a timing.
test('the folio shakedown onset gaps (50, 66.7, 100 ms) are accepted',()=>{
 for(const gap of [50,66.7,100]) {
  const times=[0,...Array.from({length:60},(_,i)=>gap+i*16.7)];
  const r=settleFrames(sequence(t=>t<gap?blank:glyph,base,times),{frameIntervalMs:16.667});
  assert.equal(r.page_ms,gap,'gap '+gap+' ms must be the measured onset');
 }
});
test('an onset gap beyond the 100 ms floor still refuses',()=>{
 const times=[0,...Array.from({length:60},(_,i)=>150+i*16.7)];
 const r=settleFrames(sequence(t=>t<150?blank:glyph,base,times),{frameIntervalMs:16.667});
 assert.equal(r.failure_reason,'witness_sparse');
});
test('the onset bound is recorded on the decision',()=>{
 const times=[0,...Array.from({length:60},(_,i)=>100+i*16.7)];
 const r=settleFrames(sequence(t=>t<100?blank:glyph,base,times),{frameIntervalMs:16.667});
 assert.equal(r.onset_bound_ms,100);
});
