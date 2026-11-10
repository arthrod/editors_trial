/** Pure pixel classification: ink contrasts with the post-change local mode
 * colour AND the pre-key baseline. Uniform flips and full-height edge bands
 * are not ink. Rectangles are inset to whole pixels to exclude outside edges.
 */
export function classifyRegion(pixels, baseline, rects, dpr, doc, tolerance = 8) {
  const values = [], regions = [];
  let inkPixels = 0;
  const differs = (a,b) => a.some((v,c) => Math.abs(v-b[c]) > tolerance);
  for (const rect of rects) {
    const x0 = Math.max(0, Math.ceil(Math.max(rect.x,doc.x)*dpr));
    const y0 = Math.max(0, Math.ceil(Math.max(rect.y,doc.y)*dpr));
    const x1 = Math.min(pixels.width, Math.floor(Math.min(rect.x+rect.width,doc.x+doc.width)*dpr));
    const y1 = Math.min(pixels.height, Math.floor(Math.min(rect.y+rect.height,doc.y+doc.height)*dpr));
    const colors = new Map(), rows = [];
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
    let ink=0;
    for (const row of rows) for(let x=0;x<row.length;x++) {
      const {rgb,before}=row[x];
      // A full-height band can be an old slot edge or an occluding caret.
      const band=rows.every(r=>differs(r[x].rgb,background));
      if (!band && differs(rgb,background) && differs(rgb,before)) ink++;
    }
    inkPixels+=ink;
    regions.push({background,ink_pixels:ink,pixels:rows.length*(rows[0]?.length||0)});
  }
  return {values,ink_pixels:inkPixels,regions};
}

/** Pure settlement over recorded, timestamped region classifications.
 * A reference must carry >= minPixels glyph ink contrasting with its local
 * post-change background and baseline; a uniform background flip is not ink.
 * Q is proven only by matching witnessed frames reaching its end. A gap
 * inside Q exceeding max(2 * median frame interval, 100 ms) is unproven.
 * A gap spanning all of Q is also insufficient, even if the sparse median
 * would inflate the gap bound. Search through W; missing evidence refuses witness_sparse, never guesses.
 * Latency uses the first frame matching the proven reference, never before
 * the first glyph-ink frame. A sparse onset also refuses: it cannot establish
 * the first paint: onset gaps over two median intervals refuse, even when
 * below the quiet-window gap bound. A supplied display calibration caps the
 * onset interval when screencast delivery is slower. A dropped frame just
 * before the last pre-ink frame also leaves onset uncertain (gap > 1.5 intervals). Later covers cannot replace a proven reference.
 */
export function settleFrames(frames, {quietMs=300,maxWaitMs=3000,markerMs=0,minPixels=4,tolerance=8,frameIntervalMs=null}={}) {
  const eligible=frames.filter(f=>Number.isFinite(f.pageMs)&&f.pageMs>=markerMs&&f.pageMs<=markerMs+maxWaitMs);
  const intervals=eligible.slice(1).map((f,i)=>f.pageMs-eligible[i].pageMs).filter(n=>n>0).sort((a,b)=>a-b);
  const middle=Math.floor(intervals.length/2);
  const median=intervals.length ? (intervals.length%2?intervals[middle]:(intervals[middle-1]+intervals[middle])/2):0;
  const gapBound=Math.max(2*median,100);
  const onsetInterval = Number.isFinite(frameIntervalMs) && frameIntervalMs>0
    ? (median>0?Math.min(median,frameIntervalMs):frameIntervalMs) : median;
  const onsetBound = onsetInterval>0 ? 2*onsetInterval : gapBound;
  const matches=(a,b)=>a.values.length===b.values.length && a.values.every((v,i)=>Math.abs(v-b.values[i])<=tolerance);
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
      if(eligible[j].pageMs>=ref.pageMs+quietMs) proven=true;
    }
    if(!proven) {if(!changed) sparse=true;continue;}
    const first=eligible.findIndex(f=>f.ink_pixels>=minPixels&&matches(f,ref));
    const onset=eligible[first].pageMs-(first?eligible[first-1].pageMs:markerMs);
    const precedingGap=first>1?eligible[first-1].pageMs-eligible[first-2].pageMs:0;
    if(onset>onsetBound || (onsetInterval>0 && precedingGap>1.5*onsetInterval)) {sparse=true;continue;}
    return {reference_index:frames.indexOf(ref),match_index:frames.indexOf(eligible[first]),page_ms:eligible[first].pageMs,frame_interval_ms:median,gap_bound_ms:gapBound,onset_bound_ms:onsetBound};
  }
  return {failure_reason:sparse?'witness_sparse':'settle_not_reached',frame_interval_ms:median,gap_bound_ms:gapBound,onset_bound_ms:onsetBound};
}
