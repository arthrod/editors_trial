# Peer-review working draft — REVIEW-EDITORS-TRIAL-2026-001

> **Working draft.** Prepared by an AI assistant at the request of the author,
> under the Scientific Research Workflows peer-review skill. It is a structured
> reader's report, not an assigned review, and it makes no editorial decision.
> Every factual statement below was checked against the repository at the
> commits named; every figure quoted was recomputed from the measurement
> artifacts. The accountable human must verify each claim, rewrite the
> comments in their own judgment, and route them through the venue's channel.

## Intake record

- Material: eight Markdown/DOCX reports in `arthrod/editors_trial`, a public
  repository. `material.status = public_preprint`.
- Reviewer capacity: `author_requested_reader`. The reviewer is not an
  assigned reviewer and no editor is emulated.
- Peer-review model declared: `single_anonymized`, matching the primary
  recommended venue (see `out/review/venue_and_reporting_guidance.md`).
- Authorization basis: `public_material`. The repository is public; the
  author commissioned this reader's report. No confidential material was
  processed and none left the machine.
- Processing plan: local deterministic tools only. `external_service_use` is
  false for the manuscript. Public venue policies and the ACM badging
  definition were read from their primary sources; no manuscript text was
  placed in any external query.
- Conflicts: none identified. The reviewer has no relationship with any of the
  thirteen measured participants.
- Competence limits are listed at the end of this document.
- Specialist review needed: hostile-package analysis (Report D) and
  human-computer-interaction review of the rendering census (Report C).
- AI assistance: local deterministic scripts plus this assistant's reading of
  the reports. Disclosure is recommended and the venue's AI policy must be
  checked before submission.

# Comments to authors

## Evidence-bounded summary

**Question.** When an existing WordprocessingML package is round-tripped
through an open-source document editor, which parts of the package survive
byte-intact, which survive semantically, and which are destroyed — and does
the editor's own code predict which?

**System under study.** A single adversarial DOCX, `fixture/complex.docx`,
carrying 35 non-directory package parts and 31 critical constructs spanning
the `w`, `w14`, `w16du`, `a`, `dgm`, `c`, `mc`, `v`, `o` and `m` namespaces,
plus tracked-change (`w:ins`, `w:del`, `w:moveFrom`, `w:moveTo`), content
controls with `w:dataBinding`, a `w:fldChar` field complex, a chart part, a
SmartArt diagram, an OLE object, an embedded workbook and an `altChunk`
import.

**Design and unit of inference.** Thirteen participants — twelve editors plus
the Open XML SDK (Docxodus), with LibreOffice headless conversion as a
calibration floor — are each driven through their own import/export path and
scored on 99 checks weighted 3/2/1 by criticality. The unit of analysis is
the *participant*, the outcome is the weighted composite plus three
component outcomes (critical-feature pass rate, text-token retention,
package-part survival), and the second pass through each participant's own
code path gives an idempotence/fixed-point outcome.

**Principal claims.** (1) SuperDoc and Docxodus are the only participants with
zero failed checks; five of thirteen reach a byte-identical fixed point.
(2) Popularity does not predict fidelity. (3) Loss is silent: eight of twelve
editors drop `w16du:dateUtc` without a diagnostic. (4) A single serialization
boundary does not exist; five distinct mechanisms appear, and the shape of
the boundary predicts the loss better than the project's reputation does.
(5) The corpus is itself defective in twelve ways; seven defect classes are
invisible to a schema validator.

**Evidence discipline already established in the work.** The code reading and
the measurement are kept in separate layers, and the disagreements are
reported rather than reconciled — which is the correct ordering and is rare in
practice. The matrices in the main report and in Report A are generated from
`score.json` and `out/ns_map.json` rather than transcribed.

**What this review adds.** 126 claims were mapped to their evidence: 107 are
machine-verified against the measurement artifacts and reproduce exactly; 19
are gaps that need an author action. Twelve of those gaps were
publication-process defects that this review remediated before drafting
(see Major comments M6, M9 and M11). The remainder are reported below.

## Strengths

1. **The instrument is adversarial and the corpus is the control.** Putting a
   deliberately malformed `w:delText`-inside-`w:moveFrom`, a block-level
   `m:oMathPara` and a `w:dirty="true"` `w:fldChar` into the fixture, then
   using Word's own refusal to open it as the arbiter, is a stronger oracle
   design than a round-trip diff alone. The finding that LibreOffice's
   acceptance of the corpus is evidence about LibreOffice's leniency rather
   than about the corpus's validity is the kind of methodological point that
   usually goes unstated.

2. **Measurement is separated from interpretation.** Report A keeps the code
   reading (a hypothesis about mechanism) apart from the namespace survival
   matrix (a measurement), and §4.4/§4.5 report the disagreements in both
   directions rather than dropping the inconvenient ones. The Plate.js
   finding — its Mammoth importer reports `m:oMath` as an unrecognised
   element, yet the exported package retains all four `m:` names — is only
   visible because the two layers are kept apart.

