#!/usr/bin/env python3
"""Apply the Docxodus additions and the §6/§4.5 corrections to Report A."""
from __future__ import annotations

import sys
from pathlib import Path

TARGET = Path("reports/Report A - Serialization by Namespace (2026).md")

EDITS: list[tuple[str, str]] = []


def edit(old: str, new: str) -> None:
    EDITS.append((old, new))


# ---------------------------------------------------------------- intro / TL;DR
edit(
"This report goes through the corpus namespace by namespace. For each one it states what the namespace *is* in WordprocessingML, what each of the twelve editors does with it **according to its own source code**, and what each editor **actually did** to it, measured by round-tripping the corpus through that editor and diffing the resulting package. The two are reported separately because they are not the same claim, and in four places they disagree — and the disagreements are the interesting part.",
"This report goes through the corpus namespace by namespace. For each one it states what the namespace *is* in WordprocessingML, what each of the **twelve editors** does with it **according to its own source code**, and what each editor **actually did** to it, measured by round-tripping the corpus through that editor and diffing the resulting package. A **thirteenth participant, Docxodus**, is measured the same way; it is not an editor but an OpenXML SDK, and §3.12 explains why its boundary is a different *kind* of boundary. The two kinds of evidence are reported separately because they are not the same claim, and in several places they disagree — in **both** directions, which is the part that was not obvious until the matrix was rebuilt against the measurement (§4.5).")

edit(
"- **The boundaries are not where the documentation says.** Read the source of all twelve editors and you find **five distinct kinds of serialization boundary**: a *typed vocabulary plus a generic catch-all* (eigenpal), a *total dispatch table over declared children with a verbatim sink for everything else* (Folio), a *byte-range splice* that never re-serializes at all (GenOffice), a *prefix-literal if/else chain* (Fidus, canvas-editor), and a *fixed namespace allow-list* (Plate.js). Only one of those five is capable of carrying a namespace it has never heard of.",
"- **The boundaries are not where the documentation says.** Read the source of all twelve editors and you find **five distinct kinds of serialization boundary**: a *typed vocabulary plus a generic catch-all* (eigenpal), a *total dispatch table over declared children with a verbatim sink for everything else* (Folio), a *byte-range splice* that never re-serializes at all (GenOffice), a *prefix-literal if/else chain* (Fidus, canvas-editor), and a *fixed namespace allow-list* (Plate.js). Only one of those five is capable of carrying a namespace it has never heard of. The thirteenth participant adds a **sixth** kind — and it is the only one that is not a vocabulary boundary at all: **Docxodus draws its line around a set of *parts*, not a set of *names*** (§3.12).")

edit(
"- **Four editors can carry a namespace they have never heard of: GenOffice, Folio, eigenpal, and — for whole parts — WordCraft.** Everything else drops unfamiliar markup at a boundary, and the corpus contains a namespace (`ns0` = `http://example.com/fixture`) that appears in **no** editor's allow-list, precisely to find that boundary.",
"- **Five editors can carry a namespace they have never heard of: GenOffice, Folio, eigenpal, Docxodus, and — for whole parts — WordCraft.** Everything else drops unfamiliar markup at a boundary, and the corpus contains a namespace (`ns0` = `http://example.com/fixture`) that appears in **no** editor's allow-list, precisely to find that boundary.")

edit(
"- **The single sharpest probe in the corpus is `w16du:dateUtc`** — a single attribute, on a revision wrapper, in a namespace Microsoft introduced in 2023. **Eight of the twelve editors drop it**, including Microsoft Word's own round-trip baseline, LibreOffice. Four keep it. **Not one of the twelve reports that it dropped it.**",
"- **The single sharpest probe in the corpus is `w16du:dateUtc`** — a single attribute, on a revision wrapper, in a namespace Microsoft introduced in 2023. **Eight of the twelve editors drop it**, including Microsoft Word's own round-trip baseline, LibreOffice. Four keep it — and the thirteenth participant, Docxodus, is the **only participant in the study that keeps it by decision rather than by accident**: it declares a typed `XName` for the attribute and validates its value (`RevisionOps.cs:37`, `:565`). **Not one of the twelve reports that it dropped it.**")

edit(
"- **Losing a namespace is almost never loud.** Of the twelve editors, exactly **two** have a namespace-level reporting mechanism: Plate.js (38 typed diagnostics, `lossPolicy` defaults to `'reject'`) and SuperDoc (a named diagnostic code per fail-closed drawing family). The other ten drop whole vocabularies without a word.",
"- **Losing a namespace is almost never loud.** Of the twelve editors, exactly **two** have a namespace-level reporting mechanism: Plate.js (38 typed diagnostics, `lossPolicy` defaults to `'reject'`) and SuperDoc (a named diagnostic code per fail-closed drawing family). The other ten drop whole vocabularies without a word. **Docxodus is the thirteenth participant, and at the serialization layer it drops nothing** — which is exactly why the obligation moves one layer up, to its renderer, which names what it cannot draw (`[SMARTART]`, `[MATH]`).")

