# Report E2 — Speed in the Browser (2026)



This report concerns browser-visible first paint, typing, scrolling, and related interactions. 551 of 909 scheduled editor/criterion/measure cells reproduced between the two seeds. 40 run folders contributed 160 jobs (seed 1: 80 jobs; seed 2: 80 jobs); earliest job start 2026-11-12, latest job end 2026-11-13.

## What is measured

Each criterion is one browser-visible or model clock on the same corpus the headless report uses.

**C03 (first visible content/first usable state).** First visible content/first usable state at the first usable boundary (layer browser visible).

**C04 (deferred work).** Deferred work at the deferred quiescence boundary (layer model).

**C05 (single-edit responsiveness).** Single-edit responsiveness at the presented frame boundary (layer browser visible).

**C06 (sustained typing/bursts).** Sustained typing/bursts at the input to next paint boundary (layer browser visible).

**C07 (cursor/selection/hit testing).** Cursor/selection/hit testing at the input to next paint boundary (layer browser visible).

**C08 (clipboard/bulk editing).** Clipboard/bulk editing at the input to next paint boundary (layer browser visible).

**C09 (undo/redo).** Undo/redo at the input to next paint boundary (layer browser visible).

**C10 (scrolling/viewport).** Scrolling/viewport at the frame time boundary (layer browser visible).

**C11 (initial layout/pagination).** Initial layout/pagination at the first contentful paint boundary (layer browser visible).

**C12 (incremental reflow).** Incremental reflow at the presented frame boundary (layer browser visible).

**C13 (global invalidation).** Global invalidation at the model ready boundary (layer model).

**C14 (large-document scaling).** Large-document scaling at the first usable boundary (layer browser visible).

**C15 (search/replace/indexing).** Search/replace/indexing at the model ready boundary (layer model).

## The host and its limits

Relaxed bounds: Clock skew: 5 ms. Ready/navigation load timeouts: 300 s by default, 600 s on the largest document workload. Sparse-witness settle onset floor: 100 ms. CPU throttle tolerance: max(1 ms, 1% of the sample span). Witness anchor lag: max(3 frame intervals, 250 ms). Typing/document content length tolerance: 2% for the prose documents; the complex document (complex-corpus) is accepted at 75% to 125% of the expected length.

Each seed ran on the same hardware class (shared_guarded) on separate virtual machines (Spaces e2-apryse, e2-canvas, e2-docen, e2-docsplus, e2-docxodus, e2-eigenpal, e2-fidus, e2-folio, e2-genoffice, e2-plate, e2-publish, e2-publish-2, e2-publish-3, e2-publish-4, e2-publish-5, e2-publish-6, e2-publish-7, e2-publish-8, e2-superdoc, e2-wordcraft), not on one host. A Space name is a machine name: the editors measured are those in the tables. Spaces e2-apryse, e2-docsplus, e2-fidus are machines named for editors this report does not measure.

Seed 1 — 80 jobs on Spaces e2-apryse, e2-canvas, e2-docen, e2-docsplus, e2-docxodus, e2-eigenpal, e2-fidus, e2-folio, e2-genoffice, e2-plate, e2-publish, e2-publish-3, e2-publish-4, e2-publish-5, e2-publish-6, e2-publish-7, e2-publish-8, e2-superdoc, e2-wordcraft: CPU model AMD EPYC 7R13 Processor; CPU quota 8.0; logical CPUs 64; OS linux 6.12.113-138.209.amzn2023.x86_64 (77 jobs), linux 6.12.111-136.204.amzn2023.x86_64 (3 jobs); Chromium 156.0.8078.80; renderer ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero) (0x0000C0DE)), SwiftShader driver); stolen CPU time less than 0.01%; throttle refusals: 2 of 2898 samples refused for cgroup CPU throttling.

Seed 2 — 80 jobs on Spaces e2-apryse, e2-canvas, e2-docen, e2-docsplus, e2-docxodus, e2-eigenpal, e2-fidus, e2-folio, e2-genoffice, e2-plate, e2-publish, e2-publish-2, e2-publish-3, e2-publish-4, e2-publish-5, e2-publish-6, e2-publish-7, e2-publish-8, e2-superdoc, e2-wordcraft: CPU model AMD EPYC 7R13 Processor; CPU quota 8.0; logical CPUs 64; OS linux 6.12.113-138.209.amzn2023.x86_64 (70 jobs), linux 6.12.111-136.204.amzn2023.x86_64 (10 jobs); Chromium 156.0.8078.80; renderer ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero) (0x0000C0DE)), SwiftShader driver); stolen CPU time less than 0.01%; throttle refusals: 3 of 2898 samples refused for cgroup CPU throttling.

Editor pins (built-editor tree SHA-256 of every attempt that ran, in every run folder): canvas-editor + plugin: db742f005c4542a8afa75f4801dd40785e1ce298331903d5ac84bce79c3b24a0; Docen: cf72bd0ee7f16b61d2751113a6533b63697cc437fdf1916e6cb8c6307a343204; Docxodus: dc663a3ee106917d5b93f06fa3ceaa2527bc917b7accfe582cf6ef411dc121ce; eigenpal: 94bdb0c2ee05a56bff1734c3b11f6d39805e4965fab5d778300ee288ce0af40e; Folio: 34e784f890d8ae99129f7ef98c0af4ca3225278b3f9f1a6ed93bee23a9b14ab4; GenOffice: 746b793e0ad8f2a0a12ec5ecf1aeddfa79895102244ac1c717bce6fbbe523789; Plate.js: 0b3c24cc2bf9348a9e904d22757449915be9abee764f5d345557f928cad6f32d; SuperDoc: 4ab1fc57f5e418532f50bc84c5380723c5ae52750d5ae2fdab55c3a4cefcfed6; WordCraft: 003a46b20c05597e3e385e745c9ddec19a4f0ecb43d57e596209e02c5623849a.

Jobs per Space, from each job summary's host-build records: e2-apryse: 9; e2-canvas: 5; e2-docen: 10; e2-docsplus: 8; e2-docxodus: 9; e2-eigenpal: 9; e2-fidus: 10; e2-folio: 9; e2-genoffice: 8; e2-plate: 8; e2-publish: 5; e2-publish-2: 6; e2-publish-3: 7; e2-publish-4: 7; e2-publish-5: 8; e2-publish-6: 8; e2-publish-7: 9; e2-publish-8: 7; e2-superdoc: 9; e2-wordcraft: 9.

Playwright not recorded, Chromium 156.0.8078.80. Renderer: ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero) (0x0000C0DE)), SwiftShader driver).

## The rule

This is a first pass with fewer samples than planned. Each cell schedules 10 samples per editor per seed and is published when at least 5 samples are kept. The 90th percentile is printed only when at least 10 samples are kept; with 5 to 9 kept, the table prints the median and the range from the smallest kept sample to the largest, because a percentile of a short sample is not a stable figure.

Typing schedules 6 sessions per kind per seed and publishes a cell when at least 5 are kept. With 5 kept sessions and fewer than 6, the table prints the median and the range from the smallest kept session to the largest. A key-to-paint 90th percentile inside one session is over keys, not over sessions.

Each launch contributes the median of its own samples; n counts kept launches. Scheduled counts come from each run's order. Publishability is decided per trial — job summaries delegate it to their trials — and a cell publishes only from trials that are publishable and record the built editor's identity (host_provenance.tree_sha256, else a pinned editor_version); a trial recording neither is refused as pin not recorded, and a reproduction across different built-editor trees is refused. Each of the two seeds must keep at least 5 launches per cell, its launches pooled across the campaign's run folders, and a run-level block — a shakedown run, dirty repos, unavailable CPU accounting or a failed run — refuses the whole run. The medians must agree within 10 percent of the larger median or the larger witnessed frame interval. Samples of frame-witnessed criteria require complete boolean flags checked against a witnessed interval; model-layer clocks such as C04 and byte counts publish without them, and sub-frame medians are buckets; p90 is printed only when at least 10 launches are kept; with 5 to 9 kept, the table prints the median and the range. p90 is over launch medians. C14 rungs and C14 measures (presented_frame, usable_no_damage) and C15 steps are separate measures; a no-damage C14 sample is the DOM document-surface time, never a compositor frame.

160 jobs in 40 run folders — seed 1: 80 jobs; seed 2: 80 jobs. Dates: 2026-11-12 to 2026-11-13.

## Read this before the tables

- **Re-run jobs.** 32 first-pass jobs were measured again after three harness defects were fixed (issues #173, #174 and #175). The tables read the 32 re-run jobs in their place and never the superseded ones. `perf/container/e2_publication.json` names every run and every replaced job.
- **How an edit is confirmed.** After each timed interval, and outside it, the harness checks that the edit landed once. It counts the typed text near the caret in the page (Plate, Docxodus, SuperDoc, GenOffice, eigenpal, and Folio through its hidden editing layer) or in the editor's model (canvas-editor, Docen). WordCraft paints into one canvas and exposes no text, so its edit is confirmed only by the modified mark in its window title.
- **WordCraft.** Because its text cannot be read, C03 and C11 cannot check the document's content for WordCraft, and those cells say so.
- **Docxodus** opens a read-only, paginated view. Lanes that edit switch it to its block editor before the timed interval starts, so its load times are those of the paginated view.
- **The complex document.** It carries Word's document protection. The lanes that edit it open a copy with that protection removed; the lanes that only load it open the original.
- **Typing tolerance.** GenOffice turns autocorrect on by default (Word's defaults except sentence capitalisation). The typing check compares the whole typed text after three folds: typographic quotes, backticks and guillemets count as straight quotes; (c), (r) and (tm), in either case, may become ©, ® and ™; and any run of whitespace (spaces, tabs, non-breaking spaces, line breaks) counts as one space. A typed list marker (`1.`, `a.`, `(i)`) is excused when the editor turned that line into a real list item, or when the editor painted another marker in its place (a renumbered `1.` shown as `2.`, or a line holding only a marker); in this run every excused marker was of the first kind. A missing or extra character still fails.
- **Criteria that do not apply.** canvas-editor and Docen paint text without glyph geometry the harness can read, so C05 and C06, which time the keystroke's own paint, do not apply to them. C15 (search and replace) applies to no editor in this run: no measured host exposes a find interface the probe can drive. The document lane ran C15 in each of its five jobs per block, so the C15 cells are also refused as a duplicate block index; since no C15 attempt was applicable, no figure is affected.
- **Chrome traces.** In every first-block job, each timed launch was followed by a separate, untimed launch that recorded a Chrome trace for diagnosis; second-block jobs ran without them, and so did most typing sessions. Traces never feed a table.
- **Throttling and steal.** The host note above gives, per seed, the CPU steal and the samples refused for cgroup CPU throttling; a refused sample is never kept.

## Tables

### C03 — first visible content

| Editor | Workload | Measure | C03 |
|---|---|---|---|
| canvas-editor + plugin | complex-corpus | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_run: 10); second: not enough samples (n = 0 of 10; reasons not_run: 10) |
| Docen | complex-corpus | process_cold_fs_warm | 1196.0 ms; 0% sub-frame launches; p90 1236.5 ms; n = 10 of 10 |
| Docxodus | complex-corpus | process_cold_fs_warm | 2980.0 ms; 0% sub-frame launches; p90 2999.3 ms; n = 10 of 10 |
| eigenpal | complex-corpus | process_cold_fs_warm | 903.5 ms; 0% sub-frame launches; p90 937.8 ms; n = 10 of 10 |
| Folio | complex-corpus | process_cold_fs_warm | 889.0 ms; 0% sub-frame launches; p90 904.6 ms; n = 10 of 10 |
| GenOffice | complex-corpus | process_cold_fs_warm | 1295.5 ms; 0% sub-frame launches; p90 1329.9 ms; n = 10 of 10 |
| Plate.js | complex-corpus | process_cold_fs_warm | 892.5 ms; 0% sub-frame launches; p90 915.2 ms; n = 10 of 10 |
| SuperDoc | complex-corpus | process_cold_fs_warm | 997.0 ms; 0% sub-frame launches; p90 1028.3 ms; n = 10 of 10 |
| WordCraft | complex-corpus | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) |
| canvas-editor + plugin | complex-corpus | warm_steady | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| Docen | complex-corpus | warm_steady | 930.5 ms; 0% sub-frame launches; p90 958.4 ms; n = 10 of 10 |
| Docxodus | complex-corpus | warm_steady | 2496.0 ms; 0% sub-frame launches; p90 2549.6 ms; n = 10 of 10 |
| eigenpal | complex-corpus | warm_steady | 597.5 ms; 0% sub-frame launches; p90 608.9 ms; n = 10 of 10 |
| Folio | complex-corpus | warm_steady | 505.0 ms; 0% sub-frame launches; p90 527.3 ms; n = 10 of 10 |
| GenOffice | complex-corpus | warm_steady | not reproduced (first 1082.5 ms; second 883.5 ms) |
| Plate.js | complex-corpus | warm_steady | 579.0 ms; 0% sub-frame launches; p90 613.7 ms; n = 10 of 10 |
| SuperDoc | complex-corpus | warm_steady | 383.0 ms; 0% sub-frame launches; p90 389.2 ms; n = 10 of 10 |
| WordCraft | complex-corpus | warm_steady | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) |
| canvas-editor + plugin | prose-250kw | process_cold_fs_warm | 45500.0 ms; 0% sub-frame launches; p90 50419.8 ms; n = 10 of 10 |
| Docen | prose-250kw | process_cold_fs_warm | not reproduced (first 9218.0 ms; second 10338.0 ms) |
| Docxodus | prose-250kw | process_cold_fs_warm | 44168.5 ms; 0% sub-frame launches; p90 47092.3 ms; n = 10 of 10 |
| eigenpal | prose-250kw | process_cold_fs_warm | 5861.0 ms; 0% sub-frame launches; p90 6465.6 ms; n = 10 of 10 |
| Folio | prose-250kw | process_cold_fs_warm | 4677.0 ms; 0% sub-frame launches; p90 5024.6 ms; n = 10 of 10 |
| GenOffice | prose-250kw | process_cold_fs_warm | 2699.0 ms; 0% sub-frame launches; p90 2924.6 ms; n = 10 of 10 |
| Plate.js | prose-250kw | process_cold_fs_warm | 18758.0 ms; 0% sub-frame launches; p90 19900.9 ms; n = 10 of 10 |
| SuperDoc | prose-250kw | process_cold_fs_warm | 1000.0 ms; 0% sub-frame launches; p90 1026.8 ms; n = 10 of 10 |
| WordCraft | prose-250kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) |
| canvas-editor + plugin | prose-250kw | warm_steady | 57138.0 ms; 0% sub-frame launches; p90 61205.7 ms; n = 10 of 10 |
| Docen | prose-250kw | warm_steady | 8858.5 ms; 0% sub-frame launches; p90 10014.8 ms; n = 10 of 10 |
| Docxodus | prose-250kw | warm_steady | 43563.0 ms; 0% sub-frame launches; p90 47171.4 ms; n = 10 of 10 |
| eigenpal | prose-250kw | warm_steady | 5575.0 ms; 0% sub-frame launches; p90 6140.5 ms; n = 10 of 10 |
| Folio | prose-250kw | warm_steady | 4366.0 ms; 0% sub-frame launches; p90 4616.3 ms; n = 10 of 10 |
| GenOffice | prose-250kw | warm_steady | 2443.0 ms; 0% sub-frame launches; p90 2695.4 ms; n = 10 of 10 |
| Plate.js | prose-250kw | warm_steady | 17202.0 ms; 0% sub-frame launches; p90 19075.1 ms; n = 10 of 10 |
| SuperDoc | prose-250kw | warm_steady | 434.5 ms; 0% sub-frame launches; p90 517.8 ms; n = 10 of 10 |
| WordCraft | prose-250kw | warm_steady | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) |
| canvas-editor + plugin | prose-500w | process_cold_fs_warm | 222.5 ms; 0% sub-frame launches; p90 242.9 ms; n = 10 of 10 |
| Docen | prose-500w | process_cold_fs_warm | 1145.0 ms; 0% sub-frame launches; p90 1214.5 ms; n = 10 of 10 |
| Docxodus | prose-500w | process_cold_fs_warm | 2445.0 ms; 0% sub-frame launches; p90 2592.8 ms; n = 10 of 10 |
| eigenpal | prose-500w | process_cold_fs_warm | 675.0 ms; 0% sub-frame launches; p90 694.6 ms; n = 10 of 10 |
| Folio | prose-500w | process_cold_fs_warm | 784.5 ms; 0% sub-frame launches; p90 806.0 ms; n = 10 of 10 |
| GenOffice | prose-500w | process_cold_fs_warm | 760.0 ms; 0% sub-frame launches; p90 790.7 ms; n = 10 of 10 |
| Plate.js | prose-500w | process_cold_fs_warm | 784.0 ms; 0% sub-frame launches; p90 824.2 ms; n = 10 of 10 |
| SuperDoc | prose-500w | process_cold_fs_warm | 993.5 ms; 0% sub-frame launches; p90 1019.3 ms; n = 10 of 10 |
| WordCraft | prose-500w | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) |
| canvas-editor + plugin | prose-500w | warm_steady | 147.0 ms; 0% sub-frame launches; p90 153.2 ms; n = 10 of 10 |
| Docen | prose-500w | warm_steady | 842.5 ms; 0% sub-frame launches; p90 929.3 ms; n = 10 of 10 |
| Docxodus | prose-500w | warm_steady | 2116.5 ms; 0% sub-frame launches; p90 2262.9 ms; n = 10 of 10 |
| eigenpal | prose-500w | warm_steady | 458.5 ms; 0% sub-frame launches; p90 547.5 ms; n = 10 of 10 |
| Folio | prose-500w | warm_steady | 473.5 ms; 0% sub-frame launches; p90 520.0 ms; n = 10 of 10 |
| GenOffice | prose-500w | warm_steady | 438.0 ms; 0% sub-frame launches; p90 478.2 ms; n = 10 of 10 |
| Plate.js | prose-500w | warm_steady | 512.5 ms; 0% sub-frame launches; p90 549.9 ms; n = 10 of 10 |
| SuperDoc | prose-500w | warm_steady | 389.5 ms; 0% sub-frame launches; p90 395.4 ms; n = 10 of 10 |
| WordCraft | prose-500w | warm_steady | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) |
| canvas-editor + plugin | prose-50kw | process_cold_fs_warm | not reproduced (first 6478.5 ms; second 5217.5 ms) |
| Docen | prose-50kw | process_cold_fs_warm | not reproduced (first 3378.0 ms; second 2551.0 ms) |
| Docxodus | prose-50kw | process_cold_fs_warm | not reproduced (first 13686.5 ms; second 10022.5 ms) |
| eigenpal | prose-50kw | process_cold_fs_warm | not reproduced (first 2716.0 ms; second 1818.0 ms) |
| Folio | prose-50kw | process_cold_fs_warm | not reproduced (first 2335.5 ms; second 1669.0 ms) |
| GenOffice | prose-50kw | process_cold_fs_warm | not reproduced (first 1774.5 ms; second 1441.0 ms) |
| Plate.js | prose-50kw | process_cold_fs_warm | not reproduced (first 6324.0 ms; second 4222.0 ms) |
| SuperDoc | prose-50kw | process_cold_fs_warm | not reproduced (first 1116.5 ms; second 988.5 ms) |
| WordCraft | prose-50kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) |
| canvas-editor + plugin | prose-50kw | warm_steady | not reproduced (first 6818.0 ms; second 4463.0 ms) |
| Docen | prose-50kw | warm_steady | not reproduced (first 3088.5 ms; second 2218.0 ms) |
| Docxodus | prose-50kw | warm_steady | not reproduced (first 12095.0 ms; second 9142.5 ms) |
| eigenpal | prose-50kw | warm_steady | not reproduced (first 2220.5 ms; second 1535.0 ms) |
| Folio | prose-50kw | warm_steady | not reproduced (first 2072.5 ms; second 1309.0 ms) |
| GenOffice | prose-50kw | warm_steady | not reproduced (first 1386.5 ms; second 1237.0 ms) |
| Plate.js | prose-50kw | warm_steady | not reproduced (first 5563.5 ms; second 3694.5 ms) |
| SuperDoc | prose-50kw | warm_steady | not reproduced (first 941.5 ms; second 388.5 ms) |
| WordCraft | prose-50kw | warm_steady | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) |
| canvas-editor + plugin | prose-5kw | process_cold_fs_warm | 653.0 ms; 0% sub-frame launches; p90 739.0 ms; n = 10 of 10 |
| Docen | prose-5kw | process_cold_fs_warm | not reproduced (first 1432.5 ms; second 1597.0 ms) |
| Docxodus | prose-5kw | process_cold_fs_warm | 3399.5 ms; 0% sub-frame launches; p90 3784.8 ms; n = 10 of 10 |
| eigenpal | prose-5kw | process_cold_fs_warm | 1020.0 ms; 0% sub-frame launches; p90 1089.1 ms; n = 10 of 10 |
| Folio | prose-5kw | process_cold_fs_warm | not reproduced (first 938.0 ms; second 1058.0 ms) |
| GenOffice | prose-5kw | process_cold_fs_warm | 940.0 ms; 0% sub-frame launches; p90 1391.3 ms; n = 10 of 10 |
| Plate.js | prose-5kw | process_cold_fs_warm | 1199.0 ms; 0% sub-frame launches; p90 1279.5 ms; n = 10 of 10 |
| SuperDoc | prose-5kw | process_cold_fs_warm | 1035.0 ms; 0% sub-frame launches; p90 1083.8 ms; n = 10 of 10 |
| WordCraft | prose-5kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) |
| canvas-editor + plugin | prose-5kw | warm_steady | 526.5 ms; 0% sub-frame launches; p90 548.7 ms; n = 10 of 10 |
| Docen | prose-5kw | warm_steady | 1099.0 ms; 0% sub-frame launches; p90 1213.6 ms; n = 10 of 10 |
| Docxodus | prose-5kw | warm_steady | 2772.0 ms; 0% sub-frame launches; p90 2904.2 ms; n = 10 of 10 |
| eigenpal | prose-5kw | warm_steady | not reproduced (first 796.5 ms; second 904.5 ms) |
| Folio | prose-5kw | warm_steady | 602.0 ms; 0% sub-frame launches; p90 633.2 ms; n = 10 of 10 |
| GenOffice | prose-5kw | warm_steady | 655.0 ms; 0% sub-frame launches; p90 722.0 ms; n = 10 of 10 |
| Plate.js | prose-5kw | warm_steady | 823.5 ms; 0% sub-frame launches; p90 837.9 ms; n = 10 of 10 |
| SuperDoc | prose-5kw | warm_steady | 394.5 ms; 0% sub-frame launches; p90 413.7 ms; n = 10 of 10 |
| WordCraft | prose-5kw | warm_steady | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) |

