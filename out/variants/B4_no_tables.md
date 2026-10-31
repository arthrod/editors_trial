# Malformed Parts: Causes, Detection, and Repair (2026-10-30)

**A companion to *Open-Source DOCX Editors, Re-verified Against Code and Measured by Round-Trip (2026-10-29)*** and to *What Is Serialized, What Is Pass-Through, and What Is Actually Rendered (2026-10-30)*.

The first report found that the corpus it used — a hand-built 35-part adversarial DOCX — **Microsoft Word 16.115 would not open at all**, and located twelve defect classes behind that. This report closes the loop: what malformed parts look like, what causes them, and — the question the first report could not answer — **does any editor repair a malformed input, or does it preserve the damage?**

---

## TL;DR

- **Not one editor repairs anything.** Handed a corpus carrying all twelve defect classes, **every** editor either reproduced the damage or dropped the part that carried it. None diagnosed it, none fixed it, and only one said anything about it.
- **Four of the eleven editor outputs cannot be opened by Microsoft Word**, and only two of those four fail for a reason a schema validator could have caught:

