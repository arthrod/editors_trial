# B9 typing lane (#143)

Each BrowserRun cell starts a fresh Chromium process and profile, loads the empty
DOCX, types one brief, checks normalized document text, and emits one session
value plus resource time series. Python attaches to Node's Chromium; it does not
launch another browser. No paste or model insertion is used. Unsupported editing
surfaces refuse. The full fixture is 12,805 words, ending at a paragraph boundary.

The owner-selected publication policy (pending the HF smoke) is 12 sessions per
editor per seed, at least 10 kept per run, two distinct seeds, cadence 0
(saturation), and 3,600 seconds per session. Other lanes retain B1's 30-repetition
gate. Typing jobs pass cadence and budget explicitly. Records remain marked
nonpublishable pending HF/resource/schema integration; this policy is not evidence
that an editor can finish within its budget.

The load baseline is a base64 PNG passed to the shared document-scoped C11
witness with the pixel-anchor clock gate. Load time is the accepted frame's page
time; a mutation timestamp alone is never a load figure.

A witness becomes due every 100 keys (configurable), then moves to the next
printable non-space ASCII key. This is a conservative subset of Playwright's US
keyboard layout: spaces/newlines need not paint ink, while §, em dashes and curly
quotes use insertText without keydown. After a deferred sample the next due index
is its index plus the interval. A null keydown anchor refuses as `no_keydown`.
Key-to-paint median/p90 use accepted samples, with scheduled/accepted/refused
counts and refusal codes. At least ceil(50% of scheduled witnesses), minimum one,
must validate. Otherwise the distribution is refused as `insufficient_accepted`.
Individual evidence and sub-frame flags remain attached.

`throughput_chars_s` divides unwitnessed characters by the sum of their keyboard
operation times and declared cadence pauses. Witnessed characters and their
entire bridge stalls are excluded from both numerator and denominator. Each
witness keeps its shared `elapsed_ms` plus end-to-end `bridge_elapsed_ms`;
`witness_wall_s` sums the latter. B9 removes duplicate stylesheets containing
exactly the shared caret-mask CSS after each operation, retaining the newest
mask and its cascade position. B1 otherwise adds one on every witness; leaving
hundreds of global selectors in the page slows subsequent unwitnessed edits.
Cleanup is charged to the bridge operation; B1 itself is unchanged. Resource sampling, final text extraction, and
witnessing remain in `typing_wall_s` and the separately labeled
`throughput_wall_chars_s`. Session wall additionally includes load, save,
quiescence and teardown. Neither figure is a human typing speed.

Backlog compares normalized typed and DOM text lengths using the same whitespace
collapse as the end check. Raw characters sent and normalized lengths are retained.
Profile bytes are deltas from the post-load mark; `profile_absolute_bytes` keeps
the absolute values. These deltas still include browser-owned growth, not only
editor writes. Missing counters stay null. Per-process disk I/O is unavailable on
macOS; CDP provides received bytes but no complete sent-wire counter. CPU percent
is per process, with 100% representing one core. No forced GC is used.

Correct final text does not prove that the caret stayed at the insertion point.
An editor that inserts correctly while parking its caret elsewhere can pass;
caret pixels are deliberately masked by the shared witness. Save uses only a
host-declared download path (SuperDoc); Playwright timeouts refuse as
`save_timeout`. Plate has no declared save path.

B6's dispatcher includes typing; its HF image installs Python playwright and
psutil before sessions. No Docker build is part of this fix. B8's sampler is
still changing: retain the provisional `typing_resources.ResourceSampler` with
async mark/sample and synchronous series/totals until its interface is settled.

Local CLI smoke (not publication):

```sh
uv run --no-project --with playwright --with psutil python -I perf/runner/benchmark_typing.py --help
```