### C04 — deferred work

| Editor | Workload | C04 |
|---|---|---|
| canvas-editor + plugin | complex-corpus | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) |
| Docen | complex-corpus | 1.8 ms; p90 1.9 ms; n = 10 of 10 |
| Docxodus | complex-corpus | 1.9 ms; p90 2.3 ms; n = 10 of 10 |
| eigenpal | complex-corpus | 2.1 ms; p90 3.1 ms; n = 10 of 10 |
| Folio | complex-corpus | 1.7 ms; p90 1.7 ms; n = 10 of 10 |
| GenOffice | complex-corpus | 1.8 ms; p90 1.9 ms; n = 10 of 10 |
| Plate.js | complex-corpus | 1.9 ms; p90 1.9 ms; n = 10 of 10 |
| SuperDoc | complex-corpus | 1.8 ms; p90 1.9 ms; n = 10 of 10 |
| WordCraft | complex-corpus | not reproduced (first 472.0 ms; second 868.0 ms) |
| canvas-editor + plugin | prose-250kw | 1.8 ms; p90 2.1 ms; n = 10 of 10 |
| Docen | prose-250kw | 1.9 ms; p90 2.0 ms; n = 10 of 10 |
| Docxodus | prose-250kw | 1.8 ms; p90 1.9 ms; n = 10 of 10 |
| eigenpal | prose-250kw | 1.9 ms; p90 3.3 ms; n = 10 of 10 |
| Folio | prose-250kw | 1.7 ms; p90 1.8 ms; n = 10 of 10 |
| GenOffice | prose-250kw | 1.9 ms; p90 2.1 ms; n = 10 of 10 |
| Plate.js | prose-250kw | 1.8 ms; range 1.7 to 2.1 ms; n = 9 of 10; 1 of 10 launches failed: quarantined: 1; also cpu_throttled: 1 |
| SuperDoc | prose-250kw | not reproduced (first 1.9 ms; second 2.3 ms) |
| WordCraft | prose-250kw | not reproduced (first 227.6 ms; second 468.8 ms) |
| canvas-editor + plugin | prose-500w | 1.8 ms; p90 1.9 ms; n = 10 of 10 |
| Docen | prose-500w | 1.8 ms; p90 2.2 ms; n = 10 of 10 |
| Docxodus | prose-500w | 2.0 ms; p90 4.6 ms; n = 10 of 10 |
| eigenpal | prose-500w | 1.7 ms; p90 2.0 ms; n = 10 of 10 |
| Folio | prose-500w | 1.8 ms; p90 2.3 ms; n = 10 of 10 |
| GenOffice | prose-500w | 1.9 ms; p90 2.4 ms; n = 10 of 10 |
| Plate.js | prose-500w | 1.8 ms; p90 2.0 ms; n = 10 of 10 |
| SuperDoc | prose-500w | 1.8 ms; p90 1.9 ms; n = 10 of 10 |
| WordCraft | prose-500w | not reproduced (first 799.3 ms; second 379.7 ms) |
| canvas-editor + plugin | prose-50kw | 1.9 ms; p90 2.1 ms; n = 10 of 10 |
| Docen | prose-50kw | not reproduced (first 2.0 ms; second 1.8 ms) |
| Docxodus | prose-50kw | 1.9 ms; p90 2.2 ms; n = 10 of 10 |
| eigenpal | prose-50kw | 1.9 ms; p90 2.4 ms; n = 10 of 10 |
| Folio | prose-50kw | not reproduced (first 2.1 ms; second 1.8 ms) |
| GenOffice | prose-50kw | not reproduced (first 2.3 ms; second 1.9 ms) |
| Plate.js | prose-50kw | 2.0 ms; p90 2.5 ms; n = 10 of 10 |
| SuperDoc | prose-50kw | 2.4 ms; p90 3.0 ms; n = 10 of 10 |
| WordCraft | prose-50kw | not reproduced (first 443.5 ms; second 2.0 ms) |
| canvas-editor + plugin | prose-5kw | not reproduced (first 1.9 ms; second 2.1 ms) |
| Docen | prose-5kw | 1.9 ms; p90 5.3 ms; n = 10 of 10 |
| Docxodus | prose-5kw | 1.9 ms; p90 2.1 ms; n = 10 of 10 |
| eigenpal | prose-5kw | 1.7 ms; p90 1.8 ms; n = 10 of 10 |
| Folio | prose-5kw | 1.9 ms; p90 2.1 ms; n = 10 of 10 |
| GenOffice | prose-5kw | not reproduced (first 1.8 ms; second 2.3 ms) |
| Plate.js | prose-5kw | not reproduced (first 1.8 ms; second 2.2 ms) |
| SuperDoc | prose-5kw | not reproduced (first 1.7 ms; second 1.9 ms) |
| WordCraft | prose-5kw | not reproduced (first 486.1 ms; second 651.1 ms); first: 1 of 10 launches failed: unverified: 1 |

### C05 — single-edit responsiveness

| Editor | Workload | Measure | C05 |
|---|---|---|---|
| canvas-editor + plugin | complex-corpus | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_run: 10); second: not enough samples (n = 0 of 10; reasons not_run: 10) |
| Docen | complex-corpus | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) |
| Docxodus | complex-corpus | process_cold_fs_warm | < 1 frame (16.7 ms); 90% sub-frame launches; p90 < 1 frame (16.7 ms); n = 10 of 10 |
| eigenpal | complex-corpus | process_cold_fs_warm | 37.1 ms; 0% sub-frame launches; p90 46.8 ms; n = 10 of 10 |
| Folio | complex-corpus | process_cold_fs_warm | 59.3 ms; 0% sub-frame launches; p90 63.1 ms; n = 10 of 10 |
| GenOffice | complex-corpus | process_cold_fs_warm | 28.4 ms; 0% sub-frame launches; p90 38.3 ms; n = 10 of 10 |
| Plate.js | complex-corpus | process_cold_fs_warm | 40.7 ms; 0% sub-frame launches; p90 51.4 ms; n = 10 of 10 |
| SuperDoc | complex-corpus | process_cold_fs_warm | 228.9 ms; 0% sub-frame launches; p90 240.9 ms; n = 10 of 10 |
| WordCraft | complex-corpus | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| canvas-editor + plugin | complex-corpus | warm_steady | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| Docen | complex-corpus | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docxodus | complex-corpus | warm_steady | < 1 frame (16.7 ms); 80% sub-frame launches; p90 17.8 ms; n = 10 of 10 |
| eigenpal | complex-corpus | warm_steady | 42.4 ms; 0% sub-frame launches; p90 48.1 ms; n = 10 of 10 |
| Folio | complex-corpus | warm_steady | 51.3 ms; 0% sub-frame launches; p90 56.2 ms; n = 10 of 10 |
| GenOffice | complex-corpus | warm_steady | 25.8 ms; 20% sub-frame launches; p90 28.3 ms; n = 10 of 10 |
| Plate.js | complex-corpus | warm_steady | 24.1 ms; 0% sub-frame launches; p90 32.3 ms; n = 10 of 10 |
| SuperDoc | complex-corpus | warm_steady | 219.3 ms; 0% sub-frame launches; p90 222.7 ms; n = 10 of 10 |
| WordCraft | complex-corpus | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| canvas-editor + plugin | prose-250kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) |
| Docen | prose-250kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) |
| Docxodus | prose-250kw | process_cold_fs_warm | 32.9 ms; 0% sub-frame launches; p90 36.4 ms; n = 10 of 10 |
| eigenpal | prose-250kw | process_cold_fs_warm | 85.1 ms; 0% sub-frame launches; p90 95.6 ms; n = 10 of 10 |
| Folio | prose-250kw | process_cold_fs_warm | 442.7 ms; 0% sub-frame launches; p90 469.5 ms; n = 10 of 10 |
| GenOffice | prose-250kw | process_cold_fs_warm | second: not enough samples (n = 1 of 10; reasons unverified: 9) |
| Plate.js | prose-250kw | process_cold_fs_warm | not reproduced (first 175.2 ms; second 205.5 ms) |
| SuperDoc | prose-250kw | process_cold_fs_warm | 549.2 ms; 0% sub-frame launches; p90 616.8 ms; n = 10 of 10 |
| WordCraft | prose-250kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| canvas-editor + plugin | prose-250kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docen | prose-250kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docxodus | prose-250kw | warm_steady | 27.6 ms; 0% sub-frame launches; p90 32.8 ms; n = 10 of 10 |
| eigenpal | prose-250kw | warm_steady | 76.7 ms; 0% sub-frame launches; p90 85.4 ms; n = 10 of 10 |
| Folio | prose-250kw | warm_steady | not reproduced (first 427.2 ms; second 483.5 ms) |
| GenOffice | prose-250kw | warm_steady | second: not enough samples (n = 1 of 10; reasons unverified: 9) |
| Plate.js | prose-250kw | warm_steady | not reproduced (first 129.7 ms; second 161.8 ms) |
| SuperDoc | prose-250kw | warm_steady | 557.2 ms; 0% sub-frame launches; p90 602.8 ms; n = 10 of 10 |
| WordCraft | prose-250kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| canvas-editor + plugin | prose-500w | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) |
| Docen | prose-500w | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) |
| Docxodus | prose-500w | process_cold_fs_warm | < 1 frame (16.7 ms); 70% sub-frame launches; p90 17.8 ms; n = 10 of 10 |
| eigenpal | prose-500w | process_cold_fs_warm | 60.1 ms; 0% sub-frame launches; p90 61.2 ms; n = 10 of 10 |
| Folio | prose-500w | process_cold_fs_warm | 51.3 ms; 0% sub-frame launches; p90 58.8 ms; n = 10 of 10 |
| GenOffice | prose-500w | process_cold_fs_warm | 25.6 ms; 20% sub-frame launches; p90 30.6 ms; n = 10 of 10 |
| Plate.js | prose-500w | process_cold_fs_warm | 47.3 ms; 0% sub-frame launches; p90 51.2 ms; n = 10 of 10 |
| SuperDoc | prose-500w | process_cold_fs_warm | 148.9 ms; 0% sub-frame launches; p90 153.2 ms; n = 10 of 10 |
| WordCraft | prose-500w | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| canvas-editor + plugin | prose-500w | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docen | prose-500w | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docxodus | prose-500w | warm_steady | < 1 frame (16.7 ms); 60% sub-frame launches; p90 19.5 ms; n = 10 of 10 |
| eigenpal | prose-500w | warm_steady | 46.2 ms; 0% sub-frame launches; p90 50.2 ms; n = 10 of 10 |
| Folio | prose-500w | warm_steady | 45.2 ms; 0% sub-frame launches; p90 46.8 ms; n = 10 of 10 |
| GenOffice | prose-500w | warm_steady | 17.5 ms; 30% sub-frame launches; p90 26.1 ms; n = 10 of 10 |
| Plate.js | prose-500w | warm_steady | 22.9 ms; 0% sub-frame launches; p90 27.1 ms; n = 10 of 10 |
| SuperDoc | prose-500w | warm_steady | 137.4 ms; 0% sub-frame launches; p90 139.7 ms; n = 10 of 10 |
| WordCraft | prose-500w | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| canvas-editor + plugin | prose-50kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) |
| Docen | prose-50kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) |
| Docxodus | prose-50kw | process_cold_fs_warm | 18.6 ms; 30% sub-frame launches; p90 26.5 ms; n = 10 of 10 |
| eigenpal | prose-50kw | process_cold_fs_warm | not reproduced (first 97.6 ms; second 65.5 ms) |
| Folio | prose-50kw | process_cold_fs_warm | not reproduced (first 215.3 ms; second 134.0 ms) |
| GenOffice | prose-50kw | process_cold_fs_warm | not reproduced (first 193.6 ms; second 143.4 ms) |
| Plate.js | prose-50kw | process_cold_fs_warm | not reproduced (first 98.0 ms; second 67.9 ms) |
| SuperDoc | prose-50kw | process_cold_fs_warm | not reproduced (first 644.0 ms; second 450.2 ms); first: 1 of 10 launches failed: unverified: 1 |
| WordCraft | prose-50kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| canvas-editor + plugin | prose-50kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docen | prose-50kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docxodus | prose-50kw | warm_steady | 22.2 ms; 20% sub-frame launches; p90 26.2 ms; n = 10 of 10 |
| eigenpal | prose-50kw | warm_steady | not reproduced (first 77.3 ms; second 56.2 ms) |
| Folio | prose-50kw | warm_steady | not reproduced (first 182.8 ms; second 121.5 ms) |
| GenOffice | prose-50kw | warm_steady | not reproduced (first 207.3 ms; second 139.5 ms) |
| Plate.js | prose-50kw | warm_steady | 64.1 ms; 0% sub-frame launches; p90 77.6 ms; n = 10 of 10 |
| SuperDoc | prose-50kw | warm_steady | not reproduced (first 614.5 ms; second 431.5 ms); first: 1 of 10 launches failed: unverified: 1 |
| WordCraft | prose-50kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| canvas-editor + plugin | prose-5kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) |
| Docen | prose-5kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) |
| Docxodus | prose-5kw | process_cold_fs_warm | < 1 frame (16.7 ms); 70% sub-frame launches; p90 18.9 ms; n = 10 of 10 |
| eigenpal | prose-5kw | process_cold_fs_warm | 72.0 ms; 0% sub-frame launches; p90 79.5 ms; n = 10 of 10 |
| Folio | prose-5kw | process_cold_fs_warm | 56.4 ms; 0% sub-frame launches; p90 73.5 ms; n = 10 of 10 |
| GenOffice | prose-5kw | process_cold_fs_warm | 32.3 ms; 0% sub-frame launches; p90 35.7 ms; n = 10 of 10 |
| Plate.js | prose-5kw | process_cold_fs_warm | 49.0 ms; 0% sub-frame launches; p90 57.9 ms; n = 10 of 10 |
| SuperDoc | prose-5kw | process_cold_fs_warm | 301.1 ms; 0% sub-frame launches; p90 335.8 ms; n = 10 of 10 |
| WordCraft | prose-5kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| canvas-editor + plugin | prose-5kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docen | prose-5kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docxodus | prose-5kw | warm_steady | < 1 frame (16.7 ms); 80% sub-frame launches; p90 17.1 ms; n = 10 of 10 |
| eigenpal | prose-5kw | warm_steady | 45.8 ms; 0% sub-frame launches; p90 52.7 ms; n = 10 of 10 |
| Folio | prose-5kw | warm_steady | 44.7 ms; 0% sub-frame launches; p90 48.0 ms; n = 10 of 10 |
| GenOffice | prose-5kw | warm_steady | 26.7 ms; 10% sub-frame launches; p90 31.2 ms; n = 10 of 10 |
| Plate.js | prose-5kw | warm_steady | 27.1 ms; 0% sub-frame launches; p90 32.1 ms; n = 10 of 10 |
| SuperDoc | prose-5kw | warm_steady | not reproduced (first 286.2 ms; second 318.5 ms) |
| WordCraft | prose-5kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |

### C06 — sustained typing

