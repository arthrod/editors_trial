# B9 typing lane (#143)

Run from this checkout with the Python dependencies prepared before measuring:

```sh
uv run --no-project --with playwright --with psutil python -I perf/runner/benchmark_typing.py --editors plate --words 1000 --cadence-ms 0 --out-root /path/to/new/output
```

The Python connection attaches to the **same** Chromium launched by
`typing_session.mjs`; it does not launch a second browser. Each BrowserRun cell
has a new browser profile. Node's installed harness Playwright supplies Chromium.
Production hosts are built by the shared B1 wrapper; no host source is modified.
The empty DOCX has one empty paragraph. Unsupported editable/correctness
surfaces produce a named refusal rather than synthetic typing numbers.

`--cadence-ms` is the minimum pause after each completed key, not an asserted
human keystroke rate. Every 100th key is witnessed by default; recording and
calibration overhead remains inside session wall time. Recorder frames are
released after each witnessed key. A 5-second quiescence is declared before
launch. `--words` is a smoke-only word prefix; it retains original whitespace.
The full fixture stops at 12,805 words at the last complete paragraph below
13,000. Hashes separately identify the committed fixture and the typed prefix.
Whitespace normalization collapses DOM block separators; punctuation, word
order, missing/extra words, and character substitutions remain significant.

A `perf.typing/1` trial and `resources.json` belong to each BrowserRun cell.
This is an additive long-session record, not a claim to be an existing latency
criterion schema. The record is nonpublishable until integration is verified.
Key latency is published as a summary only if every sampled witness validates;
individual refused records remain attached. Sub-frame flags are retained.
Missing counters are null with availability reasons. CDP gives received wire
bytes but not a complete sent-wire-byte counter. Per-process disk counters are
available through psutil on Linux; macOS lacks that API and must remain null.
Process CPU uses CDP SystemInfo CPU time; percentages are deltas, with 100%
representing one fully occupied core. Profile-size scans and instrumentation
are included in elapsed time. No forced GC is used.

## Integration handoffs

* Replace the provisional asynchronous `typing_resources.ResourceSampler`
  with B8's `resources.ResourceSampler`. It has `mark(phase)`, `sample()`,
  `series()` and `totals(phase)`; constructor inputs are run/page/CDP. B9's local
  run adapter supplies process snapshots, clock, network and profile sizing.
  Confirm B8's sync/async convention and output units before switching imports.
* B6's publication policy now schedules one typing job per editor per seed.
  Its fake-host smoke dispatcher still hard-codes four runners and needs a
  `benchmark_typing` dispatch entry. Its four-runner cardinality test needs an
  additive update. Those files are outside this lane's edit authorization.
* The HF Python environment must provide `playwright` and `psutil` before the
  plain-Python publication orchestrator starts. Installing those packages is
  not part of a timed session. The current container does not provision them.
* B1 enforces 30 repetitions per seed for publication, exceeding #143's minimum
  of three. This lane preserves that policy and distinct seeded schedules.
* SuperDoc's declared `#export-docx` download path is supported when its typing
  surface passes the correctness gate. Plate has no save path in its host.