# ------------------------------------------------------------------ §3.12
edit(
"""---

## 4. Measured namespace survival""",
"""### 3.12 Docxodus — an OpenXML SDK that draws its boundary around *parts*, not around vocabularies

**Docxodus is not an editor, and that is the point of putting it in this table.** It is a .NET OOXML engine — the `docxodus` npm package (14.2.0) with the companion `@docxodus/export` (14.2.0), built on the `DocumentFormat.OpenXml` SDK 3.5.1 — published as WebAssembly. Its product surface is a *SDK*: an in-browser block editor, a paginated DOCX→HTML materializer, and a package writer. It enters this study twice: as the **package writer** measured in §4, and as the **renderer** measured in *Rendering Versus Word*. What follows is the write path only.

**The boundary mechanism is a list of parts.** The other five mechanisms in this report all draw a line around a *vocabulary* — a set of element names to dispatch on. Docxodus draws it around a set of *files*. `Docxodus/DocxSession.cs:968-986` — `EnumerateProjectedParts` yields the main document part, every header and footer part, footnotes, endnotes, the comments part and its three companions (`commentsExtended`, `commentsIds`, `people`), the settings part, the styles part, and the custom-XML parts. Those are the only parts the projector can write to.

**Everything outside that list is carried byte-for-byte.** The package is a ZIP and the SDK writes it entry by entry; `Docxodus/ZipPackageOutputNormalizer.cs:14` states the rule in the source's own words: *"The package payload is copied entry-for-entry; only ZIP compression and extraction metadata are normalized."* The chart, the four SmartArt parts, the image, the OLE object, the embedded workbook and the custom-XML datastore are none of them on the projected list, so none of them is re-written.

**The XML manipulation is LINQ-to-XML, not a typed DOM.** This is the single fact that explains the rest. The save path flushes each projected part's cached `XDocument` back into its part and then saves the package (`Docxodus/DocxSession.cs:838-842`; the `GetXDocument`/`PutXDocument` accessors are at `Docxodus/PtOpenXmlUtil.cs:141`). **`OpenXmlUnknownElement` appears nowhere in the repository** — so the SDK's schema model is never the thing that decides whether an element survives. An element Docxodus has never heard of is simply a node in an `XDocument`, and nodes in an `XDocument` are carried.

**Only the parts the projector actually materialised are re-written.** `DocxSession.cs:838-840` writes a part back only when `part.GetXDocument().Root is not null` — that is, only when the projector opened it. The measurement matches exactly: **10 of the corpus's 35 parts come back re-serialised and 25 come back byte-identical.** The re-serialised set is `document.xml`, `comments.xml`, `footnotes.xml`, `endnotes.xml`, `header1.xml`, `header2.xml`, `footer1.xml`, `footer2.xml`, `settings.xml` and `styles.xml`. `customXml/item1.xml` is a *candidate* for projection but comes back byte-identical, because the projector never opened it. **This is the rule that derives §6's Docxodus column**, and it is stated here rather than left to be reverse-engineered from the cells.

**`w16du` is the one namespace Docxodus handles by name.** `Docxodus/Internal/RevisionOps.cs:37` declares a typed `XName` for `w16du:dateUtc`, and `RevisionOps.cs:565` rejects a malformed value with an `invalid_revision_date_utc` diagnostic. The corpus's attribute is one of the values the product's own test suite pins (`Docxodus.Tests/DocxSessionBulkRevisionSafetyTests.cs:40`). **This is the first participant in the study whose `w16du` keep is a decision rather than a by-product** — the other four keepers keep it because their architecture carries it for free.

**And then there is a second path, one layer over, where the same product drops it.** The IR diff renderer normalises a *preserved original clone* and, in the course of it, strips *"Non-W-namespace extension attributes on revision elements (e.g. Word 2023's `w16du:dateUtc`)"*, on the stated ground that *"the extension attrs are undeclared noise to the SDK schema the output is validated against"* (`Docxodus/Ir/Diff/IrMarkupRenderer.cs:10795`). **So the same product keeps `w16du:dateUtc` in the DOCX package and removes it in the diff/merge renderer.** It is the package-versus-render distinction in its sharpest possible form: one attribute, two layers, opposite answers.

**What this means for the boundary taxonomy.** A vocabulary boundary has a floor and a ceiling: names above the line are handled, names below it are dropped. Docxodus's boundary has only a floor — **inside a projected part there is no name the projector has to know, because the XML is a tree and not a dispatch table.** The consequence cuts both ways, and the report should say so plainly: Docxodus **cannot lose a namespace it has never heard of**, and it also **cannot edit one**. Its floor is the strongest in the study; its ceiling is the only one that is not an editor's ceiling at all, because it was never trying to be an editor.

---

## 4. Measured namespace survival""")