| Editor | Workload | Measure | C06 |
|---|---|---|---|
| canvas-editor + plugin | complex-corpus | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_run: 10); second: not enough samples (n = 0 of 10; reasons not_run: 10) |
| Docen | complex-corpus | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) |
| Docxodus | complex-corpus | process_cold_fs_warm | < 1 frame (16.7 ms); 90% sub-frame launches; p90 16.8 ms; n = 10 of 10 |
| eigenpal | complex-corpus | process_cold_fs_warm | 39.8 ms; 0% sub-frame launches; p90 42.6 ms; n = 10 of 10 |
| Folio | complex-corpus | process_cold_fs_warm | 54.1 ms; 0% sub-frame launches; p90 66.4 ms; n = 10 of 10 |
| GenOffice | complex-corpus | process_cold_fs_warm | 21.4 ms; 10% sub-frame launches; p90 23.1 ms; n = 10 of 10 |
| Plate.js | complex-corpus | process_cold_fs_warm | 25.1 ms; 0% sub-frame launches; p90 29.4 ms; n = 10 of 10 |
| SuperDoc | complex-corpus | process_cold_fs_warm | 126.0 ms; 0% sub-frame launches; p90 134.9 ms; n = 10 of 10 |
| WordCraft | complex-corpus | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| canvas-editor + plugin | complex-corpus | warm_steady | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| Docen | complex-corpus | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docxodus | complex-corpus | warm_steady | < 1 frame (16.7 ms); 100% sub-frame launches; p90 < 1 frame (16.7 ms); n = 10 of 10 |
| eigenpal | complex-corpus | warm_steady | 43.1 ms; 0% sub-frame launches; p90 44.9 ms; n = 10 of 10 |
| Folio | complex-corpus | warm_steady | 53.4 ms; 0% sub-frame launches; p90 66.3 ms; n = 10 of 10 |
| GenOffice | complex-corpus | warm_steady | 21.8 ms; 20% sub-frame launches; p90 25.7 ms; n = 10 of 10 |
| Plate.js | complex-corpus | warm_steady | 21.7 ms; 0% sub-frame launches; p90 26.4 ms; n = 10 of 10 |
| SuperDoc | complex-corpus | warm_steady | 121.6 ms; 0% sub-frame launches; p90 132.8 ms; n = 10 of 10 |
| WordCraft | complex-corpus | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| canvas-editor + plugin | prose-250kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) |
| Docen | prose-250kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) |
| Docxodus | prose-250kw | process_cold_fs_warm | 29.0 ms; 0% sub-frame launches; p90 32.2 ms; n = 10 of 10 |
| eigenpal | prose-250kw | process_cold_fs_warm | 59.8 ms; 0% sub-frame launches; p90 68.4 ms; n = 10 of 10 |
| Folio | prose-250kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) |
| GenOffice | prose-250kw | process_cold_fs_warm | second: not enough samples (n = 0 of 10; reasons unverified: 10) |
| Plate.js | prose-250kw | process_cold_fs_warm | 129.6 ms; 0% sub-frame launches; p90 140.5 ms; n = 10 of 10 |
| SuperDoc | prose-250kw | process_cold_fs_warm | 313.2 ms; 0% sub-frame launches; range 286.1 to 410.3 ms; n = 9 of 10; 1 of 10 launches failed: unverified: 1 |
| WordCraft | prose-250kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| canvas-editor + plugin | prose-250kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docen | prose-250kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docxodus | prose-250kw | warm_steady | 27.6 ms; 0% sub-frame launches; p90 32.8 ms; n = 10 of 10 |
| eigenpal | prose-250kw | warm_steady | 60.7 ms; 0% sub-frame launches; p90 75.1 ms; n = 10 of 10 |
| Folio | prose-250kw | warm_steady | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) |
| GenOffice | prose-250kw | warm_steady | second: not enough samples (n = 0 of 10; reasons unverified: 10) |
| Plate.js | prose-250kw | warm_steady | 131.8 ms; 0% sub-frame launches; p90 147.0 ms; n = 10 of 10 |
| SuperDoc | prose-250kw | warm_steady | not reproduced (first 303.3 ms; second 337.5 ms); first: 1 of 10 launches failed: unverified: 1 |
| WordCraft | prose-250kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| canvas-editor + plugin | prose-500w | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) |
| Docen | prose-500w | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) |
| Docxodus | prose-500w | process_cold_fs_warm | < 1 frame (16.7 ms); 90% sub-frame launches; p90 16.8 ms; n = 10 of 10 |
| eigenpal | prose-500w | process_cold_fs_warm | 41.8 ms; 0% sub-frame launches; p90 46.8 ms; n = 10 of 10 |
| Folio | prose-500w | process_cold_fs_warm | 44.4 ms; 0% sub-frame launches; p90 52.3 ms; n = 10 of 10 |
| GenOffice | prose-500w | process_cold_fs_warm | < 1 frame (16.7 ms); 60% sub-frame launches; p90 21.1 ms; n = 10 of 10 |
| Plate.js | prose-500w | process_cold_fs_warm | 22.1 ms; 0% sub-frame launches; p90 26.6 ms; n = 10 of 10 |
| SuperDoc | prose-500w | process_cold_fs_warm | 73.4 ms; 0% sub-frame launches; p90 85.4 ms; n = 10 of 10 |
| WordCraft | prose-500w | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| canvas-editor + plugin | prose-500w | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docen | prose-500w | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docxodus | prose-500w | warm_steady | < 1 frame (16.7 ms); 80% sub-frame launches; p90 17.1 ms; n = 10 of 10 |
| eigenpal | prose-500w | warm_steady | 38.6 ms; 0% sub-frame launches; p90 40.0 ms; n = 10 of 10 |
| Folio | prose-500w | warm_steady | 48.7 ms; 0% sub-frame launches; p90 57.0 ms; n = 10 of 10 |
| GenOffice | prose-500w | warm_steady | 17.3 ms; 50% sub-frame launches; p90 21.1 ms; n = 10 of 10 |
| Plate.js | prose-500w | warm_steady | 22.3 ms; 0% sub-frame launches; p90 25.5 ms; n = 10 of 10 |
| SuperDoc | prose-500w | warm_steady | 76.6 ms; 0% sub-frame launches; p90 82.7 ms; n = 10 of 10 |
| WordCraft | prose-500w | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| canvas-editor + plugin | prose-50kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) |
| Docen | prose-50kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) |
| Docxodus | prose-50kw | process_cold_fs_warm | 17.4 ms; 30% sub-frame launches; p90 22.5 ms; n = 10 of 10 |
| eigenpal | prose-50kw | process_cold_fs_warm | not reproduced (first 66.5 ms; second 44.0 ms) |
| Folio | prose-50kw | process_cold_fs_warm | not reproduced (first 171.4 ms; second 117.5 ms) |
| GenOffice | prose-50kw | process_cold_fs_warm | not reproduced (first 176.3 ms; second 134.7 ms) |
| Plate.js | prose-50kw | process_cold_fs_warm | not reproduced (first 59.2 ms; second 39.2 ms) |
| SuperDoc | prose-50kw | process_cold_fs_warm | not reproduced (first 369.9 ms; second 278.9 ms); first: 3 of 10 launches failed: unverified: 3 |
| WordCraft | prose-50kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| canvas-editor + plugin | prose-50kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docen | prose-50kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docxodus | prose-50kw | warm_steady | 16.9 ms; 50% sub-frame launches; p90 24.8 ms; n = 10 of 10 |
| eigenpal | prose-50kw | warm_steady | 64.5 ms; 0% sub-frame launches; p90 76.3 ms; n = 10 of 10 |
| Folio | prose-50kw | warm_steady | not reproduced (first 163.5 ms; second 107.9 ms) |
| GenOffice | prose-50kw | warm_steady | not reproduced (first 203.2 ms; second 143.2 ms) |
| Plate.js | prose-50kw | warm_steady | not reproduced (first 61.2 ms; second 43.9 ms) |
| SuperDoc | prose-50kw | warm_steady | not reproduced (first 370.5 ms; second 275.1 ms); first: 3 of 10 launches failed: unverified: 3 |
| WordCraft | prose-50kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| canvas-editor + plugin | prose-5kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) |
| Docen | prose-5kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) |
| Docxodus | prose-5kw | process_cold_fs_warm | < 1 frame (16.7 ms); 90% sub-frame launches; p90 < 1 frame (16.7 ms); n = 10 of 10 |
| eigenpal | prose-5kw | process_cold_fs_warm | 44.0 ms; 0% sub-frame launches; p90 55.1 ms; n = 10 of 10 |
| Folio | prose-5kw | process_cold_fs_warm | 49.9 ms; 0% sub-frame launches; p90 59.3 ms; n = 10 of 10 |
| GenOffice | prose-5kw | process_cold_fs_warm | 22.4 ms; 0% sub-frame launches; range 17.7 to 30.4 ms; n = 9 of 10; 1 of 10 launches failed: crash: 1 |
| Plate.js | prose-5kw | process_cold_fs_warm | 24.6 ms; 0% sub-frame launches; p90 27.9 ms; n = 10 of 10 |
| SuperDoc | prose-5kw | process_cold_fs_warm | not reproduced (first 176.1 ms; second 199.9 ms) |
| WordCraft | prose-5kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| canvas-editor + plugin | prose-5kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docen | prose-5kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docxodus | prose-5kw | warm_steady | < 1 frame (16.7 ms); 100% sub-frame launches; p90 < 1 frame (16.7 ms); n = 10 of 10 |
| eigenpal | prose-5kw | warm_steady | 46.2 ms; 0% sub-frame launches; p90 59.5 ms; n = 10 of 10 |
| Folio | prose-5kw | warm_steady | 48.0 ms; 0% sub-frame launches; p90 62.2 ms; n = 10 of 10 |
| GenOffice | prose-5kw | warm_steady | 21.9 ms; 0% sub-frame launches; range 19.2 to 28.7 ms; n = 9 of 10; 1 of 10 launches failed: crash: 1 |
| Plate.js | prose-5kw | warm_steady | 23.8 ms; 10% sub-frame launches; p90 30.6 ms; n = 10 of 10 |
| SuperDoc | prose-5kw | warm_steady | 175.2 ms; 0% sub-frame launches; p90 203.4 ms; n = 10 of 10 |
| WordCraft | prose-5kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |

### C07 — cursor and selection

| Editor | Workload | C07 |
|---|---|---|
| canvas-editor + plugin | complex-corpus | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) |
| Docen | complex-corpus | 27.9 ms; 0% sub-frame launches; p90 28.6 ms; n = 10 of 10 |
| Docxodus | complex-corpus | < 1 frame (16.7 ms); 100% sub-frame launches; p90 < 1 frame (16.7 ms); n = 10 of 10 |
| eigenpal | complex-corpus | 21.6 ms; 0% sub-frame launches; p90 23.3 ms; n = 10 of 10 |
| Folio | complex-corpus | 76.2 ms; 0% sub-frame launches; p90 79.4 ms; n = 10 of 10 |
| GenOffice | complex-corpus | < 1 frame (16.7 ms); 70% sub-frame launches; p90 19.4 ms; n = 10 of 10 |
| Plate.js | complex-corpus | 30.1 ms; 0% sub-frame launches; p90 42.7 ms; n = 10 of 10 |
| SuperDoc | complex-corpus | 60.9 ms; 0% sub-frame launches; p90 62.0 ms; n = 10 of 10 |
| WordCraft | complex-corpus | 102.8 ms; 0% sub-frame launches; p90 112.3 ms; n = 10 of 10 |
| canvas-editor + plugin | prose-250kw | 384.4 ms; 0% sub-frame launches; p90 397.1 ms; n = 10 of 10 |
| Docen | prose-250kw | 1708.7 ms; 0% sub-frame launches; p90 1789.4 ms; n = 10 of 10 |
| Docxodus | prose-250kw | 40.9 ms; 0% sub-frame launches; p90 44.1 ms; n = 10 of 10 |
| eigenpal | prose-250kw | 19.1 ms; 0% sub-frame launches; p90 21.0 ms; n = 10 of 10 |
| Folio | prose-250kw | 1793.2 ms; 0% sub-frame launches; p90 1845.2 ms; n = 10 of 10 |
| GenOffice | prose-250kw | 36.4 ms; 0% sub-frame launches; p90 39.4 ms; n = 10 of 10 |
| Plate.js | prose-250kw | 355.5 ms; 0% sub-frame launches; range 331.4 to 425.2 ms; n = 9 of 10; 1 of 10 launches failed: quarantined: 1; also cpu_throttled: 1 |
| SuperDoc | prose-250kw | 326.9 ms; 0% sub-frame launches; p90 329.3 ms; n = 10 of 10 |
| WordCraft | prose-250kw | 179.1 ms; 0% sub-frame launches; p90 189.1 ms; n = 10 of 10 |
| canvas-editor + plugin | prose-500w | < 1 frame (16.7 ms); 100% sub-frame launches; p90 < 1 frame (16.7 ms); n = 10 of 10 |
| Docen | prose-500w | 27.6 ms; 0% sub-frame launches; p90 29.2 ms; n = 10 of 10 |
| Docxodus | prose-500w | < 1 frame (16.7 ms); 100% sub-frame launches; p90 < 1 frame (16.7 ms); n = 10 of 10 |
| eigenpal | prose-500w | 28.7 ms; 0% sub-frame launches; p90 30.3 ms; n = 10 of 10 |
| Folio | prose-500w | 63.6 ms; 0% sub-frame launches; p90 66.7 ms; n = 10 of 10 |
| GenOffice | prose-500w | < 1 frame (16.7 ms); 80% sub-frame launches; p90 20.9 ms; n = 10 of 10 |
| Plate.js | prose-500w | 28.7 ms; 0% sub-frame launches; p90 30.9 ms; n = 10 of 10 |
| SuperDoc | prose-500w | 59.0 ms; 0% sub-frame launches; p90 62.3 ms; n = 10 of 10 |
| WordCraft | prose-500w | 186.3 ms; 0% sub-frame launches; p90 196.8 ms; n = 10 of 10 |
| canvas-editor + plugin | prose-50kw | 62.5 ms; 0% sub-frame launches; p90 79.2 ms; n = 10 of 10 |
| Docen | prose-50kw | 100.7 ms; 0% sub-frame launches; p90 110.9 ms; n = 10 of 10 |
| Docxodus | prose-50kw | < 1 frame (16.7 ms); 60% sub-frame launches; p90 27.2 ms; n = 10 of 10 |
| eigenpal | prose-50kw | 24.7 ms; 10% sub-frame launches; p90 27.6 ms; n = 10 of 10 |
| Folio | prose-50kw | 419.9 ms; 0% sub-frame launches; p90 445.3 ms; n = 10 of 10 |
| GenOffice | prose-50kw | 20.1 ms; 30% sub-frame launches; p90 23.1 ms; n = 10 of 10 |
| Plate.js | prose-50kw | 95.1 ms; 0% sub-frame launches; p90 112.6 ms; n = 10 of 10 |
| SuperDoc | prose-50kw | 250.4 ms; 0% sub-frame launches; p90 278.7 ms; n = 10 of 10 |
| WordCraft | prose-50kw | 178.4 ms; 0% sub-frame launches; p90 216.4 ms; n = 10 of 10 |
| canvas-editor + plugin | prose-5kw | 27.0 ms; 10% sub-frame launches; p90 29.6 ms; n = 10 of 10 |
| Docen | prose-5kw | 28.9 ms; 0% sub-frame launches; p90 29.7 ms; n = 10 of 10 |
| Docxodus | prose-5kw | < 1 frame (16.7 ms); 100% sub-frame launches; p90 < 1 frame (16.7 ms); n = 10 of 10 |
| eigenpal | prose-5kw | 26.8 ms; 0% sub-frame launches; p90 29.8 ms; n = 10 of 10 |
| Folio | prose-5kw | 78.6 ms; 0% sub-frame launches; p90 79.1 ms; n = 10 of 10 |
| GenOffice | prose-5kw | < 1 frame (16.7 ms); 80% sub-frame launches; p90 20.5 ms; n = 10 of 10 |
| Plate.js | prose-5kw | 30.1 ms; 0% sub-frame launches; p90 31.8 ms; n = 10 of 10 |
| SuperDoc | prose-5kw | 77.9 ms; 0% sub-frame launches; p90 81.2 ms; n = 10 of 10 |
| WordCraft | prose-5kw | 182.2 ms; 0% sub-frame launches; p90 204.7 ms; n = 10 of 10 |

### C08 — clipboard and bulk editing

| Editor | Workload | C08 |
|---|---|---|
| canvas-editor + plugin | complex-corpus | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) |
| Docen | complex-corpus | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) |
| Docxodus | complex-corpus | 17.4 ms; 40% sub-frame launches; p90 18.9 ms; n = 10 of 10 |
| eigenpal | complex-corpus | 34.4 ms; 20% sub-frame launches; p90 69.4 ms; n = 10 of 10 |
| Folio | complex-corpus | 60.7 ms; 0% sub-frame launches; p90 64.6 ms; n = 10 of 10 |
| GenOffice | complex-corpus | 27.1 ms; 0% sub-frame launches; p90 31.1 ms; n = 10 of 10 |
| Plate.js | complex-corpus | 29.8 ms; 0% sub-frame launches; p90 35.9 ms; n = 10 of 10 |
| SuperDoc | complex-corpus | 185.6 ms; 0% sub-frame launches; p90 191.6 ms; n = 10 of 10 |
| WordCraft | complex-corpus | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| canvas-editor + plugin | prose-250kw | first: not enough samples (n = 0 of 10; reasons paint_witness_unavailable: 10); second: not enough samples (n = 0 of 10; reasons paint_witness_unavailable: 10) |
| Docen | prose-250kw | 8645.2 ms; 0% sub-frame launches; p90 9359.4 ms; n = 10 of 10 |
| Docxodus | prose-250kw | 19.9 ms; 40% sub-frame launches; p90 23.6 ms; n = 10 of 10 |
| eigenpal | prose-250kw | 103.7 ms; 20% sub-frame launches; p90 112.6 ms; n = 10 of 10 |
| Folio | prose-250kw | 25.9 ms; 0% sub-frame launches; p90 30.6 ms; n = 10 of 10 |
| GenOffice | prose-250kw | 2543.5 ms; 0% sub-frame launches; p90 2602.5 ms; n = 10 of 10 |
| Plate.js | prose-250kw | 446.0 ms; 0% sub-frame launches; range 378.2 to 488.1 ms; n = 9 of 10; 1 of 10 launches failed: quarantined: 1; also cpu_throttled: 1 |
| SuperDoc | prose-250kw | 420.8 ms; 0% sub-frame launches; p90 425.1 ms; n = 10 of 10 |
| WordCraft | prose-250kw | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| canvas-editor + plugin | prose-500w | < 1 frame (16.7 ms); 60% sub-frame launches; p90 19.4 ms; n = 10 of 10 |
| Docen | prose-500w | 33.9 ms; 0% sub-frame launches; p90 45.8 ms; n = 10 of 10 |
| Docxodus | prose-500w | < 1 frame (16.7 ms); 70% sub-frame launches; p90 21.4 ms; n = 10 of 10 |
| eigenpal | prose-500w | 54.2 ms; 0% sub-frame launches; p90 61.4 ms; n = 10 of 10 |
| Folio | prose-500w | 52.2 ms; 0% sub-frame launches; p90 62.6 ms; n = 10 of 10 |
| GenOffice | prose-500w | 20.2 ms; 10% sub-frame launches; p90 24.4 ms; n = 10 of 10 |
| Plate.js | prose-500w | 45.9 ms; 0% sub-frame launches; p90 50.3 ms; n = 10 of 10 |
| SuperDoc | prose-500w | 47.7 ms; 0% sub-frame launches; p90 101.7 ms; n = 10 of 10 |
| WordCraft | prose-500w | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| canvas-editor + plugin | prose-50kw | 227.1 ms; 0% sub-frame launches; p90 249.4 ms; n = 10 of 10 |
| Docen | prose-50kw | 571.2 ms; 0% sub-frame launches; p90 598.7 ms; n = 10 of 10 |
| Docxodus | prose-50kw | 19.5 ms; 30% sub-frame launches; p90 22.8 ms; n = 10 of 10 |
| eigenpal | prose-50kw | 80.2 ms; 0% sub-frame launches; p90 107.5 ms; n = 10 of 10 |
| Folio | prose-50kw | 102.0 ms; 0% sub-frame launches; p90 124.4 ms; n = 10 of 10 |
| GenOffice | prose-50kw | 178.1 ms; 0% sub-frame launches; p90 209.4 ms; n = 10 of 10 |
| Plate.js | prose-50kw | not reproduced (first 155.7 ms; second 116.3 ms) |
| SuperDoc | prose-50kw | not reproduced (first 126.2 ms; second 144.9 ms) |
| WordCraft | prose-50kw | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| canvas-editor + plugin | prose-5kw | not reproduced (first < 1 frame (16.7 ms); second 317.4 ms) |
| Docen | prose-5kw | 64.6 ms; 0% sub-frame launches; p90 81.6 ms; n = 10 of 10 |
| Docxodus | prose-5kw | 17.9 ms; 50% sub-frame launches; p90 21.8 ms; n = 10 of 10 |
| eigenpal | prose-5kw | 59.3 ms; 0% sub-frame launches; p90 68.4 ms; n = 10 of 10 |
| Folio | prose-5kw | 102.5 ms; 0% sub-frame launches; p90 111.8 ms; n = 10 of 10 |
| GenOffice | prose-5kw | 25.9 ms; 0% sub-frame launches; p90 39.3 ms; n = 10 of 10 |
| Plate.js | prose-5kw | 47.7 ms; 0% sub-frame launches; p90 69.3 ms; n = 10 of 10 |
| SuperDoc | prose-5kw | 167.4 ms; 0% sub-frame launches; p90 181.1 ms; n = 10 of 10 |
| WordCraft | prose-5kw | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |

### C09 — undo and redo

| Editor | Workload | C09 |
|---|---|---|
| canvas-editor + plugin | complex-corpus | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) |
| Docen | complex-corpus | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) |
| Docxodus | complex-corpus | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) |
| eigenpal | complex-corpus | 32.6 ms; 0% sub-frame launches; p90 38.6 ms; n = 10 of 10 |
| Folio | complex-corpus | 76.5 ms; 0% sub-frame launches; p90 82.9 ms; n = 10 of 10 |
| GenOffice | complex-corpus | 19.5 ms; 40% sub-frame launches; p90 27.3 ms; n = 10 of 10 |
| Plate.js | complex-corpus | 34.6 ms; 0% sub-frame launches; p90 42.9 ms; n = 10 of 10 |
| SuperDoc | complex-corpus | 177.6 ms; 0% sub-frame launches; p90 191.0 ms; n = 10 of 10 |
| WordCraft | complex-corpus | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| canvas-editor + plugin | prose-250kw | first: not enough samples (n = 0 of 10; reasons paint_witness_unavailable: 10); second: not enough samples (n = 0 of 10; reasons paint_witness_unavailable: 10) |
| Docen | prose-250kw | 8278.0 ms; 0% sub-frame launches; p90 8477.1 ms; n = 10 of 10 |
| Docxodus | prose-250kw | 15724.3 ms; 0% sub-frame launches; p90 16012.2 ms; n = 10 of 10 |
| eigenpal | prose-250kw | 42.3 ms; 0% sub-frame launches; p90 46.7 ms; n = 10 of 10 |
| Folio | prose-250kw | not reproduced (first 183.9 ms; second 135.8 ms) |
| GenOffice | prose-250kw | not reproduced (first 2323.5 ms; second 2590.9 ms) |
| Plate.js | prose-250kw | 139.7 ms; 0% sub-frame launches; range 133.5 to 154.0 ms; n = 9 of 10; 1 of 10 launches failed: quarantined: 1; also cpu_throttled: 1 |
| SuperDoc | prose-250kw | 254.5 ms; 0% sub-frame launches; p90 260.7 ms; n = 10 of 10 |
| WordCraft | prose-250kw | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| canvas-editor + plugin | prose-500w | 55.6 ms; 0% sub-frame launches; p90 72.7 ms; n = 10 of 10 |
| Docen | prose-500w | 27.4 ms; 0% sub-frame launches; p90 30.1 ms; n = 10 of 10 |
| Docxodus | prose-500w | 64.0 ms; 0% sub-frame launches; p90 68.5 ms; n = 10 of 10 |
| eigenpal | prose-500w | 24.6 ms; 0% sub-frame launches; p90 31.2 ms; n = 10 of 10 |
| Folio | prose-500w | 49.9 ms; 0% sub-frame launches; p90 61.2 ms; n = 10 of 10 |
| GenOffice | prose-500w | 17.8 ms; 50% sub-frame launches; p90 21.8 ms; n = 10 of 10 |
| Plate.js | prose-500w | 25.2 ms; 10% sub-frame launches; p90 27.4 ms; n = 10 of 10 |
| SuperDoc | prose-500w | 69.3 ms; 0% sub-frame launches; p90 72.2 ms; n = 10 of 10 |
| WordCraft | prose-500w | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| canvas-editor + plugin | prose-50kw | not reproduced (first 121.7 ms; second 145.1 ms) |
| Docen | prose-50kw | 490.8 ms; 0% sub-frame launches; p90 520.0 ms; n = 10 of 10 |
| Docxodus | prose-50kw | 3323.7 ms; 0% sub-frame launches; p90 3608.1 ms; n = 10 of 10 |
| eigenpal | prose-50kw | 33.2 ms; 0% sub-frame launches; p90 43.1 ms; n = 10 of 10 |
| Folio | prose-50kw | 144.6 ms; 0% sub-frame launches; p90 175.8 ms; n = 10 of 10 |
| GenOffice | prose-50kw | 174.1 ms; 0% sub-frame launches; p90 184.4 ms; n = 10 of 10 |
| Plate.js | prose-50kw | 51.0 ms; 0% sub-frame launches; p90 68.1 ms; n = 10 of 10 |
| SuperDoc | prose-50kw | 255.6 ms; 10% sub-frame launches; p90 316.5 ms; n = 10 of 10 |
| WordCraft | prose-50kw | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| canvas-editor + plugin | prose-5kw | < 1 frame (16.7 ms); 60% sub-frame launches; p90 31.2 ms; n = 10 of 10 |
| Docen | prose-5kw | 58.1 ms; 0% sub-frame launches; range 44.8 to 67.2 ms; n = 8 of 10; 2 of 10 launches failed: unverified: 2; second: 1 of 10 launches failed: unverified: 1 |
| Docxodus | prose-5kw | 340.9 ms; 0% sub-frame launches; p90 356.9 ms; n = 10 of 10 |
| eigenpal | prose-5kw | 26.6 ms; 0% sub-frame launches; p90 31.4 ms; n = 10 of 10 |
| Folio | prose-5kw | 46.3 ms; 0% sub-frame launches; p90 62.8 ms; n = 10 of 10 |
| GenOffice | prose-5kw | 19.7 ms; 40% sub-frame launches; p90 25.9 ms; n = 10 of 10 |
| Plate.js | prose-5kw | 23.0 ms; 0% sub-frame launches; p90 31.7 ms; n = 10 of 10 |
| SuperDoc | prose-5kw | 136.3 ms; 0% sub-frame launches; p90 163.4 ms; n = 10 of 10 |
| WordCraft | prose-5kw | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |

### C10 — scrolling

| Editor | Workload | C10 |
|---|---|---|
| canvas-editor + plugin | complex-corpus | first: not enough samples (n = 0 of 10; reasons paint_witness_unavailable: 10); second: not enough samples (n = 0 of 10; reasons paint_witness_unavailable: 10) |
| Docen | complex-corpus | < 1 frame (16.7 ms); 50% sub-frame launches; p90 23.2 ms; n = 10 of 10 |
| Docxodus | complex-corpus | < 1 frame (16.7 ms); 100% sub-frame launches; p90 < 1 frame (16.7 ms); n = 10 of 10 |
| eigenpal | complex-corpus | first: not enough samples (n = 0 of 10; reasons paint_witness_unavailable: 10); second: not enough samples (n = 0 of 10; reasons paint_witness_unavailable: 10) |
| Folio | complex-corpus | < 1 frame (16.7 ms); 60% sub-frame launches; p90 19.9 ms; n = 10 of 10 |
| GenOffice | complex-corpus | first: not enough samples (n = 0 of 10; reasons paint_witness_unavailable: 10); second: not enough samples (n = 0 of 10; reasons paint_witness_unavailable: 10) |
| Plate.js | complex-corpus | < 1 frame (16.7 ms); 90% sub-frame launches; p90 < 1 frame (16.7 ms); n = 10 of 10 |
| SuperDoc | complex-corpus | 16.9 ms; 50% sub-frame launches; p90 24.7 ms; n = 10 of 10 |
| WordCraft | complex-corpus | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| canvas-editor + plugin | prose-250kw | < 1 frame (16.7 ms); 60% sub-frame launches; p90 22.5 ms; n = 10 of 10 |
| Docen | prose-250kw | 24.0 ms; 0% sub-frame launches; p90 28.5 ms; n = 10 of 10 |
| Docxodus | prose-250kw | 62.4 ms; 0% sub-frame launches; p90 72.0 ms; n = 10 of 10 |
| eigenpal | prose-250kw | 28.7 ms; 0% sub-frame launches; p90 34.5 ms; n = 10 of 10 |
| Folio | prose-250kw | < 1 frame (16.7 ms); 90% sub-frame launches; p90 < 1 frame (16.7 ms); n = 10 of 10 |
| GenOffice | prose-250kw | 63.0 ms; 0% sub-frame launches; p90 67.3 ms; n = 10 of 10 |
| Plate.js | prose-250kw | 60.7 ms; 0% sub-frame launches; p90 66.7 ms; n = 10 of 10 |
| SuperDoc | prose-250kw | 51.6 ms; 0% sub-frame launches; p90 58.7 ms; n = 10 of 10 |
| WordCraft | prose-250kw | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| canvas-editor + plugin | prose-500w | < 1 frame (16.7 ms); 50% sub-frame launches; p90 18.5 ms; n = 10 of 10 |
| Docen | prose-500w | < 1 frame (16.7 ms); 70% sub-frame launches; p90 19.4 ms; n = 10 of 10 |
| Docxodus | prose-500w | < 1 frame (16.7 ms); 90% sub-frame launches; p90 < 1 frame (16.7 ms); n = 10 of 10 |
| eigenpal | prose-500w | < 1 frame (16.7 ms); 80% sub-frame launches; p90 17.1 ms; n = 10 of 10 |
| Folio | prose-500w | < 1 frame (16.7 ms); 70% sub-frame launches; p90 20.2 ms; n = 10 of 10 |
| GenOffice | prose-500w | < 1 frame (16.7 ms); 100% sub-frame launches; p90 < 1 frame (16.7 ms); n = 10 of 10 |
| Plate.js | prose-500w | < 1 frame (16.7 ms); 90% sub-frame launches; p90 < 1 frame (16.7 ms); n = 10 of 10 |
| SuperDoc | prose-500w | < 1 frame (16.7 ms); 60% sub-frame launches; p90 26.5 ms; n = 10 of 10 |
| WordCraft | prose-500w | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| canvas-editor + plugin | prose-50kw | < 1 frame (16.7 ms); 70% sub-frame launches; p90 22.3 ms; n = 10 of 10 |
| Docen | prose-50kw | < 1 frame (16.7 ms); 80% sub-frame launches; p90 17.3 ms; n = 10 of 10 |
| Docxodus | prose-50kw | < 1 frame (16.7 ms); 70% sub-frame launches; p90 20.7 ms; n = 10 of 10 |
| eigenpal | prose-50kw | 32.0 ms; 0% sub-frame launches; p90 34.1 ms; n = 10 of 10 |
| Folio | prose-50kw | < 1 frame (16.7 ms); 50% sub-frame launches; p90 20.4 ms; n = 10 of 10 |
| GenOffice | prose-50kw | 21.1 ms; 20% sub-frame launches; p90 27.4 ms; n = 10 of 10 |
| Plate.js | prose-50kw | 19.0 ms; 20% sub-frame launches; p90 28.3 ms; n = 10 of 10 |
| SuperDoc | prose-50kw | 25.4 ms; 10% sub-frame launches; p90 29.4 ms; n = 10 of 10 |
| WordCraft | prose-50kw | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| canvas-editor + plugin | prose-5kw | < 1 frame (16.7 ms); 60% sub-frame launches; p90 19.9 ms; n = 10 of 10 |
| Docen | prose-5kw | < 1 frame (16.7 ms); 60% sub-frame launches; p90 30.7 ms; n = 10 of 10 |
| Docxodus | prose-5kw | < 1 frame (16.7 ms); 70% sub-frame launches; p90 17.3 ms; n = 10 of 10 |
| eigenpal | prose-5kw | 26.0 ms; 0% sub-frame launches; p90 35.1 ms; n = 10 of 10 |
| Folio | prose-5kw | < 1 frame (16.7 ms); 80% sub-frame launches; p90 18.1 ms; n = 10 of 10 |
| GenOffice | prose-5kw | 16.7 ms; 50% sub-frame launches; p90 20.2 ms; n = 10 of 10 |
| Plate.js | prose-5kw | < 1 frame (16.7 ms); 70% sub-frame launches; p90 17.7 ms; n = 10 of 10 |
| SuperDoc | prose-5kw | 21.7 ms; 0% sub-frame launches; p90 26.6 ms; n = 10 of 10 |
| WordCraft | prose-5kw | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |

### C11 — initial layout

| Editor | Workload | C11 |
|---|---|---|
| canvas-editor + plugin | complex-corpus | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) |
| Docen | complex-corpus | first: not enough samples (n = 0 of 10; reasons paint_witness_unavailable: 10); second: not enough samples (n = 0 of 10; reasons paint_witness_unavailable: 10) |
| Docxodus | complex-corpus | 3519.0 ms; 0% sub-frame launches; p90 3589.0 ms; n = 10 of 10 |
| eigenpal | complex-corpus | 735.2 ms; 0% sub-frame launches; p90 789.8 ms; n = 10 of 10 |
| Folio | complex-corpus | 910.3 ms; 0% sub-frame launches; p90 998.7 ms; n = 10 of 10 |
| GenOffice | complex-corpus | 1034.8 ms; 0% sub-frame launches; p90 1145.2 ms; n = 10 of 10 |
| Plate.js | complex-corpus | 885.5 ms; 0% sub-frame launches; p90 951.7 ms; n = 10 of 10 |
| SuperDoc | complex-corpus | 2777.3 ms; 0% sub-frame launches; p90 2906.0 ms; n = 10 of 10 |
| WordCraft | complex-corpus | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) |
| canvas-editor + plugin | prose-250kw | 135.5 ms; 0% sub-frame launches; p90 154.1 ms; n = 10 of 10 |
| Docen | prose-250kw | first: not enough samples (n = 0 of 10; reasons paint_witness_unavailable: 10); second: not enough samples (n = 0 of 10; reasons paint_witness_unavailable: 10) |
| Docxodus | prose-250kw | 203435.2 ms; 0% sub-frame launches; p90 219860.2 ms; n = 10 of 10 |
| eigenpal | prose-250kw | 2387.9 ms; 0% sub-frame launches; p90 2455.4 ms; n = 10 of 10 |
| Folio | prose-250kw | 4685.2 ms; 0% sub-frame launches; p90 5083.5 ms; n = 10 of 10 |
| GenOffice | prose-250kw | 2085.1 ms; 0% sub-frame launches; p90 7786.6 ms; n = 10 of 10 |
| Plate.js | prose-250kw | first: not enough samples (n = 0 of 10; reasons editor_crash: 2; harness_error: 8); second: not enough samples (n = 0 of 10; reasons editor_crash: 6; harness_error: 4) |
| SuperDoc | prose-250kw | 16218.4 ms; 0% sub-frame launches; p90 16738.6 ms; n = 10 of 10 |
| WordCraft | prose-250kw | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) |
| canvas-editor + plugin | prose-500w | 151.7 ms; 0% sub-frame launches; p90 192.7 ms; n = 10 of 10 |
| Docen | prose-500w | first: not enough samples (n = 3 of 10; reasons paint_witness_unavailable: 7); second: not enough samples (n = 1 of 10; reasons paint_witness_unavailable: 9) |
| Docxodus | prose-500w | 2747.8 ms; 0% sub-frame launches; p90 2973.9 ms; n = 10 of 10 |
| eigenpal | prose-500w | 659.6 ms; 0% sub-frame launches; p90 735.4 ms; n = 10 of 10 |
| Folio | prose-500w | not reproduced (first 939.8 ms; second 842.8 ms) |
| GenOffice | prose-500w | 806.2 ms; 0% sub-frame launches; p90 845.6 ms; n = 10 of 10 |
| Plate.js | prose-500w | 830.3 ms; 0% sub-frame launches; p90 864.1 ms; n = 10 of 10 |
| SuperDoc | prose-500w | 2664.4 ms; 0% sub-frame launches; p90 2926.1 ms; n = 10 of 10 |
| WordCraft | prose-500w | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) |
| canvas-editor + plugin | prose-50kw | 136.0 ms; 0% sub-frame launches; p90 155.5 ms; n = 10 of 10 |
| Docen | prose-50kw | first: not enough samples (n = 0 of 10; reasons paint_witness_unavailable: 10); second: not enough samples (n = 0 of 10; reasons paint_witness_unavailable: 10) |
| Docxodus | prose-50kw | 17307.0 ms; 0% sub-frame launches; p90 18723.6 ms; n = 10 of 10 |
| eigenpal | prose-50kw | 1106.7 ms; 0% sub-frame launches; p90 1211.3 ms; n = 10 of 10 |
| Folio | prose-50kw | 1776.4 ms; 0% sub-frame launches; p90 1944.6 ms; n = 10 of 10 |
| GenOffice | prose-50kw | 1175.9 ms; 0% sub-frame launches; p90 1282.4 ms; n = 10 of 10 |
| Plate.js | prose-50kw | 17334.5 ms; 0% sub-frame launches; p90 22600.9 ms; n = 10 of 10 |
| SuperDoc | prose-50kw | 6117.4 ms; 0% sub-frame launches; p90 7116.6 ms; n = 10 of 10 |
| WordCraft | prose-50kw | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) |
| canvas-editor + plugin | prose-5kw | 141.2 ms; 0% sub-frame launches; p90 152.0 ms; n = 10 of 10 |
| Docen | prose-5kw | first: not enough samples (n = 0 of 10; reasons paint_witness_unavailable: 10); second: not enough samples (n = 0 of 10; reasons paint_witness_unavailable: 10) |
| Docxodus | prose-5kw | 3885.0 ms; 0% sub-frame launches; p90 4597.9 ms; n = 10 of 10 |
| eigenpal | prose-5kw | 718.8 ms; 0% sub-frame launches; p90 844.8 ms; n = 10 of 10 |
| Folio | prose-5kw | first seed unpublishable: block 2 has no launch files (blocked) |
| GenOffice | prose-5kw | 960.3 ms; 0% sub-frame launches; p90 1069.7 ms; n = 10 of 10 |
| Plate.js | prose-5kw | 1364.2 ms; 0% sub-frame launches; p90 1603.2 ms; n = 10 of 10 |
| SuperDoc | prose-5kw | 3018.4 ms; 0% sub-frame launches; p90 3249.3 ms; n = 10 of 10 |
| WordCraft | prose-5kw | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) |

### C12 — incremental reflow

