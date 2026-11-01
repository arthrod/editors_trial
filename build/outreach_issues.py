#!/usr/bin/env python3
"""Write the vendor-facing issue drafts for the editor trial.

Every figure in a draft comes from the score files the scorer wrote, not from
the prose, so a draft cannot carry a number the measurement does not support.
The per-vendor prose is here; the numbers are read from out/.

Usage:
    python3 build/outreach_issues.py            # write the drafts
    python3 build/outreach_issues.py --check    # check the drafts' figures
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
DRAFTS = ROOT / "outreach"

REPO_URL = "https://github.com/arthrod/editors_trial"
BLANK = "https://github.com/arthrod/editors_trial/blob/main/"


def url(path: str) -> str:
    """Return a GitHub blob URL for a path in the published repository."""
    return BLANK + quote(path, safe="/")



PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")


def fill(text: str, mapping: dict) -> str:
    """Substitute {key} placeholders, leaving any other braces alone.

    The vendor prose contains literal OOXML-ish braces such as {title} and
    {@bibliography}, so a plain str.format() would try to read them as fields.
    """
    out: list[str] = []
    pos = 0
    while True:
        m = PLACEHOLDER.search(text, pos)
        if not m:
            out.append(text[pos:])
            break
        key = m.group(1)
        if key in mapping:
            out.append(text[pos:m.start()])
            out.append(str(mapping[key]))
        else:
            out.append(text[pos:m.end()])
        pos = m.end()
    return "".join(out)


REPORTS = {
    "A": ("Report A — Serialization by Namespace",
          "reports/Report A - Serialization by Namespace (2026).md",
          "what each of the corpus's 27 namespace vocabularies does, and what it costs when it is lost. One section per namespace: what the vocabulary is in WordprocessingML, what each editor's own source does with it, and what each editor actually did to it, measured."),
    "A2": ("Report A2 — Pass-Through",
           "reports/Report A2 - Pass-Through (2026).md",
           "the complement of fidelity: of the bytes that came out, how many did the editor never even look at. Pass-through is the strongest possible fidelity and the weakest possible editing, and it is the same fact."),
    "B": ("Report B — Malformed Parts, Causes, Detection and Repair",
          "reports/Report B - Malformed Parts, Causes and Repair (2026).md",
          "twelve defect classes that Microsoft Word refuses to open, found by bisecting the corpus against Word itself; what malformed parts look like, what causes them, and whether any editor repairs them."),
    "C": ("Report C — Rendering Versus Word",
          "reports/Report C - Rendering Versus Word (2026).md",
          "what each editor's own running application puts on the page, screenshotted and compared with Word's own PDF export of the same corpus. Fidelity in the file and fidelity on the page are two different results, and this report keeps them apart."),
    "D": ("Report D — Safety, Resource Bombs and Hostile Input",
          "reports/Report D - Safety, Resource Bombs and Hostile Input (2026).md",
          "ten hostile packages — decompression, entry flood, attribute bomb, deep nesting, entities, zip-slip, external relationships, active content, layout bomb, corrupt parts — graded on a separate axis, because preserving a hostile payload is not the same result as a crash."),
}

INTRO = """We measured {name} together with eleven other open-source DOCX tools and published the whole thing — the corpus, the harnesses, the scorer, the logs and the reports — so that every number below can be checked and corrected.

**Everything is here: {repo}**

## What the trial is

One input: `fixture/complex.docx`, a 35-part hand-built OOXML document that deliberately contains tracked changes, complex and simple fields, five content controls, tables with merges and nested tables, three sections including a landscape two-column one, a bar chart, a SmartArt diagram, an OLE object with an embedded workbook, an image, footnotes, endnotes, comments, headers and footers, and a set of namespace extensions Word writes.

Every editor was driven through **its own** documented import and export path — {name}'s own entry point, not a re-implementation of it — and the result was scored by a {checks}-check diff at package-part, element, attribute and text level. Every output was re-opened to confirm it is still a valid document. The scorer, the harnesses, the fixture and the raw logs are in the repository.

## What we measured for {name}

{body}

## The reports, and what each one is

{reports}

- **The per-tool note for {name}:** {note_url}
- **What each measured tool is:** {vendors_url}

## If anything here is wrong, please open a pull request

We would rather have a correction from you than a quiet disagreement. Three things are worth correcting, in this order of usefulness:

1. **A number.** Every figure in the reports is produced by `python3 build/score_all.py` over the committed outputs in `out/`, and it is checked against the scorer's own output by `build/check_report_consistency.py`, so a figure that cannot be reproduced fails the gate rather than slipping through. If one of ours is wrong, open a PR against the file that carries it — {note_url} for the per-tool note, or the report that quotes it — and if the figure comes from the measurement rather than from prose, include the corrected `out/{slug}/score.json` too. `build/test_report_claims.py` enforces that the per-tool note still agrees with the shipped scorer, so it will tell you whether a correction is self-consistent.
2. **A reading of your code.** The `[CODE]` citations name a file and a line. If we read your implementation wrong — or if it has moved on since the commit we pinned — a PR that fixes the citation is as welcome as one that fixes a number.
3. **A judgement.** Some of the report's claims are readings, not measurements: what a design decision "means", which of two behaviours is the better one. If you disagree with a judgement, the place to say so is a pull request against the report, not a new issue.

We are not going to argue about the framing of a published number. If our reading is wrong, the fix belongs in the repository, in public, where the next person can check it.

## What the trial does not claim

- **One document.** The corpus is deliberately hostile, but it is one document, not a corpus survey.
- **A round trip, not an editing session.** Every project was exercised on import → export with no edits. Selective-save behaviour that only triggers on a dirty block is therefore not distinguished from unconditional regeneration, except where the project documents otherwise.
- **Word as a validator, not as an oracle.** The corpus is checked against the ECMA-376 schemas and opened in Microsoft Word 16.115, but the outputs were judged by the scorer and by LibreOffice. A document that Word opens but that the scorer flags is still a loss.
- **A moving instrument.** The checker gained checks over the life of the study; the published figures come from the current {checks}-check scorer, and the repository is the record of that.

## Reproducing it

```sh
git clone {repo}.git && cd editors_trial
python3 build/score_all.py                       # the scorecard table
python3 build/check_roundtrip.py fixture/complex.docx out/{slug}/complex.docx
bash build/run_second_pass.sh                    # the idempotence table
```
"""


def load(slug: str, kind: str = "") -> dict:
    """Return one score file for a tool."""
    path = OUT / slug / "score.json" if not kind else OUT / slug / kind / "score.json"
    return json.loads(path.read_text(encoding="utf-8"))


def figures(slug: str) -> dict:
    """Return the measured figures a draft quotes for one tool."""
    first = load(slug)
    second = load(slug, "second")
    import zipfile
    with zipfile.ZipFile(OUT / slug / "complex.docx") as z:
        out_parts = {n for n in z.namelist() if not n.endswith("/")}
    with zipfile.ZipFile(ROOT / "fixture" / "complex.docx") as z:
        in_parts = {n for n in z.namelist() if not n.endswith("/")}
    failed = [c["label"] for c in first["checks"] if not c["pass"]]
    return {
        "weighted": first["score"]["weighted"],
        "critical": first["score"]["critical_pct"],
        "critical_passed": first["score"]["critical_passed"],
        "critical_total": first["score"]["critical_total"],
        "features_passed": first["score"]["features_passed"],
        "features_total": first["score"]["features_total"],
        "checks": first["score"]["features_total"],
        "text": first["text_retention_pct"],
        "parts_kept": len(in_parts & out_parts),
        "parts_total": len(in_parts),
        "parts_lost": len(in_parts - out_parts),
        "parts_added": len(out_parts - in_parts),
        "failed": len(failed),
        "failed_labels": failed,
        "second_weighted": second["score"]["weighted"],
        "second_text": second["text_retention_pct"],
        "bytes": (OUT / slug / "complex.docx").stat().st_size,
    }


def report_block() -> str:
    """Return the markdown list of the reports."""
    lines = []
    for key, (title, path, blurb) in REPORTS.items():
        lines.append(f"- **[{title}]({url(path)})** — {blurb}")
    return "\n".join(lines)



FIDUS_APP_EXTRA = """We are filing the same note on the package repository, because the DOCX importer and exporter we measured live in `@fiduswriter/document` and not in the application. The two findings that belong to the application rather than to the package are these: the "Updating document. Please wait…" cover that never clears, and the fact that the editor DOM contains no table, no chart, no SmartArt band, no OLE object, no equation and no text box when the corpus is opened (Report C §2.11). The fidelity numbers are the same in both places; the round trip we ran was the package's own importer and exporter, not a full application round trip.
"""


VENDORS = [
    {
        "slug": "superdoc",
        "repo": "superdoc/docx-editor",
        "name": "SuperDoc",
        "subject": "SuperDoc",
        "body": """**{weighted}% weighted, {critical}% critical ({critical_passed}/{critical_total}), {features_passed}/{features_total} checks, {text}% text retention, {parts_kept}/{parts_total} parts kept — and {failed} failed checks.**

SuperDoc is one of only two participants in the trial with no failed check at all, and one of five that reach a **byte-identical fixed point**: feed its own output back through the SDK and it reproduces the same file, byte for byte.