# ------------------------------------------------------------------ §4.2
edit(
"Reading the `w` row: **five editors keep every one of the 309 distinct `w:` names** — SuperDoc, Folio, GenOffice and eigenpal, plus office-open which loses exactly one (`@dirty`). Below them there is a cliff: office-open and Docen lose a handful of names, WordCraft loses fifteen, and then Fidus, canvas-editor, docs.plus and Plate.js each keep **roughly a third** of the main vocabulary.",
"Reading the `w` row: **five participants keep every one of the 309 distinct `w:` names** — SuperDoc, Folio, GenOffice, eigenpal and Docxodus. office-open comes next, losing exactly one (`@dirty`), then Docen four and WordCraft fifteen; below them there is a cliff, where Fidus, canvas-editor, docs.plus and Plate.js each keep **roughly a third** of the main vocabulary.")

# ------------------------------------------------------------------ §4.3
edit(
"Three details in that table are worth pulling out.",
"Four details in that table are worth pulling out.")

edit(
"""**The `a` namespace tells the drawing story.** Fidus and canvas-editor keep 11 of 60 `a:` names — and the ones they lose are the *theme* names (`themeElements`, `clrScheme`, `fontScheme`, `fmtScheme`, `effectStyleLst`, `fillStyleLst`, `bgFillStyleLst`) plus every text-body name (`bodyPr`, `p`, `r`, `t`, `rPr`, `pPr`). They keep the *geometry* names they need for a bitmap (`blipFill`, `spPr`, `prstGeom`, `xfrm`) and lose everything else, because they model a picture as a picture and nothing more. Plate.js keeps 33: it keeps the text-body names (`bodyPr`, `p`, `r`, `t`, `rPr`, `pPr`) because it has a text model, and loses `blip` — which is exactly the image loss the diagnostic reports.""",
"""**The `a` namespace tells the drawing story.** Fidus and canvas-editor keep 11 of 60 `a:` names — and the ones they lose are the *theme* names (`themeElements`, `clrScheme`, `fontScheme`, `fmtScheme`, `effectStyleLst`, `fillStyleLst`, `bgFillStyleLst`) plus every text-body name (`bodyPr`, `p`, `r`, `t`, `rPr`, `pPr`). They keep the *geometry* names they need for a bitmap (`blipFill`, `spPr`, `prstGeom`, `xfrm`) and lose everything else, because they model a picture as a picture and nothing more. Plate.js keeps 33: it keeps the text-body names (`bodyPr`, `p`, `r`, `t`, `rPr`, `pPr`) because it has a text model, and loses `blip` — which is exactly the image loss the diagnostic reports.

**The one participant with no row in this table is Docxodus, and its absence is the finding.** Docxodus is the only participant in the study that loses **no** distinct name in any namespace — not one partial loss anywhere. Every other participant has at least one row. The reason is architectural rather than lucky: there is no name-based dispatch in its write path at all (§3.12), so there is no name that *can* be left behind.""")

# ------------------------------------------------------------------ §4.4
edit(
"**Disagreement 1 — WordCraft and the two namespaces the code never mentions.** §3.7 showed that WordCraft has no `w16du` handling anywhere in `crates/docx/src`. The measurement adds two more: WordCraft also loses **`w15:restartNumberingAfterBreak`** and **`w16cid:durableId`**, and also loses `cs` (the chart-style parts), `w10`, and the `v:textbox` element. The code reading is right that there is no handler; it is incomplete because *absence of a handler for `w16du` implies absence of handlers for the neighbouring namespaces too*.",
"**Disagreement 1 — WordCraft and the namespaces the code never mentions.** §3.7 showed that WordCraft has no `w16du` handling anywhere in `crates/docx/src`. The measurement adds three more losses: WordCraft also loses **`w15:restartNumberingAfterBreak`**, **`cs`** (the chart-style parts) and **`w10:wrap`**, and it loses **`v:textbox`** while keeping the other two `v` names. **It does not lose `w16cid:durableId`** — an earlier edition of this report said it did, and that was wrong; the attribute is present in `word/commentsIds.xml` in WordCraft's output, and §6 now carries the measured value. The code reading is right that there is no handler; it is incomplete because *absence of a handler for `w16du` implies absence of handlers for the neighbouring namespaces too* — though not for every one of them.")

# ------------------------------------------------------------------ §5.1
edit(
"**What the twelve do.**",
"**What the twelve editors do — and what the thirteenth participant does.**")