| Editor | Workload | C12 |
|---|---|---|
| canvas-editor + plugin | complex-corpus | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) |
| Docen | complex-corpus | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docxodus | complex-corpus | 48.7 ms; 0% sub-frame launches; p90 49.0 ms; n = 10 of 10 |
| eigenpal | complex-corpus | 65.6 ms; 0% sub-frame launches; p90 81.6 ms; n = 10 of 10 |
| Folio | complex-corpus | 65.2 ms; 0% sub-frame launches; p90 80.6 ms; n = 10 of 10 |
| GenOffice | complex-corpus | 31.7 ms; 0% sub-frame launches; p90 32.3 ms; n = 10 of 10 |
| Plate.js | complex-corpus | 65.3 ms; 0% sub-frame launches; p90 65.6 ms; n = 10 of 10 |
| SuperDoc | complex-corpus | 365.0 ms; 0% sub-frame launches; p90 398.4 ms; n = 10 of 10 |
| WordCraft | complex-corpus | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| canvas-editor + plugin | prose-250kw | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docen | prose-250kw | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docxodus | prose-250kw | 132.1 ms; 0% sub-frame launches; p90 149.9 ms; n = 10 of 10 |
| eigenpal | prose-250kw | 114.9 ms; 0% sub-frame launches; p90 115.3 ms; n = 10 of 10 |
| Folio | prose-250kw | 2415.0 ms; 0% sub-frame launches; p90 2544.6 ms; n = 10 of 10 |
| GenOffice | prose-250kw | 2632.2 ms; 0% sub-frame launches; range 2515.2 to 147976.0 ms; n = 9 of 10; 1 of 10 launches failed: recorded_move_before_input: 1 |
| Plate.js | prose-250kw | first: not enough samples (n = 0 of 10; reasons editor_crash: 2; harness_error: 8); second: not enough samples (n = 0 of 10; reasons editor_crash: 1; harness_error: 9) |
| SuperDoc | prose-250kw | 1431.8 ms; 0% sub-frame launches; p90 1481.2 ms; n = 10 of 10 |
| WordCraft | prose-250kw | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| canvas-editor + plugin | prose-500w | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docen | prose-500w | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docxodus | prose-500w | 48.6 ms; 0% sub-frame launches; p90 64.3 ms; n = 10 of 10 |
| eigenpal | prose-500w | 56.2 ms; 0% sub-frame launches; p90 66.2 ms; n = 10 of 10 |
| Folio | prose-500w | 64.7 ms; 0% sub-frame launches; p90 67.1 ms; n = 10 of 10 |
| GenOffice | prose-500w | 31.2 ms; 0% sub-frame launches; p90 31.8 ms; n = 10 of 10 |
| Plate.js | prose-500w | 64.8 ms; 0% sub-frame launches; p90 83.2 ms; n = 10 of 10 |
| SuperDoc | prose-500w | not reproduced (first 206.4 ms; second 181.9 ms) |
| WordCraft | prose-500w | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| canvas-editor + plugin | prose-50kw | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docen | prose-50kw | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docxodus | prose-50kw | 65.0 ms; 0% sub-frame launches; p90 68.6 ms; n = 10 of 10 |
| eigenpal | prose-50kw | 81.8 ms; 0% sub-frame launches; p90 84.0 ms; n = 10 of 10 |
| Folio | prose-50kw | 532.3 ms; 0% sub-frame launches; p90 619.8 ms; n = 10 of 10 |
| GenOffice | prose-50kw | 190.4 ms; 0% sub-frame launches; p90 237.6 ms; n = 10 of 10 |
| Plate.js | prose-50kw | 482.0 ms; 0% sub-frame launches; p90 570.1 ms; n = 10 of 10 |
| SuperDoc | prose-50kw | 898.2 ms; 0% sub-frame launches; p90 951.7 ms; n = 10 of 10 |
| WordCraft | prose-50kw | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| canvas-editor + plugin | prose-5kw | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docen | prose-5kw | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docxodus | prose-5kw | 47.5 ms; 0% sub-frame launches; p90 50.4 ms; n = 10 of 10 |
| eigenpal | prose-5kw | 81.6 ms; 0% sub-frame launches; p90 98.2 ms; n = 10 of 10 |
| Folio | prose-5kw | first seed unpublishable: block 2 has no launch files (blocked) |
| GenOffice | prose-5kw | 31.8 ms; 0% sub-frame launches; p90 33.9 ms; n = 10 of 10 |
| Plate.js | prose-5kw | 115.3 ms; 0% sub-frame launches; p90 147.4 ms; n = 10 of 10 |
| SuperDoc | prose-5kw | 431.2 ms; 0% sub-frame launches; p90 474.9 ms; n = 10 of 10 |
| WordCraft | prose-5kw | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |

### C13 — global invalidation

not in these runs.

### C14 — large-document scaling

Each C14 size rung is a separate measure, and within a rung each clock is its own measure: `presented_frame` (document damage followed load; the sample ends at the first compositor screencast frame at or after the document became usable) and `usable_no_damage` (no damage followed; the sample ends at the DOM document-surface mark and is never labelled a compositor frame). Rungs and measures are never pooled.

| Editor | Workload | Measure | C14 |
|---|---|---|---|
| canvas-editor + plugin | complex-corpus | presented_frame | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) |
| Docen | complex-corpus | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| Docxodus | complex-corpus | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| eigenpal | complex-corpus | presented_frame | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) |
| Folio | complex-corpus | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| GenOffice | complex-corpus | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| Plate.js | complex-corpus | presented_frame | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) |
| SuperDoc | complex-corpus | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| WordCraft | complex-corpus | presented_frame | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) |
| canvas-editor + plugin | complex-corpus | usable_no_damage | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) |
| Docen | complex-corpus | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) |
| Docxodus | complex-corpus | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) |
| eigenpal | complex-corpus | usable_no_damage | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| Folio | complex-corpus | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) |
| GenOffice | complex-corpus | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) |
| Plate.js | complex-corpus | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) |
| SuperDoc | complex-corpus | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) |
| WordCraft | complex-corpus | usable_no_damage | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| canvas-editor + plugin | prose-250kw | presented_frame | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) |
| Docen | prose-250kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| Docxodus | prose-250kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| eigenpal | prose-250kw | presented_frame | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) |
| Folio | prose-250kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| GenOffice | prose-250kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| Plate.js | prose-250kw | presented_frame | first: not enough samples (n = 0 of 10; reasons editor_crash: 1; harness_error: 9); second: not enough samples (n = 0 of 10; reasons editor_crash: 4; harness_error: 6) |
| SuperDoc | prose-250kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| WordCraft | prose-250kw | presented_frame | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) |
| canvas-editor + plugin | prose-250kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) |
| Docen | prose-250kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) |
| Docxodus | prose-250kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) |
| eigenpal | prose-250kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| Folio | prose-250kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) |
| GenOffice | prose-250kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) |
| Plate.js | prose-250kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons editor_crash: 1; harness_error: 9); second: not enough samples (n = 0 of 10; reasons editor_crash: 4; harness_error: 6) |
| SuperDoc | prose-250kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) |
| WordCraft | prose-250kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| canvas-editor + plugin | prose-500w | presented_frame | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) |
| Docen | prose-500w | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| Docxodus | prose-500w | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| eigenpal | prose-500w | presented_frame | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) |
| Folio | prose-500w | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| GenOffice | prose-500w | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| Plate.js | prose-500w | presented_frame | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) |
| SuperDoc | prose-500w | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| WordCraft | prose-500w | presented_frame | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) |
| canvas-editor + plugin | prose-500w | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) |
| Docen | prose-500w | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) |
| Docxodus | prose-500w | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) |
| eigenpal | prose-500w | usable_no_damage | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| Folio | prose-500w | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) |
| GenOffice | prose-500w | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) |
| Plate.js | prose-500w | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) |
| SuperDoc | prose-500w | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) |
| WordCraft | prose-500w | usable_no_damage | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| canvas-editor + plugin | prose-50kw | presented_frame | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) |
| Docen | prose-50kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| Docxodus | prose-50kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| eigenpal | prose-50kw | presented_frame | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) |
| Folio | prose-50kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| GenOffice | prose-50kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| Plate.js | prose-50kw | presented_frame | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) |
| SuperDoc | prose-50kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| WordCraft | prose-50kw | presented_frame | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) |
| canvas-editor + plugin | prose-50kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) |
| Docen | prose-50kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) |
| Docxodus | prose-50kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) |
| eigenpal | prose-50kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| Folio | prose-50kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) |
| GenOffice | prose-50kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) |
| Plate.js | prose-50kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) |
| SuperDoc | prose-50kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) |
| WordCraft | prose-50kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| canvas-editor + plugin | prose-5kw | presented_frame | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) |
| Docen | prose-5kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| Docxodus | prose-5kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| eigenpal | prose-5kw | presented_frame | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) |
| Folio | prose-5kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| GenOffice | prose-5kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| Plate.js | prose-5kw | presented_frame | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) |
| SuperDoc | prose-5kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| WordCraft | prose-5kw | presented_frame | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) |
| canvas-editor + plugin | prose-5kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) |
| Docen | prose-5kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) |
| Docxodus | prose-5kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) |
| eigenpal | prose-5kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| Folio | prose-5kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) |
| GenOffice | prose-5kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) |
| Plate.js | prose-5kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) |
| SuperDoc | prose-5kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) |
| WordCraft | prose-5kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |

### C15 — search and replace

Each C15 step is a separate measure; steps are never pooled.

| Editor | Workload | Measure | C15 |
|---|---|---|---|
| canvas-editor + plugin | micro-search | first_match | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| Docen | micro-search | first_match | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| Docxodus | micro-search | first_match | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| eigenpal | micro-search | first_match | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| Folio | micro-search | first_match | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| GenOffice | micro-search | first_match | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| Plate.js | micro-search | first_match | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| SuperDoc | micro-search | first_match | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| WordCraft | micro-search | first_match | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| canvas-editor + plugin | micro-search | index_quiescence | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| Docen | micro-search | index_quiescence | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| Docxodus | micro-search | index_quiescence | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| eigenpal | micro-search | index_quiescence | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| Folio | micro-search | index_quiescence | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| GenOffice | micro-search | index_quiescence | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| Plate.js | micro-search | index_quiescence | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| SuperDoc | micro-search | index_quiescence | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| WordCraft | micro-search | index_quiescence | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| canvas-editor + plugin | micro-search | replace_all | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| Docen | micro-search | replace_all | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| Docxodus | micro-search | replace_all | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| eigenpal | micro-search | replace_all | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| Folio | micro-search | replace_all | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| GenOffice | micro-search | replace_all | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| Plate.js | micro-search | replace_all | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| SuperDoc | micro-search | replace_all | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| WordCraft | micro-search | replace_all | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| canvas-editor + plugin | micro-search | search_complete | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| Docen | micro-search | search_complete | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| Docxodus | micro-search | search_complete | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| eigenpal | micro-search | search_complete | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| Folio | micro-search | search_complete | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| GenOffice | micro-search | search_complete | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| Plate.js | micro-search | search_complete | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| SuperDoc | micro-search | search_complete | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| WordCraft | micro-search | search_complete | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |

### C17 — memory by phase

