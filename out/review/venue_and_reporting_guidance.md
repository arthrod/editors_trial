# Venue and reporting-guidance dossier — the editors_trial benchmark

> Prepared 2026-11-01 against the repository at `demo-docs@d8b08a7`.
> Venue policies and the artifact standard were read from their primary
> sources on 2026-11-01. No prestige, impact-factor or citation-count
> criterion was used at any point: the selection is a fit analysis on scope,
> review model, artifact policy and data policy, and nothing else.
> This document makes no publication-readiness judgement and no editorial
> recommendation; the venue choice remains the author's.

## 1. The finding that shapes everything else

The peer-review skill's reporting-guideline selector was run against a
profile for this study:

```json
{"study_types": ["software_benchmark"],
 "report_kind": "results",
 "domains": ["software_engineering"]}
```

Result:

```json
{"selected_guidelines": [], "status": "VALID",
 "warnings": [{"code": "NO_BUNDLED_GUIDELINE_MATCH", "field": "profile.study_types"}]}
```

The bundled catalogue, reviewed 2026-07-23, contains **only** clinical and
health instruments — CONSORT, SPIRIT, STROBE, PRISMA, PRISMA-S, PRISMA-P,
TRIPOD, PRISMA-ScR, CHEERS, STARD, SQUIRE, RECORD, SRQR, and the CONSORT
extensions. There is no software-engineering benchmarking instrument in it.

Two consequences, and the second is the one that matters:

1. **No checklist coverage audit was possible.** The `--coverage` mode of
   the selector cannot be run, so "is this study completely reported?" has no
   instrument to answer it.
2. **`status: VALID` must not be read as "reporting is complete."** It is a
   coverage statement about a catalogue that does not cover this class of
   study. Any manuscript that cites this selector's output as evidence of
   reporting completeness would be making a false claim. The study should
   say plainly that no clinical reporting guideline applies and name the
   instruments it does adopt.

This is not a defect in the study. It is a gap in the tooling that the study
has to fill by prespecifying its own reporting instruments — which is exactly
what review comment M3 asks for.

## 2. Reporting instruments the study should prespecify

Three layers, each for a different part of the work.

### Layer 1 — the study design and its reporting

The empirical software-engineering guidelines (Wohlin and colleagues' series,
"Guidelines for conducting and reporting software engineering empirical
research", and the 2020 Springer volume *A Guide to Advanced Empirical
Software Engineering*) are the field-standard reporting instrument for a
study of this shape. They are what the main report's §"Method and Its
Limits" and §"Limits of this trial" are already written in — case selection,
measures, data collection, analysis, threats to validity — but they are not
named. Naming them converts the limits section from a narrative into an
auditable checklist.

This is also the layer that addresses the study's largest weakness: the
threats-to-validity taxonomy the guidelines require is exactly the framework
that would make the n=1 corpus (review comment M1), the author-defined
composite (M2) and the participant-selection question (M4) legible as
*known, named* threats rather than as concessions scattered through prose.

### Layer 2 — the artifact

**ACM Artifact Review and Badging, Version 1.1 (August 24, 2020)** —
<https://www.acm.org/publications/policies/artifact-review-and-badging-current>

The repository satisfies a good deal of this already, and the criteria map
onto what is there:

| Badging criterion | Status in this repository |
|---|---|
| **Documented** — an inventory of artifacts, sufficient description to exercise them | Partly. `README.md` names the reports, the harnesses and the layout; the harnesses are documented per participant in the main report. The missing piece is a single *artifact inventory* that names every file class a reviewer needs and where it lives. |
| **Consistent** — artifacts are relevant and contribute to the main results | Met. The 99-check scorer, the harness per participant and the corpus generate every headline figure. |
| **Complete** — all components relevant to the paper are included, to the extent possible | Met with one caveat. 702 tracked files under `out/` carry every `score.json`, package, render figure and screenshot. The caveat is that the editors' *own source repositories* are not vendored; they are pinned by commit and cloned on demand, which is the standard practice and should be stated as such rather than left implicit. |
| **Exercisable** — included scripts can be executed and data accessed | Met, subject to the honest caveat that the thirteen editor lanes require network access and each project's toolchain, while the scorer, the matrix generators, the safety harness and the report builders run offline. |
| **Evidence of verification and validation** | Strengthened by this edition: `build/verify_twin_parity.py`, `build/verify_findings.py`, `build/validate_ooxml.py`, `build/verify_deliverables.py` and the existing test suite now form a release gate. |