edit(
"| **Keeps the construct whole, with no branch selector of its own** — it reaches the model as an opaque `unsupportedDrawing` payload and is re-emitted verbatim | office-open, Docen | `office-open/.../drawing-parse.ts:225-284`; `unsupported-drawing-run.ts:163` |",
"""| **Keeps the construct whole, with no branch selector of its own** — it reaches the model as an opaque `unsupportedDrawing` payload and is re-emitted verbatim | office-open, Docen | `office-open/.../drawing-parse.ts:225-284`; `unsupported-drawing-run.ts:163` |
| **Re-serialises the construct through the SDK's part model, keeping both branches** | Docxodus | `Docxodus/DocxSession.cs:838-842` — the part is flushed from its `XDocument` and the package re-saved |""")

edit(
"**Measured.** `mc` is kept whole by SuperDoc, Folio, GenOffice, eigenpal, office-open, Docen and LibreOffice; kept at 1/4 (the `mc:Ignorable` attribute only) by WordCraft, Fidus and canvas-editor; and **dropped entirely by docs.plus and Plate.js**.",
"**Measured.** `mc` is kept whole by SuperDoc, Folio, GenOffice, eigenpal, office-open, Docen, **Docxodus** and LibreOffice; kept at 1/4 (the `mc:Ignorable` attribute only) by WordCraft, Fidus and canvas-editor; and **dropped entirely by docs.plus and Plate.js**.")

edit(
"| Docen | 1,133 bytes | `xmlns:a` declared onto the element |",
"""| Docen | 1,133 bytes | `xmlns:a` declared onto the element |
| **Docxodus** | 1,080 bytes | **equivalent to the corpus after normalising self-closing-tag spacing** (11 `/>` become ` />`); both branches intact |""")

edit(
"**Six of the seven editors that keep the structure keep *both* branches.**",
"**Every participant that keeps the structure keeps *both* branches** — the seven in the table above plus LibreOffice, eight in all.")

# ------------------------------------------------------------------ §5.2
edit(
"**Who keeps it.** SuperDoc, Folio, GenOffice, eigenpal — four editors. **Folio and GenOffice keep it as a *consequence* of their architecture rather than as a decision**: Folio's `w:ins` wrapper is carried by the verbatim sink, and GenOffice splices the original bytes, so the attribute rides along inside them. eigenpal keeps it because `w:ins` is a typed element and unknown attributes on typed elements are retained.",
"**Who keeps it.** SuperDoc, Folio, GenOffice, eigenpal — four editors — **and Docxodus**. **Folio and GenOffice keep it as a *consequence* of their architecture rather than as a decision**: Folio's `w:ins` wrapper is carried by the verbatim sink, and GenOffice splices the original bytes, so the attribute rides along inside them. eigenpal keeps it because `w:ins` is a typed element and unknown attributes on typed elements are retained. **Docxodus is the only participant in the study that keeps it by decision**: its revision layer declares a typed `XName` for the attribute (`Docxodus/Internal/RevisionOps.cs:37`) and rejects a malformed value with an `invalid_revision_date_utc` diagnostic (`RevisionOps.cs:565`).")

edit(
"**Who loses it.** office-open, Docen, WordCraft, Fidus, canvas-editor, docs.plus, Plate.js **and LibreOffice** — eight.",
"""**Who loses it.** office-open, Docen, WordCraft, Fidus, canvas-editor, docs.plus, Plate.js **and LibreOffice** — eight.

**But the loss is not universal inside Docxodus either.** The same product *drops* the attribute in its IR diff renderer, which strips *"non-`w`-namespace extension attributes on revision elements (e.g. Word 2023's `w16du:dateUtc`)"* when normalising a preserved original clone (`Docxodus/Ir/Diff/IrMarkupRenderer.cs:10795`). **The package keeps it; the diff renderer drops it.** That is the package-versus-render distinction in its sharpest form: one product, two layers, opposite answers on the same attribute.""")

# ------------------------------------------------------------------ §5.3
edit(
"**Measured.** `w14` is kept whole by SuperDoc, GenOffice, eigenpal and WordCraft; kept at 10/12 by Folio, office-open, Docen and LibreOffice (losing exactly `@paraId` and `@textId`); and **lost entirely by Fidus, canvas-editor, docs.plus and Plate.js**.",
"**Measured.** `w14` is kept whole by SuperDoc, GenOffice, eigenpal, WordCraft **and Docxodus**; kept at 10/12 by Folio, office-open, Docen and LibreOffice (losing exactly `@paraId` and `@textId`); and **lost entirely by Fidus, canvas-editor, docs.plus and Plate.js**.")

# ------------------------------------------------------------------ §5.4
edit(
"- `w15` — kept by SuperDoc, Folio, GenOffice, eigenpal, office-open, Docen, Fidus, canvas. Lost by WordCraft, docs.plus, Plate.js, LibreOffice.\n- `w16cid` — kept by SuperDoc, Folio, GenOffice, eigenpal, WordCraft. Lost by office-open, Docen, Fidus, canvas, docs.plus, Plate.js, LibreOffice.",
"- `w15` — kept by SuperDoc, Folio, GenOffice, eigenpal, office-open, Docen, Fidus, canvas, **Docxodus**. Lost by WordCraft, docs.plus, Plate.js, LibreOffice.\n- `w16cid` — kept by SuperDoc, Folio, GenOffice, eigenpal, WordCraft, **Docxodus**. Lost by office-open, Docen, Fidus, canvas, docs.plus, Plate.js, LibreOffice.")

