# B9 typing lane (#143)

Each BrowserRun cell starts a fresh Chromium process and profile, loads the empty
DOCX, types one brief, checks normalized document text, and emits one session
value plus resource time series. Python attaches to Node's Chromium; it does not
launch another browser. No paste or model insertion is used. Unsupported editing
surfaces refuse. The full fixture is 12,805 words, ending at a paragraph boundary.

Publication schedules 12 throughput sessions and 12 latency sessions per editor
per seed, each kind independently requiring at least 10 kept. There are two
distinct seeds, cadence 0 (saturation), and a 3,600 second session budget.
`--session-kind throughput|latency` selects one kind for each run. Each session
uses a fresh browser and profile and types the entire brief. Other lanes retain
B1's 30-repetition gate. Records remain nonpublishable pending complete publication
validation; scheduling does not prove that an editor finishes within budget.
Budget refusals retain characters typed and elapsed session time in `progress`.

The load baseline is a base64 PNG passed to the shared document-scoped C11
witness with the pixel-anchor clock gate. Load time is the accepted frame's page
time; a mutation timestamp alone is never a load figure.

A witness becomes due every 100 keys (configurable), then moves to the next
printable non-space ASCII key. This is a conservative subset of Playwright's US
keyboard layout: spaces/newlines need not paint ink, while §, em dashes and curly
quotes use insertText without keydown. After a deferred sample the next due index
is its index plus the interval. A null keydown anchor refuses as `no_keydown`.
Key-to-paint median/p90 use accepted samples, with scheduled/accepted/refused
counts and refusal codes. At least max(ceil(50% of scheduled), min(100, scheduled)) witnesses
must validate; an empty distribution never publishes. The refusal also reaches
the run summary cell through the nested refused outcome. Otherwise the distribution is refused as `insufficient_accepted`.
Individual evidence and sub-frame flags remain attached.

Throughput sessions request no key witnesses and run no screencast during typing.
The load witness finishes and its recorder stops before typing starts. Published
`throughput_chars_s` is accepted characters divided by unadjusted `typing_wall_s`,
including resource samples, final text extraction, cadence and deferred editor
work observed in that wall interval. A text mismatch or session failure refuses
the rate. This kind supplies all published resource phases, endpoints and peaks.
Its load timing remains diagnostic.

Latency sessions publish only `load_ms` and `key_to_paint`, retaining the raw
per-witness records. Their wall throughput, resources, endpoints and milestones
are nested under `instrumented`; the resource time-series file is also labelled
`instrumented`. No witness-time subtraction or refused-key fallback remains.
The per-kind kept gate never uses instrumented values. The schema is
`perf.typing/2`; `published_fields` declares the fields belonging to that kind,
without claiming that a diagnostic run is publishable.

Each witness keeps shared `elapsed_ms` and end-to-end `bridge_elapsed_ms`;
`witness_wall_s` sums the latter for diagnosis. B9 removes duplicate shared
caret-mask stylesheets after bridge operations, retaining the newest sheet.
Session wall additionally includes load, save, quiescence and teardown. Neither
throughput figure represents human typing speed.

Backlog compares normalized typed and DOM text lengths using the same whitespace
collapse as the end check. Raw characters sent and normalized lengths are retained.
Profile bytes are deltas from the post-load mark; `profile_absolute_bytes` keeps
the absolute values. These deltas still include browser-owned growth, not only
editor writes. B8's `AsyncResourceSampler` owns resource measurements, installs
network listeners before navigation, and attributes only the launched browser's
process tree. Missing counters use B8's `not_available_on_platform` marker.
Load, typing and quiescence have separate first-to-last counter deltas, with
per-role CPU deltas. A one-sample phase has no counter delta. Milestones are
additive labels and do not split the typing phase. Before the final DOM read and typing mark, a browser task turn drains already
queued work, including zero-delay timers from the last input. That wait is part
of the typing wall. Longer delayed work may still belong to quiescence. Heap, RSS, storage and profile
are levels; after-load and end endpoints include separately labelled post-GC
heap. GC samples are excluded from the natural series. Endpoint counters are
`not_applicable_endpoint`. CPU percent sums cores (100% represents one core).

Correct final text does not prove that the caret stayed at the insertion point.
An editor that inserts correctly while parking its caret elsewhere can pass;
caret pixels are deliberately masked by the shared witness. Save uses only a
host-declared download path (SuperDoc); Playwright timeouts refuse as
`save_timeout`. Plate has no declared save path.

B6's smoke schedule runs one session of each typing kind on the fake host; its HF image installs Python playwright and
psutil before sessions. No Docker build is part of this fix. The local fallback sampler has been removed; B9 uses B8's shared accounting.

Local CLI smoke (not publication):

```sh
uv run --no-project --with playwright --with psutil python -I perf/runner/benchmark_typing.py --help
```
