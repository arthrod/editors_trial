#!/usr/bin/env python3
"""
Build the complete claim-evidence matrix for the benchmark reports.

Two kinds of claim enter the matrix, and the difference matters:

  MEASURED claims come from the findings ledger that build/verify_findings.py
  writes. Each one is a figure the reports state and the artifact that
  produced it. Their support level is derived by recomputation, not asserted.

  REVIEW findings are the gaps this review identified in the reports, the
  gates and the repository. They are declared here in one place, with the
  evidence that exposes them and the action each one needs.

The matrix is complete over the finding set: every machine-checked finding in
the scorecard, the idempotence table and the three derived matrices, plus
every gap the review found. It is not a sample.

Usage:
    python3 build/build_claim_evidence.py --ledger out/findings_ledger.csv \\
        --out out/review/claim_evidence_matrix.csv
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FIELDS = [
    "claim_id",
    "location",
    "claim_type",
    "claim_summary",
    "evidence_ids",
    "support_level",
    "alignment_issue",
    "limitation",
    "requested_action",
]

# The metric in the ledger decides the claim type. A weighted score is the
# primary outcome of the trial; a byte-identical second pass is a
# reproducibility claim; a regenerated table is a primary outcome that
# happens to be stated as a grid.
CLAIM_TYPES = {
    "weighted": "primary_outcome",
    "critical": "primary_outcome",
    "text": "secondary_outcome",
    "parts kept": "secondary_outcome",
    "failed checks": "secondary_outcome",
    "first pass": "methods",
    "second pass": "methods",
    "byte-identical": "methods",
    "table equality": "primary_outcome",
}

EVIDENCE = {
    "weighted": "EV:score.json",
    "critical": "EV:score.json",
    "text": "EV:score.json",
    "parts kept": "EV:package-entries",
    "failed checks": "EV:score.json",
    "first pass": "EV:score.json",
    "second pass": "EV:second-score.json",
    "byte-identical": "EV:package-bytes",
    "table equality": "EV:derived-matrix",
}

# Gaps this review found. Each one names the evidence that exposes it and
# the action that closes it. The remediation state is stated, so a reader can
# tell an open finding from a closed one.
REVIEW_FINDINGS = [
    {
        "claim_id": "RVW-001",
        "location": "Main report, Method and Its Limits, step 4 (line 40); "
                    "Reproducing This (line 573)",
        "claim_type": "methods",
        "claim_summary": "The method section states a 97-check scorer and the "
                         "reproduction command is annotated '# 97-check "
                         "scorer', while the scorer implements 99 checks "
                         "(features_total=99 in every score.json) and every "
                         "other mention in the report says 99.",
        "evidence_ids": "EV:out-superdoc-score.json;EV:scorer-check-count",
        "support_level": "unsupported",
        "alignment_issue": "magnitude",
        "note": (
            "The stated instrument size disagrees with the  instrument: two stale 97s survive in the method  section and the reproduction recipe."
        ),
        "limitation": "",
        "requested_action": "Correct both occurrences to 99 and state the "
                            "check count once, sourced from the scorer, "
                            "rather than restating it in prose.",
    },
    {
        "claim_id": "RVW-002",
        "location": "Main report, How the twelve were chosen, selection table "
                    "(line 89) against the round-trip scorecard (line 164)",
        "claim_type": "generalization",
        "claim_summary": "The participant-selection table records Docxodus as "
                         "excluded ('no - .NET/WASM; a different toolchain "
                         "from the rest of the trial'), yet Docxodus is "
                         "measured on the same instrument and ties for first "
                         "at 100.0%. The report does not state the criterion "
                         "by which it was admitted.",
        "evidence_ids": "EV:main-report-selection-table;EV:out-docxodus-score.json",
        "support_level": "partly_supported",
        "alignment_issue": "scope",
        "note": (
            "The measurement of Docxodus is supported; the  selection rationale that excludes and then  includes it is not stated anywhere in the report."
        ),
        "limitation": "",
        "requested_action": "State the inclusion criterion for the thirteenth "
                            "participant in the selection section, and "
                            "reconcile the section title and the twelve/thirteen "
                            "phrasing with it.",
    },
    {
        "claim_id": "RVW-003",
        "location": "Main report, Limits of this trial (line 107)",
        "claim_type": "other",
        "claim_summary": "The bullet states that star counts were not "
                         "re-measured and is then superseded in the same "
                         "bullet by the statement that they were; it also "
                         "cross-references a section as 'How the twelve were "
                         "chose'.",
        "evidence_ids": "EV:main-report-limits-bullet",
        "support_level": "unsupported",
        "alignment_issue": "other",
        "note": (
            "A revision artifact - a superseded statement kept  inline - is carried into the published text, with  a misspelled section reference."
        ),
        "limitation": "",
        "requested_action": "Fold the superseded bullet into its final "
                            "statement and correct the section reference.",
    },
    {
        "claim_id": "RVW-004",
        "location": "build/check_report_consistency.py, number gate scope",
        "claim_type": "methods",
        "claim_summary": "The number gate selects the reports to scan with "
                         "'git diff --name-status main -- reports'. On the "
                         "publication branch that diff is empty, so the gate "
                         "scans zero reports and reports the empty scan as a "
                         "problem; the repository's own test suite fails 1 of "
                         "9 on the current branch as a result.",
        "evidence_ids": "EV:check-report-consistency-scope;EV:test-report-claims",
        "support_level": "partly_supported",
        "alignment_issue": "scope",
        "note": (
            "The gate that is supposed to police the published  numbers does not run on a clean tree, so on the  publication branch the headline figures are  unverified by it."
        ),
        "limitation": "",
        "requested_action": "Make the gate scan the full active report set, "
                            "or fail closed with a distinct message when the "
                            "diff is empty, and keep the test green.",
    },
    {
        "claim_id": "RVW-005",
        "location": "reports/Report B and Report C, DOCX twins at HEAD",
        "claim_type": "methods",
        "claim_summary": "Commit d824103 corrected the 'only' claims and "
                         "stale statuses in Report B and Report C but rebuilt "
                         "neither DOCX twin. Both twins were stale at HEAD: "
                         "Report B's twin carried the superseded heading "
                         "'The four that pass every static check and still fail "
                         "in Word' and Report C's carried 'the only editor "
                         "that labels the SmartArt band'.",
        "evidence_ids": "EV:git-d824103;EV:verify-twin-parity",
        "support_level": "unsupported",
        "alignment_issue": "other",
        "note": (
            "The published DOCX twins did not carry the  corrections the Markdown source carried, so the  two versions of the same report disagreed."
        ),
        "limitation": "",
        "requested_action": "Remediated in this edition by rebuilding both "
                            "twins with build/make_report.sh; keep "
                            "build/verify_twin_parity.py in the release gate "
                            "so a source edit without a rebuild cannot ship.",
    },
    {
        "claim_id": "RVW-006",
        "location": "reports/Report D, Report D1, Report D2",
        "claim_type": "other",
        "claim_summary": "The safety report set had no DOCX twin at all; "
                         "only the main report and Reports A, A2, B and C "
                         "were built as Word deliverables, while the three "
                         "reports that carry the hostile-input findings were "
                         "published as Markdown only.",
        "evidence_ids": "EV:reports-directory;EV:build-make-report",
        "support_level": "unsupported",
        "alignment_issue": "other",
        "note": (
            "The part of the study with the strongest safety  implications shipped in the format a reviewer is  least likely to read."
        ),
        "limitation": "",
        "requested_action": "Remediated in this edition: all three twins are "
                            "built, schema-validated and open in Word.",
    },
    {
        "claim_id": "RVW-007",
        "location": "build/verify_deliverables.py, DELIVERABLES",
        "claim_type": "methods",
        "claim_summary": "The Word-open deliverable list still pointed at "
                         "'reports/Report A - Serialized vs Pass-Through vs "
                         "Rendered (2026).docx', which was superseded and "
                         "moved to reports/archive/, and it omitted Reports D, "
                         "D1 and D2 entirely.",
        "evidence_ids": "EV:verify-deliverables-list;EV:reports-archive",
        "support_level": "unsupported",
        "alignment_issue": "other",
        "note": (
            "The gate that proves the published files open in  Word was checking a file that had been retired."
        ),
        "limitation": "",
        "requested_action": "Remediated in this edition: the list names the "
                            "eight live reports and the fixture, and all nine "
                            "open in Word 16.115.",
    },
    {
        "claim_id": "RVW-008",
        "location": "reports/ and fixture/, owner-lock files",
        "claim_type": "other",
        "claim_summary": "Microsoft Word owner-lock files ('~$port C - "
                         "Rendering Versus Word (2026).docx', "
                         "'~$omplex.docx') are committed to the repository, "
                         "including inside the published reports directory.",
        "evidence_ids": "EV:git-ls-files;EV:reports-lock-file",
        "support_level": "unsupported",
        "alignment_issue": "other",
        "note": (
            "A 162-byte transient lock file sits beside the  published Report C and is listed by git as a  tracked deliverable."
        ),
        "limitation": "",
        "requested_action": "Remove the lock files from version control and "
                            "ignore the '~$' pattern; they are Word "
                            "artefacts, not content.",
    },
    {
        "claim_id": "RVW-009",
        "location": "Main report, The Corpus: fixture/complex.docx",
        "claim_type": "generalization",
        "claim_summary": "The whole trial is measured against a single "
                         "adversarial document. Every per-editor score, every "
                         "namespace finding and every rendering verdict is a "
                         "statement about one input.",
        "evidence_ids": "EV:fixture-complex-docx;EV:main-report-corpus-section",
        "support_level": "partly_supported",
        "alignment_issue": "population",
        "note": (
            "The claim 'the twelve editors were compared' is  supported for one document; the generalization to  the editors' fidelity in general rests on a corpus  of n=1."
        ),
        "limitation": "A single corpus document can be adversarial to one "
                      "implementation and unrepresentative of another.",
        "requested_action": "Publish the ablation, variant and group fixtures "
                            "already built in out/ as a sensitivity analysis "
                            "over a corpus set, and report per-corpus scores "
                            "alongside the aggregate.",
    },
    {
        "claim_id": "RVW-010",
        "location": "Main report, Method and Its Limits; Report A",
        "claim_type": "methods",
        "claim_summary": "The trial's central quantity, 'fidelity', is "
                         "defined by the trial's own 99-check scorer and is "
                         "not mapped onto a standard software quality "
                         "characteristic or a named OOXML conformance class.",
        "evidence_ids": "EV:scorer-checks;EV:ecma-376-transitional",
        "support_level": "partly_supported",
        "alignment_issue": "scope",
        "note": (
            "The measurement is internally consistent and  reproducible, but its construct validity rests on  the trial's own definition rather than on an  external quality model."
        ),
        "limitation": "The scorer was written by the same authors as the "
                      "reports.",
        "requested_action": "Map the composite onto ISO/IEC 25010 "
                            "functional suitability and functional "
                            "compatibility, state the conformance class "
                            "(ECMA-376 Transitional) the corpus targets, and "
                            "report the individual checks alongside the "
                            "composite so a reader can re-aggregate.",
    },
    {
        "claim_id": "RVW-011",
        "location": "Report D, Safety, Resource Bombs and Hostile Input",
        "claim_type": "safety",
        "claim_summary": "The safety report classifies hostile packages into "
                         "twelve defect classes of its own devising, with no "
                         "mapping to an established weakness taxonomy.",
        "evidence_ids": "EV:report-d-defect-taxonomy;EV:logs-bombs-scorecard",
        "support_level": "partly_supported",
        "alignment_issue": "scope",
        "note": (
            "The observations are measured and reproducible,  but a reader cannot situate the classes against  known vulnerability classes or check that the  taxonomy is exhaustive."
        ),
        "limitation": "Twelve classes is not a complete taxonomy of hostile "
                      "DOCX input.",
        "requested_action": "Map each class to a CWE identifier - CWE-409 "
                            "for compression amplification, CWE-776 for XML "
                            "entity expansion, CWE-22 for archive path "
                            "traversal - and state explicitly which known "
                            "classes the trial did not attempt.",
    },
    {
        "claim_id": "RVW-012",
        "location": "Whole study, reporting standard",
        "claim_type": "methods",
        "claim_summary": "No reporting guideline is prespecified for the "
                         "study. The bundled reporting-guideline catalogue "
                         "contains only clinical and health instruments, and "
                         "the selector returns NO_BUNDLED_GUIDELINE_MATCH for "
                         "a software-benchmark profile, so no coverage audit "
                         "was possible.",
        "evidence_ids": "EV:select-reporting-guidelines;EV:reporting-catalog-2026-07-23",
        "support_level": "partly_supported",
        "alignment_issue": "other",
        "note": (
            "The study has no declared reporting standard,  so 'complete reporting' cannot be audited against  anything."
        ),
        "limitation": "",
        "requested_action": "Prespecify the reporting instruments in the "
                            "manuscript: the empirical software engineering "
                            "guidelines for study design and reporting, ACM "
                            "Artifact Review and Badging v1.1 for the "
                            "artifact, and ECMA-376 Transitional conformance "
                            "for the corpus.",
    },
    {
        "claim_id": "RVW-013",
        "location": "Main report, title block, edition note, Popularity",
        "claim_type": "other",
        "claim_summary": "The report carries three dates: the title block "
                         "says 2026-10-29, the edition note is 2026-10-30, "
                         "and the star counts are stated as re-measured on "
                         "2026-11-01.",
        "evidence_ids": "EV:main-report-title-block;EV:main-report-popularity",
        "support_level": "partly_supported",
        "alignment_issue": "timepoint",
        "note": (
            "A reader cannot tell which measurements belong  to which edition, which matters for a document  whose star-count finding is stated as measured."
        ),
        "limitation": "",
        "requested_action": "Add a short version-and-date table naming the "
                            "edition, the corpus commit, the measurement run "
                            "and the date each population statistic was taken.",
    },
    {
        "claim_id": "RVW-014",
        "location": "Report A, sections 4.4 and 4.5",
        "claim_type": "methods",
        "claim_summary": "The report states a direct disagreement between the "
                         "code reading and the measured matrix: four "
                         "disagreements among the twelve editors, and the "
                         "code reading understates the loss in all four.",
        "evidence_ids": "EV:report-a-4.4;EV:report-a-4.5;EV:out-ns-map.json",
        "support_level": "partly_supported",
        "alignment_issue": "direction",
        "note": (
            "The code reading is stated as a hypothesis and  the measurement as the result, which is the right  ordering, but the reading is still the only  evidence offered for the claims it explains."
        ),
        "limitation": "The code reading is bound to one commit per project.",
        "requested_action": "Keep the two layers separate, as the report now "
                            "does, and cite the pinned commit beside each "
                            "code-level claim so a reader can reproduce the "
                            "reading.",
    },
    {
        "claim_id": "RVW-016",
        "location": "Main report, Fidus Writer findings, methodological note",
        "claim_type": "methods",
        "claim_summary": "The report states that using the input document "
                         "itself as the Fidus export template scores 99.5%. It "
                         "is a real control measurement and the report rightly "
                         "warns that it is the kind of number that could be "
                         "published in error - but no committed artifact "
                         "records it, and no script in build/ reproduces it.",
        "evidence_ids": "EV:main-report-fidus-control;EV:out-fidus-score.json",
        "support_level": "partly_supported",
        "alignment_issue": "other",
        "note": "The control measurement is quoted with no committed "
                "evidence and no reproduction recipe, so a reader can "
                "neither verify it nor re-run it.",
        "limitation": "",
        "requested_action": "Commit the control run's score.json and add the "
                            "script that produces it, or drop the figure and "
                            "keep only the qualitative warning. If it is kept, "
                            "it belongs in the artifact with everything else.",
    },
    {
        "claim_id": "RVW-017",
        "location": "Report C, ablation section (no_chart and no_pic byte "
                    "deltas)",
        "claim_type": "methods",
        "claim_summary": "Report C quotes ablation byte deltas - 42,474 and "
                         "42,474 differing pixels for 190 and 190 bytes - but "
                         "the ablation harness writes only the fixtures; no "
                         "committed result file records the comparison.",
        "evidence_ids": "EV:report-c-ablation;EV:out-ab-fixtures",
        "support_level": "partly_supported",
        "alignment_issue": "other",
        "note": "The ablation is the evidence that distinguishes a "
                "rendering difference from a payload difference, and its "
                "result file is not part of the artifact.",
        "limitation": "",
        "requested_action": "Commit the ablation result file, including the "
                            "per-variant pixel and byte deltas, so the "
                            "ablation table is re-derivable like every other "
                            "table in the report set.",
    },
    {
        "claim_id": "RVW-018",
        "location": "reports/extras/folio.md and reports/extras/eigenpal.md, "
                    "editor-lane blocks",
        "claim_type": "methods",
        "claim_summary": "The extras notes quote the editor lanes' weighted "
                         "scores - 95.5% for the Folio editor lane and 98.5% "
                         "for the eigenpal editor lane - but neither lane had "
                         "a committed score.json, so the only lanes in the "
                         "study whose figures were unbacked were the two "
                         "secondary lanes.",
        "evidence_ids": "EV:reports-extras-folio;EV:reports-extras-eigenpal",
        "support_level": "partly_supported",
        "alignment_issue": "other",
        "note": "The figures were correct, but the primary lanes were the "
                "ones the repository test policed, and the secondary lanes "
                "were measured and then dropped.",
        "limitation": "",
        "requested_action": "Remediated in this edition: both lanes were "
                            "re-scored with build/check_roundtrip.py and "
                            "their score.json files committed. Extend the "
                            "extras test to the editor lanes so they cannot "
                            "silently lose their score file again.",
    },
    {
        "claim_id": "RVW-019",
        "location": "build/check_report_consistency.py, number gate",
        "claim_type": "methods",
        "claim_summary": "Widening the number gate to the published report "
                         "set exposed seven stale figures in the shipped text: "
                         "83% for WordCraft where the score is 84.9%, a "
                         "Docxodus word/document.xml delta of 18,194 -> 19,409 "
                         "bytes where the measurement is 18,276 -> 18,495, "
                         "Plate's second pass as 20.0% where it is 20.1%, "
                         "Folio as 98.5% and Plate as 20.5% in Report A2 where "
                         "the scores are 97.5% and 20.6%, an ink share of "
                         "0.0006% where the measurement is 0.005%, and seven "
                         "references to a 97-check scorer where the scorer "
                         "runs 99 checks.",
        "evidence_ids": "EV:verify-findings;EV:check-report-consistency-scope",
        "support_level": "unsupported",
        "alignment_issue": "magnitude",
        "note": "The published text carried figures that no measurement "
                "produced; in every case the figure was stale rather than "
                "wrong in intent.",
        "limitation": "",
        "requested_action": "Remediated in this edition: all seven figures "
                            "are corrected and the number gate now scans every "
                            "live report, checks 468 percentages and byte "
                            "sizes against the measurement artifacts, and "
                            "rejects a fabricated figure.",
    },
    {
        "claim_id": "RVW-015",
        "location": "Main report, round-trip scorecard and How the twelve "
                    "were chosen",
        "claim_type": "other",
        "claim_summary": "LibreOffice appears as a row in the scorecard and "
                         "is described as the calibration floor rather than a "
                         "candidate, while the surrounding prose counts "
                         "twelve editors, a thirteenth participant and a "
                         "thirteen-row table across the same document.",
        "evidence_ids": "EV:main-report-scorecard;EV:out-lo-baseline-score.json",
        "support_level": "partly_supported",
        "alignment_issue": "scope",
        "note": (
            "The counts are each defensible, but the document  never states in one place whether LibreOffice is  a participant, a baseline or a thirteenth row,  and the report's own vocabulary shifts between  the three."
        ),
        "limitation": "",
        "requested_action": "State the participant set once - twelve editors, "
                            "one SDK participant, one LibreOffice calibration "
                            "floor - and use that vocabulary throughout.",
    },
]


def evidence_id_for(metric: str, slug: str) -> str:
    """Return the evidence identifier for a ledger metric.

    Args:
        metric: The metric name from the ledger.
        slug: The participant's output directory.

    Returns:
        An identifier that satisfies the peer-review identifier grammar.
    """
    base = EVIDENCE.get(metric, "EV:score.json")
    if base == "EV:score.json":
        return f"EV:out-{slug}-score.json"
    if base == "EV:second-score.json":
        return f"EV:out-{slug}-second-score.json"
    return base


def main() -> int:
    """Write the claim-evidence matrix.

    Returns:
        0 on success.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", default="out/findings_ledger.csv")
    parser.add_argument("--out", default="out/review/claim_evidence_matrix.csv")
    args = parser.parse_args()

    ledger_path = ROOT / args.ledger
    rows: list[dict] = []
    if ledger_path.is_file():
        with ledger_path.open(encoding="utf-8", newline="") as handle:
            for entry in csv.DictReader(handle):
                slug = entry["finding_id"].removeprefix("FND-SCORE-").removeprefix(
                    "FND-IDEM-")
                slug = slug.rsplit("-", 1)[0] if entry["finding_id"].count("-") > 3 \
                    else slug
                metric = entry["metric"]
                rows.append({
                    "claim_id": entry["finding_id"],
                    "location": f"{entry['report']} :: {entry['location']}",
                    "claim_type": CLAIM_TYPES.get(metric, "primary_outcome"),
                    "claim_summary": (
                        f"{entry['subject']} - {metric}: the report states "
                        f"{entry['reported'] or 'a value'}, the measurement "
                        f"gives {entry['measured']}."
                    ),
                    "evidence_ids": evidence_id_for(metric, slug),
                    "support_level": ("supported" if entry["status"] == "match"
                                      else "unsupported"),
                    "alignment_issue": ("none" if entry["status"] == "match"
                                        else "the report states a figure the "
                                             "measurement does not reproduce"),
                    "limitation": "",
                    "requested_action": ("" if entry["status"] == "match"
                                         else "Correct the figure to the "
                                              "measured value and rebuild the "
                                              "DOCX twin."),
                })
    else:
        print(f"ledger not found: {ledger_path}")

    for finding in REVIEW_FINDINGS:
        note = finding.pop("note", "")
        if note:
            finding["claim_summary"] = f"{finding['claim_summary']} {note}"
    rows.extend(REVIEW_FINDINGS)

    out_path = ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    supported = sum(1 for r in rows if r["support_level"] == "supported")
    print(f"claims: {len(rows)} (supported {supported}, "
          f"review findings {len(REVIEW_FINDINGS)}) -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
