# Folio

## What the driver runs

`build/score_all.py` measures the Folio model lane from `out/folio`. `build/run_all.sh` also runs an editor lane to `out/folio-editor`.

The model lane parses with `parseDocx` and repacks with `repackDocx`.

The editor lane is the headless prose conversion. It parses, calls `toProseDoc`, calls `fromProseDoc` with `stylesheetSource` set to `{ type: 'package' }`, and repacks. That is the call the project's editor round-trip invariant makes. The browser UI is a separate entry, and this lane did not start it.

## This run

```
[folio:model] wrote 25355 bytes
weighted: 97.5%
features: 97/99
failed-check-ids: tc.moveFrom mx.unknownAttr
```

```
[folio:editor] wrote 25373 bytes
weighted: 95.5%
features: 95/99
failed-check-ids: tc.moveFrom mx.unknownAttr fmt.hyphens text.exact
```

The editor lane fails `tc.moveFrom`, `mx.unknownAttr`, `fmt.hyphens`, and `text.exact`. The model lane fails `tc.moveFrom` and `mx.unknownAttr`. The checks that differ are `fmt.hyphens` and `text.exact`.

## Trivia

Folio describes itself as a browser editor and a framework-neutral engine for OOXML `.docx` documents. The React, Vue, and Nuxt editors sit on `folio-core`, whose npm name is `@stll/folio-core`, from the stella project. The license is Apache-2.0. The README is published in English, Simplified Chinese, and Brazilian Portuguese.