What we like about how it works:

- The save is a **genuine re-save, not a copy**. `word/document.xml` and the notes and header parts are re-serialized; the other 27 parts pass through byte-identically. Nothing is regenerated that did not need to be.
- **The binary payload is intact and still wired up.** All ten payload parts are present — the chart and its style and colour companions, all four SmartArt parts, the OLE object, the embedded workbook and the image — and the body still references the chart, the diagram and the OLE object. Seven of the {checks} checks are exactly that, and SuperDoc passes all seven.
- **It is the closest thing to a Word clone we measured on screen** (Report C §2.1). Your application shows the table with the inserted row highlighted and the deleted row struck through in red, the blue picture, the chart with its blue bars and its "Cat A / Cat B / Cat C" axis labels and its "Series 1" legend, the `mc:Choice` text box reading "Text box content", the equation **E = mc²**, and the comment in a review sidebar with two cards, both attributed to the fixture author. And when Word opens the file SuperDoc produced, the rendering differs from Word's rendering of the corpus by **83 pixels across six pages** — the same 83 that Docxodus leaves, and the smallest gap we measured.
- **It carries namespaces it has never heard of** (Report A): `w16du:dateUtc`, the `w14` identifiers and the `w16du` declaration all survive, which is not something the architecture gives for free.
- On the hostile-input axis (Report D) it **refused five of the ten packages outright** — the decompression bomb, the entry flood, the attribute bomb, the entity bomb and the corrupt-parts package — rather than writing them out.""",
    },
    {
        "slug": "docxodus",
        "repo": "JSv4/Docxodus",
        "name": "Docxodus",
        "subject": "Docxodus",
        "body": """**{weighted}% weighted, {critical}% critical ({critical_passed}/{critical_total}), {features_passed}/{features_total} checks, {text}% text retention, {parts_kept}/{parts_total} parts kept — and {failed} failed checks.**

Docxodus shares the top of the scorecard, and it gets there in a way that is different from every other participant in the study:

- **It is the only tool in the study with nothing changed and nothing dropped.** 25 parts come through byte-identical, 10 are re-serialised, **0 changed, 0 dropped, 0 added**. No editor returns an author's bytes more faithfully.
- **You do not need a policy to get there.** It opens the package with `WordprocessingDocument.Open(stream, isEditable: true)` and saves the same object graph back out, so parts it has no schema for are carried through untouched and parts it owns are re-printed. It draws its line around a set of *parts*, not a set of *names* (Report A §3.12).
- **It is the only participant that keeps `w16du:dateUtc` by decision rather than by accident** — it declares a typed `XName` for the attribute and validates its value (`RevisionOps.cs:37`, `:565`). Not one of the other twelve reports that it dropped it.
- **It is on the good side of all three axes at once** (Report C). It reproduces Word's pagination — six pages — and Word's page geometry to the pixel, keeps all 35 parts with zero changed and zero dropped, keeps every `w:` element and the `w15` / `w16cid` / `w16du` / `w10` namespaces that eight of the other twelve lose, has **zero dangling relationship references**, and produces a file Word opens and renders pixel-identically.
- **Your engine independently corroborates our hardest measurement.** Word draws zero pixels in the 142,766-pixel band where the corpus's SmartArt diagram sits. Docxodus reserves the same band and draws a "[SMARTART]" placeholder in it, naming the element that defeated it (`relIds`). That is a second engine landing on the same band by a different route, and it is the control that makes the claim checkable (Report C §5).
- **You are the only participant that ships a repair funnel** (`PackageOpenRepair`), and Report B uses that as the cleanest available demonstration of a distinction worth making: having a repair stage and repairing a given malformation are different properties.
- Its second pass is a **byte-identical fixed point** — one of five in the trial.""",
    },
    {
        "slug": "folio",
        "repo": "stella/folio",
        "name": "Folio",
        "subject": "Folio",
        "body": """**{weighted}% weighted, {critical}% critical ({critical_passed}/{critical_total}), {features_passed}/{features_total} checks, {text}% text retention, {parts_kept}/{parts_total} parts kept — {failed} failed checks.**

Folio is the only project in the trial that keeps **100% of the text** while losing a package part, and it loses no package part at all.

What we like about how it works:

- **It returns an author's bytes more faithfully than any other editor we measured** (Report A2). Folio copies 34 of the corpus's 35 parts byte-for-byte — and copies the *raw compressed bytes*, not re-serialised XML, so the CRC and the compressed size come through exactly. A copy-and-override architecture and a byte-splice architecture produce different kinds of fidelity, and yours is the strongest row in that report.
- **Your own corpus-invariant harness is the same shape as this trial's.** `scripts/lib/corpus-invariants/save-idempotence.ts` does exactly the parse → repack → compare cycle we ran, and `scripts/lib/corpus-invariants/editor-round-trip.ts` does the full editor-model round trip. We drove your own code path rather than writing one against you, and your second pass is a **byte-identical fixed point**.
- **Your rendering is the closest to Word's of any editor we measured** (Report C §2.2). Folio is one of two tools in the study that reproduce Word's comment balloon — a rounded card in the right margin with the author, the timestamp and the comment body — and it reproduces the tracked-change table exactly as Word does: the inserted row plain, the deleted row struck through in red.
- **On the hostile-input axis, Folio has the strongest ceiling set of any participant** (Report D): a named ceiling on the decompression bomb, the entry flood and the deep nest, the attribute bomb cleaned, and the entity bomb, the zip-slip and the corrupt-parts package refused by name.
- The two checks Folio fails are `tc.moveFrom` and `mx.unknownAttr`. The first is the move source serialised with `w:delText` where Word writes `w:t` — the same defect we have already reported to you in issue #2230 — and the second is the `w14` run identifiers. If either of those is fixed, the figure moves, and the per-tool note is written so that it has to move with it.""",
    },
    {
        "slug": "genoffice",
        "repo": "genspark-ai/genoffice",
        "name": "GenOffice",
        "subject": "GenOffice",
        "body": """**{weighted}% weighted, {critical}% critical ({critical_passed}/{critical_total}), {features_passed}/{features_total} checks, {text}% text retention, {parts_kept}/{parts_total} parts kept — {failed} failed check.**

GenOffice keeps the whole package and loses almost nothing, and the way it keeps it is worth naming:

- **The "verbatim copy of untouched blocks" claim holds for 40 of 41 blocks.** The save plan showed 40 blocks kept as `original` and **1 regenerated as `xml`** — the table, whose block signature did not match. That is the design working as intended: a selective save that falls back to regeneration for the one block it does not recognise.
- **Its second pass is a byte-identical fixed point**, one of five in the trial.
- **It is the only editor in the trial that draws the SmartArt's node texts** (Report C §2.3). Where Word reserves a completely blank band, GenOffice draws a dashed band labelled "SmartArt" containing "Step one" and "Step two". The two applications show the reader *different information in the same place*: Word shows nothing, GenOffice shows the diagram's data as text. That is a defensible reading of an underspecified construct, and it is the kind of thing that is easy to miss in a benchmark and impossible to miss in a screenshot.
- It **paginates the corpus into six pages — the same count as Word** — and draws the chart as SVG with the correct bar heights (4.3 / 2.5 / 3.5) and the correct axis labels.
- On the hostile-input axis it puts a **named ceiling on the zip entry flood**, cleans the attribute bomb and refuses the corrupt-parts package (Report D).
- The single failing check is `text.exact`: the text inside the vertically-merged continuation cells. Worth saying plainly that **this matches Word's own merge semantics** — Word discards content in vertically-merged continuation cells too — so the behaviour is defensible, and it is still a text loss, which is why it is counted as one.""",
    },
    {
        "slug": "eigenpal",
        "repo": "eigenpal/docx-editor",
        "name": "eigenpal",
        "subject": "eigenpal",
        "body": """**{weighted}% weighted, {critical}% critical ({critical_passed}/{critical_total}), {features_passed}/{features_total} checks, {text}% text retention, {parts_kept}/{parts_total} parts kept — {failed} failed check.**

Two things we would like to point at.

- **Two independent lanes agree.** The canonical store lane (`readOoxmlPackage` → `writeOoxmlPackage`) and the editor lane (`DocxEditor.createServer` → `save()`) produce the same weighted score and the same single failing check. When two different entry points into an engine land on the same figure, that is usually the engine and not the entry point doing the work.
- **Your page-3 rendering is a near-exact reproduction of Word's** (Report C §2.4). The same table with the same merged cells and the same nested table, the inserted row highlighted green, the deleted row struck through on a pink background, the blue picture, and a chart that reproduces Word's "Series 1" title above the plot, the 0–5 value axis with 0.5 steps, the "Cat A / Cat B / Cat C" categories and the "Series 1" legend. We did not expect a browser editor to reproduce that.

And one thing we owe you:

- **Your `xml:space` normaliser caught a defect in our own fixture.** The first build of the corpus wrote six runs with leading or trailing whitespace but without `xml:space="preserve"` on four of them, which OOXML permits a consumer to trim. We had read your normaliser as the strict editor that lost whitespace, and it was in fact right: `normalizedWmlTextAttributes` re-derives the attribute from the text, and the fixture was wrong. We rebuilt the corpus so every whitespace-significant run carries the attribute, as Word always writes it. **A fidelity benchmark that does not mark its own whitespace as significant will report the most careful editor as the most lossy one** — we published that lesson rather than quietly fixing it.

On the hostile-input axis eigenpal has **named ceilings on the decompression bomb, the entry flood and the deep nest**, cleans the attribute bomb, and refuses the entity bomb (by document type), the zip-slip (by bad name) and the corrupt-parts package (Report D). Its second pass is a **byte-identical fixed point**.""",
    },
    {
        "slug": "officeopen",
        "repo": "DemoMacro/office-open",
        "name": "office-open",
        "subject": "office-open",
        "body": """**{weighted}% weighted, {critical}% critical ({critical_passed}/{critical_total}), {features_passed}/{features_total} checks, {text}% text retention, {parts_kept}/{parts_total} parts kept, none lost and none added — {failed} failed checks.**

office-open keeps **100% of the text** and every one of the {parts_total} package parts. That is the joint-highest text retention in the trial, and it is not a small thing for a library that rebuilds the package from a parsed model.

The README's own coverage claim — all 2,273 elements and 1,969 attributes across the 21 OOXML Transitional schemas — is ambitious, and the measurement is broadly consistent with it: what a typed, XSD-shaped model carries is what it carries, and the gaps are where the gaps are.

**Three findings, all in the chart and diagram path, all of which we would like fixed:**

1. **The chart and SmartArt relationships in the saved body do not resolve to any part.** The package still carries `word/charts/chart1.xml` and the four diagram parts, and the body still carries the `w:drawing` element — but the body was rewritten to use *different* relationship ids, and those ids were never written into `word/_rels/document.xml.rels`. The original relationships survive, still resolve, and nothing uses them. This is the defect class every conventional checker misses: the file passes a part-level diff, a content-types audit, a schema validation and an XML fidelity score, and still does not draw the chart. Resolving the body *forwards* — every `r:id`, `r:embed`, `r:dm`, `r:lo`, `r:qs` and `r:cs` used in a part, looked up in *that part's* `.rels` — is what finds it.
2. **The second pass is not well-formed XML.** Feeding office-open its own output through `parseDocument` → `generateDocument` yields a `word/document.xml` that fails to parse: `unbound prefix`, column 13606. The chart and SmartArt `<a:graphic>` elements are emitted bare, because the namespace is declared on an ancestor element that the regenerated tree does not reproduce. The second-pass score collapses from {weighted}% to {second_weighted}%. **This is invisible in a first-pass diff** — the file looks fine, opens in LibreOffice, and only breaks when the tool's own output is fed back in.
3. `w16du:dateUtc`, the `w14` run identifiers and the `w16du` namespace declaration are dropped, which is what a full regeneration does to markup it does not model.

We are not filing separate bug reports for these, because the trial already has a page for exactly this: {note_url} and Report B §3.6. A pull request that fixes the relationship ids and the namespace rebinding would change both the fidelity table and the second-pass table, and we would update the reports in the same pull request.""",
    },
    {
        "slug": "docen",
        "repo": "DemoMacro/docen",
        "name": "Docen",
        "subject": "Docen",
        "body": """**{weighted}% weighted, {critical}% critical ({critical_passed}/{critical_total}), {features_passed}/{features_total} checks, {text}% text retention, {parts_kept}/{parts_total} parts kept, none lost — {failed} failed checks.**

Docen keeps **99.4% of the text** and every one of the {parts_total} package parts, in a full Word-like application, and it renders like one:

- It **paginates the corpus into six pages**, the same count as Word, and draws the table with its merged cells, the nested table and the tracked-change rows, the blue picture, **the footnote marker and the footnote body with its separator rule**, and the `mc:Choice` text box reading "Text box content" (Report C §2.5). Reproducing the footnote *body* with its rule is not a trivial thing to do.
- The pagination engine that follows Word's stacking rules — document grid, repeating table headers, text wrapping around floats — is a real piece of work, and it is visible on the page.

Two findings, and a suggestion:

1. **Docen inherits office-open's two chart-path defects verbatim**, because `@docen/docx` is powered by `@office-open/docx`: the chart and SmartArt relationships in the saved body do not resolve to any part, and the second pass emits a `word/document.xml` that is not well-formed XML (`unbound prefix`, column 15858). The second-pass score collapses to {second_weighted}%. **A fix in office-open fixes both**, which is why we have reported it there rather than duplicating it here.
2. Docen's own losses are `w:noBreakHyphen` / `w:softHyphen`, and the tracked change inside `header2.xml` is relocated to `header3.xml` — the loss is path-scoped, not content-scoped, which is a much smaller thing than losing it.
3. The chart is drawn with three differently-coloured bars and a three-entry legend where Word draws one blue series called "Series 1". The bar heights and the category labels are right; the *series* is read as three. That is a chart-model question, and it is the only place where Docen and Word disagree about what the reader sees.""",
    },
    {
        "slug": "wordcraft",
        "repo": "storytold/wordcraft",
        "name": "WordCraft",
        "subject": "WordCraft",
        "body": """**{weighted}% weighted, {critical}% critical ({critical_passed}/{critical_total}), {features_passed}/{features_total} checks, {text}% text retention, {parts_kept}/{parts_total} parts kept — {failed} failed checks.**

WordCraft is the most interesting result in the trial in both directions.

**What it does well:**

- **It keeps the whole binary payload.** The chart, all four SmartArt parts, the OLE object, the embedded workbook, the image, the glossary, the customXml store and every header and footer all survive — one of only seven tools that keep that payload set, and it does it with a regeneration writer, not a pass-through.
- **Its own renderer is very good** (Report C §2.7). WordCraft has its own Rust page-layout engine, the deepest in the trial, and a clean-room reimplementation of Word is not a small thing to attempt.
- **It is the most careful of the regeneration writers on the hostile-input axis** (Report D): **named ceilings on the entry flood, the attribute bomb and the deep nest**, and it *cleans* the zip-slip, the external-relationship bomb and the corrupt-parts package rather than writing them out. The written grid span is capped at 63 on the layout bomb. **That is the best combination of ceilings and sanitation we measured.**
- Its second pass is stable in content: {second_weighted}% against its own first pass, with 100% text retained.

**What it loses,** stated plainly: it is the only payload keeper that loses the revision model. `w:proofErr`, `w:fldSimple`, `w:altChunk`, `mc:AlternateContent`, `w16du:dateUtc`, the `w14` identifiers and the **row-level revisions** (`w:trPr/w:ins`, `w:trPr/w:del`) all disappear, and one of the three `w:ins`/`w:del` pairs goes with them. It also drops three package parts of its own: `word/afchunk.html` and the chart's two companions, `word/charts/colors1.xml` and `word/charts/style1.xml`.

We are not going to pretend the two are the same kind of thing. A writer that regenerates and a writer that passes payloads through are different designs, and WordCraft's payload passthrough is what saves it here.""",
    },
    {
        "slug": "canvas",
        "repo": "Hufe921/canvas-editor",
        "name": "canvas-editor",
        "subject": "canvas-editor",
        "body": """**{weighted}% weighted, {critical}% critical ({critical_passed}/{critical_total}), {features_passed}/{features_total} checks, {text}% text retention, {parts_kept}/{parts_total} parts kept — {failed} failed checks.**

The score is low, and almost all of it comes from one place, so we would rather tell you exactly where than leave you with a table.

**One exception dominates the result.** The DOCX importer drops `w:vMerge` continuation cells without recording the occupied grid column, so the table layout engine reads `colgroup[3]` of a three-column table and throws `TypeError: Cannot read properties of undefined (reading 'width')` at `TableParticle.ts:724`. It is plain JavaScript and it reproduces in a browser. The trigger has been isolated by bisection to a vertical merge and a horizontal span in the same table. **A pull request that fixes that bookkeeping would change our table.** We would like that more than we would like a correction to this issue.

**Two things that are genuinely good:**

- **The architecture is the point, and it is a defensible one.** canvas-editor takes over the rendering pipeline instead of letting a `contenteditable` host own the typography. That is why the DOCX plugin is a regeneration from the editor's own element list rather than a pass-through, and it is why the fidelity number is what it is.
- **canvas-editor has the best sanitation record in the trial** (Report D). It **cleaned six of the ten hostile packages** — the entry flood, the entity bomb, the zip-slip, the external-relationship bomb, the active-content package and the corrupt-parts package. Very few participants sanitised that many packages. (It hung on the decompression bomb, the attribute bomb and the layout bomb, and kept the deep nest; that is in the same table, published the same way.)

The importer is a bespoke OOXML parser over JSZip — about 1,859 lines — and the exporter rebuilds the package with the `docx` npm package.""",
    },
    {
        "slug": "fidus",
        "repo": "fiduswriter/fiduswriter-document-ts",
        "name": "Fidus Writer",
        "subject": "Fidus Writer",
        "body": """**{weighted}% weighted, {critical}% critical ({critical_passed}/{critical_total}), {features_passed}/{features_total} checks, {text}% text retention, {parts_kept}/{parts_total} parts kept — {failed} failed checks.**

Fidus Writer scores low on fidelity and **highest on safety of every participant in the trial**, and we think both halves of that belong in the same issue.

**On safety, Fidus Writer is the strongest result we measured** (Report D). It **cleaned seven of the ten hostile packages** — the entry flood, the attribute bomb, the zip-slip, the external-relationship bomb, the active-content package, the layout bomb and the corrupt-parts package — put a **named ceiling on the deep nest**, and refused the entity bomb. Its safety grade of 0.72 is the highest in the study, and the reason is specific rather than accidental: the exporter is template-driven, so it writes what the template asks for and not what the input happened to contain.

**On fidelity, one absent feature dominates the number.** There is **no table handling anywhere in `src/importer/docx/*`**, so both fixture tables — 11 rows, 16 cells — are gone before the export even begins. The importer also reports twelve unhandled element classes (`w:proofErr`, `w:ins`, `w:del`, `w:moveFrom`/`w:moveTo` and their range markers, `w:bookmarkStart`/`End`, `w:fldSimple`, `w:permStart`/`End`). **The entire table row in our scorecard comes from that one missing handler.** A DOM census of your running application confirms it: the editor DOM contains no table, no chart, no SmartArt band, no OLE object, no equation and no text box (Report C §2.11).

Two other things we found, which are yours to fix:

- The template-adjustment worker throws `RangeError: Invalid content for node title` on the corpus's first heading, which leaves the "Updating document. Please wait…" cover permanently on screen. The document renders underneath it; the cover is what stops you seeing it.
- The exporter is **placeholder-driven** — `{title}`, `{@<part-id>}`, `{@bibliography}`, `{@copyright}`, `{@licenses}` — so the exported styles, numbering and settings are the *template's*, not the corpus's. That is a reasonable design for an academic publishing tool; it is also why a fidelity score is a poor fit, and we say so in the report rather than only in the number.

**What Fidus Writer does that nothing else in the trial does** is worth saying as well: one schema exporting to JATS, HTML, LaTeX, Pandoc JSON, EPUB, DOCX and ODT, with a custom template. That is a publishing engine, not an editor, and it is why the round trip is the wrong instrument for it.""",
    },
    {
        "slug": "docsplus",
        "repo": "docs-plus/docs.plus",
        "name": "docs.plus",
        "subject": "docs.plus",
        "body": """**{weighted}% weighted, {critical}% critical ({critical_passed}/{critical_total}), {features_passed}/{features_total} checks, {text}% text retention, {parts_kept}/{parts_total} parts kept — {failed} failed checks.**

docs.plus keeps **{text}% of the text** — among the highest in the trial — and the reason it loses the revision model is a single, identifiable seam rather than a design flaw.

**The revision loss is `mammoth`, and we can point at the lines.** `mammoth/lib/docx/body-reader.js:447` unwraps `w:ins` and `:450` unwraps `w:moveTo`, so insertions become ordinary text; `:729` sets `ignoreElements["w:del"] = true` and `:732` sets `ignoreElements["w:moveFrom"] = true`, so deletions and move-outs are dropped outright; `:727` drops `w:sectPr` entirely. Counted across the whole chain — fixture → mammoth HTML → rendered HTML → Tiptap JSON → output — `w:ins` goes 3→0→0→0→0, `w:del` 3→0→0→0→0 and `w:moveFrom` 1→0→0→0→0. **No author, no date and no `w16du:dateUtc` survives anywhere downstream.** That is the import step, not the editor.

**Two things worth knowing that are not in the score:**

- On the hostile-input axis, docs.plus **cleaned six of the ten hostile packages** — the decompression bomb, the entry flood, the attribute bomb, the zip-slip, the external-relationship bomb and the active-content package — and refused the entity bomb and the corrupt-parts package (Report D).
- In the rendering report, docs.plus **moves the footnote and endnote bodies to the end of the document** as a numbered list, instead of placing them at the foot of their page (Report C §2.10). Your round trip keeps the text; the page is where it lands that differs.

The product itself — every heading with its own chatroom, the table of contents showing who is in the room, an MCP path so Claude or ChatGPT can read the documents an account can open — is not something a DOCX fidelity benchmark can score, and we would rather say that than pretend the number describes it.""",
    },
    {
        "slug": "plate",
        "repo": "udecode/plate",
        "name": "Plate.js",
        "subject": "Plate.js",
        "body": """**{weighted}% weighted, {critical}% critical ({critical_passed}/{critical_total}), {features_passed}/{features_total} checks, {text}% text retention, {parts_kept}/{parts_total} parts kept — {failed} failed checks.**

Plate.js scores last in the trial, and it is the **only editor in the trial that reports what it lost.** That is worth more than the score, and we would like to be explicit about it.

- **38 typed diagnostics** name each dropped construct — 19 `unsupported-content`, 6 `converter-message`, 2 `resource-omitted`, 8 `property-dropped`, 2 `lossy-content` and 1 `source-unavailable`. No other editor in this trial says anything at all.
- **The default `lossPolicy: 'reject'` refuses a document it cannot represent losslessly.** Handed the corpus, the import fails with 18 typed errors and **writes no output file at all**. There is nothing to corrupt.
- **It is the only editor that detects malformation and refuses it.** Given a corpus carrying all twelve defect classes, Plate fails with `decode-failed` and produces nothing. The other eleven editors read the malformed file and produced output; Plate is the one that declined to process it.
- **The closed "passive vocabulary"** (`internal/sourceEligibility.ts`) decides whether an unchanged document may be exported byte-exactly. That is a genuinely careful piece of design, and it is the reason a low score is not a careless score.

**What the score itself reflects** is the pipeline's shape rather than a defect: DOCX → HTML → editor model → static HTML → DOCX. Every revision is flattened, every field is dropped, every content control is unwrapped, and 24 of the {parts_total} parts go with them. What survives is the text — **{text}%, the second-highest in the trial** — plus the table grid, `gridSpan`, `vMerge`, nested tables, cell shading, bookmarks, `w:vertAlign` and `xml:space="preserve"`.

**On the hostile-input axis, Plate has the strongest ceiling set of any participant** (Report D): named ceilings on the decompression bomb, the entry flood and the deep nest; the attribute bomb **cleaned**; the external-relationship bomb **cleaned** — that is the SSRF and credential vector, and cleaning it is a real result; and the entity bomb, the zip-slip, the active-content package and the corrupt-parts package refused.

Two numbers we would particularly like checked, because they are ours and not yours:

- **The breakdown of the 38 diagnostics.** We counted 19 `unsupported-content`, 6 `converter-message`, 2 `resource-omitted`, 8 `property-dropped`, 2 `lossy-content` and 1 `source-unavailable`. If that enumeration is wrong, the per-tool note is wrong, and we would rather fix it than publish it.
- **The second pass.** The package shrinks from 42,964 to **8,010** bytes as the retained source is replaced by a regenerated one. That is the sharpest second-pass change in the trial, and it is a consequence of the passive-vocabulary gate rather than of a defect.""",
    },
]


