/**
 * C11's surface clock on a model host (docen, eigenpal, canvas-editor).
 *
 * Every input is a page-clock instant (performance.now() since navigation):
 * `at` the content-gated surface stamp, `inkAt` the settled screencast-ink
 * frame, `firstElementMs` the first layout box, `readyPageMs` the host's
 * ready flag. The surface is the latest of them, except that ready only
 * stands in when no ink stamp exists: the settled ink frame is the first
 * frame identical to the screen captured after ready, so a later ready flag
 * is not a later layout (review D: docen's C11 was refused at every size).
 */
export function bindModelSurfaceClock({ at = null, inkAt = null, firstElementMs = null, readyPageMs = null } = {}) {
  const fallback = firstElementMs ?? (inkAt === null ? readyPageMs : null);
  const candidates = [at, inkAt, fallback].filter((value) => typeof value === 'number');
  return candidates.length ? Math.max(...candidates) : null;
}
