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
 * A sparse onset between two delivered frames also does not refuse when the
 * measured input's own Event Timing entry (inputProcessing, in the same
 * page clock as the frames' pageMs) shows no new content was presented
 * before its end: the entry's duration is startTime to the presentation of
 * the first rendering update after the event's processing (rounded to 8
 * ms), so the ink-less frames delivered in the hole are compositor frames
 * of the old content and the hole is the input latency under measurement
 * (issue #171). The entry must be the measured input's own — its startMs
 * equal to the measured event's startTime exactly — and the glyph must sit
 * in the verified window around pEnd = startMs + durationMs: on the early
 * side the reported end can sit up to 4 ms before the true end (nearest-8
 * rounding), and the screencast frame's timestamp is its capture time —
 * capture can precede presentation by up to one vsync (one frame interval;
 * calibrated on the trusted corpus where every normal-path sample sat at or
 * above -(4+interval), issue #171 sparse4), so a glyph earlier than
 * pEnd - 4 - interval refuses glyph_before_next_paint; on the late side the
 * glyph may have been presented as early as pEnd - 4, so the unverified
 * interval is glyph - (pEnd - 4) and it must stay within the onset bound —
 * the same tolerance the normal path grants between the last ink-less
 * delivered frame and the glyph — else it refuses glyph_after_next_paint.
 * No contiguity is required from the onset to the quiet reference: the
 * published claim is "the glyph was visible at eligible[first]",
 * covers(first, ref) proves it with first's own pixels, and a delivery hole
 * after first cannot make the glyph appear earlier — the hole the entry
 * explains is the one before first (sparse4; the normal path does not check
 * that span either).
 * processingEnd only says the handler returned — an editor that renders
 * asynchronously stays blocked after it — so it is disclosure, never the
 * bound. Without the entry, without its duration, or outside the verified
 * window, the refusal stands; the accepted decision discloses
 * onset_hole_explained_by with both numbers.
 * Later covers cannot replace a proven reference.
 */
/** The onset bound floor in ms (lax layer, owner decision 2026-11-11): the
 * worst onset gap the HF shakedown evidence supports accepting (folio C05/C06
 * cells: 50/66.7/100 ms between the last ink-less delivered frame and the
 * glyph). Exported so tests and disclosures can name it. */
export const ONSET_BOUND_FLOOR_MS = 100;
/** Event Timing duration is rounded to the nearest 8 ms, so the reported end
 * can sit up to 4 ms on either side of the true first rendering update. */
export const EVENT_TIMING_ROUNDING_MS = 4;

export function settleFrames(frames, {quietMs=300,maxWaitMs=3000,markerMs=0,minPixels=4,tolerance=8,frameIntervalMs=null,inputProcessing=null,eventStartMs=null}={}) {
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
  let sparseReason=null;
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
    if(first>0 && onset>onsetBound+0.001) {
      // Issue #171: the hole is the measured input's own latency when its
      // Event Timing entry shows no new content was presented before its
      // end — duration is startTime to the presentation of the first
      // rendering update after the event's processing, rounded to 8 ms, so
      // the ink-less frames delivered in the hole are compositor frames of
      // the old content. The entry must be the measured input's own:
      // PerformanceEventTiming.startTime is the dispatched event's
      // timeStamp, so exact equality with the measured event's startTime is
      // the identity check — a fuzzy match can adopt a different keydown,
      // and zero or several matches is no verified entry. Around
      // pEnd = startMs + durationMs: duration rounds to the nearest 8 ms,
      // so the true end can sit up to EVENT_TIMING_ROUNDING_MS on either
      // side of pEnd; on the early side the frame timestamp is the capture
      // time and capture can precede presentation by up to one vsync — one
      // frame interval (the calibrated onsetInterval; every trusted corpus
      // sample sat at or above -(rounding+interval), issue #171 sparse4) —
      // so a glyph earlier than pEnd - rounding - interval refuses
      // glyph_before_next_paint. On the late side the glyph may have been
      // presented as early as pEnd - rounding, so the unverified interval is
      // glyph - (pEnd - rounding) and it must stay within onsetBound — the
      // same tolerance the normal path grants between the last ink-less
      // delivered frame and the glyph — else glyph_after_next_paint.
      // No contiguity check runs from first to the reference: the claim is
      // "the glyph was visible at eligible[first]", covers(first, ref)
      // proves it with first's own pixels, and a delivery hole after first
      // cannot make the glyph appear earlier (sparse4; the normal path does
      // not check that span either). processingEnd is disclosure only: an
      // editor that renders asynchronously stays blocked after the handler
      // returns. Without the entry, without its duration, or outside the
      // verified window, the refusal stands.
      const p=inputProcessing;
      const eventStart=Number.isFinite(eventStartMs)?eventStartMs:markerMs;
      const pStart=p&&Number.isFinite(p.startMs)?p.startMs:NaN;
      const pEnd=Number.isFinite(pStart)&&Number.isFinite(p&&p.durationMs)?pStart+p.durationMs:NaN;
      const glyph=eligible[first].pageMs;
      if(!(pStart===eventStart&&Number.isFinite(pEnd))) {sparse=true;continue;}
      if(glyph<pEnd-EVENT_TIMING_ROUNDING_MS-onsetInterval) {sparse=true;sparseReason='glyph_before_next_paint';continue;}
      if(glyph-(pEnd-EVENT_TIMING_ROUNDING_MS)>onsetBound) {sparse=true;sparseReason='glyph_after_next_paint';continue;}
      const explained={reference_index:frames.indexOf(ref),match_index:frames.indexOf(eligible[first]),page_ms:eligible[first].pageMs,frame_interval_ms:median,gap_bound_ms:gapBound,onset_bound_ms:onsetBound,
        onset_hole_explained_by:'event_next_paint',onset_gap_ms:onset,event_next_paint_ms:pEnd};
      if(Number.isFinite(p.processingEndMs)) explained.event_processing_end_ms=p.processingEndMs;
      return explained;
    }
    return {reference_index:frames.indexOf(ref),match_index:frames.indexOf(eligible[first]),page_ms:eligible[first].pageMs,frame_interval_ms:median,gap_bound_ms:gapBound,onset_bound_ms:onsetBound};
  }
  return {failure_reason:sparse?(sparseReason||'witness_sparse'):'settle_not_reached',frame_interval_ms:median,gap_bound_ms:gapBound,onset_bound_ms:onsetBound};
}