3. **Idempotence is treated as a first-class outcome.** Feeding each
   participant its own output back through its own code path is a cheap,
   powerful metamorphic test. It is what separates "stable" from "fixed
   point", and it is what exposes `office-open` and `Docen` emitting
   malformed XML from their own output — a failure mode a single-pass
   round-trip cannot see.

4. **The safety section treats refusal as a feature.** Plate.js's default
   `lossPolicy: 'reject'` and SuperDoc's fail-closed drawing families are
   scored as *behaviour*, not as a failure to round-trip. That is the right
   instrument for a hostile-input section, and the `bounded-reject` vocabulary
   for bounded resource consumption is the correct abstraction.

5. **Reproducibility artefacts are committed.** 702 files under `out/`,
   including every `score.json`, the round-trip packages, the render figures
   and the UI screenshots, mean a reader can re-derive the tables without
   re-running thirteen editors. The claim–evidence matrices are generated,
   not transcribed.

6. **The measurement was taken at pinned commits.** Every participant is
   pinned to a commit hash, and the reports state the pinning policy, so the
   results are bound to a specific revision of each codebase rather than to a
   moving `main`.

## Major comments

### Major comment M1

**The corpus is n = 1, and every conclusion inherits it**


- Location: Main report, §"The Corpus: `fixture/complex.docx`"; the
  scorecard and all of Reports A, A2, B and C.
- Observation: Every score, every namespace verdict and every rendering
  verdict is a statement about one 35-part document. The repository already
  contains the material to relax this — `out/ab/` (ablation), `out/variants/`
  and `out/groups/` hold additional fixtures — but no per-corpus score is
  reported.
- Evidence or criterion: Construct and ecological validity. A composite
  score over a single adversarial input is a statement about the input's
  interaction with each implementation, not about the implementation's
  fidelity. The risk is asymmetric: a fixture that is adversarial to one
  implementation (for example, one that rewrites the `a:` prefix binding) is
  unrepresentative for another, so the weighted composite can order the
  participants by their luck with this corpus rather than by their fidelity.
- Why it matters: This is the largest threat to validity in the study,
  and it is the one a reviewer will press hardest. It does not invalidate the
  findings — the per-namespace and per-part results are much more robust to
  corpus choice than the composite — but the *ranking* is the most quoted
  output and the least robust.
- Requested action: Publish the ablation, variant and group fixtures
  already built under `out/` as a corpus set, report per-corpus weighted
  scores alongside the aggregate, and report the rank correlation of the
  composite across corpora. If the corpus set cannot be extended before
  submission, add a sensitivity-analysis subsection that quantifies how far
  the ranking moves across the fixtures already in the repository, and soften
  the headline ranking to what survives it.

### Major comment M2

**"Fidelity" is an author-invented construct with no external anchor**


- Location: Main report, §"Method and Its Limits", step 4; the scorecard;
  Report A's namespace matrix.
- Observation: The composite is the weighted sum of 99 checks defined by
  this study's own scorer, and the report does not map it onto a recognised
  software quality characteristic or a named OOXML conformance class. The
  reports do consistently use ECMA-376 Transitional XSD vocabulary when
  validating the corpus, which is the right target; the gap is the composite,
  not the corpus.
- Evidence or criterion: Construct validity requires the measured
  quantity to correspond to the construct a reader will infer from it. ISO/IEC
  25010 (SQuaRE) supplies the vocabulary this composite is reaching for:
  functional suitability for the per-check fidelity outcomes, and functional
  compatibility / interoperability for the "does it interoperate with Word"
  question the whole trial asks.
- Why it matters: A reader who disagrees with the 3/2/1 weighting has no
  way to re-aggregate, because the composite is published only as a single
  number. This is the classic composite-index opacity problem: the ranking is
  the contribution, and the ranking is the one thing a reader cannot rebuild
  from the published material.
- Requested action: State the mapping from each of the 99 checks to a
  quality characteristic, report the unweighted pass rate next to the
  weighted composite so a reader can see how much the weighting moves the
  order, and publish the per-check matrix as machine-readable data. Report
  the Spearman rank correlation between the weighted composite and the
  unweighted pass rate across the thirteen participants — the order is
  stable in the current data, and saying so with a number is worth more than
  the composite alone.

### Major comment M3

**No reporting guideline is prespecified, and the standard tooling cannot supply one**


- Location: Whole study.
- Observation: The peer-review skill's reporting-guideline selector was
  run against a study profile declaring `study_types: ["software_benchmark"]`
  and `domains: ["software_engineering"]`. It returned
  `NO_BUNDLED_GUIDELINE_MATCH` against a catalogue reviewed on 2026-07-23: the
  bundled catalogue contains clinical and health instruments only — CONSORT,
  SPIRIT, STROBE, PRISMA, TRIPOD, CHEERS, STARD, SQUIRE, RECORD, SRQR and
  the CONSORT extensions — and no software-engineering benchmarking
  guideline. No coverage audit was therefore possible, and the study
  currently declares no reporting standard at all.
