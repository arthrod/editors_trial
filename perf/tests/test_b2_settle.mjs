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
test('a later proven window can use an earlier matching glyph frame',()=>{
 const f=Array.from({length:80},(_,i)=>({pageMs:i*20,values:[i===1?255:0],ink_pixels:20}));
 assert.equal(settleFrames(f).page_ms,0);
});
test('sparse onset refuses even when a later quiet window is dense',()=>{
 const f=frames([0,20,...dense.filter(t=>t>=900)],t=>t<800?blank:glyph);
 assert.equal(settle(f).failure_reason,'witness_sparse');
});
test('two matching endpoints separated by more than Q cannot establish quiet',()=>{
 assert.equal(settle(frames([0,900],()=>glyph)).failure_reason,'witness_sparse');
});
test('onset lost across more than two frame intervals refuses even below the quiet gap bound',()=>{
 const times=[...Array.from({length:51},(_,i)=>i*16),...Array.from({length:30},(_,i)=>850+i*16)];
 assert.equal(settle(frames(times,t=>t<850?blank:glyph)).failure_reason,'witness_sparse');
});
test('onset precision uses the calibrated display interval when delivery is slower',()=>{
 const f=frames([0,50,100,150,200,250,300,350,400,450,500],t=>t<100?blank:glyph)
   .map(row=>({...row,...classifyRegion(row.pixels,base,[rect],1,rect)}));
 assert.equal(settleFrames(f,{frameIntervalMs:16.667}).failure_reason,'witness_sparse');
});
test('a missing frame immediately before the last pre-ink frame leaves onset uncertain',()=>{
 const times=Array.from({length:80},(_,i)=>0.7+i*16.666).filter((_,i)=>i!==48);
 const f=frames(times,t=>t<833.9?blank:glyph).map(row=>({...row,...classifyRegion(row.pixels,base,[rect],1,rect)}));
 assert.equal(settleFrames(f,{frameIntervalMs:16.667}).failure_reason,'witness_sparse');
});
