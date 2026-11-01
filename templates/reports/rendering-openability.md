# Rendering openability

Report C, section 6, compares Word's rendering of each editor's output with Word's rendering of the fixture.

## Raw refusals

In section 6.1 the rows for Folio, office-open, Docen, and Fidus Writer say Word refused the file. Those rows are the raw round-trip outputs. They were not produced by opening a file after `build/folio_deltext_test.py` or `build/officeopen_rels_test.py`.

## Repair experiments are counterfactuals

Report B names `build/folio_deltext_test.py` and `build/officeopen_rels_test.py` as repair experiments. A file that Word opened only after one of those repairs would be a counterfactual. Report C section 6 does not present that counterfactual.

Section 6.2 states there is no Word rendering for those four outputs because the raw file does not open. LibreOffice is what that section uses when Word will not open the raw file.

## Diagram in the fixture

The fixture has one SmartArt. `word/_rels/document.xml.rels` links it with one `diagramData` relationship to `diagrams/data1.xml`, plus `diagramLayout`, `diagramQuickStyle`, and `diagramColors`. There is no diagram drawing part. This note does not describe a further diagram.