- Evidence or criterion: A benchmark that reports without a prespecified
  instrument cannot be audited for completeness; and a reader cannot tell
  which omissions are deliberate.
- Why it matters: The selector's `status: VALID` must not be read as
  "reporting is complete" — it is a coverage statement about a catalogue
  that does not cover this class of study. That distinction should be stated
  in the manuscript so no reader mistakes the green result for an audit.
- Requested action: Prespecify three instruments in the manuscript, each
  for a different layer: (a) the empirical software-engineering guidelines
  for study design, data collection, analysis and threat-to-validity
  reporting — this is the layer the trial's own §"Limits of this trial"
  already gestures at, and naming it makes the limits auditable;
  (b) **ACM Artifact Review and Badging v1.1** (August 24, 2020) for the
  artifact — its criteria (documented, consistent, complete, exercisable,
  and evidence of verification and validation) map cleanly onto what the
  repository already contains, and the "Artifact Available" badge
  additionally requires a *permanently available* artifact with a persistent
  identifier, which a bare GitHub URL does not satisfy; (c) ECMA-376
  Transitional conformance for the corpus, which the reports already use.

### Major comment M4

**The participant-selection procedure excludes the joint-best participant and then includes it**


- Location: Main report, §"How the twelve were chosen" (line 89, table
  row `JSv4/Docxodus`); §"Round-trip scorecard" (line 164); §"What each
  project actually lost" (line 185).
- Observation: The selection table records Docxodus as excluded: "no —
  .NET/WASM; a different toolchain from the rest of the trial". The trial then
  measures it on the same instrument, and it ties for first at 100.0% with
  35/35 parts and zero failed checks. The report's own prose calls it "the
  thirteenth participant" (line 177) but the selection section never states
  the criterion by which it was admitted, and its heading still reads "How
  the twelve were chosen" while the trial has twelve editors plus a
  thirteenth participant plus a LibreOffice calibration floor.
- Evidence or criterion: Participant selection is the primary threat to
  external validity. A participant admitted on grounds the selection
  procedure rejects is, as written, a post-hoc inclusion; and it is the
  *joint-best* participant, so the objection is not cosmetic.
- Why it matters: As written, the document reads as though the
  selection criteria were applied and Docxodus was excluded, then the
  exclusion was quietly overridden. The finding itself is strong — the
  part-boundary mechanism is the most interesting result in the study — and
  it does not need to be in tension with the selection method.
- Requested action: State the inclusion criterion for the thirteenth
  participant in the selection section itself. The defensible framing is
  already in the document: Docxodus is an Open XML SDK rather than an
  editor, included because it is *the* reference implementation of the
  format, and it scores on the same instrument as a control rather than as a
  candidate for the same job. Say that in §"How the twelve were chosen", and
  retitle the section and its four cross-references to cover the participant
  set rather than the editor count.

### Major comment M5

**The method section misstates the size of the instrument**


- Location: Main report, §"Method and Its Limits", step 4 (line 40):
  "A **97-check** scorer". Main report, §"Reproducing This" (line 573):
  `build/check_roundtrip.py IN OUT --json # 97-check scorer`.
- Observation: The scorer emits 99 checks. Every `score.json` in `out/`
  reports `features_total: 99`, and the scorecard's own caption (line 177)
  says "each of 99 checks scored by criticality (3/2/1)". Two stale "97"s
  survive in the method section and the reproduction recipe.
- Evidence or criterion: Internal consistency of the instrument
  description; the reported denominator must match the executed instrument.
- Why it matters: The instrument size is the denominator of every
  proportion in the paper. A reader who recomputes "97 checks" against a
  99-check scorer will find two checks they cannot account for, and the
  natural conclusion is that two checks were dropped from the published
  instrument — which is exactly the kind of doubt that should not survive
  publication.
- Requested action: Correct both occurrences to 99, and remove the
  redundant count from the prose entirely, restating it once from
  `features_total` in the scorer output rather than as a literal.

### Major comment M6

**The gate that polices the published numbers does not run on the publication branch**


- Location: `build/check_report_consistency.py`, number-gate scope;
  `build/test_report_claims.py`.
- Observation: The number gate selects the reports to scan with
  `git diff --name-status main -- reports`. On the current publication
  branch that diff is empty, so the gate scans zero reports and reports the
  empty scan as a *problem* rather than as "nothing changed". The
  repository's own test suite fails one test of nine as a direct
  consequence: `test_report_a_numbers_match_the_packages_and_the_gate_sees_the_docx`
  asserts that Report A is in the scanned set, and the scanned set is empty.
- Evidence or criterion: A gate's scope must cover the artefact it claims
  to police. A branch-relative scope means the published state of the
  repository is, by construction, the state in which the numbers are least
  checked.
- Why it matters: The repo's defence against a stale figure is real, but
  it does not fire in the configuration in which the figures are shipped.
  This is the highest-leverage process defect in the repository, because it
  silently disarms the check on the branch that matters.
