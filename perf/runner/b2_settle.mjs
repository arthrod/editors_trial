/** Pure pixel classification: ink contrasts with the post-change local mode
 * colour AND the pre-key baseline. Uniform flips and full-height edge bands
 * are not ink. Rectangles are inset to whole pixels to exclude outside edges.
 */
export function classifyRegion(pixels, baseline, rects, dpr, doc, tolerance = 8) {
  const values = [], regions = [], ink = [];
  let inkPixels = 0;
  const differs = (a,b) => a.some((v,c) => Math.abs(v-b[c]) > tolerance);
  for (const rect of rects) {
    const x0 = Math.max(0, Math.ceil(Math.max(rect.x,doc.x)*dpr));
    const y0 = Math.max(0, Math.ceil(Math.max(rect.y,doc.y)*dpr));
    const x1 = Math.min(pixels.width, Math.floor(Math.min(rect.x+rect.width,doc.x+doc.width)*dpr));
    const y1 = Math.min(pixels.height, Math.floor(Math.min(rect.y+rect.height,doc.y+doc.height)*dpr));
    const colors = new Map(), rows = [];
    const regionOffset=values.length/3;
    for (let y=y0;y<y1;y++) {
      const row=[];
      for (let x=x0;x<x1;x++) {
        const offset=(y*pixels.width+x)*4;
        const rgb=Array.from(pixels.data.slice(offset,offset+3));
        const before=Array.from(baseline.data.slice(offset,offset+3));
        values.push(...rgb); row.push({rgb,before});
        const key=rgb.join(',');colors.set(key,(colors.get(key)||0)+1);
      }
      rows.push(row);
    }
    const ranked=[...colors].sort((a,b)=>b[1]-a[1]);
    if (!ranked.length) continue;
    const background=ranked[0][0].split(',').map(Number);
    let regionInk=0, changedMode=0, unchanged=0;
    for (let y=0;y<rows.length;y++) for(let x=0;x<rows[y].length;x++) {
      const row=rows[y];
      const {rgb,before}=row[x];
      // A full-height band can be an old slot edge or an occluding caret.
      const band=rows.every(r=>differs(r[x].rgb,background));
      // Full-width changed rows are background bands too (vertical gradients).
      const rowBand=row.every(p=>differs(p.rgb,background)&&differs(p.rgb,p.before));
      const isInk=!band && !rowBand && differs(rgb,background) && differs(rgb,before);
      ink[regionOffset+y*row.length+x]=isInk?1:0;
      if(isInk) regionInk++;
      if(!differs(rgb,before)) unchanged++;
      if(!differs(rgb,background)&&differs(rgb,before)) changedMode++;
    }
    inkPixels+=regionInk;
    const count=rows.length*(rows[0]?.length||0);
    // A changed modal interior with >=10% unchanged border may be a heavy
    // glyph. Retain its expected area so a later tiny mark cannot become paint.
    regions.push({background,ink_pixels:regionInk,pixels:count,
      expected_ink:changedMode>count/2 && unchanged>=count/10?changedMode:0});
  }
  return {values,ink,ink_pixels:inkPixels,regions};
}

/** Pure settlement over recorded, timestamped region classifications.
 * A reference must carry >= minPixels glyph ink contrasting with its local
 * post-change background and baseline; a uniform background flip is not ink.
 * Q is proven only by matching witnessed frames reaching its end. A gap
 * inside Q exceeding max(2 * median frame interval, 100 ms) is unproven.
 * A gap spanning all of Q is also insufficient, even if the sparse median
 * would inflate the gap bound. Search through W; missing evidence refuses witness_sparse, never guesses.
 * Latency is the first F whose ink covers >=50% of reference ink, with every
 * F ink pixel present in the reference and its colour within tolerance. Every
 * later frame through the reference must retain that property (no regression).
 * A disappearing qualifying glyph before quiet proof refuses; unrelated or
 * sub-half transient decoys cannot veto the eventual glyph reference.
 * A modal-colour glyph followed only by a mark <25% of its expected ink refuses.
 * A sparse onset between two delivered frames refuses: it cannot establish
 * the first paint — onset gaps over max(2 median intervals, 100 ms) refuse
 * (the 100 ms floor is the lax layer, owner decision 2026-11-11; see
 * ONSET_BOUND_FLOOR_MS below), even when below the quiet-window gap bound. When no frame was delivered between the
 * marker and the onset, that interval is the input's own processing time,
 * not a delivery gap, and it does not refuse. A supplied display calibration caps the
 * onset interval when screencast delivery is slower. Only the gap immediately
 * before the selected onset matters. A 0.001 ms numerical tolerance covers
 * timestamp conversion roundoff at the onset bound; it is not a frame allowance.
 * Later covers cannot replace a proven reference.
 */
/** The onset bound floor in ms (lax layer, owner decision 2026-11-11): the
 * worst onset gap the HF shakedown evidence supports accepting (folio C05/C06
 * cells: 50/66.7/100 ms between the last ink-less delivered frame and the
 * glyph). Exported so tests and disclosures can name it. */
export const ONSET_BOUND_FLOOR_MS = 100;