# ------------------------------------------------------------------ §5.5
edit(
"**Measured.** `dgm` is kept whole by SuperDoc, Folio, GenOffice, eigenpal, office-open, Docen, WordCraft and LibreOffice, and **dropped entirely by Fidus, canvas-editor, docs.plus and Plate.js** — 35 distinct names, 69 element uses, four parts, gone.",
"**Measured.** `dgm` is kept whole by SuperDoc, Folio, GenOffice, eigenpal, office-open, Docen, WordCraft, **Docxodus** and LibreOffice, and **dropped entirely by Fidus, canvas-editor, docs.plus and Plate.js** — 35 distinct names, 69 element uses, four parts, gone.")

edit(
"| **SuperDoc** | Preserved in the file, **drawn as a placeholder**, with the diagnostic `render.drawing.unsupported-object` (`drawing-taxonomy.ts:328-332`). |",
"""| **SuperDoc** | Preserved in the file, **drawn as a placeholder**, with the diagnostic `render.drawing.unsupported-object` (`drawing-taxonomy.ts:328-332`). |
| **Docxodus** | The four diagram parts are **copied byte-for-byte** — they are not among the ten parts the projector rewrites — while the `dgm:relIds` pointer in `document.xml` is re-serialised. **The payload is the author's; the pointer is Docxodus's.** Its *renderer*, however, substitutes a `[SMARTART]` placeholder for the diagram (see *Rendering Versus Word*). |""")

edit(
"**The cost.** For the four editors that drop it: a diagram becomes a blank rectangle. For the four that keep it but render a placeholder (SuperDoc, and by extension Folio's bounded 128-shape preview and eigenpal's summary): **the file is right and the screen is wrong** — the user sees a placeholder, sends the file on, and the recipient sees the real diagram. For WordCraft: the diagram is *replaced*, and the user is not told.",
"**The cost.** For the four editors that drop it: a diagram becomes a blank rectangle. For the four that keep it but render a placeholder (SuperDoc and Docxodus, and by extension Folio's bounded 128-shape preview and eigenpal's summary): **the file is right and the screen is wrong** — the user sees a placeholder, sends the file on, and the recipient sees the real diagram. For WordCraft: the diagram is *replaced*, and the user is not told.")

# ------------------------------------------------------------------ §5.6
edit(
"- `c` — kept whole by SuperDoc, Folio, GenOffice, eigenpal, office-open, Docen and WordCraft; **dropped entirely** by Fidus, canvas-editor, docs.plus and Plate.js; kept at 39/40 by LibreOffice (losing `c:layout`).\n- `cs` — kept whole by SuperDoc, Folio, GenOffice, eigenpal, office-open and Docen; **dropped by WordCraft**, Fidus, canvas-editor, docs.plus, Plate.js **and LibreOffice**.",
"- `c` — kept whole by SuperDoc, Folio, GenOffice, eigenpal, office-open, Docen, WordCraft **and Docxodus**; **dropped entirely** by Fidus, canvas-editor, docs.plus and Plate.js; kept at 39/40 by LibreOffice (losing `c:layout`).\n- `cs` — kept whole by SuperDoc, Folio, GenOffice, eigenpal, office-open, Docen **and Docxodus**; **dropped by WordCraft**, Fidus, canvas-editor, docs.plus, Plate.js **and LibreOffice**.")

edit(
"**WordCraft is the only editor that keeps the chart and loses its companions.** That is the mechanism behind its chart rendering differently from the original while the chart part itself measures as pass-through — a finding from the first report, now with its namespace-level explanation.",
"""**WordCraft is the only editor that keeps the chart and loses its companions.** That is the mechanism behind its chart rendering differently from the original while the chart part itself measures as pass-through — a finding from the first report, now with its namespace-level explanation.

**Docxodus keeps both, and for a structural reason worth stating.** `word/charts/style1.xml` and `word/charts/colors1.xml` are not among the ten parts the projector rewrites, so they are copied byte-for-byte — the author's chart design, not a re-derived one. This is the strongest form of the companion-part result available: not only is nothing lost, the *appearance* is literally the author's bytes.""")