**"Artifacts Available" needs one thing the repository does not yet have.**
The badge requires that artifacts "have been placed on a publically accessible
archival repository" with "a DOI or link to this repository along with a
unique identifier for the object", and the standard is explicit that
"personal web pages are not acceptable for this purpose" — with publisher,
institutional, figshare and Dryad repositories named as acceptable. A GitHub
URL is a personal or project page, not an archival repository with a declared
plan for permanent accessibility.

**Action:** archive the release (the corpus, the harness, the scorer, the
reports, the committed `out/` measurement set) to Zenodo with a versioned
DOI, and cite that DOI in the manuscript. This is the single highest-value
publication-preparation step left, because it satisfies the artifact
requirement for every venue in the shortlist below at once, and because a
versioned DOI makes the pinned commits citable rather than merely
referenced.

**Terminology, which the study should adopt exactly.** ACM harmonised with
NISO's definitions, and the distinction matters for this study's claims:

- **Repeatability** — same team, same setup: the measurement can be obtained
  repeatedly. *This is what the trial demonstrates.* Its "re-running the
  corpus through the same code path" test is repeatability, not
  reproducibility.
- **Reproducibility** — a different team, same setup, using the author's
  artifacts.
- **Replicability** — a different team, different setup, using artifacts they
  develop independently.