export function settleFrames(frames, {quietMs=300,maxWaitMs=3000,markerMs=0,minPixels=4,tolerance=8,frameIntervalMs=null}={}) {
  const eligible=frames.filter(f=>Number.isFinite(f.pageMs)&&f.pageMs>=markerMs&&f.pageMs<=markerMs+maxWaitMs).sort((a,b)=>a.pageMs-b.pageMs);
  const intervals=eligible.slice(1).map((f,i)=>f.pageMs-eligible[i].pageMs).filter(n=>n>0).sort((a,b)=>a-b);
  const middle=Math.floor(intervals.length/2);
  const median=intervals.length ? (intervals.length%2?intervals[middle]:(intervals[middle-1]+intervals[middle])/2):0;
  const gapBound=Math.max(2*median,100);
  const onsetInterval = Number.isFinite(frameIntervalMs) && frameIntervalMs>0
    ? (median>0?Math.min(median,frameIntervalMs):frameIntervalMs) : median;
  // Lax layer (owner decision 2026-11-11; issue #155 item 6): the onset
  // bound keeps a 100 ms floor. The HF shakedown's folio C05/C06 cells show
  // the glyph arriving 50/66.7/100 ms after the last ink-less DELIVERED
  // frame while the main thread blocked compositor delivery, and a 2-interval
  // bound refused every one of them. No evidence asks for more: no refusal
  // showed an onset gap beyond 100 ms, the delivery-gap bound above stays
  // untouched (no refusal exceeded it), and a sample whose witness never
  // painted still never becomes a timing (it has no cover to walk back to).
  const onsetBound = onsetInterval>0 ? Math.max(2*onsetInterval,ONSET_BOUND_FLOOR_MS) : gapBound;
  const matches=(a,b)=>a.values.length===b.values.length && a.values.every((v,i)=>Math.abs(v-b.values[i])<=tolerance);
  const covers=(f,ref)=>{
    if(f.ink_pixels<minPixels || f.ink_pixels<ref.ink_pixels/2) return false;
    // Legacy scalar classifications are accepted only by full-image equality.
    if(!f.ink || !ref.ink) return matches(f,ref);
    return f.ink.length===ref.ink.length && f.ink.every((v,k)=>!v ||
      (ref.ink[k] && [0,1,2].every(c=>Math.abs(f.values[k*3+c]-ref.values[k*3+c])<=tolerance)));
  };
  let sparse=false;
  for(let i=0;i<eligible.length;i++) {
    const ref=eligible[i];
    if(ref.ink_pixels<minPixels) continue;
    if(ref.pageMs+quietMs>markerMs+maxWaitMs) continue;
    let proven=quietMs===0;
    let changed=false;
    for(let j=i+1;!proven&&j<eligible.length;j++) {
      if(eligible[j].pageMs-eligible[j-1].pageMs>Math.min(gapBound,quietMs)) {sparse=true;break;}
      if(!matches(ref,eligible[j])) {changed=true;break;}
      if(eligible[j].pageMs>=ref.pageMs+quietMs &&
        (j+1===eligible.length || eligible[j+1].pageMs>eligible[j].pageMs)) proven=true;
    }
    if(!proven) {if(!changed) sparse=true;continue;}
    const prior=eligible.slice(0,i+1);
    if(prior.some((f,k)=>f.ink_pixels<minPixels && prior.slice(0,k).some(p=>covers(p,ref))))
      return {failure_reason:'settle_not_reached',frame_interval_ms:median,gap_bound_ms:gapBound,onset_bound_ms:onsetBound};
    const expected=Math.max(0,...prior.flatMap(f=>(f.regions||[]).map(r=>r.expected_ink||0)));
    if(expected && ref.ink_pixels<expected/4)
      return {failure_reason:'settle_not_reached',frame_interval_ms:median,gap_bound_ms:gapBound,onset_bound_ms:onsetBound};
    let first=i;
    while(first>0 && covers(eligible[first-1],ref)) first--;
    // Only a gap between two delivered frames (first>0) can hide an earlier
    // presentation of the glyph. When the onset frame is the first frame
    // delivered at or after the marker (first===0), nothing was delivered in
    // (marker, onset): the recorder delivers every compositor commit (each
    // frame is acked before the next can be sent), so nothing was presented
    // in that interval, and the input itself bounds the onset by causality —
    // a paint cannot predate its keydown. Refusing on that interval would
    // refuse the very input-processing latency this criterion measures
    // (Plate on HF: 103 ms of blocking keydown handling, then dense frames).
    const onset=eligible[first].pageMs-(first?eligible[first-1].pageMs:markerMs);
    if(first>0 && onset>onsetBound+0.001) {sparse=true;continue;}
    return {reference_index:frames.indexOf(ref),match_index:frames.indexOf(eligible[first]),page_ms:eligible[first].pageMs,frame_interval_ms:median,gap_bound_ms:gapBound,onset_bound_ms:onsetBound};
  }
  return {failure_reason:sparse?'witness_sparse':'settle_not_reached',frame_interval_ms:median,gap_bound_ms:gapBound,onset_bound_ms:onsetBound};
}