# ------------------------------------------------------------------ §5.7
edit(
"- `v` — kept whole by SuperDoc, Folio, GenOffice, eigenpal, office-open, Docen and LibreOffice; **2/3 by WordCraft** (losing `v:textbox`); **dropped entirely** by Fidus, canvas-editor, docs.plus and Plate.js.\n- `o` — kept whole by SuperDoc, Folio, GenOffice, eigenpal, office-open, Docen, WordCraft and LibreOffice; **dropped entirely** by Fidus, canvas-editor, docs.plus and Plate.js.",
"- `v` — kept whole by SuperDoc, Folio, GenOffice, eigenpal, office-open, Docen, **Docxodus** and LibreOffice; **2/3 by WordCraft** (losing `v:textbox`); **dropped entirely** by Fidus, canvas-editor, docs.plus and Plate.js.\n- `o` — kept whole by SuperDoc, Folio, GenOffice, eigenpal, office-open, Docen, WordCraft, **Docxodus** and LibreOffice; **dropped entirely** by Fidus, canvas-editor, docs.plus and Plate.js.")

# ------------------------------------------------------------------ §5.8
edit(
"""**Measured.** `m` is kept whole by SuperDoc, Folio (converted to MathML, `mathToMathml.ts`), GenOffice, eigenpal, eigenpal's dedicated OMML path (`omml-equation.ts:770`), office-open, Docen, WordCraft (dedicated reader/writer) and LibreOffice; and **dropped entirely by Fidus, canvas-editor, docs.plus and Plate.js**.

**The reporting is the interesting part.** Mammoth has no math reader, so it emits *"An unrecognised element was ignored: m:oMath"*. docs.plus surfaces that as an `unsupported-element` `ConversionWarning`; Plate surfaces it as a `converter-message` diagnostic. **Both report it, and both lose the mathematics.** Reporting is not preservation — and this pair is the clean demonstration of the difference, because they are the same importer with different reporting layers.""",
"""**Measured.** `m` is kept whole by SuperDoc, Folio (converted to MathML, `mathToMathml.ts`), GenOffice, eigenpal, eigenpal's dedicated OMML path (`omml-equation.ts:770`), office-open, Docen, WordCraft (dedicated reader/writer), **Plate.js**, Docxodus and LibreOffice; and **dropped entirely by Fidus, canvas-editor and docs.plus**.

**Plate.js is the surprise, and it sharpens the point.** Mammoth has no math reader, so it emits *"An unrecognised element was ignored: m:oMath"*. docs.plus surfaces that as an `unsupported-element` `ConversionWarning`; Plate surfaces it as a `converter-message` diagnostic. **Both report it. docs.plus loses the mathematics — its package has none of the four `m:` names. Plate.js does not: its DOCX export lane writes all four.** The importer ignored the element and the writer still carried it, because the subtree reached the model by a route the importer's own diagnostic never mentions. **Reporting is not preservation, and neither is ignoring**: a namespace can be reported as unrecognised, be absent from the rendered HTML, and still be sitting in the exported package. An earlier edition of this report listed Plate.js among the editors that drop `m`; that was the code reading, and §4.5 corrects it.

**Fidus is the other correction.** The earlier reading said Fidus converts OMML to MathML. It does not — Fidus's output has none of the four `m:` names.

**Docxodus keeps the OMML in the package and substitutes a `[MATH]` chip for it on the page.** The package layer and the render layer give opposite answers about the same namespace, which is the subject of this study in a single cell.""")

# ------------------------------------------------------------------ §5.9
edit(
"**Measured.** `ns0` is kept whole by SuperDoc, Folio, GenOffice, eigenpal, office-open, Docen, WordCraft and LibreOffice, and **dropped entirely by Fidus, canvas-editor, docs.plus and Plate.js**.",
"**Measured.** `ns0` is kept whole by SuperDoc, Folio, GenOffice, eigenpal, office-open, Docen, WordCraft, **Docxodus** and LibreOffice, and **dropped entirely by Fidus, canvas-editor, docs.plus and Plate.js**.")

edit(
"| WordCraft | The whole part is copied through a manifest-gated passthrough | **Not a decision** |",
"""| WordCraft | The whole part is copied through a manifest-gated passthrough | **Not a decision** |
| Docxodus | `customXml/item1.xml` is not among the ten parts the projector rewrites, so it is copied byte-for-byte | **Not a decision** — a side effect of the part boundary |""")

# ------------------------------------------------------------------ §5.10
edit(
"**Measured.** `w` is kept whole by SuperDoc, Folio, GenOffice and eigenpal; office-open loses 1 of 309, Docen 4, WordCraft 15, LibreOffice 49, and then the cliff: Fidus 98, canvas 119, docs.plus 114, Plate.js 108. `r` is kept whole by eight editors, and by **none of Fidus, canvas-editor, docs.plus or Plate.js** beyond one or two names.",
"**Measured.** `w` is kept whole by SuperDoc, Folio, GenOffice, eigenpal **and Docxodus**; office-open loses 1 of 309, Docen 4, WordCraft 15, LibreOffice 49, and then the cliff: Fidus 98, canvas 119, docs.plus 114, Plate.js 108. `r` is kept whole by nine participants, and by **none of Fidus, canvas-editor, docs.plus or Plate.js** beyond one or two names.")

