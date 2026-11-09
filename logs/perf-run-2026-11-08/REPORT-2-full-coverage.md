# perf/ full-coverage run — every editor, every measurable criterion (2026-11-08/09)

Coordinator-run, swarm-executed (7 builders + measurement passes), inspector-audited.
All numbers are **diagnostic**: `publishable=false` on this `ci_coarse` host class, machine
never quiet (load 6–20 from other sessions' builds; recorded per summary in
`quiet_machine_check`). Word and Docker were not needed — perf/ uses neither.

## Master matrix (medians, ms; C03/C05/C06 show cold, `warm` when distinct)

```
editor           C02      C03      C04      C05      C06      C07      C08      C09      C10      C11      C12      C14      C15      C16      C17      C19      C21
plate             66      258      1.0   119/83       83      9.6       26       19       35      540       63      760        —      113        —      737     1445
docxodus         143     1864      1.2    83/81       83        —        —        —       16       24        —        —        —       21        —      380      730
apryse             —     1916      2.3    98/81       83        —        —        —       14      588        —        —        —        —        —        —        —
superdoc         706     3301      609    69/63    67/83        —        —        —       19       20      102     4509        —      3.3        —      313      187
folio             16      213      2.1  173/116       83       26        —        —       50     1484       32     1496        —      8.4        —        —      179
genoffice         85     8366      1.3   116/89       83       27       58       36       22      692       91      826      3.7      1.4        —      194     1549
eigenpal         4.7     1679      509   108/74       83        —       23        —       35       36       33     1661        —      6.9        —      996      178
office-open      6.1        —        —        —        —        —        —        —        —        —        —        —        —       13        —        —      469
docen            7.4      878      1.0  115/116    84/83        —        —        —       31      780        —        —        —       12        —      448      446
wordcraft        5.4      793      931  195/210  249/283       58        —        —       48       20        —        —        —      0.7        —      525      4.4
fidus            5.7        —        —        —        —        —        —        —        —        —        —        —        —       85        —        —     1068
canvas            18      844      1.1    94/78       83      8.9        —        —       28      184        —        —        —       26        —      244     2175
docsplus          23      341      1.6   133/83      84       10       26       19       36      340       22      685      658       19        —      680      450
libreoffice     2194        —        —        —        —        —        —        —        —        —        —        —        —        —        —        —      987
```

Reading notes (within-layer observations only — cross-layer comparison is a diagnostic, never a ranking):

- **C02 model load (headless)**: wordcraft 5.4, eigenpal 4.7, docen 7.4, office-open 6.1, fidus 5.7 ms
  (native/local crates); folio 16, canvas 18, docsplus 23, plate 66, docxodus 143 ms;
  superdoc 706 ms (worker boot); genoffice 858 ms; libreoffice 2194 ms (whole conversion, by design).
- **C03 first usable (cold)**: folio 213 ms is the fastest browser surface; plate 258, docsplus 341;
  docxodus/apryse/eigenpal ≈1.7–1.9 s; superdoc 3.3 s; genoffice 8.4 s.
- **C05 single edit**: superdoc 69→63 ms is the fastest; plate 119→83, canvas 94→78, docxodus 83→81.
- **C06 sustained typing**: most editors ≈83 ms/burst (frame-quantized); wordcraft 249→283 ms (wasm round-trips).
- **C10 scroll-to-frame**: docxodus 16, superdoc 19, genoffice 22, apryse 14 ms; folio 50 ms is the slowest.
- **C16 save**: wordcraft 0.7 ms (in-proc crate), genoffice 1.4 ms, superdoc 3.3 ms; plate 113, fidus 85 ms.
- **C17 memory (MB, ready phase)**: genoffice 420, canvas 763, plate 1108, docxodus 1052, wordcraft 1121,
  eigenpal 1813, superdoc 2068, docsplus 2060; office-open 154 / libreoffice 191 (one-shot peak).
- **C19 retained after close (MB)**: genoffice 194, canvas 244, docxodus 380, docsplus 680, plate 737,
  eigenpal 996, wordcraft 525, superdoc 313, docen 448.
- **C24 wasm boundary**: docxodus instantiate 10.3 ms then µs-scale calls; wordcraft instantiate 83 ms,
  empty call 0.000008 ms, batched 2.9 ms.

## Coverage: what each "—" means (per-cell reasons, all recorded in the artifacts)

