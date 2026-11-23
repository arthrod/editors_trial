/**
 * The C15 find probe's page side (document_probe.mjs runFind), in its own
 * module so a test can install it on a fake page (perf/tests/e2_find_probe_repro.mjs).
 *
 * It wraps the page's setTimeout (and, for OnlyOffice, setInterval) to tell a
 * reply to the full query from a reply to a prefix of it, and records when the
 * full query's own count text first appears (`complete_at`). BetterOffice's
 * reply renders after its timer (`lateReply`); a count change then is matched
 * to the timers that ran before it, and refused when a prefix reply and the
 * full query's reply are both pending (`ambiguous_reply`).
 */
export const INSTALL_FIND_PROBE = ({ countSel, matchSel, expected, query, inputSel, intervalReplies, lateReply }) => {
        const probe = (window.__findProbe = {
          first_at: null,
          complete_at: null,
          last: '',
          accepted_text: '',
          prefix_text: '',
          prefixTexts: new Set(),
          pendingReplies: [],
          ambiguous_reply: false,
          scheduling: false,
          expected: expected,
          query: query,
          inputSel: inputSel,
        });
        const input = inputSel ? document.querySelector(inputSel) : null;
        const read = () => {
          const el = countSel ? document.querySelector(countSel) : null;
          const text = el ? (el.textContent || '').trim() : '';
          const matches = matchSel ? document.querySelectorAll(matchSel).length : null;
          return { text, matches };
        };
        const total = (text, matches) => {
          if (typeof matches === 'number') return matches;
          const numbers = (text.match(/\d+/g) || []).map(Number);
          return numbers.length ? Math.max.apply(null, numbers) : null;
        };
        // Completion and first-match are the full query's own count text.
        // A reply scheduled while the input was still a prefix is not that
        // response, even if it arrives after the input already shows the query.
        const notePrefix = (text) => {
          if (!text) return;
          probe.prefixTexts.add(text);
          probe.prefix_text = text;
        };
        const noteFull = (text) => {
          if (!text) return;
          const count = total(text, read().matches);
          const matchesExpected = probe.expected === null || (count !== null && count === probe.expected);
          if (!matchesExpected) return;
          probe.last = text;
          probe.accepted_text = text;
          const now = performance.now();
          if (probe.first_at === null) probe.first_at = now;
          if (probe.complete_at === null) probe.complete_at = now;
        };
        const nativeSetTimeout = window.setTimeout;
        const origTimeout = nativeSetTimeout.bind(window);
        // Capture runs before the page's element listener. A microtask queued
        // there runs before that listener on this input path, so the flag stays
        // up until bubble. Timers from later tasks are not a search response.
        const arm = (event) => {
          if (input && event.target === input) probe.scheduling = true;
        };
        const disarm = (event) => {
          if (!input || event.target !== input) return;
          const value = input.value;
          const text = read().text;
          if (value !== probe.query) notePrefix(text);
          else if (text && !probe.prefixTexts.has(text)) noteFull(text);
          probe.scheduling = false;
        };
        window.addEventListener('input', arm, true);
        window.addEventListener('input', disarm, false);
        window.setTimeout = function (fn, delay) {
          const extra = Array.prototype.slice.call(arguments, 2);
          const valueAtSchedule = input && typeof input.value === 'string' ? input.value : '';
          const fromInput = probe.scheduling === true;
          if (typeof fn !== 'function') return origTimeout.apply(window, arguments);
          return origTimeout(function () {
            const before = read().text;
            const result = fn.apply(this, extra);
            const after = read().text;
            if (!fromInput) return result;
            if (lateReply && after === before) {
              // BetterOffice only: its find dialog's input-scheduled timer
              // runs the search and sets React state, and the status line
              // renders in a later task. The next change of the count text
              // after this timer is this timer's reply (full query or prefix).
              // Every such timer is kept: one that runs before an earlier one
              // commits must not erase it (CodeRabbit on #283, 2026-11-23).
              probe.pendingReplies.push({ value: valueAtSchedule, before });
              return result;
            }
            if (valueAtSchedule === probe.query) noteFull(after);
            else if (after && after !== before) notePrefix(after);
            return result;
          }, delay);
        };
        // OnlyOffice only (intervalReplies): its find bar starts one setInterval
        // on the first input and searches whatever the input holds 400 ms after
        // the last input (web-apps onInputSearchChange, 9.3.2); it never uses
        // setTimeout for it. A tick of an interval started from an input is a
        // reply to the text the input holds when that tick runs: the search it
        // runs reads that text. Other editors keep the setTimeout rule alone.
        const nativeSetInterval = window.setInterval;
        if (intervalReplies) {
          const origInterval = nativeSetInterval.bind(window);
          window.setInterval = function (fn, delay) {
            const extra = Array.prototype.slice.call(arguments, 2);
            const fromInput = probe.scheduling === true;
            if (typeof fn !== 'function' || !fromInput) return origInterval.apply(window, arguments);
            return origInterval(function () {
              const valueAtTick = input && typeof input.value === 'string' ? input.value : '';
              const before = read().text;
              const result = fn.apply(this, extra);
              const after = read().text;
              // Only a tick that changed the count answers anything. A tick that
              // ran with the full query and changed the count is that query's
              // reply even when its text equals an earlier prefix reply's (3, 2,
              // then 3 again): the search it ran read the full query (CodeRabbit
              // on #283, 2026-11-23).
              if (after && after !== before) {
                if (valueAtTick === probe.query) noteFull(after);
                else notePrefix(after);
              }
              return result;
            }, delay);
          };
        }
        let replyObserver = null;
        if (lateReply && typeof MutationObserver === 'function') {
          replyObserver = new MutationObserver(() => {
            const pending = probe.pendingReplies;
            if (!pending.length) return;
            const latest = pending[pending.length - 1];
            const text = read().text;
            if (!text || text === latest.before) return;
            probe.pendingReplies = [];
            // A change while a prefix reply and the full query's reply are both
            // pending cannot be attributed: the cell is unverified, not guessed.
            const values = new Set(pending.map((reply) => reply.value));
            if (values.size > 1 && values.has(probe.query)) {
              probe.ambiguous_reply = true;
              return;
            }
            if (latest.value === probe.query) noteFull(text);
            else notePrefix(text);
          });
          replyObserver.observe(document.body, { childList: true, subtree: true, characterData: true });
        }
        probe.stop = () => {
          window.setTimeout = nativeSetTimeout;
          window.setInterval = nativeSetInterval;
          if (replyObserver) replyObserver.disconnect();
        };
};