# ------------------------------------------------------------------ §5.11
edit(
"""- `app` — kept whole by six editors; partially by WordCraft (8/9), Fidus (3/9), canvas (1/9), LibreOffice (4/9); **gone entirely** from docs.plus and Plate.js.
- `cp` — kept whole by eight editors; 4/5 by docs.plus and Plate.js; 3/5 by canvas; **1/5 by Fidus**.
- `dc` — kept whole by nine; 2/4 by Fidus; 1/4 by canvas.
- `dcterms` — **kept whole by every single editor**, including the four that drop `app` and `cp` entirely.""",
"""- `app` — kept whole by seven participants; partially by WordCraft (8/9), Fidus (3/9), canvas (1/9), LibreOffice (4/9); **gone entirely** from docs.plus and Plate.js.
- `cp` — kept whole by eight participants; 4/5 by docs.plus and Plate.js; 3/5 by canvas; **1/5 by Fidus**.
- `dc` — kept whole by every participant except Fidus (2/4) and canvas (1/4).
- `dcterms` — **kept whole by every single participant**, including the four that drop `app` and `cp` entirely.""")

# ------------------------------------------------------------------ §7
edit(
"- **There is no single serialization boundary, and the shape of the boundary predicts the loss better than the editor's reputation does.** Five distinct mechanisms appear across twelve editors, and they sort cleanly: **splice-and-carry** (GenOffice, and Folio's verbatim sink) loses least; **typed-plus-generic** (eigenpal) is the only design that *documents* its fallback; **closed allow-lists** (Plate.js's `PASSIVE_NAMESPACES`, Mammoth's 9-entry namespace map) lose exactly what is not on the list; **prefix-literal dispatch** (office-open, Fidus, canvas-editor) loses whatever the switch did not enumerate; and **model-regeneration** (Docen, WordCraft, docs.plus) loses whatever the model did not type.",
"""- **There is no single serialization boundary, and the shape of the boundary predicts the loss better than the editor's reputation does.** Five distinct mechanisms appear across the twelve editors, and a **sixth** appears across the thirteen participants. They sort cleanly: **splice-and-carry** (GenOffice, and Folio's verbatim sink) loses least; **typed-plus-generic** (eigenpal) is the only design that *documents* its fallback; **closed allow-lists** (Plate.js's `PASSIVE_NAMESPACES`, Mammoth's 9-entry namespace map) lose exactly what is not on the list; **prefix-literal dispatch** (office-open, Fidus, canvas-editor) loses whatever the switch did not enumerate; **model-regeneration** (Docen, WordCraft, docs.plus) loses whatever the model did not type; and **part-boundary** (Docxodus) does not dispatch on names at all — it rewrites ten parts and copies the other twenty-five byte-for-byte, so it has no vocabulary boundary to lose across.
- **The thirteenth participant wins by not having the kind of boundary the others have.** Docxodus is the only participant to keep every distinct name of all 28 namespaces, and it does it by drawing its boundary around a set of *parts* rather than a set of *names* (§3.12). The price is equally clear: a namespace it has never heard of is carried but cannot be changed, and its *renderer* is the layer that must decide what to do with what it cannot draw.""")

edit(
"- **\"Keeps every name\" and \"keeps every *value*\" are different claims, and the difference is where the surprises live.** `dcterms:modified` survives in all twelve outputs — but in at least four of them it is a *freshly written* timestamp.",
"- **\"Keeps every name\" and \"keeps every *value*\" are different claims, and the difference is where the surprises live.** `dcterms:modified` survives in all thirteen outputs — but in at least four of them it is a *freshly written* timestamp.")

edit(
"- **Silence is the default, and it is the most expensive default.** Eight editors drop `w16du:dateUtc`. Two editors report namespace losses in a typed vocabulary (Plate.js, and docs.plus's `ConversionWarning` layer over the same Mammoth importer). One editor reports drawing failures by family (SuperDoc). **The remaining nine say nothing at all** — and the corpus's `w16du`, `w15` and `w16cid` losses are exactly the ones no user would ever notice, which is precisely why the silence is dangerous.",
"- **Silence is the default, and it is the most expensive default.** Eight editors drop `w16du:dateUtc`. Two editors report namespace losses in a typed vocabulary (Plate.js, and docs.plus's `ConversionWarning` layer over the same Mammoth importer). One editor reports drawing failures by family (SuperDoc). **The remaining nine say nothing at all** — and the corpus's `w16du`, `w15` and `w16cid` losses are exactly the ones no user would ever notice, which is precisely why the silence is dangerous. Docxodus is silent at the serialization layer for the best possible reason — it loses nothing there — but its renderer names what it cannot draw, and that is the layer where the user is actually looking.")