| Cell | Reason (verbatim source: suite summaries/attempts) |
|---|---|
| apryse C02/C16/C21 (headless) | not_run by design — proprietary WebViewer, no headless round-trip harness |
| apryse C07/C08/C09 | failed `editable_not_found` — edit surface lives in WebViewer's shadow DOM; the probe's in-page query cannot see it |
| apryse C17/C19 | failed 3× reproducibly: memory-probe ready timeout (isolated repro of the same steps passes; unresolved probe incompatibility) |
| fidus C03–C15, C10 | **editor defect**: fidus's DOCX importer crashes on packages without `docProps/core.xml` (`DocxConvert.extractAuthors … Cannot read properties of null`) — verified 3 ways; harness fixtures legitimately lack that part; host verified working on `fixture/complex.docx` (diagnostic: model-ready 2390 ms, reload 907, edit 117/71 ms) |
| docxodus C07/C08/C09 | failed: static paginated render — at 15.0.0 the paginated mount wires 0 contenteditable blocks (verified; editable blocks exist only in the non-paginated mount) |
| docxodus C12 | refused: anchor block does not move (no keyboard-driven y-shift surface on the paginated mount) |
| docxodus C14 | refused: no compositor frame after the usable mark (single innerHTML render, page static) |
| superdoc/docxodus C07 | failed `no_painted_frame` at page-centre point (probe evidence captured) |
| superdoc C07/C08/C09 | C07 failed (above); C08/C09 not driven in that run (single-load session ordering) |
| eigenpal C07/C09 | failed `editable_not_in_viewport` / typed char not observable (viewport virtualization keeps the target paragraph off-screen) |
| canvas, docen, wordcraft, apryse C12/C14 | structural: no DOM block boxes (canvas/shadow surfaces) — config notes record it; C11 still measured |
| all editors C22 | not_applicable — no host exposes P0–P3 feature flags (per-editor source inspection recorded) |
| C01, C13, C18, C20, C23 | no runner implements them; C20/C01 additionally require a `dedicated_publish` host (by design, `perf/README.md`) |
| office-open browser criteria | not_applicable — the library exposes no interactive UI; a browser "first usable" would measure our own host (removed by decision, noted in `benchmark_warm_cold.py`) |

## Editor defects found (belongs in the trial's reports, not hidden in hosts)

1. **Fidus Writer importer crash** on DOCX without `docProps/core.xml` (optional part per OOXML).
2. **Docxodus 15.0.0 paginated mount wires no editable blocks** (product has the surface in the
   non-paginated mount; verified by forced-mount experiments).

## Harness work delivered this session (all in perf/, + tests; uncommitted except e57b13a)

- 8 new browser hosts wired into `BROWSER_TARGETS` (apryse, folio, eigenpal, docen, docsplus, fidus,
  wordcraft, office-open→removed with reason) with per-target lane labels + `test_browser_lane_label.py`
  (fixes a pre-existing mislabel: plate pixels recorded as `headless_docx`).
- C04/C07/C08/C09 probe (`criteria_input.mjs` + `warm_cold_browser.mjs --criteria`) with CDP-screencast
  frame evidence; `benchmark_input.py` runner; honesty tests `test_input_criteria.py`.
- C11/C12/C14/C15 (`benchmark_document.py` + `document_probe.mjs`, 38 tests) with 12 verified
  `DOCUMENT_TARGETS` configs (each selector verified against the live host).
- C17/C19/C22 (`benchmark_memory.py` + `memory_tree.py` + `memory_probe.mjs`) — ps-based RSS, explicit
  about no smaps on darwin; fixed a soffice in-place-conversion bug (output overwrote input).
- C24 (`wasm_boundary.py` + `wasm_host.mjs`): wordcraft 7/7 ops, docxodus 4/7 + documented refusals.
- Apryse key gate reads `APRYSE_API_KEY` (`test_apryse_key_gate.py`); quantized-equality warm/cold
  samples recorded as `warm_equals_cold` flags instead of aborting the run (`test_warm_cold_quantized.py`).
- Commit **e57b13a** (canvas mock absolute-path fix + regression test) from the earlier phase.

Unit suite: 324 tests, 1 pre-existing failure (`test_warm_cold_honesty` needs
`perf/out/unblocked_2026_11_07b/`, never present on this host). Coverage gate OK.

## Caveats

- The machine was **never quiet** (load 6–20, other sessions' rust builds/jubarte sweep — never touched).
  Every figure is a diagnostic; nothing may be published (and the harness enforces it).
- Reproduce-twice (AGENTS §4) was applied where runs repeated naturally (warm/cold ran ≥2× per editor
  across passes; c10 twice for the first five) but not systematically for every cell.
- Artifacts: `perf/out/{ci_contract_2026_11_09,ci_broad_2026_11_09,warm_cold_2026_11_09,criteria_input_*,document_2026_11_09,memory_2026_11_08*,c10_*,wasm_boundary_2026_11_08}`;
  warm/cold summaries are per-run — the immutable `attempts/` files are the source of record
  (`tmp-diag/master_table.py` reads exactly those).

## Suggested follow-ups (issues)

1. `assert_warm_cold_distinct`-adjacent flake → now a recorded flag; consider a probe-level copy guard.
2. apryse/folio memory-probe ready timeout (reproducible; isolated steps pass) — root-cause needed.
3. C14 frame-race for static-render hosts (docxodus) and DOM-text usability gate for canvas hosts —
   probe change, parent decision.
4. The two editor defects above → report sections, not host fixes.
5. A dedicated quiet-host `dedicated_publish` runner (C01/C20 and publishable distributions).