The reports use "reproducible" loosely for what the definitions call
repeatability. Under ACM's vocabulary the strongest claim the trial can make
is **repeatability**, and it should be labelled as such. The venue-facing
language to use is then precise: the artifact is repeatable by the same team,
and reproducible by another team *if and when* someone else runs it — which
is also exactly what "Results Reproduced" (as opposed to "Results
Replicated") would mean if a second team ever does so.

### Layer 3 — the corpus and the standard

**ECMA-376 / ISO/IEC 29500.** The reports already use "ECMA-376 Transitional
XSD" when validating, which is the correct target: the corpus is a
Transitional-conformance fixture, and the `w16du` finding is a finding about
a namespace that exists in that class. Two additions: state the conformance
class of the corpus in the corpus section, and cite the standard by edition
and clause rather than by name.

**ISO/IEC 25010 (SQuaRE).** The trial's composite is named "fidelity" and is
not mapped to a recognised quality characteristic. Mapping the per-check
outcomes onto *functional suitability* (does the editor preserve the
constructs it claims to model) and *functional compatibility* /
*interoperability* (does the output interoperate with Word) would give the
composite an external anchor and a standard vocabulary — and would make the
composite's weighting auditable rather than author-defined. This is review
comment M2.

**CWE for the safety taxonomy.** Report D's twelve defect classes should
carry CWE identifiers — CWE-409 for the compression-amplification class,
CWE-776 for XML entity expansion, CWE-22 for the archive-path-traversal
class, CWE-918 for the `altChunk` external-reference class — and the report
should state which known classes the trial did not attempt. Review comment
M7.

## 3. Venue shortlist, by fit

The criteria used, and only these: **scope fit** (does the venue publish
this kind of work), **review model** (can the study's evidence be reviewed
in the form it takes), **artifact policy** (does the venue support or require
the artifact evaluation the work needs), and **data/code availability policy**
(is a public repository plus an archival DOI acceptable, and is a data/code
statement required). No metric of journal standing was consulted or applied.

### Primary recommendation — *Empirical Software Engineering* (Springer)

- **Scope fit: direct.** The journal's stated scope covers "applied software
  engineering research with a strong empirical component", includes
  "quality assurance" and "dependability analysis" among its topics, and
  explicitly welcomes "papers on the infrastructure for supporting empirical
  research". The trial is a measurement study of a document-processing tool
  class, and its harness and corpus are infrastructure for empirical research
  about that tool class.
- **Review model:** **single-anonymous** — the journal's ethics and
  disclosures page states that research content published in it is peer
  reviewed (single-anonymous).
  <https://link.springer.com/journal/10664/ethics-and-disclosures>
- **Artifact policy:** the journal has run an open-science initiative for
  artifacts connected to its articles, so an artifact statement is an
  established part of its practice rather than an unusual request.
- **Fit caveat:** the journal prefers studies that can be replicated or
  expanded, which raises the bar on exactly the point review comment M1
  makes. Landing the corpus-sensitivity analysis before submission is
  therefore not optional politeness — it is what this venue's readership
  will ask for.

### Alternative A — an ACM venue (for example *ACM DocEng*)

- **Scope fit:** the subject is document engineering, and DocEng is the
  community where OOXML fidelity work belongs.
- **Review model:** double-anonymous, the ACM default.
- **Artifact policy:** strongest of the shortlist. ACM's badging scheme is
  native to it, so the artifact work in §2 pays off directly, and the
  "Results Reproduced" path is a defined route for a second team to take the
  study further.
- **Fit caveat:** proceedings format means a length budget, and the eight
  reports will have to be condensed into one paper. The reports themselves
  remain valuable as a technical-report appendix or as a companion
  repository.

### Alternative B — *Journal of Open Source Software*

- **Scope fit:** for the *harness* as research software, not for the
  findings. The scorer, the corpus generator, the sandbox runner and the
  report builders are exactly the kind of tool JOSS reviews.
- **Review model:** open — a public review thread on the repository, with a
  checklist a reviewer works through.
- **Artifact policy:** requires a tagged release and a DOI-minted archive
  (Zenodo or figshare) — the same archival step §2 asks for.
- **Fit caveat:** a JOSS paper documents the software; it does not report
  the benchmark results. The two are complementary, not alternatives, and
  running them in sequence gives the study both a citable artifact and a
  citable result.

### Alternative C — preprint plus archival DOI, no formal review

- **Scope fit:** total. arXiv `cs.SE` (or a Zenodo concept DOI) accepts the
  report set as-is.
- **Review model:** none — the review is by readers.
- **Why it is worth doing anyway:** it establishes priority and it forces the
  archival DOI, which every other option on this list needs. It is also the
  cheapest way to get the eight reports into circulation, and the reports
  are already in publication form.

## 4. The recommended sequence

1. **Archive.** Deposit the release in Zenodo with a versioned DOI. This
   satisfies ACM's "Artifacts Available" requirement and JOSS's release
   requirement, and every venue option inherits it.
2. **Fix the reporting instrument.** Prespecify the three layers in §2 in the
   manuscript. Add the artifact inventory the badging "Documented" criterion
   asks for.
3. **Close the findings that change a claim.** Review comments M1 (corpus
   sensitivity), M2 (composite's external anchor and weighting
   transparency), M4 (participant selection), M5 (the stale check count) and
   M7 (CWE mapping) are the ones that change what the paper can claim. The
   other comments change presentation and process.
4. **Submit the preprint.** arXiv `cs.SE` with the Zenodo DOI. The eight
   reports go out as they are.
5. **Submit the manuscript** to *Empirical Software Engineering*, with the
   artifact statement and the data/code availability statement pointing at
   the DOI. If the condensed form does not fit EMSE's format, *ACM DocEng*
   is the alternative that makes the artifact badges worth having.

## 5. What is still the author's decision

- **The venue.** The fit analysis above supports EMSE as the primary
  choice and names two credible alternatives. Only the author can weigh
  against their own priorities, and the choice does not block steps 1–4.
- **Whether to submit the eight reports as a report set** rather than
  condensing them into one paper. The reports are already in publication
  form and a preprint carries them as-is; the condensation is a separate
  piece of work that belongs to whichever venue is chosen.
- **Whether to run the corpus-sensitivity analysis** before submission
  rather than in a later revision. M1 is the strongest argument for doing it
  first, and the fixtures it needs are already built.
- **The AI-assistance disclosure.** This review used an AI assistant with
  local deterministic tooling. The venue's AI policy governs what must be
  disclosed and in what form; the disclosure drafted in
  `out/review/review_draft.md` is a starting point and must be checked
  against the chosen venue's policy.

## 6. Sources

- ACM Artifact Review and Badging, Version 1.1, August 24, 2020 —
  <https://www.acm.org/publications/policies/artifact-review-and-badging-current>
  (read 2026-11-01: badge criteria, the archival-repository requirement
  including the exclusion of personal web pages, and the
  repeatability/reproducibility/replicability definitions harmonised with
  NISO)
- *Empirical Software Engineering*, aims and scope —
  <https://link.springer.com/journal/10664/aims-and-scope> (read 2026-11-01:
  scope including infrastructure for empirical research; preference for
  replicable studies)
- *Empirical Software Engineering*, ethics and disclosures —
  <https://link.springer.com/journal/10664/ethics-and-disclosures>
  (read 2026-11-01: peer review is single-anonymous)
- *Journal of Open Source Software*, reviewer guidelines and review process —
  <https://joss.readthedocs.io/> (read 2026-11-01: open review on the
  repository, checklist-driven, tagged release with a DOI-minted archive)
- Local reporting-guideline selector, run against
  `out/review/study_profile.json` — `NO_BUNDLED_GUIDELINE_MATCH`, catalogue
  reviewed 2026-07-23