edit(
"- **The `mc` namespace is where a document stops being a document.** It is the only construct in the corpus whose two encodings carry *different visible text*, and the only one where twelve editors produce **six different outcomes** on the same input: two take the wrong branch, two take the right one without checking `Requires`, two drop it, one flattens it, one preserves it with a diagnostic, one preserves it in the file while splicing the original bytes back. If you are choosing an editor by namespace behaviour, this is the row to look at.",
"- **The `mc` namespace is where a document stops being a document.** It is the only construct in the corpus whose two encodings carry *different visible text*, and the only one where the thirteen participants produce **seven different outcomes** on the same input: two take the wrong branch, two take the right one without checking `Requires`, three drop it, one flattens it, one preserves it with a diagnostic, one preserves it in the file while splicing the original bytes back, and one re-serialises it through a schema-typed SDK. If you are choosing an editor by namespace behaviour, this is the row to look at.")

edit(
"- **The editors that keep the most are not the ones that tell you the most, and the editors that tell you the most are not the ones that keep the most.** Plate.js and docs.plus share an importer and differ only in reporting; Plate keeps less and reports more. WordCraft keeps almost everything and reports nothing.",
"- **The editors that keep the most are not the ones that tell you the most, and the editors that tell you the most are not the ones that keep the most.** Plate.js and docs.plus share an importer and differ only in reporting; Plate keeps less and reports more. WordCraft keeps almost everything and reports nothing. Docxodus keeps everything and reports nothing about serialization — but names, in the renderer, exactly the two namespaces it cannot draw.")

# ------------------------------------------------------------------ Reproducing
edit(
"""build/ns_map.py                 # measured namespace survival, printed matrix
build/ns_json.py                # the same measurement as JSON (out/ns_map.json)
build/ns_tables.py condensed    # report tables: who kept what, per namespace
build/ns_tables.py partial      # report tables: the exact lost names
build/part_map.py --matrix      # the part-level matrix (the companion report)""",
"""build/ns_map.py                 # measured namespace survival, printed matrix
build/ns_json.py                # the same measurement as JSON (out/ns_map.json)
build/ns_tables.py condensed    # report tables: who kept what, per namespace
build/ns_tables.py partial      # report tables: the exact lost names
build/ns_group_tables.py --patch "reports/Report A - Serialization by Namespace (2026).md"
build/report_a_matrix.py        # §6: rebuild the cross-editor matrix, validated
                                #         against out/ns_map.json before patching
build/part_map.py --matrix      # the part-level matrix (the companion report)""")

# ------------------------------------------------------------------ Gaps
edit(
"8. **This report measures serialization, not rendering.** Whether a kept construct is *drawn* is a separate question, answered in *Rendering Versus Word*.",
"""8. **This report measures serialization, not rendering.** Whether a kept construct is *drawn* is a separate question, answered in *Rendering Versus Word*. For Docxodus the two answers are unusually far apart: its package keeps every namespace, and its renderer substitutes a `[SMARTART]` placeholder and a `[MATH]` chip for two of them.
9. **Docxodus was measured through its CLI, not through its in-browser block editor.** The browser host could not be used: `convertDocxToPaginatedHtml` inside the Vite dev server fails its own asset-graph attestation (*"The runtime asset graph is malformed"*) because Vite's pre-bundling breaks `import.meta.url` resolution of `export-assets.json`. The `@docxodus/export` CLI was used instead, with the machine's existing Playwright Chrome for Testing in place of a bundled Chromium (the `@playwright/browser-chromium` download stalled and was abandoned) and with 20 static TTFs copied out of LibreOffice's bundle in place of the shipped font directory, which the product rejects because it contains a variable font. **All three substitutions are harness interventions and are disclosed here**; the rendered pages are the product's own materialisation, photographed rather than reproduced.
10. **Docxodus is an SDK, not an editor, and the comparison is not symmetric.** It has no editing model to lose edits in, no import pipeline to lose a namespace *in*, and no diagnostic vocabulary to report with. §6's Docxodus column is **derived** from the part classification in §3.12 — which parts the projector re-writes, and which it copies — and every cell in it is checked against `out/ns_map.json` by `build/report_a_matrix.py` before the table is written. Where the mechanism is a byte-for-byte copy of a part the projector does not touch, the cell says so (`K (part)`); where the namespace spans both a rewritten and a copied part, it says `R (parts K)`.""")


def main() -> int:
    text = TARGET.read_text()
    for i, (old, new) in enumerate(EDITS, 1):
        n = text.count(old)
        if n != 1:
            print(f"EDIT {i} matched {n} times (expected 1):\n---\n{old[:200]}\n---")
            return 1
        text = text.replace(old, new)
    TARGET.write_text(text)
    print(f"applied {len(EDITS)} edits to {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
