# PR Merge Campaign Report — editors_trial, 2026-11-07/08

Crew: Coordinator + **Conejo-Merge** (triage and reply drafting, two dispatches)
+ **Inspector (Completion Skeptic)** (final gate). Conejo-Merge holds no exec
tools in this environment, so the coordinator executed every git/gh action under
its ledger; every verdict and every reply text is Conejo-Merge's.

## 1. Pre-release branch

`release/v0.9.5` — created from `main` (ec62c39), pushed, checked out, and
fast-forwarded to the post-campaign main tip `145256c` at the end. The existing
`et-v0.9.5` tag and `release/et-v0.9.5` branch belong to the published-bundle
series (`bench publish` manifests on HF) and were deliberately left untouched.

## 2. The campaign (started with 14 open PRs; ended with 0)

### Merged — 7 PRs, one by one, merge commits, never waiting on CI/CD
| PR | What | Note |
|---|---|---|
| #87 | Low-resource execution tiers (perf/ package + plans docs) | Verified first: supersedes the #77/#78/#82 stack; deliberately untracks `out/`, `logs/` artifacts in favor of the HF bundle flow (RELEASING.md updated in the same PR). Merge 77ffede. |
| #85 | parse5 8.1.1 | Quiet 19-fix security release (mutation-XSS, script-strip bypass, quadratic DoS), no CVEs. Merged first among deps. |
| #84 | mutative 2.0.2 | Patch fix; Socket 100s. |
| #86 | @vitejs/plugin-react 6.2.1 | Includes refreshInclude/Exclude fix. |
| #61 | @types/node 26.6.6 (demos/docs-plus) | Not a duplicate of #73 — different files. |
| #73 | @types/node 26.6.6 (demos/superdoc lockfile) | Merged after #61. |
| #62 | pnpm 11.28.11 | Patch line; range covers GHSA-xjj6-f33q-929c (undici). |

### Closed exceptionally — 9 PRs (7 originals + 2 renovate recreations), each with a substantive comment
- **#77, #78, #82** — superseded by #87. Every unresolved thread answered with a
  per-thread coverage note (which files of #87 own the concern); the four
  `harness/ui/docxodus/src/main.ts` mark-semantics threads from #82 are *not*
  covered by #87 and were carried into #88 so they are not lost.
- **#72 and #89 (recreated by renovate mid-campaign)** — editor-pin policy:
  pins move only via `build/update_editors.sh` during a release (AGENTS.md §1),
  and the version was younger than the cutoff.
- **#64 and #90 (new)** — major bumps (pnpm 12, puppeteer 25) are environment
  changes needing a full re-measure; deferred to dedicated post-release effort.
- **#80, #81** — renovate lockfile artifact failures; the versions (Nov 5) are
  younger than the repo's `minimumReleaseAge`, which is exactly what the guard
  exists for. Renovate recreates them automatically once mature.

### Comments — 90/90 unresolved review threads answered individually
- #87: 35 ACCEPT (each with a specific technical reply + tracked in #88),
  2 DECLINE (gitar-bot's `out/facts.json` and docsplus-gitlink findings — both
  reflect the intended artifacts-via-bundle rework, not accidents).
- #77/#78/#82: 53 SUPERSEDED replies with per-thread coverage statements.
- Bot status comments (renovate bodies, socket tables, qodo paused, codeant
  skipping, codex billing) required no replies; none were left unanswered.
- Accepted findings consolidated in issue
  [#88](https://github.com/arthrod/editors_trial/issues/88) (ends with
  `@coderabbitai plan` per the repo's issues-first rule).

### CodeRabbit cadence (never waited for)
Batch 1 (`@coderabbitai review`) sent immediately to the latest 10 PRs by
update time: 87, 85, 82, 86, 78, 84, 64, 81, 80, 73. CodeRabbit in fact
reviewed #87 within minutes (33 actionable comments) — all answered before the
merge; nothing was waited on. Batch 2 (72, 62, 61, 77) had no recipients: all
four were merged or closed before the +30 min mark.

## 3. Branches

- Deleted (remote, 24): everything already in main (cherry/pr16-scorer-refs,
  demo-docs, deps/pnpm-5day, fix/deterministic-demo-docs, generated-reports,
  release/v0.9.0–v0.9.4) plus the dead heads of closed PRs (cursor/* stack,
  renovate/*). #87's head was auto-deleted on merge.
- Deleted (local, 14): the same set plus gone-upstream docs branches.
- Remaining remote (6, each justified): `main`, `release/v0.9.5` (pre-release),
  `release/et-v0.9.5` (bundle manifest, **not** in main), `benchmark-fairness-reports`
  (unmerged work), and two flagged keepers not in main with no open PR:
  `cursor/full-browser-and-pixels-4268`, `coderabbit/simplify-pull-request-code/3390848a`.
- Final local: `main`, `release/v0.9.5` (checked out), `benchmark-fairness-reports`.

## 4. Hidden gems (pay-attention items)

1. **parse5 8.1.1 is a quiet security release** — 19 fixes incl. mutation-XSS
   and DoS, no CVEs; worth citing in the changelog's next Measured section.
2. **Renovate recurrence loop** — superdoc / pnpm-12 / puppeteer PRs recreate on
   every merge (observed live: #89, #90, force-pushes). Fix: ignore editor pins
   and majors in renovate config; recorded in #88.
3. **CodeRabbit has no seat for bot authors** — every renovate PR runs without
   CR review (only Socket + manual). Assign a seat or document the policy.
4. **6 open dependabot alerts on main, including a CRITICAL `zip` crate alert**
   (Rust, `harness/wordcraft/Cargo.lock`) plus 2 more zip, 2 katex, 1 elliptic —
   none addressed by any PR we merged or closed.
5. **#87's architecture change itself**: measurement artifacts are now generated
   locally and published via the HF bundle; `out/facts.json` and history live in
   git history and on the Hub, not in the working tree. Fresh checkouts must run
   a measurement (or `bench` fetch) before perf tests pass — ergonomics tracked
   in #88.

## 5. Deviations & judgment calls (stated, not silent)

- Batch-2 pings were not sent: no PR was left open to receive them.
- #80/#81 were closed rather than left open (Conejo-Merge's original verdict was
  WITHHOLD) to reach the user's stated end state of no open PRs; renovate
  recreates them automatically and the close comments say so.
- Bot status comments were not replied to (no question asked, no thread).
- `release/et-v0.9.5`, `benchmark-fairness-reports`, and the two flagged
  branches were kept: they are not "already in main".

Verification receipts: `gh pr list --state open` → 0;
`git ls-remote --heads origin` → the 6 branches above; merge chain ends at
145256c; all 90 reply POSTs returned success. Ledger: `coord/state.md`.