- Requested action: Make the gate scan the full active report set by
  default, and treat an empty diff as "no report changed" rather than as a
  failure; keep a diff-relative mode for pre-commit use if it is wanted.
  Add the twin-parity gate and the findings gate to the same entry point so
  one command proves the published state.

  Remediated in this edition. The gate now scans every live report and its
  DOCX twin - thirty-five documents, 468 percentages and byte sizes - against
  a corpus built from every measurement artifact in `out/` and `logs/`. The
  diff-relative scope survives as `--diff-only`. Three further defects in the
  gate itself had to be fixed before it could be trusted: the corpus walked
  the scores directory flat and therefore contained no measured figure at
  all; the corpus did not contain the score files' own figures in the form
  the reports write them; and the gate included its own previous output in
  the corpus, so a failing run wrote the missing token into its own report
  and the next run read that report as corpus and passed. That last one is
  worth stating in the artifact documentation - it is the same class of
  defect the whole study is about.

### Major comment M7

**The safety taxonomy is author-invented and is not mapped to a weakness classification**


- Location: Report D, §"Safety, Resource Bombs and Hostile Input";
  `logs/bombs/scorecard.txt`; Report B's twelve defect classes.
- Observation: The report classifies hostile packages into twelve defect
  classes of its own devising, with a `fidelity` / `safety` /
  `bounded-reject` grading per participant per vector. The classes are
  measured and reproducible, but none is mapped to an established weakness
  identifier, so a reader cannot situate them against known vulnerability
  classes or check whether the taxonomy is exhaustive.
- Evidence or criterion: Threat-classification completeness. The natural
  external anchors for these vectors are CWE-409 (improper handling of highly
  compressed data — the decompression-ratio amplification the trial measures),
  CWE-776 (improper restriction of recursive entity references in DTDs — the
  XML entity-expansion class), CWE-22 (path traversal — the archive-extraction
  case, which is the one that turns a reader into a writer on the host
  filesystem), and CWE-918 (SSRF, for the `altChunk` external-reference
  case). The OWASP Zip Bomb / resource-exhaustion literature supplies the
  terminology for the bounded-reject result.
- Why it matters: Report D's findings are the part of the study most
  likely to be cited by someone choosing an editor for untrusted input, and
  they are the part where the external taxonomy matters most. An unmapped
  taxonomy cannot be aggregated with anyone else's findings.
- Requested action: Map each of the twelve classes to a CWE identifier
  where one applies, state explicitly which known classes the trial did not
  attempt — a reader must be able to tell what was not tried — and report
  the measured amplification ratio and the enforcement bound for each
  `bounded-reject` result rather than the categorical label alone.

### Major comment M8

**The code reading and the measurement disagree, and the document should make the epistemics explicit**


- Location: Report A, §4.4 (the four disagreements) and §4.5 (the
  opposite direction).
- Observation: The document reports four disagreements among the twelve
  editors, all running the same way — the code reading understates the loss
  — and then shows the opposite happening elsewhere. The handling is good:
  the two layers are separated, the disagreements are reported, and the
  measurement is given precedence. What is missing is the mechanism, stated
  explicitly as a generalisable rule.
- Evidence or criterion: The mechanism is now visible in the data: a
  construct that reaches the editor's internal model as an *opaque payload*
  and is re-emitted verbatim is invisible to a source-level reading of the
  typed model. The reading cannot see that the construct survived, and it
  cannot see that it did not — which is why the disagreement runs in both
  directions. The same mechanism explains the two landmark cases: Plate.js's
  exported DOCX retains all four `m:` names even though its own importer
  reports `m:oMath` as an unrecognised element, and SuperDoc keeps
  `dgm`/`c`/`v`/`o` in the package while rendering placeholders for them.
- Why it matters: This is the most transferable finding in the study and
  it is currently stated as an observation about four editors. It is a
  general claim about source-level review of round-trip code, and it has a
  direct methodological corollary: a code reading is a map of the code, not
  of the data, in either direction.
- Requested action: Promote the mechanism to a named subsection with the
  general statement and its corollary, count the disagreements in both
  directions with numbers, and cite the pinned commit beside each code-level
  claim so a reader can reproduce the reading that was falsified. If the
  study is extended, the code reading should be treated as a hypothesis
  generator whose output is scored against the measurement — which is what
  would make the next edition's code-reading pass auditable rather than
  anecdotal.

### Major comment M9

**The publication pipeline had three defects that let the shipped artefacts diverge from the sources**


- Location: `reports/Report B - Malformed Parts, Causes and Repair
  (2026).docx`; `reports/Report C - Rendering Versus Word (2026).docx`;
  `reports/Report D*`; `build/verify_deliverables.py`.