| Editor | Workload | Measure | C17 |
|---|---|---|---|
| canvas-editor + plugin | complex-corpus | after_edit_burst | first: not enough samples (n = 0 of 10; reasons editor_crash: 10); second: not enough samples (n = 0 of 10; reasons editor_crash: 10) |
| Docen | complex-corpus | after_edit_burst | 819259392.0 bytes; p90 845148979.2 bytes; n = 10 of 10 |
| Docxodus | complex-corpus | after_edit_burst | 750077952.0 bytes; p90 752466329.6 bytes; n = 10 of 10 |
| eigenpal | complex-corpus | after_edit_burst | 673687552.0 bytes; p90 681938534.4 bytes; n = 10 of 10 |
| Folio | complex-corpus | after_edit_burst | 624859136.0 bytes; p90 627243417.6 bytes; n = 10 of 10 |
| GenOffice | complex-corpus | after_edit_burst | 659646464.0 bytes; p90 664256512.0 bytes; n = 10 of 10 |
| Plate.js | complex-corpus | after_edit_burst | 659787776.0 bytes; p90 661772697.6 bytes; n = 10 of 10 |
| SuperDoc | complex-corpus | after_edit_burst | 722798592.0 bytes; p90 726952345.6 bytes; n = 10 of 10 |
| WordCraft | complex-corpus | after_edit_burst | 1192824832.0 bytes; p90 1213393305.6 bytes; n = 10 of 10 |
| canvas-editor + plugin | complex-corpus | quiescent | first: not enough samples (n = 0 of 10; reasons editor_crash: 10); second: not enough samples (n = 0 of 10; reasons editor_crash: 10) |
| Docen | complex-corpus | quiescent | 820629504.0 bytes; p90 845968179.2 bytes; n = 10 of 10 |
| Docxodus | complex-corpus | quiescent | 750219264.0 bytes; p90 752638361.6 bytes; n = 10 of 10 |
| eigenpal | complex-corpus | quiescent | 677216256.0 bytes; p90 682496819.2 bytes; n = 10 of 10 |
| Folio | complex-corpus | quiescent | 626063360.0 bytes; p90 628182630.4 bytes; n = 10 of 10 |
| GenOffice | complex-corpus | quiescent | 669829120.0 bytes; p90 674478080.0 bytes; n = 10 of 10 |
| Plate.js | complex-corpus | quiescent | 659888128.0 bytes; p90 661793177.6 bytes; n = 10 of 10 |
| SuperDoc | complex-corpus | quiescent | 729851904.0 bytes; p90 734563532.8 bytes; n = 10 of 10 |
| WordCraft | complex-corpus | quiescent | 1193031680.0 bytes; p90 1211926528.0 bytes; n = 10 of 10 |
| canvas-editor + plugin | complex-corpus | ready | first: not enough samples (n = 0 of 10; reasons editor_crash: 10); second: not enough samples (n = 0 of 10; reasons editor_crash: 10) |
| Docen | complex-corpus | ready | 736028672.0 bytes; p90 737302118.4 bytes; n = 10 of 10 |
| Docxodus | complex-corpus | ready | 729561088.0 bytes; p90 730230784.0 bytes; n = 10 of 10 |
| eigenpal | complex-corpus | ready | 656617472.0 bytes; p90 659155353.6 bytes; n = 10 of 10 |
| Folio | complex-corpus | ready | 568553472.0 bytes; p90 570650624.0 bytes; n = 10 of 10 |
| GenOffice | complex-corpus | ready | 626479104.0 bytes; p90 627746816.0 bytes; n = 10 of 10 |
| Plate.js | complex-corpus | ready | 552925184.0 bytes; p90 555472076.8 bytes; n = 10 of 10 |
| SuperDoc | complex-corpus | ready | 677033984.0 bytes; p90 684746342.4 bytes; n = 10 of 10 |
| WordCraft | complex-corpus | ready | 789477376.0 bytes; p90 800933478.4 bytes; n = 10 of 10 |
| canvas-editor + plugin | prose-250kw | after_edit_burst | first: not enough samples (n = 0 of 10; reasons editor_crash: 4; editor_timeout: 6); second: not enough samples (n = 0 of 10; reasons editor_crash: 3; editor_timeout: 7) |
| Docen | prose-250kw | after_edit_burst | first: not enough samples (n = 0 of 10; reasons editor_timeout: 10); second: not enough samples (n = 0 of 10; reasons editor_timeout: 10) |
| Docxodus | prose-250kw | after_edit_burst | 2010253312.0 bytes; p90 2028285132.8 bytes; n = 10 of 10 |
| eigenpal | prose-250kw | after_edit_burst | 1044436992.0 bytes; p90 1058777907.2 bytes; n = 10 of 10 |
| Folio | prose-250kw | after_edit_burst | 2220709888.0 bytes; p90 2227079577.6 bytes; n = 10 of 10 |
| GenOffice | prose-250kw | after_edit_burst | 2119845888.0 bytes; p90 2245514854.4 bytes; n = 10 of 10 |
| Plate.js | prose-250kw | after_edit_burst | 2153476096.0 bytes; p90 2173014016.0 bytes; n = 10 of 10 |
| SuperDoc | prose-250kw | after_edit_burst | 1425788928.0 bytes; p90 1490201395.2 bytes; n = 10 of 10 |
| WordCraft | prose-250kw | after_edit_burst | 1401225216.0 bytes; p90 1406826496.0 bytes; n = 10 of 10 |
| canvas-editor + plugin | prose-250kw | quiescent | first: not enough samples (n = 0 of 10; reasons editor_crash: 4; editor_timeout: 6); second: not enough samples (n = 0 of 10; reasons editor_crash: 3; editor_timeout: 7) |
| Docen | prose-250kw | quiescent | first: not enough samples (n = 0 of 10; reasons editor_timeout: 10); second: not enough samples (n = 0 of 10; reasons editor_timeout: 10) |
| Docxodus | prose-250kw | quiescent | 2007523328.0 bytes; p90 2013662003.2 bytes; n = 10 of 10 |
| eigenpal | prose-250kw | quiescent | 1044606976.0 bytes; p90 1058929049.6 bytes; n = 10 of 10 |
| Folio | prose-250kw | quiescent | 2032279552.0 bytes; p90 2043575500.8 bytes; n = 10 of 10 |
| GenOffice | prose-250kw | quiescent | 2319116288.0 bytes; p90 2413978419.2 bytes; n = 10 of 10 |
| Plate.js | prose-250kw | quiescent | 2153494528.0 bytes; p90 2173037772.8 bytes; n = 10 of 10 |
| SuperDoc | prose-250kw | quiescent | 1426434048.0 bytes; p90 1490870681.6 bytes; n = 10 of 10 |
| WordCraft | prose-250kw | quiescent | 1401448448.0 bytes; p90 1407116492.8 bytes; n = 10 of 10 |
| canvas-editor + plugin | prose-250kw | ready | first: not enough samples (n = 0 of 10; reasons editor_crash: 4; editor_timeout: 6); second: not enough samples (n = 0 of 10; reasons editor_crash: 3; editor_timeout: 7) |
| Docen | prose-250kw | ready | first: not enough samples (n = 0 of 10; reasons editor_timeout: 10); second: not enough samples (n = 0 of 10; reasons editor_timeout: 10) |
| Docxodus | prose-250kw | ready | 2060060672.0 bytes; p90 2083982131.2 bytes; n = 10 of 10 |
| eigenpal | prose-250kw | ready | 934078464.0 bytes; p90 935773388.8 bytes; n = 10 of 10 |
| Folio | prose-250kw | ready | 779079680.0 bytes; p90 780568985.6 bytes; n = 10 of 10 |
| GenOffice | prose-250kw | ready | not reproduced (first 1304973312.0 bytes; second 1168482304.0 bytes) |
| Plate.js | prose-250kw | ready | 1999652864.0 bytes; p90 2054521241.6 bytes; n = 10 of 10 |
| SuperDoc | prose-250kw | ready | 666779648.0 bytes; p90 669729996.8 bytes; n = 10 of 10 |
| WordCraft | prose-250kw | ready | 874870784.0 bytes; p90 879153971.2 bytes; n = 10 of 10 |
| canvas-editor + plugin | prose-500w | after_edit_burst | 900198400.0 bytes; p90 952194662.4 bytes; n = 10 of 10 |
| Docen | prose-500w | after_edit_burst | 732450816.0 bytes; p90 741679104.0 bytes; n = 10 of 10 |
| Docxodus | prose-500w | after_edit_burst | 729010176.0 bytes; p90 732758425.6 bytes; n = 10 of 10 |
| eigenpal | prose-500w | after_edit_burst | 695248896.0 bytes; p90 707946905.6 bytes; n = 10 of 10 |
| Folio | prose-500w | after_edit_burst | 590708736.0 bytes; p90 595458048.0 bytes; n = 10 of 10 |
| GenOffice | prose-500w | after_edit_burst | 612063232.0 bytes; p90 615047577.6 bytes; n = 10 of 10 |
| Plate.js | prose-500w | after_edit_burst | 650409984.0 bytes; p90 668106752.0 bytes; n = 10 of 10 |
| SuperDoc | prose-500w | after_edit_burst | 687841280.0 bytes; p90 691631718.4 bytes; n = 10 of 10 |
| WordCraft | prose-500w | after_edit_burst | 1198585856.0 bytes; p90 1213925785.6 bytes; n = 10 of 10 |
| canvas-editor + plugin | prose-500w | quiescent | 900110336.0 bytes; p90 952791040.0 bytes; n = 10 of 10 |
| Docen | prose-500w | quiescent | 733308928.0 bytes; p90 742544588.8 bytes; n = 10 of 10 |
| Docxodus | prose-500w | quiescent | 729094144.0 bytes; p90 732942745.6 bytes; n = 10 of 10 |
| eigenpal | prose-500w | quiescent | 692586496.0 bytes; p90 707539353.6 bytes; n = 10 of 10 |
| Folio | prose-500w | quiescent | 591790080.0 bytes; p90 596509081.6 bytes; n = 10 of 10 |
| GenOffice | prose-500w | quiescent | 613257216.0 bytes; p90 615694745.6 bytes; n = 10 of 10 |
| Plate.js | prose-500w | quiescent | 650467328.0 bytes; p90 668127232.0 bytes; n = 10 of 10 |
| SuperDoc | prose-500w | quiescent | 691877888.0 bytes; p90 693102592.0 bytes; n = 10 of 10 |
| WordCraft | prose-500w | quiescent | 1198184448.0 bytes; p90 1213909811.2 bytes; n = 10 of 10 |
| canvas-editor + plugin | prose-500w | ready | 555937792.0 bytes; p90 560771891.2 bytes; n = 10 of 10 |
| Docen | prose-500w | ready | 687667200.0 bytes; p90 695345971.2 bytes; n = 10 of 10 |
| Docxodus | prose-500w | ready | 698034176.0 bytes; p90 700136652.8 bytes; n = 10 of 10 |
| eigenpal | prose-500w | ready | 637954048.0 bytes; p90 640423936.0 bytes; n = 10 of 10 |
| Folio | prose-500w | ready | 559695872.0 bytes; p90 561134796.8 bytes; n = 10 of 10 |
| GenOffice | prose-500w | ready | 580214784.0 bytes; p90 582672793.6 bytes; n = 10 of 10 |
| Plate.js | prose-500w | ready | 533405696.0 bytes; p90 534811443.2 bytes; n = 10 of 10 |
| SuperDoc | prose-500w | ready | 636798976.0 bytes; p90 638865408.0 bytes; n = 10 of 10 |
| WordCraft | prose-500w | ready | 822824960.0 bytes; p90 872320204.8 bytes; n = 10 of 10 |
| canvas-editor + plugin | prose-50kw | after_edit_burst | 7286439936.0 bytes; range 7165808640.0 to 11208536064.0 bytes; n = 8 of 10; 2 of 10 launches failed: editor_timeout: 2; second: 1 of 10 launches failed: editor_timeout: 1 |
| Docen | prose-50kw | after_edit_burst | 2030780416.0 bytes; p90 2046273126.4 bytes; n = 10 of 10 |
| Docxodus | prose-50kw | after_edit_burst | 1037137920.0 bytes; p90 1072340172.8 bytes; n = 10 of 10 |
| eigenpal | prose-50kw | after_edit_burst | 795648000.0 bytes; p90 801205452.8 bytes; n = 10 of 10 |
| Folio | prose-50kw | after_edit_burst | 913059840.0 bytes; p90 943810150.4 bytes; n = 10 of 10 |
| GenOffice | prose-50kw | after_edit_burst | 1011167232.0 bytes; p90 1019171225.6 bytes; n = 10 of 10 |
| Plate.js | prose-50kw | after_edit_burst | 952135680.0 bytes; p90 954373734.4 bytes; n = 10 of 10 |
| SuperDoc | prose-50kw | after_edit_burst | 942741504.0 bytes; p90 950832332.8 bytes; n = 10 of 10 |
| WordCraft | prose-50kw | after_edit_burst | 1230723072.0 bytes; p90 1253617254.4 bytes; n = 10 of 10 |
| canvas-editor + plugin | prose-50kw | quiescent | 7252049920.0 bytes; range 7118868480.0 to 11157270528.0 bytes; n = 8 of 10; 2 of 10 launches failed: editor_timeout: 2; second: 1 of 10 launches failed: editor_timeout: 1 |
| Docen | prose-50kw | quiescent | 2043017216.0 bytes; p90 2067081216.0 bytes; n = 10 of 10 |
| Docxodus | prose-50kw | quiescent | 1037191168.0 bytes; p90 1072338534.4 bytes; n = 10 of 10 |
| eigenpal | prose-50kw | quiescent | 795715584.0 bytes; p90 800789299.2 bytes; n = 10 of 10 |
| Folio | prose-50kw | quiescent | 919480320.0 bytes; p90 950195404.8 bytes; n = 10 of 10 |
| GenOffice | prose-50kw | quiescent | 1015664640.0 bytes; p90 1021855744.0 bytes; n = 10 of 10 |
| Plate.js | prose-50kw | quiescent | 952152064.0 bytes; p90 954442137.6 bytes; n = 10 of 10 |
| SuperDoc | prose-50kw | quiescent | 954730496.0 bytes; p90 962236825.6 bytes; n = 10 of 10 |
| WordCraft | prose-50kw | quiescent | 1230581760.0 bytes; p90 1251047424.0 bytes; n = 10 of 10 |
| canvas-editor + plugin | prose-50kw | ready | 2035441664.0 bytes; range 1765638144.0 to 2151559168.0 bytes; n = 8 of 10; 2 of 10 launches failed: editor_timeout: 2; second: 1 of 10 launches failed: editor_timeout: 1 |
| Docen | prose-50kw | ready | 1468106752.0 bytes; p90 1471211929.6 bytes; n = 10 of 10 |
| Docxodus | prose-50kw | ready | 1011273728.0 bytes; p90 1044491059.2 bytes; n = 10 of 10 |
| eigenpal | prose-50kw | ready | 725364736.0 bytes; p90 727973888.0 bytes; n = 10 of 10 |
| Folio | prose-50kw | ready | 655802368.0 bytes; p90 657222451.2 bytes; n = 10 of 10 |
| GenOffice | prose-50kw | ready | 823193600.0 bytes; p90 840120729.6 bytes; n = 10 of 10 |
| Plate.js | prose-50kw | ready | 868161536.0 bytes; p90 871073792.0 bytes; n = 10 of 10 |
| SuperDoc | prose-50kw | ready | 667543552.0 bytes; p90 670427545.6 bytes; n = 10 of 10 |
| WordCraft | prose-50kw | ready | 810409984.0 bytes; p90 813400883.2 bytes; n = 10 of 10 |
| canvas-editor + plugin | prose-5kw | after_edit_burst | 1856942080.0 bytes; p90 2424104140.8 bytes; n = 10 of 10 |
| Docen | prose-5kw | after_edit_burst | 996028416.0 bytes; p90 1011515392.0 bytes; n = 10 of 10 |
| Docxodus | prose-5kw | after_edit_burst | 768116736.0 bytes; p90 770079539.2 bytes; n = 10 of 10 |
| eigenpal | prose-5kw | after_edit_burst | 714336256.0 bytes; p90 734372659.2 bytes; n = 10 of 10 |
| Folio | prose-5kw | after_edit_burst | 623341568.0 bytes; p90 636638003.2 bytes; n = 10 of 10 |
| GenOffice | prose-5kw | after_edit_burst | 679376896.0 bytes; p90 691703398.4 bytes; n = 10 of 10 |
| Plate.js | prose-5kw | after_edit_burst | 707098624.0 bytes; p90 710900121.6 bytes; n = 10 of 10 |
| SuperDoc | prose-5kw | after_edit_burst | 766554112.0 bytes; p90 771482009.6 bytes; n = 10 of 10 |
| WordCraft | prose-5kw | after_edit_burst | 1201481728.0 bytes; p90 1218519859.2 bytes; n = 10 of 10 |
| canvas-editor + plugin | prose-5kw | quiescent | 1852588032.0 bytes; p90 2418040422.4 bytes; n = 10 of 10 |
| Docen | prose-5kw | quiescent | 991227904.0 bytes; p90 994759065.6 bytes; n = 10 of 10 |
| Docxodus | prose-5kw | quiescent | 768141312.0 bytes; p90 770270412.8 bytes; n = 10 of 10 |
| eigenpal | prose-5kw | quiescent | 711999488.0 bytes; p90 730477772.8 bytes; n = 10 of 10 |
| Folio | prose-5kw | quiescent | 632184832.0 bytes; p90 645738086.4 bytes; n = 10 of 10 |
| GenOffice | prose-5kw | quiescent | 680208384.0 bytes; p90 691785728.0 bytes; n = 10 of 10 |
| Plate.js | prose-5kw | quiescent | 707145728.0 bytes; p90 711049625.6 bytes; n = 10 of 10 |
| SuperDoc | prose-5kw | quiescent | 808949760.0 bytes; p90 812283494.4 bytes; n = 10 of 10 |
| WordCraft | prose-5kw | quiescent | 1201559552.0 bytes; p90 1218537881.6 bytes; n = 10 of 10 |
| canvas-editor + plugin | prose-5kw | ready | 744474624.0 bytes; p90 748195840.0 bytes; n = 10 of 10 |
| Docen | prose-5kw | ready | 785393664.0 bytes; p90 787410534.4 bytes; n = 10 of 10 |
| Docxodus | prose-5kw | ready | 742199296.0 bytes; p90 744343142.4 bytes; n = 10 of 10 |
| eigenpal | prose-5kw | ready | 667633664.0 bytes; p90 669437952.0 bytes; n = 10 of 10 |
| Folio | prose-5kw | ready | 579721216.0 bytes; p90 582055526.4 bytes; n = 10 of 10 |
| GenOffice | prose-5kw | ready | 603351040.0 bytes; p90 605839769.6 bytes; n = 10 of 10 |
| Plate.js | prose-5kw | ready | 588558336.0 bytes; p90 591923609.6 bytes; n = 10 of 10 |
| SuperDoc | prose-5kw | ready | 713125888.0 bytes; p90 714423091.2 bytes; n = 10 of 10 |
| WordCraft | prose-5kw | ready | 799764480.0 bytes; p90 818044928.0 bytes; n = 10 of 10 |

### C19 — retained memory

| Editor | Workload | C19 |
|---|---|---|
| canvas-editor + plugin | complex-corpus | first: not enough samples (n = 0 of 10; reasons editor_crash: 10); second: not enough samples (n = 0 of 10; reasons editor_crash: 10) |
| Docen | complex-corpus | 336515072.0 bytes; p90 337346560.0 bytes; n = 10 of 10 |
| Docxodus | complex-corpus | 338989056.0 bytes; p90 339867238.4 bytes; n = 10 of 10 |
| eigenpal | complex-corpus | 336900096.0 bytes; p90 340020838.4 bytes; n = 10 of 10 |
| Folio | complex-corpus | 336510976.0 bytes; p90 337728716.8 bytes; n = 10 of 10 |
| GenOffice | complex-corpus | 337848320.0 bytes; p90 339499008.0 bytes; n = 10 of 10 |
| Plate.js | complex-corpus | 336586752.0 bytes; p90 338862489.6 bytes; n = 10 of 10 |
| SuperDoc | complex-corpus | 344907776.0 bytes; p90 346454016.0 bytes; n = 10 of 10 |
| WordCraft | complex-corpus | 377987072.0 bytes; p90 379987148.8 bytes; n = 10 of 10 |
| canvas-editor + plugin | prose-250kw | first: not enough samples (n = 0 of 10; reasons editor_crash: 4; editor_timeout: 6); second: not enough samples (n = 0 of 10; reasons editor_crash: 3; editor_timeout: 7) |
| Docen | prose-250kw | first: not enough samples (n = 0 of 10; reasons editor_timeout: 10); second: not enough samples (n = 0 of 10; reasons editor_timeout: 10) |
| Docxodus | prose-250kw | 337711104.0 bytes; p90 339802931.2 bytes; n = 10 of 10 |
| eigenpal | prose-250kw | 338448384.0 bytes; p90 339783680.0 bytes; n = 10 of 10 |
| Folio | prose-250kw | 337876992.0 bytes; p90 339241779.2 bytes; n = 10 of 10 |
| GenOffice | prose-250kw | 336504832.0 bytes; p90 338391449.6 bytes; n = 10 of 10 |
| Plate.js | prose-250kw | 335863808.0 bytes; p90 338232115.2 bytes; n = 10 of 10 |
| SuperDoc | prose-250kw | 345405440.0 bytes; p90 347064729.6 bytes; n = 10 of 10 |
| WordCraft | prose-250kw | 378030080.0 bytes; p90 381451059.2 bytes; n = 10 of 10 |
| canvas-editor + plugin | prose-500w | 337057792.0 bytes; p90 339448217.6 bytes; n = 10 of 10 |
| Docen | prose-500w | 337491968.0 bytes; p90 338759680.0 bytes; n = 10 of 10 |
| Docxodus | prose-500w | 337846272.0 bytes; p90 339816448.0 bytes; n = 10 of 10 |
| eigenpal | prose-500w | 336353280.0 bytes; p90 339197952.0 bytes; n = 10 of 10 |
| Folio | prose-500w | 337315840.0 bytes; p90 338000691.2 bytes; n = 10 of 10 |
| GenOffice | prose-500w | 337252352.0 bytes; p90 337862656.0 bytes; n = 10 of 10 |
| Plate.js | prose-500w | 336142336.0 bytes; p90 337394483.2 bytes; n = 10 of 10 |
| SuperDoc | prose-500w | 344596480.0 bytes; p90 347408793.6 bytes; n = 10 of 10 |
| WordCraft | prose-500w | 376098816.0 bytes; p90 378238156.8 bytes; n = 10 of 10 |
| canvas-editor + plugin | prose-50kw | 337807360.0 bytes; range 335040512.0 to 340115456.0 bytes; n = 8 of 10; 2 of 10 launches failed: editor_timeout: 2; second: 1 of 10 launches failed: editor_timeout: 1 |
| Docen | prose-50kw | 336820224.0 bytes; p90 338185420.8 bytes; n = 10 of 10 |
| Docxodus | prose-50kw | 338849792.0 bytes; p90 339631718.4 bytes; n = 10 of 10 |
| eigenpal | prose-50kw | 337451008.0 bytes; p90 339498598.4 bytes; n = 10 of 10 |
| Folio | prose-50kw | 337297408.0 bytes; p90 339402342.4 bytes; n = 10 of 10 |
| GenOffice | prose-50kw | 336457728.0 bytes; p90 338227609.6 bytes; n = 10 of 10 |
| Plate.js | prose-50kw | 335196160.0 bytes; p90 336142745.6 bytes; n = 10 of 10 |
| SuperDoc | prose-50kw | 346357760.0 bytes; p90 347631616.0 bytes; n = 10 of 10 |
| WordCraft | prose-50kw | 378910720.0 bytes; p90 379758182.4 bytes; n = 10 of 10 |
| canvas-editor + plugin | prose-5kw | 335837184.0 bytes; p90 338093260.8 bytes; n = 10 of 10 |
| Docen | prose-5kw | 337702912.0 bytes; p90 338539724.8 bytes; n = 10 of 10 |
| Docxodus | prose-5kw | 337526784.0 bytes; p90 339687424.0 bytes; n = 10 of 10 |
| eigenpal | prose-5kw | 336617472.0 bytes; p90 338614272.0 bytes; n = 10 of 10 |
| Folio | prose-5kw | 336822272.0 bytes; p90 338168627.2 bytes; n = 10 of 10 |
| GenOffice | prose-5kw | 336994304.0 bytes; p90 338518835.2 bytes; n = 10 of 10 |
| Plate.js | prose-5kw | 333594624.0 bytes; p90 336586342.4 bytes; n = 10 of 10 |
| SuperDoc | prose-5kw | 346734592.0 bytes; p90 347955200.0 bytes; n = 10 of 10 |
| WordCraft | prose-5kw | 376528896.0 bytes; p90 378588774.4 bytes; n = 10 of 10 |

### B8 — resources while opening and editing

**B8 — resources while opening and editing.** One fresh browser per launch opens the document, waits until the editor is idle, types sixteen characters into a body line on the first screen, and waits again. CPU is the processor time of the whole browser process tree: to open (from navigation until idle, including work an editor does after it reports ready), during the edit (the keystrokes plus half a second), and while settling afterwards. Peak memory is the resident memory of that tree. An edit counts only when it is verified in the document: the text of the block at the caret, read from the page or from the editor's model, gained exactly the typed text; WordCraft, which exposes no text, is verified by its own modified flag. An editor that never goes idle is measured over a 30-second cap and flagged. The complex document is loaded without its read-only protection, which the editors honour.

Each cell shows the first seed's median and the second seed's median. A figure is printed only when the two agree within 10 percent (20 ms for CPU).

### 500 words

Not published or flagged:

- canvas-editor + plugin: first seed: run blocked (scheduled_below_10; second_seed_required).
- Docen: first seed: run blocked (scheduled_below_10; second_seed_required).
- Docxodus: first seed: run blocked (scheduled_below_10; second_seed_required).
- eigenpal: first seed: run blocked (scheduled_below_10; second_seed_required).
- Folio: first seed: run blocked (scheduled_below_10; second_seed_required).
- GenOffice: first seed: run blocked (scheduled_below_10; second_seed_required).
- Plate.js: first seed: run blocked (scheduled_below_10; second_seed_required).
- SuperDoc: first seed: run blocked (scheduled_below_10; second_seed_required).
- WordCraft: first seed: run blocked (scheduled_below_10; second_seed_required).

### 5,000 words

Not published or flagged:

- canvas-editor + plugin: first seed: run blocked (scheduled_below_10; second_seed_required).
- Docen: first seed: run blocked (scheduled_below_10; second_seed_required).
- Docxodus: first seed: run blocked (scheduled_below_10; second_seed_required).
- eigenpal: first seed: run blocked (scheduled_below_10; second_seed_required).
- Folio: first seed: run blocked (scheduled_below_10; second_seed_required).
- GenOffice: first seed: run blocked (scheduled_below_10; second_seed_required).
- Plate.js: first seed: run blocked (scheduled_below_10; second_seed_required).
- SuperDoc: first seed: run blocked (scheduled_below_10; second_seed_required).
- WordCraft: first seed: run blocked (scheduled_below_10; second_seed_required).

### 50,000 words

Not published or flagged:

- canvas-editor + plugin: first seed: run blocked (scheduled_below_10; second_seed_required).
- Docen: first seed: run blocked (scheduled_below_10; second_seed_required).
- Docxodus: first seed: run blocked (scheduled_below_10; second_seed_required).
- eigenpal: first seed: run blocked (scheduled_below_10; second_seed_required).
- Folio: first seed: run blocked (scheduled_below_10; second_seed_required).
- GenOffice: first seed: run blocked (scheduled_below_10; second_seed_required).
- Plate.js: first seed: run blocked (scheduled_below_10; second_seed_required).
- SuperDoc: first seed: run blocked (scheduled_below_10; second_seed_required).
- WordCraft: first seed: run blocked (scheduled_below_10; second_seed_required).

### 250,000 words

Not published or flagged:

- canvas-editor + plugin: first seed: run blocked (scheduled_below_10; second_seed_required).
- Docen: first seed: run blocked (scheduled_below_10; second_seed_required).
- Docxodus: first seed: run blocked (scheduled_below_10; second_seed_required).
- eigenpal: first seed: run blocked (scheduled_below_10; second_seed_required).
- Folio: first seed: run blocked (scheduled_below_10; second_seed_required).
- GenOffice: first seed: run blocked (scheduled_below_10; second_seed_required).
- Plate.js: first seed: run blocked (scheduled_below_10; second_seed_required).
- SuperDoc: first seed: run blocked (scheduled_below_10; second_seed_required).
- WordCraft: first seed: run blocked (scheduled_below_10; second_seed_required).

### Complex document

Not published or flagged:

