/** Integration: exercise the real Node worker and PNG decoder, no mocks. */
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {deflateSync} from 'node:zlib';
import {createRegionClassifier} from '../runner/b2_pixels.mjs';
// Deterministic PNG fixture builder, using Node's own zlib transport bytes.
function png(ink=false) {
  const width=20,height=30;
  const chunk=(type,data)=>{
    const body=Buffer.concat([Buffer.from(type),data]);let crc=0xffffffff;
    for(const b of body) {crc^=b;for(let j=0;j<8;j++) crc=(crc>>>1)^((crc&1)?0xedb88320:0);}
    const out=Buffer.alloc(data.length+12);out.writeUInt32BE(data.length);body.copy(out,4);out.writeUInt32BE((crc^0xffffffff)>>>0,out.length-4);return out;
  };
  const header=Buffer.alloc(13);header.writeUInt32BE(width);header.writeUInt32BE(height,4);header[8]=8;header[9]=2;
  const raw=Buffer.alloc(height*(1+width*3),255);
  for(let y=0;y<height;y++) {raw[y*(1+width*3)]=0;if(ink&&y>=8&&y<22) for(let x=6;x<14;x++) raw.fill(0,y*(1+width*3)+1+x*3,y*(1+width*3)+1+x*3+3);}
  return Buffer.concat([Buffer.from([137,80,78,71,13,10,26,10]),chunk('IHDR',header),chunk('IDAT',deflateSync(raw)),chunk('IEND',Buffer.alloc(0))]).toString('base64');
}
const rect={x:0,y:0,width:20,height:30};
const options={baseline:png(),rects:[rect],dpr:1,doc:rect,tolerance:8};
test('classification leaves the main event loop available for CDP acknowledgements',async()=>{
 const classifier=createRegionClassifier(options);
 try {
  let yielded=false;setImmediate(()=>{yielded=true;});
  const result=await classifier.classify(png(true));
  assert.equal(yielded,true,'PNG classification blocked the CDP event loop');
  assert.equal(result.ink_pixels,112);
  assert.deepEqual(result.regions[0].background,[255,255,255]);
  assert.equal((await classifier.classify(png())).ink_pixels,0);
 } finally {await classifier.close();}
});
test('malformed frame rejects without poisoning the next request',async()=>{
 const classifier=createRegionClassifier(options);
 try {
  await assert.rejects(classifier.classify('bad'),/not a PNG/);
  assert.equal((await classifier.classify(png(true))).ink_pixels,112);
 } finally {await classifier.close();}
 await assert.rejects(classifier.classify(png()),/closed/);
});
test('startup failure propagates',async()=>{
 const classifier=createRegionClassifier({...options,baseline:'bad'});
 try {await assert.rejects(classifier.classify(png()),/not a PNG/);} finally {await classifier.close();}
});
test('concurrent misuse is refused and pending work is cancelled on close',async()=>{
 const classifier=createRegionClassifier(options);
 const pending=classifier.classify(png());
 const cancelled=assert.rejects(pending,/closed/);
 await assert.rejects(classifier.classify(png()),/already pending/);
 await classifier.close();await cancelled;
});