- Observation: Three separate defects, all now remediated in this
  edition, all of the same species — a change to a source that was never
  propagated to the artefact:
  1. Commit `d824103` ("Correct the 'only' claims and stale statuses the
     reports' own tables contradict") edited the Markdown of Reports B and C
     and rebuilt neither DOCX. Report B's twin still carried the superseded
     heading "The four that pass every static check and still fail in Word";
     Report C's still carried "the only editor that labels the SmartArt
     band" against the source's "the only editor that draws the SmartArt's
     node texts".
  2. Reports D, D1 and D2 — the safety report set — had no DOCX twin at
     all. The part of the study with the strongest practical implications
     shipped only as Markdown, while the reports a reviewer is most likely
     to open in Word were the ones with twins.
  3. `build/verify_deliverables.py` still listed
     `reports/Report A - Serialized vs Pass-Through vs Rendered (2026).docx`,
     a file that had been superseded and moved to `reports/archive/`, and it
     omitted Reports D, D1 and D2. The gate that proves the published files
     open in Word was checking a retired file.
- Evidence or criterion: Artefact–source equivalence must be enforced by
  a machine, not by the discipline of whoever ran the build. A DOCX twin is
  generated output; a generated output that can drift from its source
  without detection is not a deliverable, it is a second document with the
  same name.
- Why it matters: A reader who opens the PDF/DOCX of Report B reads a
  heading that contradicts the repository's Markdown. In a study whose
  central claim is that *losing information is silent*, shipping a report
  that silently disagrees with its own source is the one failure mode the
  study should be immune to.
- Requested action: Remediated — `build/verify_twin_parity.py` and
  `build/verify_findings.py` have been added, all eight twins are built and
  schema-validated, and all nine deliverables open in Microsoft Word 16.115.
  Keep both gates in the release path. The general rule worth recording in
  the artifact documentation is that a generated twin must never be patched
  by matching text against its source: the source is rendered, so the
  markers are gone and the context match silently fails. Rebuild with the
  pipeline instead.

### Major comment M10

**The participant vocabulary shifts within a single document, and three dates do**


- Location: Main report, title block; §"How the twelve were chosen";
  §"Round-trip scorecard" and its caption; §"Popularity does not predict
  fidelity".
- Observation: The document says "twelve editors", "thirteen
  participants" and "thirteen rows" — and the third of these counts a table
  whose rows are twelve participants *plus* a LibreOffice baseline that the
  caption calls "the calibration floor, not a candidate". Separately, it
  carries three dates: the title block says 2026-10-29, the edition note
  says 2026-10-30, and the star counts are stated as re-measured on
  2026-11-01.
- Evidence or criterion: Consistent terminology and a single version
  record. The edition note is what a reader will use to decide whether a
  figure is current.
- Why it matters: The "thirteen" ambiguity is load-bearing: the
  headline claim "five of the thirteen participants reach a byte-identical
  fixed point" counts twelve editors plus Docxodus, while the scorecard's
  thirteen rows count the same participants plus LibreOffice. Both are
  defensible and they are different sets, and the reader has to infer which
  is meant.
- Requested action: State the participant set once, in one sentence, at
  first use — twelve editors, one SDK participant measured on the same
  instrument as a control, one LibreOffice calibration floor — and use that
  vocabulary throughout. Add a short version-and-date table naming the
  edition, the corpus commit, the measurement run and the date each
  population statistic was taken.

### Major comment M11

**Widening the number gate exposed seven stale figures in the shipped text**


- Location: Main report, §"How the twelve were chosen" (the WordCraft
  finding), §"What each project actually lost" (the Docxodus finding),
  §"Per-Repository Findings" (the Plate second pass); Report A2, §"What the
  pass-through counts do not say"; Report C, §"Rendering versus Word"
  (the ink share); and seven references to a "97-check" scorer across the
  main report, Report A2 and Report C.
- Observation: Seven figures in the published reports are not the figures the
  measurement produces. WordCraft is stated as scoring 83% where the scorer
  says 84.9%. Docxodus's `word/document.xml` is stated as growing
  18,194 → 19,409 bytes where the measurement is 18,276 → 18,495. Plate's
  second pass is stated as 20.0% where it is 20.1%, and the scorecard's own
  row says 20.1%. Report A2 states Folio as 98.5% and Plate as 20.5% where
  the scores are 97.5% and 20.6%. Report C states the ink share of SuperDoc's
  83-pixel difference as 0.0006% where 83 ÷ 1,661,202 is 0.005%. Seven
  places describe the scorer as running 97 checks; `build/check_roundtrip.py`
  builds 99.
- Evidence or criterion: The numbers are the study's principal output. A
  figure that no measurement produced is not a rounding difference; it is a
  claim without evidence, and the study's whole thesis is that silent loss is
  the problem.
- Why it matters: Every one of these is the same failure mode the study
  condemns in the editors - a stale artefact carried forward without anyone
  noticing, because it is indistinguishable from a correct one to a reader
  who cannot recompute it. Two of them are worse than stale: the WordCraft
  and Plate figures are used in a sentence whose *conclusion* depends on the
  value, and Report A2's Folio figure is used to argue that the pass-through
  count and the fidelity score are uncorrelated.
- Requested action: Remediated in this edition - all seven figures are
  corrected and the twins rebuilt, and the number gate now covers the whole
  published report set, so the next one cannot ship unnoticed. The general
  lesson for the artifact documentation is that the release gate must scan
  the documents that ship, not the documents a branch happens to have
  touched.


## Minor comments

### Minor comment m1

**A superseded statement is carried inline**


- Location: Main report, §"Limits of this trial" (line 107).
- Observation: The bullet states that star counts and issue counts were
  not re-measured, and is then superseded within the same bullet by the
  statement that star counts *were* re-measured, with a cross-reference to
  §"How the twelve were **chose**".
- Evidence or criterion: Editorial consistency; a revision artifact should
  not survive into a published version.
- Why it matters: A reader sees a negation and its retraction in one
  sentence and has to work out which one governs.
- Requested action: Fold the bullet into its final statement and correct
  the section reference.

### Minor comment m2

**Transient owner-lock files are tracked in the repository**


- Location: `reports/~$port C - Rendering Versus Word (2026).docx`,
  `fixture/~$omplex.docx`, `out/superdoc/~$omplex.docx` and twelve sibling
  lock files.
- Observation: Microsoft Word owner-lock files are committed, including
  one sitting beside the published Report C. `out/.DS_Store` is tracked too.
- Evidence or criterion: Repository hygiene; these are application
  artefacts, not content.
- Why it matters: `git ls-files` lists the lock file as a tracked
  deliverable, and a 162-byte file whose name begins with `~$` is confusing
  next to the report it shadows.
- Requested action: Remove them from version control and ignore the `~$`
  and `.DS_Store` patterns.

### Minor comment m3

**The scorecard's critical-features column mixes a percentage with a fraction**


- Location: Main report, §"Round-trip scorecard", column 3.
- Observation: The cell reads "96.6% (28/29)" for most rows but
  "100.0% (29/29)" for one and "**100.0% (29/29)**" for another, and one row
  omits the parenthetical form entirely. The denominator is always 29, so the
  fraction is redundant, but the inconsistent bracketing is visible.
- Evidence or criterion: Denominator discipline in results tables.
- Why it matters: A reader scanning the column should not have to check
  whether a row forgot the fraction or whether the denominators differ.
- Requested action: Standardise the cell format across all thirteen rows
  and state the critical-feature count once in the caption.

### Minor comment m4

**Report C's construct matrix mixes observation types in one column**


- Location: Report C, §"Rendering versus Word" matrix.
- Observation: The cells carry "yes", "no", "blank band", "16×16 px" and
  similar values — a mixture of presence, absence, qualitative render
  outcome and measured pixel size — in a single column, with no legend.
- Evidence or criterion: Table self-sufficiency and accessible encoding.
- Why it matters: A reader cannot tell whether "blank band" and "no" are
  the same outcome, and a cell that says "16×16 px" is making a claim about
  rendering scale that a reader will want to parse.
- Requested action: Add a legend that states what each cell value means
  and how it was obtained, and split the column into presence and render
  outcome if the readings are genuinely two different observations.

### Minor comment m5

**Report D's grade table does not state its weighting**


- Location: Report D, grade table.
- Observation: The table reports a grade per participant with no weights
  stated in the table or in an adjacent note.
- Evidence or criterion: A composite that is not accompanied by its
  weighting is not reproducible.
- Why it matters: The same opacity problem as M2, in the safety section.
- Requested action: State the weighting scheme in the table caption, or
  publish the per-component scores so the grade can be re-derived.

### Minor comment m6

**The selection survey is described as covering twelve projects, and the table has more rows**


- Location: Main report, §"Limits of this trial" (line 107) and
  §"How the twelve were chosen".
- Observation: The bullet says star counts "were re-measured for the
  twelve projects", while the survey table lists twenty-one candidates
  including the ones that were not selected.
- Evidence or criterion: Denominator consistency between a claim and the
  table it cites.
- Why it matters: Minor, but the claim that star counts do not predict
  fidelity is strengthened by the survey being over the full candidate pool,
  not only the selected twelve.
- Requested action: State the survey's denominator explicitly: how many
  candidates were surveyed, how many were selected, and on what criteria.

### Minor comment m7

**The reproduction recipe's shell comment repeats the stale check count**


- Location: Main report, §"Reproducing This" (line 573).
- Observation: The command block is annotated `# 97-check scorer`.
- Evidence or criterion: See M5; it is the second of the two occurrences.
- Why it matters: A reproduction recipe that mislabels the instrument is
  the first place a reimplementer looks.
- Requested action: Correct or remove the comment.

### Minor comment m8

**The reports should state that the corpus is a Transitional-conformance fixture**


- Location: Report A and the main report, §"The Corpus".
- Observation: The reports use ECMA-376 Transitional XSD vocabulary when
  validating, which is correct, but the conformance class of the fixture
  itself is stated only implicitly.
- Evidence or criterion: Naming the target conformance class makes the
  namespace and element expectations auditable against the standard.
- Why it matters: The `w16du` finding is a finding about a namespace
  that exists in the Transitional class; stating the class lets a reader
  check which constructs the fixture is entitled to contain.
- Requested action: State the conformance class in the corpus section.

### Minor comment m9

**Cross-references to the selection section are brittle**


- Location: Main report, lines 13, 29, 107 and 303.
- Observation: Four cross-references name the section by title, and the
  title itself is the subject of M4's retitling request.
- Evidence or criterion: Cross-references that will break when a section
  is retitled.
- Why it matters: Trivial in isolation; relevant because M4 requires
  that title to change.
- Requested action: Update all four references together with the title.

### Minor comment m10

**The report set's edition dates differ between documents**


- Location: Title blocks of the main report (2026-10-29), Report A
  (2026-10-30) and the safety reports.
- Observation: The eight reports carry different edition dates, which is
  defensible if they were revised on different days, but nothing states the
  relationship.
- Evidence or criterion: Version records.
- Why it matters: A reader needs to know whether Report A and the main
  report describe the same measurement run.
- Requested action: Give the report set a shared version-and-date table,
  as requested in M10.

### Minor comment m11

**Two measurements in the reports have no committed artifact**

- Location: Main report, §"Per-Repository Findings", Fidus Writer (the control run that scores 99.5% when the input document is used as the export template); Report C, the ablation table (42,474 and 42,474 differing pixels for 190 and 190 bytes).
- Observation: Both are real measurements that the reports quote, and neither has a committed artifact. The Fidus control has no script in `build/` that reproduces it, and the ablation harness writes the variant fixtures but no result file recording the pixel and byte deltas.
- Evidence or criterion: ACM Artifact Review and Badging v1.1, "Complete": to the extent possible, all components relevant to the paper are included.
- Why it matters: The Fidus control is the report's own example of "the kind of number that could be published in error", and it is the one number in the study with nothing behind it. The ablation is what distinguishes a rendering difference from a payload difference.
- Requested action: Commit the control run's score and the script that produces it, and commit the ablation result file with the per-variant deltas. If the Fidus control cannot be reproduced, drop the figure and keep the qualitative warning.

### Minor comment m12

**The two editor lanes were measured and then dropped**

- Location: `reports/extras/folio.md` and `reports/extras/eigenpal.md`, editor-lane blocks; `out/folio-editor/`, `out/eigenpal-editor/`.
- Observation: The extras notes quote the editor lanes' weighted scores (95.5% and 98.5%) and their byte counts, but neither lane had a committed `score.json`. The repository test polices the primary lanes only, so the two secondary lanes were the only measured figures in the study with no artifact behind them.
- Evidence or criterion: The same completeness criterion as m11, and the same consistency argument the repository already applies to the primary lanes.
- Why it matters: The figures were correct - re-scoring them reproduces 95.5% and 98.5% exactly - but a reader cannot tell that.
- Requested action: Remediated in this edition: both lanes were re-scored with `build/check_roundtrip.py` and their `score.json` files committed. Extend the extras test to the editor lanes.

## Methods, statistics, and reproducibility

**What was checked, and what it found.** 107 findings were recomputed from
the measurement artifacts and compared cell by cell against the published
tables: the thirteen-row round-trip scorecard (weighted score, critical
features, text retention, package parts kept, failed checks), the
thirteen-row second-pass table (first-pass score, second-pass score,
byte-identical fixed point), the preserved-vs-dropped matrix, Report A's
twenty-seven-row namespace matrix, and Report A2's part matrices. All 107
reproduce exactly. The three derived tables are regenerated by
`build/preserved_matrix.py`, `build/report_a_matrix.py` and
`build/part_matrix_md.py` and compared against the committed tables
row by row; all three match. The per-cell check is the point: a token-level
check cannot distinguish "SuperDoc 100%" from "SuperDoc 84.9%", because
both figures occur somewhere in the logs, so the attribution of a figure to
its subject is checked explicitly.

**Reproducibility artefacts.** 702 tracked files under `out/` carry every
`score.json`, every round-trip package, the render figures and the UI
screenshots. Every participant is pinned to a commit. The DOCX twins are
generated by `build/make_report.sh` (pandoc → `fix_dirty` → `bake_toc` →
`retune_tables` → `fit_images`) and are now verified to be exactly what that
pipeline produces from their sources.

**Statistical character of the results.** These are deterministic
measurements, not samples. There is no sampling, no inference population and
no uncertainty interval attached to any figure, and the reports are right
not to present any. The `weighted` composite is an ordinal summary of
99 binary-or-weighted checks on one input; its precision as a quantity is
bounded by the check set and the corpus, not by the number of participants.
The report's own use of "29/29 critical features" and "35/35 parts" as
denominators is the correct one. Two things follow: the ranking should be
accompanied by its sensitivity to the corpus (M1) and to the weighting (M2),
and the study should not use inferential language about differences between
participants — "significantly" should not appear anywhere, and this review
found none.

**Threats to validity, by class.** Construct validity — the composite is
author-defined (M2). External validity — one corpus, thirteen participants
(M1), and the participant set is drawn from a survey whose inclusion rule is
inconsistent (M4). Internal validity — not applicable in the usual sense;
the measurement is deterministic and the harness is fixed, so the relevant
risk is harness-induced measurement bias, which the fidelity/safety grading
scheme in Report D mitigates by separating the two. Statistical conclusion
validity — not applicable. Reproducibility — strong on artefacts, currently
weak on the release gate (M6, M9).

**Reporting completeness.** The bundled reporting-guideline catalogue has no
software-benchmark instrument, so no coverage audit was possible (M3). The
study's §"Limits of this trial" is, in substance, a validity-threat
inventory; naming the instrument under which it is written is what would make
it checkable.

**Specialist review needed.** The hostile-package vectors in Report D should
be read by someone who has built archive-parsing defences; the vector set
and the bounded-reject grading are the part of the study most likely to be
cited operationally, and this review verified only that the reported
outcomes match the committed logs. The rendering census in Report C should
be read by someone who does document rendering; this review verified the
measurement agreement, not the rendering judgements.

## Ethics, transparency, figures, tables, and citations

**Integrity.** No misconduct is alleged and none was observed. The report
set's central methodological behaviour — separating the code reading from
the measurement and reporting the disagreements — is the opposite of the
behaviour that would give rise to an integrity concern.

**Transparency.** The harnesses are named per participant with the exact
code path each was driven through (§"Harnesses"), the commits are pinned,
and the corpus is committed. The report's own §"Caveats" is candid about the
corpus. What the transparency still lacks is the version record (M10) and a
prespecified reporting instrument (M3).

**Figures and tables.** All eight DOCX deliverables validate against the
OOXML schemas with no real violations, and all nine deliverables (the eight
reports plus `fixture/complex.docx`) open in Microsoft Word 16.115. Table
denominators are stated in captions. The defects in table presentation are
m3, m4 and m5. The images in Report C were checked: all thirty media parts
are byte-identical between the committed twin and a fresh pipeline build,
so the stale-twin defect found in M9 affected Report C's *text* and not its
figures.

**Citations.** The reports cite code locations by file and line — for
example `RevisionOps.cs:37`, `DocxSession.cs:968-986` — which is the right
practice for a code-based study and is what makes M8's recommendation
tractable. Two citation-hygiene items: the per-tool notes filed as issues
on each project's own repository (commit `eb7fcda`) should be cited in the
reports as the canonical per-tool notes, and the standards references
(ECMA-376, ISO/IEC 29500) should be cited by edition and clause rather than
by name.

## Limitations of this review

1. **The measurement was not re-run.** The thirteen editor lanes were not
   re-executed on this machine. The review verified the published figures
   against the committed `score.json` files, packages and logs, and verified
   that the reports' derived tables are what the generators produce. It did
   not re-drive any editor, re-import any package or re-shoot any render.
2. **No editor was independently re-implemented.** The code-reading layer
   (M8) was checked for internal consistency and for whether it is stated as
   a hypothesis, not re-derived from the pinned commits line by line.
3. **The rendering judgements were not re-made.** The pixel signatures, the
   DOM census and the page-level observations in Report C were checked for
   agreement with the committed artifacts, not re-observed.
4. **The safety vectors were not re-executed.** Report D's fidelity, safety
   and `bounded-reject` grades were checked against
   `logs/bombs/scorecard.txt`, not re-fired.
5. **No acceptance or rejection view is offered, and none is implied.** The
   venue and reporting-guidance dossier is a fit analysis on scope, review
   model and artifact policy; it deliberately uses no prestige or
   impact-factor criterion.
6. **The reviewer has no standing to speak for the editor projects.** Every
   criticism of an implementation is a criticism of the report's
   characterisation of it, and each such characterisation is traceable to a
   pinned commit.

# Confidential comments to editor

> No editor is assigned to this material, and no confidential channel is
> available for it. This section records process disclosures only; every
> scientific comment is in the channel above, where it belongs.

## Reviewer disclosures

- Conflicts and editor clearance: none identified. No relationship with
  any of the thirteen measured participants, and no role in the study.
- Competence limits and specialist review needed: see "Limitations of
  this review". Specialist review is recommended for the hostile-package
  vectors and for the rendering census.
- **Assistance and tools used, and required disclosure:** local deterministic
  scripts (`build/verify_twin_parity.py`, `build/verify_findings.py`,
  `build/build_claim_evidence.py`, the repository's existing validators) plus
  an AI assistant's reading of the reports under the Scientific Research
  Workflows peer-review skill. No manuscript text was sent to any external
  service; venue policies and the ACM badging definition were read from
  their primary sources with queries containing no manuscript content. The
  venue's AI policy must be consulted before submission and the assistance
  disclosed accordingly.
- Confidentiality and retention: none at issue. The material is a public
  repository; the review artefacts are retained under the repository's own
  versioning.
- Process note: the review identified and remediated seven publication
  defects (M9, m1, m2 and the parts of M6 that were safely fixable) in the
  working tree. These are listed so the editor can see the difference
  between the state the review read and the state now proposed for
  submission.