- canvas-editor + plugin: first seed: run blocked (scheduled_below_10; kept_below_5; second_seed_required); TypeError: Cannot read properties of undefined (reading 'width')
    at pa.computeRowColInfo (http://127.0.0.1:33203/assets/index-L94yjsVH.js:58:70981)
    at sr.computeRowList (http://127.0.0.1:33203; TypeError: Cannot read properties of undefined (reading 'width')
    at pa.computeRowColInfo (http://127.0.0.1:33591/assets/index-L94yjsVH.js:58:70981)
    at sr.computeRowList (http://127.0.0.1:33591; TypeError: Cannot read properties of undefined (reading 'width')
    at pa.computeRowColInfo (http://127.0.0.1:33871/assets/index-L94yjsVH.js:58:70981)
    at sr.computeRowList (http://127.0.0.1:33871; TypeError: Cannot read properties of undefined (reading 'width')
    at pa.computeRowColInfo (http://127.0.0.1:35259/assets/index-L94yjsVH.js:58:70981)
    at sr.computeRowList (http://127.0.0.1:35259; TypeError: Cannot read properties of undefined (reading 'width')
    at pa.computeRowColInfo (http://127.0.0.1:39261/assets/index-L94yjsVH.js:58:70981)
    at sr.computeRowList (http://127.0.0.1:39261; TypeError: Cannot read properties of undefined (reading 'width')
    at pa.computeRowColInfo (http://127.0.0.1:40981/assets/index-L94yjsVH.js:58:70981)
    at sr.computeRowList (http://127.0.0.1:40981; TypeError: Cannot read properties of undefined (reading 'width')
    at pa.computeRowColInfo (http://127.0.0.1:42967/assets/index-L94yjsVH.js:58:70981)
    at sr.computeRowList (http://127.0.0.1:42967; TypeError: Cannot read properties of undefined (reading 'width')
    at pa.computeRowColInfo (http://127.0.0.1:43905/assets/index-L94yjsVH.js:58:70981)
    at sr.computeRowList (http://127.0.0.1:43905; TypeError: Cannot read properties of undefined (reading 'width')
    at pa.computeRowColInfo (http://127.0.0.1:44751/assets/index-L94yjsVH.js:58:70981)
    at sr.computeRowList (http://127.0.0.1:44751; TypeError: Cannot read properties of undefined (reading 'width')
    at pa.computeRowColInfo (http://127.0.0.1:45541/assets/index-L94yjsVH.js:58:70981)
    at sr.computeRowList (http://127.0.0.1:45541; TypeError: Cannot read properties of undefined (reading 'width')
    at pa.computeRowColInfo (http://127.0.0.1:47947/assets/index-L94yjsVH.js:58:70981)
    at sr.computeRowList (http://127.0.0.1:47947; TypeError: Cannot read properties of undefined (reading 'width')
    at pa.computeRowColInfo (http://127.0.0.1:49509/assets/index-L94yjsVH.js:58:70981)
    at sr.computeRowList (http://127.0.0.1:49509; TypeError: Cannot read properties of undefined (reading 'width')
    at pa.computeRowColInfo (http://127.0.0.1:49717/assets/index-L94yjsVH.js:58:70981)
    at sr.computeRowList (http://127.0.0.1:49717; TypeError: Cannot read properties of undefined (reading 'width')
    at pa.computeRowColInfo (http://127.0.0.1:50287/assets/index-L94yjsVH.js:58:70981)
    at sr.computeRowList (http://127.0.0.1:50287; TypeError: Cannot read properties of undefined (reading 'width')
    at pa.computeRowColInfo (http://127.0.0.1:52025/assets/index-L94yjsVH.js:58:70981)
    at sr.computeRowList (http://127.0.0.1:52025; TypeError: Cannot read properties of undefined (reading 'width')
    at pa.computeRowColInfo (http://127.0.0.1:53355/assets/index-L94yjsVH.js:58:70981)
    at sr.computeRowList (http://127.0.0.1:53355; TypeError: Cannot read properties of undefined (reading 'width')
    at pa.computeRowColInfo (http://127.0.0.1:53659/assets/index-L94yjsVH.js:58:70981)
    at sr.computeRowList (http://127.0.0.1:53659; TypeError: Cannot read properties of undefined (reading 'width')
    at pa.computeRowColInfo (http://127.0.0.1:56581/assets/index-L94yjsVH.js:58:70981)
    at sr.computeRowList (http://127.0.0.1:56581; TypeError: Cannot read properties of undefined (reading 'width')
    at pa.computeRowColInfo (http://127.0.0.1:59035/assets/index-L94yjsVH.js:58:70981)
    at sr.computeRowList (http://127.0.0.1:59035; TypeError: Cannot read properties of undefined (reading 'width')
    at pa.computeRowColInfo (http://127.0.0.1:59713/assets/index-L94yjsVH.js:58:70981)
    at sr.computeRowList (http://127.0.0.1:59713.
- Docen: first seed: run blocked (scheduled_below_10; kept_below_5; second_seed_required).
- Docxodus: first seed: run blocked (scheduled_below_10; kept_below_5; second_seed_required).
- eigenpal: first seed: run blocked (scheduled_below_10; kept_below_5; second_seed_required).
- Folio: first seed: run blocked (scheduled_below_10; kept_below_5; second_seed_required).
- GenOffice: first seed: run blocked (scheduled_below_10; kept_below_5; second_seed_required).
- Plate.js: first seed: run blocked (scheduled_below_10; kept_below_5; second_seed_required).
- SuperDoc: first seed: run blocked (scheduled_below_10; kept_below_5; second_seed_required).
- WordCraft: first seed: run blocked (scheduled_below_10; kept_below_5; second_seed_required).

### B9 — typing marathon

Throughput sessions publish chars/s and resources. Latency sessions publish load and key-to-paint with witness counts; their instrumented throughput and resources are withheld.

canvas-editor + plugin — latency: first: not enough sessions or run blocked (n = 0 of 307; insufficient_typing_sessions); progress [{'characters_typed': 30939}, {'characters_typed': 30748}]; second: not enough sessions or run blocked (n = 0 of 287; insufficient_typing_sessions); progress [{'characters_typed': 29447}, {'characters_typed': 29128}] Latency-session throughput and resources are instrumented; figures withheld.

canvas-editor + plugin — throughput: first: not enough sessions or run blocked (n = 0 of 307; insufficient_typing_sessions); progress [{'characters_typed': 29470}, {'characters_typed': 29907}]; second: not enough sessions or run blocked (n = 0 of 287; insufficient_typing_sessions); progress [{'characters_typed': 30276}, {'characters_typed': 29993}]

Docen — latency: first: not enough sessions or run blocked (n = 0 of 297; insufficient_typing_sessions); progress [{'characters_typed': 81225}, {'characters_typed': 81225}]; second: not enough sessions or run blocked (n = 0 of 312; insufficient_typing_sessions); progress [{'characters_typed': 32652}, {'characters_typed': 33292}] Latency-session throughput and resources are instrumented; figures withheld.

Docen — throughput: first: not enough sessions or run blocked (n = 0 of 297; insufficient_typing_sessions); progress [{'characters_typed': 35689}, {'characters_typed': 34263}]; second: not enough sessions or run blocked (n = 0 of 312; insufficient_typing_sessions); progress [{'characters_typed': 38838}, {'characters_typed': 38915}]

Docxodus — latency: first: not enough sessions or run blocked (n = 0 of 282; insufficient_typing_sessions); progress [{'characters_typed': 81225}, {'characters_typed': 81225}]; second: not enough sessions or run blocked (n = 0 of 272; insufficient_typing_sessions); progress [{'characters_typed': 81225}, {'characters_typed': 81225}] Latency-session throughput and resources are instrumented; figures withheld.

Docxodus — throughput: first: not enough sessions or run blocked (n = 6 of 282; insufficient_typing_sessions); second: not enough sessions or run blocked (n = 6 of 272; insufficient_typing_sessions)

eigenpal — latency: first: not enough sessions or run blocked (n = 6 of 277; insufficient_typing_sessions); second: not enough sessions or run blocked (n = 6 of 307; insufficient_typing_sessions) Latency-session throughput and resources are instrumented; figures withheld.

eigenpal — throughput: first: not enough sessions or run blocked (n = 6 of 277; insufficient_typing_sessions); second: not enough sessions or run blocked (n = 6 of 307; insufficient_typing_sessions)

Folio — latency: first: not enough sessions or run blocked (n = 0 of 292; insufficient_typing_sessions); progress [{'characters_typed': 0}, {'characters_typed': 0}]; second: not enough sessions or run blocked (n = 0 of 282; insufficient_typing_sessions); progress [{'characters_typed': 0}, {'characters_typed': 0}] Latency-session throughput and resources are instrumented; figures withheld.

Folio — throughput: first: not enough sessions or run blocked (n = 0 of 292; insufficient_typing_sessions); progress [{'characters_typed': 0}, {'characters_typed': 0}]; second: not enough sessions or run blocked (n = 0 of 282; insufficient_typing_sessions); progress [{'characters_typed': 0}, {'characters_typed': 0}]

GenOffice — latency: first: not enough sessions or run blocked (n = 6 of 297; insufficient_typing_sessions); second: not enough sessions or run blocked (n = 6 of 282; insufficient_typing_sessions) Latency-session throughput and resources are instrumented; figures withheld.

GenOffice — throughput: first: not enough sessions or run blocked (n = 6 of 297; insufficient_typing_sessions); second: not enough sessions or run blocked (n = 6 of 282; insufficient_typing_sessions)

Plate.js — latency: first: not enough sessions or run blocked (n = 6 of 292; insufficient_typing_sessions); second: not enough sessions or run blocked (n = 6 of 277; insufficient_typing_sessions) Latency-session throughput and resources are instrumented; figures withheld.

Plate.js — throughput: first: not enough sessions or run blocked (n = 6 of 292; insufficient_typing_sessions); second: not enough sessions or run blocked (n = 6 of 277; insufficient_typing_sessions)

SuperDoc — latency: first: not enough sessions or run blocked (n = 0 of 252; insufficient_typing_sessions); progress [{'characters_typed': 81225}, {'characters_typed': 81225}]; second: not enough sessions or run blocked (n = 0 of 287; insufficient_typing_sessions); progress [{'characters_typed': 81225}, {'characters_typed': 81225}] Latency-session throughput and resources are instrumented; figures withheld.

SuperDoc — throughput: first: not enough sessions or run blocked (n = 6 of 252; insufficient_typing_sessions); second: not enough sessions or run blocked (n = 6 of 287; insufficient_typing_sessions)

WordCraft — latency: first: not enough sessions or run blocked (n = 0 of 307; insufficient_typing_sessions); progress [{'characters_typed': 18886}, {'characters_typed': 18876}]; second: not enough sessions or run blocked (n = 0 of 297; insufficient_typing_sessions); progress [{'characters_typed': 20505}, {'characters_typed': 20090}] Latency-session throughput and resources are instrumented; figures withheld.

WordCraft — throughput: first: not enough sessions or run blocked (n = 0 of 307; insufficient_typing_sessions); progress [{'characters_typed': 20685}, {'characters_typed': 20814}]; second: not enough sessions or run blocked (n = 0 of 297; insufficient_typing_sessions); progress [{'characters_typed': 17765}, {'characters_typed': 17586}]

## Not measured in the browser run

- **Apryse:** Apryse WebViewer needs a licence key, and the key is never placed on the measuring machines.
- **docs.plus:** docs.plus runs only as an application with its own application servers, which the browser run does not start.
- **Fidus Writer:** Fidus Writer runs only as an application with its own application server, which the browser run does not start.
- **LibreOffice (baseline):** LibreOffice is the conversion baseline of the headless report, not a browser editor.
- **office-open:** office-open is a library with no editing surface to paint, so no browser criterion applies.

## Not reproduced

| Editor | Criterion | Workload | Measure | First seed / reason | Second seed, median |
|---|---|---|---|---|---|
| canvas-editor + plugin | C03 | complex-corpus | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_run: 10); second: not enough samples (n = 0 of 10; reasons not_run: 10) | — |
| WordCraft | C03 | complex-corpus | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) | — |
| canvas-editor + plugin | C03 | complex-corpus | warm_steady | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| GenOffice | C03 | complex-corpus | warm_steady | 1082.5 ms | 883.5 ms |
| WordCraft | C03 | complex-corpus | warm_steady | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) | — |
| Docen | C03 | prose-250kw | process_cold_fs_warm | 9218.0 ms | 10338.0 ms |
| WordCraft | C03 | prose-250kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) | — |
| WordCraft | C03 | prose-250kw | warm_steady | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) | — |
| WordCraft | C03 | prose-500w | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) | — |
| WordCraft | C03 | prose-500w | warm_steady | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) | — |
| canvas-editor + plugin | C03 | prose-50kw | process_cold_fs_warm | 6478.5 ms | 5217.5 ms |
| Docen | C03 | prose-50kw | process_cold_fs_warm | 3378.0 ms | 2551.0 ms |
| Docxodus | C03 | prose-50kw | process_cold_fs_warm | 13686.5 ms | 10022.5 ms |
| eigenpal | C03 | prose-50kw | process_cold_fs_warm | 2716.0 ms | 1818.0 ms |
| Folio | C03 | prose-50kw | process_cold_fs_warm | 2335.5 ms | 1669.0 ms |
| GenOffice | C03 | prose-50kw | process_cold_fs_warm | 1774.5 ms | 1441.0 ms |
| Plate.js | C03 | prose-50kw | process_cold_fs_warm | 6324.0 ms | 4222.0 ms |
| SuperDoc | C03 | prose-50kw | process_cold_fs_warm | 1116.5 ms | 988.5 ms |
| WordCraft | C03 | prose-50kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) | — |
| canvas-editor + plugin | C03 | prose-50kw | warm_steady | 6818.0 ms | 4463.0 ms |
| Docen | C03 | prose-50kw | warm_steady | 3088.5 ms | 2218.0 ms |
| Docxodus | C03 | prose-50kw | warm_steady | 12095.0 ms | 9142.5 ms |
| eigenpal | C03 | prose-50kw | warm_steady | 2220.5 ms | 1535.0 ms |
| Folio | C03 | prose-50kw | warm_steady | 2072.5 ms | 1309.0 ms |
| GenOffice | C03 | prose-50kw | warm_steady | 1386.5 ms | 1237.0 ms |
| Plate.js | C03 | prose-50kw | warm_steady | 5563.5 ms | 3694.5 ms |
| SuperDoc | C03 | prose-50kw | warm_steady | 941.5 ms | 388.5 ms |
| WordCraft | C03 | prose-50kw | warm_steady | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) | — |
| Docen | C03 | prose-5kw | process_cold_fs_warm | 1432.5 ms | 1597.0 ms |
| Folio | C03 | prose-5kw | process_cold_fs_warm | 938.0 ms | 1058.0 ms |
| WordCraft | C03 | prose-5kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) | — |
| eigenpal | C03 | prose-5kw | warm_steady | 796.5 ms | 904.5 ms |
| WordCraft | C03 | prose-5kw | warm_steady | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) | — |
| canvas-editor + plugin | C04 | complex-corpus | — | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) | — |
| WordCraft | C04 | complex-corpus | — | 472.0 ms | 868.0 ms |
| SuperDoc | C04 | prose-250kw | — | 1.9 ms | 2.3 ms |
| WordCraft | C04 | prose-250kw | — | 227.6 ms | 468.8 ms |
| WordCraft | C04 | prose-500w | — | 799.3 ms | 379.7 ms |
| Docen | C04 | prose-50kw | — | 2.0 ms | 1.8 ms |
| Folio | C04 | prose-50kw | — | 2.1 ms | 1.8 ms |
| GenOffice | C04 | prose-50kw | — | 2.3 ms | 1.9 ms |
| WordCraft | C04 | prose-50kw | — | 443.5 ms | 2.0 ms |
| canvas-editor + plugin | C04 | prose-5kw | — | 1.9 ms | 2.1 ms |
| GenOffice | C04 | prose-5kw | — | 1.8 ms | 2.3 ms |
| Plate.js | C04 | prose-5kw | — | 1.8 ms | 2.2 ms |
| SuperDoc | C04 | prose-5kw | — | 1.7 ms | 1.9 ms |
| WordCraft | C04 | prose-5kw | — | 486.1 ms | 651.1 ms |
| canvas-editor + plugin | C05 | complex-corpus | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_run: 10); second: not enough samples (n = 0 of 10; reasons not_run: 10) | — |
| Docen | C05 | complex-corpus | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) | — |
| WordCraft | C05 | complex-corpus | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| canvas-editor + plugin | C05 | complex-corpus | warm_steady | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| Docen | C05 | complex-corpus | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| WordCraft | C05 | complex-corpus | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| canvas-editor + plugin | C05 | prose-250kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) | — |
| Docen | C05 | prose-250kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) | — |
| GenOffice | C05 | prose-250kw | process_cold_fs_warm | second: not enough samples (n = 1 of 10; reasons unverified: 9) | — |
| Plate.js | C05 | prose-250kw | process_cold_fs_warm | 175.2 ms | 205.5 ms |
| WordCraft | C05 | prose-250kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| canvas-editor + plugin | C05 | prose-250kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| Docen | C05 | prose-250kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| Folio | C05 | prose-250kw | warm_steady | 427.2 ms | 483.5 ms |
| GenOffice | C05 | prose-250kw | warm_steady | second: not enough samples (n = 1 of 10; reasons unverified: 9) | — |
| Plate.js | C05 | prose-250kw | warm_steady | 129.7 ms | 161.8 ms |
| WordCraft | C05 | prose-250kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| canvas-editor + plugin | C05 | prose-500w | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) | — |
| Docen | C05 | prose-500w | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) | — |
| WordCraft | C05 | prose-500w | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| canvas-editor + plugin | C05 | prose-500w | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| Docen | C05 | prose-500w | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| WordCraft | C05 | prose-500w | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| canvas-editor + plugin | C05 | prose-50kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) | — |
| Docen | C05 | prose-50kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) | — |
| eigenpal | C05 | prose-50kw | process_cold_fs_warm | 97.6 ms | 65.5 ms |
| Folio | C05 | prose-50kw | process_cold_fs_warm | 215.3 ms | 134.0 ms |
| GenOffice | C05 | prose-50kw | process_cold_fs_warm | 193.6 ms | 143.4 ms |
| Plate.js | C05 | prose-50kw | process_cold_fs_warm | 98.0 ms | 67.9 ms |
| SuperDoc | C05 | prose-50kw | process_cold_fs_warm | 644.0 ms | 450.2 ms |
| WordCraft | C05 | prose-50kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| canvas-editor + plugin | C05 | prose-50kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| Docen | C05 | prose-50kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| eigenpal | C05 | prose-50kw | warm_steady | 77.3 ms | 56.2 ms |
| Folio | C05 | prose-50kw | warm_steady | 182.8 ms | 121.5 ms |
| GenOffice | C05 | prose-50kw | warm_steady | 207.3 ms | 139.5 ms |
| SuperDoc | C05 | prose-50kw | warm_steady | 614.5 ms | 431.5 ms |
| WordCraft | C05 | prose-50kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| canvas-editor + plugin | C05 | prose-5kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) | — |
| Docen | C05 | prose-5kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) | — |
| WordCraft | C05 | prose-5kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| canvas-editor + plugin | C05 | prose-5kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| Docen | C05 | prose-5kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| SuperDoc | C05 | prose-5kw | warm_steady | 286.2 ms | 318.5 ms |
| WordCraft | C05 | prose-5kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| canvas-editor + plugin | C06 | complex-corpus | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_run: 10); second: not enough samples (n = 0 of 10; reasons not_run: 10) | — |
| Docen | C06 | complex-corpus | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) | — |
| WordCraft | C06 | complex-corpus | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| canvas-editor + plugin | C06 | complex-corpus | warm_steady | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| Docen | C06 | complex-corpus | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| WordCraft | C06 | complex-corpus | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| canvas-editor + plugin | C06 | prose-250kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) | — |
| Docen | C06 | prose-250kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) | — |
| Folio | C06 | prose-250kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) | — |
| GenOffice | C06 | prose-250kw | process_cold_fs_warm | second: not enough samples (n = 0 of 10; reasons unverified: 10) | — |
| WordCraft | C06 | prose-250kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| canvas-editor + plugin | C06 | prose-250kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| Docen | C06 | prose-250kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| Folio | C06 | prose-250kw | warm_steady | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) | — |
| GenOffice | C06 | prose-250kw | warm_steady | second: not enough samples (n = 0 of 10; reasons unverified: 10) | — |
| SuperDoc | C06 | prose-250kw | warm_steady | 303.3 ms | 337.5 ms |
| WordCraft | C06 | prose-250kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| canvas-editor + plugin | C06 | prose-500w | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) | — |
| Docen | C06 | prose-500w | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) | — |
| WordCraft | C06 | prose-500w | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| canvas-editor + plugin | C06 | prose-500w | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| Docen | C06 | prose-500w | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| WordCraft | C06 | prose-500w | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| canvas-editor + plugin | C06 | prose-50kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) | — |
| Docen | C06 | prose-50kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) | — |
| eigenpal | C06 | prose-50kw | process_cold_fs_warm | 66.5 ms | 44.0 ms |
| Folio | C06 | prose-50kw | process_cold_fs_warm | 171.4 ms | 117.5 ms |
| GenOffice | C06 | prose-50kw | process_cold_fs_warm | 176.3 ms | 134.7 ms |
| Plate.js | C06 | prose-50kw | process_cold_fs_warm | 59.2 ms | 39.2 ms |
| SuperDoc | C06 | prose-50kw | process_cold_fs_warm | 369.9 ms | 278.9 ms |
| WordCraft | C06 | prose-50kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| canvas-editor + plugin | C06 | prose-50kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| Docen | C06 | prose-50kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| Folio | C06 | prose-50kw | warm_steady | 163.5 ms | 107.9 ms |
| GenOffice | C06 | prose-50kw | warm_steady | 203.2 ms | 143.2 ms |
| Plate.js | C06 | prose-50kw | warm_steady | 61.2 ms | 43.9 ms |
| SuperDoc | C06 | prose-50kw | warm_steady | 370.5 ms | 275.1 ms |
| WordCraft | C06 | prose-50kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| canvas-editor + plugin | C06 | prose-5kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) | — |
| Docen | C06 | prose-5kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) | — |
| SuperDoc | C06 | prose-5kw | process_cold_fs_warm | 176.1 ms | 199.9 ms |
| WordCraft | C06 | prose-5kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| canvas-editor + plugin | C06 | prose-5kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| Docen | C06 | prose-5kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| WordCraft | C06 | prose-5kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| canvas-editor + plugin | C07 | complex-corpus | — | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) | — |
| canvas-editor + plugin | C08 | complex-corpus | — | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) | — |
| Docen | C08 | complex-corpus | — | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) | — |
| WordCraft | C08 | complex-corpus | — | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| canvas-editor + plugin | C08 | prose-250kw | — | first: not enough samples (n = 0 of 10; reasons paint_witness_unavailable: 10); second: not enough samples (n = 0 of 10; reasons paint_witness_unavailable: 10) | — |
| WordCraft | C08 | prose-250kw | — | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| WordCraft | C08 | prose-500w | — | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| Plate.js | C08 | prose-50kw | — | 155.7 ms | 116.3 ms |
| SuperDoc | C08 | prose-50kw | — | 126.2 ms | 144.9 ms |
| WordCraft | C08 | prose-50kw | — | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| canvas-editor + plugin | C08 | prose-5kw | — | < 1 frame (16.7 ms) | 317.4 ms |
| WordCraft | C08 | prose-5kw | — | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| canvas-editor + plugin | C09 | complex-corpus | — | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) | — |
| Docen | C09 | complex-corpus | — | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) | — |
| Docxodus | C09 | complex-corpus | — | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) | — |
| WordCraft | C09 | complex-corpus | — | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| canvas-editor + plugin | C09 | prose-250kw | — | first: not enough samples (n = 0 of 10; reasons paint_witness_unavailable: 10); second: not enough samples (n = 0 of 10; reasons paint_witness_unavailable: 10) | — |
| Folio | C09 | prose-250kw | — | 183.9 ms | 135.8 ms |
| GenOffice | C09 | prose-250kw | — | 2323.5 ms | 2590.9 ms |
| WordCraft | C09 | prose-250kw | — | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| WordCraft | C09 | prose-500w | — | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| canvas-editor + plugin | C09 | prose-50kw | — | 121.7 ms | 145.1 ms |
| WordCraft | C09 | prose-50kw | — | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| WordCraft | C09 | prose-5kw | — | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| canvas-editor + plugin | C10 | complex-corpus | — | first: not enough samples (n = 0 of 10; reasons paint_witness_unavailable: 10); second: not enough samples (n = 0 of 10; reasons paint_witness_unavailable: 10) | — |
| eigenpal | C10 | complex-corpus | — | first: not enough samples (n = 0 of 10; reasons paint_witness_unavailable: 10); second: not enough samples (n = 0 of 10; reasons paint_witness_unavailable: 10) | — |
| GenOffice | C10 | complex-corpus | — | first: not enough samples (n = 0 of 10; reasons paint_witness_unavailable: 10); second: not enough samples (n = 0 of 10; reasons paint_witness_unavailable: 10) | — |
| WordCraft | C10 | complex-corpus | — | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| WordCraft | C10 | prose-250kw | — | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| WordCraft | C10 | prose-500w | — | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| WordCraft | C10 | prose-50kw | — | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| WordCraft | C10 | prose-5kw | — | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| canvas-editor + plugin | C11 | complex-corpus | — | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) | — |
| Docen | C11 | complex-corpus | — | first: not enough samples (n = 0 of 10; reasons paint_witness_unavailable: 10); second: not enough samples (n = 0 of 10; reasons paint_witness_unavailable: 10) | — |
| WordCraft | C11 | complex-corpus | — | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) | — |
| Docen | C11 | prose-250kw | — | first: not enough samples (n = 0 of 10; reasons paint_witness_unavailable: 10); second: not enough samples (n = 0 of 10; reasons paint_witness_unavailable: 10) | — |
| Plate.js | C11 | prose-250kw | — | first: not enough samples (n = 0 of 10; reasons editor_crash: 2; harness_error: 8); second: not enough samples (n = 0 of 10; reasons editor_crash: 6; harness_error: 4) | — |
| WordCraft | C11 | prose-250kw | — | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) | — |
| Docen | C11 | prose-500w | — | first: not enough samples (n = 3 of 10; reasons paint_witness_unavailable: 7); second: not enough samples (n = 1 of 10; reasons paint_witness_unavailable: 9) | — |
| Folio | C11 | prose-500w | — | 939.8 ms | 842.8 ms |
| WordCraft | C11 | prose-500w | — | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) | — |
| Docen | C11 | prose-50kw | — | first: not enough samples (n = 0 of 10; reasons paint_witness_unavailable: 10); second: not enough samples (n = 0 of 10; reasons paint_witness_unavailable: 10) | — |
| WordCraft | C11 | prose-50kw | — | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) | — |
| Docen | C11 | prose-5kw | — | first: not enough samples (n = 0 of 10; reasons paint_witness_unavailable: 10); second: not enough samples (n = 0 of 10; reasons paint_witness_unavailable: 10) | — |
| Folio | C11 | prose-5kw | — | first seed unpublishable: block 2 has no launch files (blocked) | — |
| WordCraft | C11 | prose-5kw | — | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) | — |
| canvas-editor + plugin | C12 | complex-corpus | — | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) | — |
| Docen | C12 | complex-corpus | — | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| WordCraft | C12 | complex-corpus | — | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| canvas-editor + plugin | C12 | prose-250kw | — | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| Docen | C12 | prose-250kw | — | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| Plate.js | C12 | prose-250kw | — | first: not enough samples (n = 0 of 10; reasons editor_crash: 2; harness_error: 8); second: not enough samples (n = 0 of 10; reasons editor_crash: 1; harness_error: 9) | — |
| WordCraft | C12 | prose-250kw | — | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| canvas-editor + plugin | C12 | prose-500w | — | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| Docen | C12 | prose-500w | — | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| SuperDoc | C12 | prose-500w | — | 206.4 ms | 181.9 ms |
| WordCraft | C12 | prose-500w | — | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| canvas-editor + plugin | C12 | prose-50kw | — | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| Docen | C12 | prose-50kw | — | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| WordCraft | C12 | prose-50kw | — | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| canvas-editor + plugin | C12 | prose-5kw | — | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| Docen | C12 | prose-5kw | — | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| Folio | C12 | prose-5kw | — | first seed unpublishable: block 2 has no launch files (blocked) | — |
| WordCraft | C12 | prose-5kw | — | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| canvas-editor + plugin | C14 | complex-corpus | presented_frame | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) | — |
| Docen | C14 | complex-corpus | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| Docxodus | C14 | complex-corpus | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| eigenpal | C14 | complex-corpus | presented_frame | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) | — |
| Folio | C14 | complex-corpus | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| GenOffice | C14 | complex-corpus | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| Plate.js | C14 | complex-corpus | presented_frame | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) | — |
| SuperDoc | C14 | complex-corpus | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| WordCraft | C14 | complex-corpus | presented_frame | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) | — |
| canvas-editor + plugin | C14 | complex-corpus | usable_no_damage | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) | — |
| Docen | C14 | complex-corpus | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) | — |
| Docxodus | C14 | complex-corpus | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) | — |
| eigenpal | C14 | complex-corpus | usable_no_damage | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| Folio | C14 | complex-corpus | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) | — |
| GenOffice | C14 | complex-corpus | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) | — |
| Plate.js | C14 | complex-corpus | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) | — |
| SuperDoc | C14 | complex-corpus | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) | — |
| WordCraft | C14 | complex-corpus | usable_no_damage | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| canvas-editor + plugin | C14 | prose-250kw | presented_frame | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) | — |
| Docen | C14 | prose-250kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| Docxodus | C14 | prose-250kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| eigenpal | C14 | prose-250kw | presented_frame | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) | — |
| Folio | C14 | prose-250kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| GenOffice | C14 | prose-250kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| Plate.js | C14 | prose-250kw | presented_frame | first: not enough samples (n = 0 of 10; reasons editor_crash: 1; harness_error: 9); second: not enough samples (n = 0 of 10; reasons editor_crash: 4; harness_error: 6) | — |
| SuperDoc | C14 | prose-250kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| WordCraft | C14 | prose-250kw | presented_frame | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) | — |
| canvas-editor + plugin | C14 | prose-250kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) | — |
| Docen | C14 | prose-250kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) | — |
| Docxodus | C14 | prose-250kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) | — |
| eigenpal | C14 | prose-250kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| Folio | C14 | prose-250kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) | — |
| GenOffice | C14 | prose-250kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) | — |
| Plate.js | C14 | prose-250kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons editor_crash: 1; harness_error: 9); second: not enough samples (n = 0 of 10; reasons editor_crash: 4; harness_error: 6) | — |
| SuperDoc | C14 | prose-250kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) | — |
| WordCraft | C14 | prose-250kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| canvas-editor + plugin | C14 | prose-500w | presented_frame | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) | — |
| Docen | C14 | prose-500w | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| Docxodus | C14 | prose-500w | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| eigenpal | C14 | prose-500w | presented_frame | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) | — |
| Folio | C14 | prose-500w | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| GenOffice | C14 | prose-500w | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| Plate.js | C14 | prose-500w | presented_frame | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) | — |
| SuperDoc | C14 | prose-500w | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| WordCraft | C14 | prose-500w | presented_frame | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) | — |
| canvas-editor + plugin | C14 | prose-500w | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) | — |
| Docen | C14 | prose-500w | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) | — |
| Docxodus | C14 | prose-500w | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) | — |
| eigenpal | C14 | prose-500w | usable_no_damage | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| Folio | C14 | prose-500w | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) | — |
| GenOffice | C14 | prose-500w | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) | — |
| Plate.js | C14 | prose-500w | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) | — |
| SuperDoc | C14 | prose-500w | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) | — |
| WordCraft | C14 | prose-500w | usable_no_damage | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| canvas-editor + plugin | C14 | prose-50kw | presented_frame | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) | — |
| Docen | C14 | prose-50kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| Docxodus | C14 | prose-50kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| eigenpal | C14 | prose-50kw | presented_frame | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) | — |
| Folio | C14 | prose-50kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| GenOffice | C14 | prose-50kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| Plate.js | C14 | prose-50kw | presented_frame | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) | — |
| SuperDoc | C14 | prose-50kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| WordCraft | C14 | prose-50kw | presented_frame | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) | — |
| canvas-editor + plugin | C14 | prose-50kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) | — |
| Docen | C14 | prose-50kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) | — |
| Docxodus | C14 | prose-50kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) | — |
| eigenpal | C14 | prose-50kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| Folio | C14 | prose-50kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) | — |
| GenOffice | C14 | prose-50kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) | — |
| Plate.js | C14 | prose-50kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) | — |
| SuperDoc | C14 | prose-50kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) | — |
| WordCraft | C14 | prose-50kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| canvas-editor + plugin | C14 | prose-5kw | presented_frame | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) | — |
| Docen | C14 | prose-5kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| Docxodus | C14 | prose-5kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| eigenpal | C14 | prose-5kw | presented_frame | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) | — |
| Folio | C14 | prose-5kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| GenOffice | C14 | prose-5kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| Plate.js | C14 | prose-5kw | presented_frame | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) | — |
| SuperDoc | C14 | prose-5kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| WordCraft | C14 | prose-5kw | presented_frame | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) | — |
| canvas-editor + plugin | C14 | prose-5kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) | — |
| Docen | C14 | prose-5kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) | — |
| Docxodus | C14 | prose-5kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) | — |
| eigenpal | C14 | prose-5kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| Folio | C14 | prose-5kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) | — |
| GenOffice | C14 | prose-5kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) | — |
| Plate.js | C14 | prose-5kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) | — |
| SuperDoc | C14 | prose-5kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) | — |
| WordCraft | C14 | prose-5kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| canvas-editor + plugin | C15 | micro-search | first_match | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| Docen | C15 | micro-search | first_match | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| Docxodus | C15 | micro-search | first_match | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| eigenpal | C15 | micro-search | first_match | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| Folio | C15 | micro-search | first_match | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| GenOffice | C15 | micro-search | first_match | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| Plate.js | C15 | micro-search | first_match | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| SuperDoc | C15 | micro-search | first_match | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| WordCraft | C15 | micro-search | first_match | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| canvas-editor + plugin | C15 | micro-search | index_quiescence | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| Docen | C15 | micro-search | index_quiescence | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| Docxodus | C15 | micro-search | index_quiescence | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| eigenpal | C15 | micro-search | index_quiescence | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| Folio | C15 | micro-search | index_quiescence | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| GenOffice | C15 | micro-search | index_quiescence | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| Plate.js | C15 | micro-search | index_quiescence | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| SuperDoc | C15 | micro-search | index_quiescence | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| WordCraft | C15 | micro-search | index_quiescence | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| canvas-editor + plugin | C15 | micro-search | replace_all | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| Docen | C15 | micro-search | replace_all | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| Docxodus | C15 | micro-search | replace_all | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| eigenpal | C15 | micro-search | replace_all | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| Folio | C15 | micro-search | replace_all | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| GenOffice | C15 | micro-search | replace_all | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| Plate.js | C15 | micro-search | replace_all | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| SuperDoc | C15 | micro-search | replace_all | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| WordCraft | C15 | micro-search | replace_all | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| canvas-editor + plugin | C15 | micro-search | search_complete | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| Docen | C15 | micro-search | search_complete | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| Docxodus | C15 | micro-search | search_complete | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| eigenpal | C15 | micro-search | search_complete | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| Folio | C15 | micro-search | search_complete | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| GenOffice | C15 | micro-search | search_complete | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| Plate.js | C15 | micro-search | search_complete | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| SuperDoc | C15 | micro-search | search_complete | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| WordCraft | C15 | micro-search | search_complete | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| canvas-editor + plugin | C17 | complex-corpus | after_edit_burst | first: not enough samples (n = 0 of 10; reasons editor_crash: 10); second: not enough samples (n = 0 of 10; reasons editor_crash: 10) | — |
| canvas-editor + plugin | C17 | complex-corpus | quiescent | first: not enough samples (n = 0 of 10; reasons editor_crash: 10); second: not enough samples (n = 0 of 10; reasons editor_crash: 10) | — |
| canvas-editor + plugin | C17 | complex-corpus | ready | first: not enough samples (n = 0 of 10; reasons editor_crash: 10); second: not enough samples (n = 0 of 10; reasons editor_crash: 10) | — |
| canvas-editor + plugin | C17 | prose-250kw | after_edit_burst | first: not enough samples (n = 0 of 10; reasons editor_crash: 4; editor_timeout: 6); second: not enough samples (n = 0 of 10; reasons editor_crash: 3; editor_timeout: 7) | — |
| Docen | C17 | prose-250kw | after_edit_burst | first: not enough samples (n = 0 of 10; reasons editor_timeout: 10); second: not enough samples (n = 0 of 10; reasons editor_timeout: 10) | — |
| canvas-editor + plugin | C17 | prose-250kw | quiescent | first: not enough samples (n = 0 of 10; reasons editor_crash: 4; editor_timeout: 6); second: not enough samples (n = 0 of 10; reasons editor_crash: 3; editor_timeout: 7) | — |
| Docen | C17 | prose-250kw | quiescent | first: not enough samples (n = 0 of 10; reasons editor_timeout: 10); second: not enough samples (n = 0 of 10; reasons editor_timeout: 10) | — |
| canvas-editor + plugin | C17 | prose-250kw | ready | first: not enough samples (n = 0 of 10; reasons editor_crash: 4; editor_timeout: 6); second: not enough samples (n = 0 of 10; reasons editor_crash: 3; editor_timeout: 7) | — |
| Docen | C17 | prose-250kw | ready | first: not enough samples (n = 0 of 10; reasons editor_timeout: 10); second: not enough samples (n = 0 of 10; reasons editor_timeout: 10) | — |
| GenOffice | C17 | prose-250kw | ready | 1304973312.0 bytes | 1168482304.0 bytes |
| canvas-editor + plugin | C19 | complex-corpus | — | first: not enough samples (n = 0 of 10; reasons editor_crash: 10); second: not enough samples (n = 0 of 10; reasons editor_crash: 10) | — |
| canvas-editor + plugin | C19 | prose-250kw | — | first: not enough samples (n = 0 of 10; reasons editor_crash: 4; editor_timeout: 6); second: not enough samples (n = 0 of 10; reasons editor_crash: 3; editor_timeout: 7) | — |
| Docen | C19 | prose-250kw | — | first: not enough samples (n = 0 of 10; reasons editor_timeout: 10); second: not enough samples (n = 0 of 10; reasons editor_timeout: 10) | — |

## How to reproduce

See perf/container/README.md.

## DOCX verification

The DOCX twin is a deliverable of the release gate: `build/verify_publication.sh --with-word` opens it in Microsoft Word and fails on any warning or offer to repair the file.
