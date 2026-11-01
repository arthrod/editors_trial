# Outreach

The trial's per-tool notes are published here, and the same note has been
filed as an issue on each project's own repository, so that a maintainer can
correct the measurement from where they already work. Every issue links back
to the report it quotes and asks for a pull request rather than a reply.

| Tool | Repository | Issue |
|---|---|---|
| SuperDoc | `superdoc/docx-editor` | https://github.com/superdoc/docx-editor/issues/4125 |
| Docxodus | `JSv4/Docxodus` | https://github.com/JSv4/Docxodus/issues/1518 |
| Folio | `stella/folio` | https://github.com/stella/folio/issues/2237 |
| GenOffice | `genspark-ai/genoffice` | https://github.com/genspark-ai/genoffice/issues/2381 |
| eigenpal | `eigenpal/docx-editor` | https://github.com/eigenpal/docx-editor/issues/1753 |
| office-open | `DemoMacro/office-open` | https://github.com/DemoMacro/office-open/issues/67 |
| Docen | `DemoMacro/docen` | https://github.com/DemoMacro/docen/issues/40 |
| WordCraft | `storytold/wordcraft` | https://github.com/storytold/wordcraft/issues/5163 |
| canvas-editor | `Hufe921/canvas-editor` | https://github.com/Hufe921/canvas-editor/issues/1513 |
| Fidus Writer (`@fiduswriter/document`) | `fiduswriter/fiduswriter-document-ts` | https://github.com/fiduswriter/fiduswriter-document-ts/issues/1 |
| Fidus Writer (application) | `fiduswriter/fiduswriter` | https://github.com/fiduswriter/fiduswriter/issues/1424 |
| docs.plus | `docs-plus/docs.plus` | https://github.com/docs-plus/docs.plus/issues/662 |
| Plate.js | `udecode/plate` | https://github.com/udecode/plate/issues/5327 |

The drafts in this directory are generated, not hand-written:
`python3 build/outreach_issues.py` writes them from the score files in `out/`,
so a figure in an issue cannot drift from the measurement, and
`python3 build/outreach_issues.py --check` verifies every percentage in a
draft against `out/`.

Filing a correction is a pull request against the report that carries the
figure, and `build/test_report_claims.py` checks that the per-tool note still
agrees with the shipped scorer.
