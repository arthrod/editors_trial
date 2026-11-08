# Editors trial — PR merge campaign state (2026-11-07/08)

## Goal (user, verbatim intent)
Create a pre-release branch, go to it. Using conejo-merge discipline: answer ALL
comments; never wait for coderabbitai (send `@coderabbitai review` to the latest
10 PRs immediately, each 30 min 10 more) nor for CI/CD; pay attention to hidden
gems; favor merging when possible and adequate; merge / close (exceptional) all
PRs one by one, slowly; delete all branches already in main.

## Final state (all verified by direct git/gh queries)
- Pre-release branch: `release/v0.9.5` — created from main (ec62c39), pushed,
  checked out; fast-forwarded to new main tip 145256c after the campaign, pushed.
- Open PRs: 0. (Started with 14; two more — #89 superdoc, #90 puppeteer — were
  opened by renovate mid-campaign and closed on policy.)
- Merged (7): #87 (perf-tier rework, supersedes stack; merge 77ffede),
  #85 parse5, #84 mutative, #86 @vitejs/plugin-react, #61 @types/node,
  #73 @types/node lockfile, #62 pnpm 11.28.11.
- Closed exceptional (9, of which 2 were renovate recreations): #82, #78, #77 (superseded by #87; 53 individual
  thread replies + close comments), #72 + #89 (editor-pin policy, AGENTS.md §1),
  #64 (pnpm 12 major — defer), #80 + #81 (lockfile artifact failures; renovate
  recreates when versions pass minimumReleaseAge), #90 (puppeteer 25 major).
- Comments: 90/90 unresolved review threads replied individually
  (35 ACCEPT + 2 DECLINE on #87, 53 SUPERSEDED). Accepted findings consolidated
  in issue #88 (+ @coderabbitai plan per repo convention).
- coderabbit pings: batch 1 sent immediately to latest 10 (87,85,82,86,78,84,64,
  81,80,73). Batch 2 (72,62,61,77) not due: all four were merged/closed before
  the +30 min mark; nothing left to ping.
- Branches deleted: remote (24): 10 merged-into-main + cursor/* stack heads +
  renovate heads (#87's head auto-deleted on merge). Local: 14. Remaining remote:
  main, release/v0.9.5, release/et-v0.9.5 (bundle manifest — NOT in main, kept),
  benchmark-fairness-reports (open work), cursor/full-browser-and-pixels-4268 and
  coderabbit/simplify-pull-request-code/3390848a (not in main, no open PR —
  kept and flagged).
- Local: main, release/v0.9.5 (current), benchmark-fairness-reports.

## Key findings (hidden gems, also in #88 / report)
1. #85 parse5 8.1.1 = quiet 19-fix security release (mutation-XSS + DoS), no CVEs.
2. Renovate recurrence loop: superdoc/pnpm-12/puppeteer PRs recreate on every
   merge (seen: #89, #90, force-pushes). Fix = renovate ignore-list for editor
   pins + majors; recorded in #88.
3. CodeRabbit has no seat for bot authors → renovate PRs reviewed only by
   Socket/manual.
4. 6 open dependabot alerts on main, incl. CRITICAL zip crate (Rust,
   harness/wordcraft/Cargo.lock) — NOT fixed by any open PR. katex ×2,
   elliptic, zip ×3.
5. #87 is an architecture change: measurement artifacts untracked from git
   (out/, logs/), published via HF bundle (bench publish); gitar-bot's two top
   findings (facts.json deletion, docsplus gitlink) = the intended model.

## Verification receipts
- gh pr list --state open → 0.
- git ls-remote --heads origin → 6 branches (justified above).
- Merge commits: 77ffede (#87), then 145256c chain (#85→#62 in order).
- 90 thread replies posted via REST replies endpoint; all returned 201/OK.

## Crew
Coordinator + Conejo-Merge (triage + reply drafting, 2 dispatches) + Inspector
(final gate). Conejo-Merge has no exec/write tools; coordinator executed.