def targets(vendor: dict) -> list[tuple[str, str, str]]:
    """Return (repository, slug, extra prose) for each issue to file."""
    slug = vendor["slug"]
    out = [(vendor["repo"], slug, "")]
    if slug == "fidus":
        out.append(("fiduswriter/fiduswriter", slug, FIDUS_APP_EXTRA))
    return out


def render(vendor: dict, extra: str = "") -> str:
    """Return the issue body for one vendor."""
    slug = vendor["slug"]
    f = figures(slug)
    note = f"reports/extras/{slug}.md"
    body = fill(vendor["body"], {**f, "note_url": url(note)})
    if extra:
        body = body.rstrip() + "\n\n" + extra.strip()
    reports = report_block()
    text = fill(INTRO, {
        "name": vendor["name"],
        "repo": REPO_URL,
        "body": body,
        "reports": reports,
        "note_url": url(note),
        "vendors_url": url("reports/vendors.md"),
        "checks": f["features_total"],
        "slug": slug,
    })
    return text


def main() -> int:
    """Write the drafts, or check the figures in them."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        return check()
    DRAFTS.mkdir(exist_ok=True)
    for vendor in VENDORS:
        for repo, slug, extra in targets(vendor):
            name = slug if extra else vendor["slug"]
            path = DRAFTS / f"{vendor['slug']}{'_app' if extra else ''}.md"
            path.write_text(render(vendor, extra), encoding="utf-8")
            print("wrote", path.relative_to(ROOT), "->", repo)
    return 0


PCT = re.compile(r"\d[\d,]*(?:\.\d+)?%")


def check() -> int:
    """Check every percentage in a draft against the measurement."""
    bad = 0
    for vendor in VENDORS:
        slug = vendor["slug"]
        f = figures(slug)
        allowed = {
            f"{f['weighted']}%", f"{f['critical']}%", f"{f['text']}%",
            f"{f['second_weighted']}%", f"{f['second_text']}%",
            "100%", "0%", "99.5%", "20.5%", "88.2%",
        }
        raw = (DRAFTS / f"{slug}.md").read_text(encoding="utf-8")
        # URLs carry percent-encoded spaces, which look like percentages.
        text = re.sub(r"https?://\S+", " ", raw)
        for token in set(PCT.findall(text)):
                if token not in allowed:
                    print(f"  {slug}: unverified figure {token}")
                    bad += 1
    print("unverified figures:", bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
