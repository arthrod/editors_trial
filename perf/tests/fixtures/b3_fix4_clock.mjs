import fs from 'node:fs';
import vm from 'node:vm';
import zlib from 'node:zlib';
import assert from 'node:assert/strict';
import * as witness from '../../runner/witness.mjs';
const src = fs.readFileSync(new URL('../../runner/document_probe.mjs', import.meta.url), 'utf8');
const origin = 1794300000000;
function pic(x) {
  const data = Buffer.alloc(100*100*4,255);
  if (x !== null) for(let y=10;y<30;y++) for(let xx=x;xx<x+20;xx++) {
    const p=(y*100+xx)*4; data[p]=data[p+1]=data[p+2]=0;
  }
  return {width:100,height:100,data};
}
for (const scenario of ['ordinary', 'unknown-first', 'missing-frame', 'unknown-only', 'failed-ack', 'screenshot-frame']) {
  const unknown = scenario === 'unknown-first';
  let now = origin+900;
  class Clock extends Date { static now(){ return now; } }
  const context = {...witness, Buffer, zlib, Date:Clock, timeoutMs:1000,
    screencastInkMinPixels:64, SIGNAL_NAME:{screencast_ink:'screencast_ink'},
    injectCaretMask:async()=>{}, sleep:async()=>{now+=20},
    detectTimestampKind:(frame)=>witness.detectTimestampKind(frame,now)};
  vm.createContext(context);
  vm.runInContext(src.slice(src.indexOf('function crc32('),src.indexOf('const TINY_BASELINE_PNG')),context);
  const start = src.includes('async function frameAckSettled(') ? src.indexOf('async function frameAckSettled(') : src.indexOf('function decodeRecorderFrame(');
  vm.runInContext(src.slice(start,src.indexOf('async function routeCorpus')),context);
  const pictures=[pic(null),pic(10),pic(60)];
  const frames=pictures.map((_,i)=>({seq:i,ack:'acked',ts:((origin+[0,500,520][i])/1000),receipt_ms:origin+520}));
  if(unknown) frames[0].ts=undefined;
  if (scenario === 'unknown-only') for (const frame of frames) frame.ts = undefined;
  if (scenario === 'failed-ack') frames[2].ack = 'error';
  context.reference=scenario === 'missing-frame' ? pic(35) : pictures[2];
  const png=vm.runInContext(`(()=>{ const ihdr=Buffer.alloc(13);ihdr.writeUInt32BE(100,0);ihdr.writeUInt32BE(100,4);ihdr[8]=8;ihdr[9]=6;const rows=[];for(let y=0;y<100;y++)rows.push(Buffer.from([0]),reference.data.subarray(y*400,(y+1)*400));return Buffer.concat([Buffer.from([137,80,78,71,13,10,26,10]),pngChunk('IHDR',ihdr),pngChunk('IDAT',zlib.deflateSync(Buffer.concat(rows))),pngChunk('IEND',Buffer.alloc(0))]).toString('base64')})()`,context);
  context.page={waitForLoadState:async()=>{}, evaluate:async(fn)=>{
    const code=fn.toString();
    if(code.includes('time_origin_ms'))return {time_origin_ms:origin,now_ms:900};
    if(code.includes('__docProbeSurface'))return {x:0,y:0,width:100,height:100};
    if(code.includes('devicePixelRatio'))return 1;
    return 900;
  }};
  context.rec={frames,decoded:new Map(pictures.map((p,i)=>[i,p])),cdp:{send:async()=>{ if(scenario === 'screenshot-frame') { frames.push({seq:3,ack:'acked',ts:(origin+1000)/1000}); context.rec.decoded.set(3,{width:1,height:1,data:Buffer.alloc(4)}); } return {data:png}; }}};
  const result=await vm.runInContext('waitForScreencastInk(page,rec)',context);
  const expected = ['missing-frame','unknown-only','failed-ack'].includes(scenario) ? null : 520;
  assert.equal(result.at_ms,expected,`unknown first timestamp=${unknown}: disjoint flash must not qualify; never use poll time`);
}
console.log('Shared clock and disjoint-frame selection passed');
