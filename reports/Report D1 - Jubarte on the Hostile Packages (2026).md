# Report D1 — Jubarte on the Hostile Packages (2026)

Jubarte is not one of the editors in Report D. This file is only the release binary of `../jubarte-redlines`.

## Grade

0.65 on the scale in Report D. 1 is a named ceiling that refuses the package. 0 is a kept weapon, a hang, or a stack overflow. The grade is the mean of the ten packages.

| Package | Level | Weight |
| --- | --- | --- |
| Decompression | bounded-refusal | 1.0 |
| Entry flood | bounded-refusal | 1.0 |
| Attributes | bounded-refusal | 1.0 |
| Deep nesting | bounded-refusal | 1.0 |
| Entities | unexpanded-kept | 0.3 |
| Zip-slip | not-in-view | 0.3 |
| External relationships | not-in-view | 0.3 |
| Active content | sanitation | 0.8 |
| Layout bomb | bounded-delivery | 0.5 |
| Corrupt parts | not-in-view | 0.3 |

The four ceilings are why the mean is above the editors that only clean a file. The entity references are still in the view, so that package is 0.3 and not 0. The zip-slip warning is not scored as a refusal. The mean is 6.5 divided by 10.

## What the binary did

The binary is `jubarte 0.14.0`, built from that checkout. The skill copy is 0.12.0 and was not used. The scored command is `jubarte read FILE -o view.md --force`. Page markers stay on. The skill quick start adds `--no-page-markers`. This run did not, and it did not override the input limits. `read` writes a markdown view, not a second package. A missing package is not a catch.

The binary ran under the same seatbelt as the editors: external network denied, localhost and unix sockets inside the work directory allowed, writes only in the work directory. It is a macOS executable and was not run in the Linux container. Word was not opened. No hash collector was started. The wall was the same as the editors. No cell hit that wall. No cell died. No cell leaked. The canary file's contents are not in any view.

The first automatic score of the entity package said fidelity dropped, safety ok, catch yes, level sanitation. That score is wrong. The view still contains the unexpanded references `&lol6;&xxe;&canary;`. Keeping those references is not sanitation and it is not a catch. The fidelity field is corrected to preserved. `caught()` was not changed. Preserved and ok is not a catch. The protection level is `unexpanded-kept`.

The first protection line for the attribute package said `erroring`. That is also wrong. The stderr names a ceiling on the attributes of one element. The level is `bounded-refusal`. The catch stays yes, because the read was refused.

## Scorecard

The lines below are the corrected scorecard. The binary was not run a second time. The correction reads the views and the stderr the first run saved. Streams that mention a size stay in `logs/jubarte-bombs` and are not copied here.

```
version: jubarte 0.14.0
binary: release build of ../jubarte-redlines. The skill copy was not used.
command: jubarte read FILE -o view.md --force
config: binary default. Page markers stay on. The skill quick start adds --no-page-markers. This run did not. No input-limit override.
sandbox: jubarte under seatbelt. External network is denied. Localhost and unix sockets inside the work directory are allowed. Writes stay in the work directory. The binary is a macOS executable and was not run inside the Linux container.
taxonomy: preserving a hostile payload is not the same single result as a crash.
reference Word fidelity: not-run safety: not-run Word was not opened.
B7 note: NTLM credential leak was not measured. No hash collector was started. External network and UNC were denied. Localhost was allowed.
B5 note: the entity bomb expands one million times, not to a gigabyte. This Mac cannot cap address space.
B1 note: one deflate member tops out near one thousand to one. A single member at two thousand five hundred to one is not a real deflate stream.
view: read writes markdown. No view file is refused. A view that still carries the weapon is preserved. A weapon the markdown view does not carry, and that was not echoed, is not-in-view. That is not sanitation and it is not a catch.
protection: the safety word bounded-reject is not a resource bound.
tool jubarte B1 fidelity: refused safety: bounded-reject catch: yes
protection jubarte B1 level: bounded-refusal detail: INPUT_LIMIT named a ceiling on one part. No view was written.
tool jubarte B10 fidelity: not-in-view safety: ok catch: no
protection jubarte B10 level: not-in-view detail: layout named INVALID_XML on the comments part and still wrote a body view. The bad image marker is not in the view.
tool jubarte B2 fidelity: refused safety: bounded-reject catch: yes
protection jubarte B2 level: bounded-refusal detail: INPUT_LIMIT named a ceiling on the zip entry count. No view was written.
tool jubarte B3 fidelity: refused safety: bounded-reject catch: yes
protection jubarte B3 level: bounded-refusal detail: INVALID_XML named a ceiling on the attributes of one element. No view was written.
tool jubarte B4 fidelity: refused safety: bounded-reject catch: yes
protection jubarte B4 level: bounded-refusal detail: the reader refused the package for XML nesting too deep. No view was written.
tool jubarte B5 fidelity: preserved safety: ok catch: no
protection jubarte B5 level: unexpanded-kept detail: the view keeps the unexpanded entity references and does not expand them
tool jubarte B6 fidelity: not-in-view safety: ok catch: no
protection jubarte B6 level: not-in-view detail: layout named UNSUPPORTED_PACKAGE for the unsafe entry and still wrote a body view that does not carry the slip
tool jubarte B7 fidelity: not-in-view safety: ok catch: no
protection jubarte B7 level: not-in-view detail: the markdown view does not carry the relationship targets. The log shows no connection attempt.
tool jubarte B8 fidelity: dropped safety: ok catch: yes
protection jubarte B8 level: sanitation detail: the view keeps the body marker and omits the hyperlink, the javascript target, and the script
tool jubarte B9 fidelity: not-in-view safety: ok catch: no
protection jubarte B9 level: bounded-delivery detail: the view clamps the merged span to the renderer grid cap and summarizes the empty field paragraphs. The bibliography is not in the view.
```

## Degrees on these ten reads

The same ladder as Report D. `bounded-reject` on a score line is not a resource bound.

| Package | Catch | Level | What the binary actually did |
| --- | --- | --- | --- |
| Decompression | yes | bounded-refusal | `INPUT_LIMIT` named a ceiling on one part. No view. |
| Entry flood | yes | bounded-refusal | `INPUT_LIMIT` named a ceiling on the zip entry count: 25004 entries against a cap of 10000. No view. |
| Attributes | yes | bounded-refusal | `INVALID_XML`: the element exceeds 1024 attributes. That is a named cap. No view. |
| Deep nesting | yes | bounded-refusal | The reader refused the package: XML nesting too deep. No view. |
| Entities | no | unexpanded-kept | Exit 0. The view keeps the raw references and does not expand them. |
| Zip-slip | no | not-in-view | Exit 0. Layout named `UNSUPPORTED_PACKAGE` for the unsafe entry and still wrote a body view. The slip is not in that view. |
| External relationships | no | not-in-view | Exit 0. The targets are not in the markdown. The log shows no connection. |
| Active content | yes | sanitation | Exit 0. The view keeps the body marker and omits the hyperlink, the javascript target, and the script. |
| Layout bomb | no | bounded-delivery | Exit 0. The view clamps the merged span to the renderer grid cap. Fidelity stays not-in-view, so the catch is no. |
| Corrupt parts | no | not-in-view | Exit 0. Layout named `INVALID_XML` on the comments part and still wrote the body view. |

## Entities

Layout printed that the docx has no main document part. The markdown pass still wrote a view. The body is the ordinary marker, then the literal references:

```
BOMB_BODY_OK

&lol6;&xxe;&canary;
```

The expanded token is not in the view. The hosts file is not in the view. The canary file's contents are not in the view. The references were not expanded, and they were not removed. That is `unexpanded-kept`. It is not `sanitation`. It is not `failed-load-exit-zero`, because a view was written. It is not a catch.

## Attributes, depth, and the two size ceilings

The decompression read and the entry-count read both failed with `INPUT_LIMIT` and wrote no view. Those are `bounded-refusal`. The decompression message also states sizes. Those sizes stay in the cell log.

The attribute read failed with `INVALID_XML` and the words "element exceeds 1024 attributes". The code token is an XML error. The sentence is still a declared attribute cap, so the level is `bounded-refusal`, the same degree as wordcraft's attribute cap in Report D, and not the same degree as Plate's sanitation of that package.

The deep read failed with "XML nesting too deep" and wrote no view. That is a depth ceiling, `bounded-refusal`. It is not stack exhaustion. The process returned an error inside the wall.

## Zip-slip and the corrupt comments part

On zip-slip, layout named `UNSUPPORTED_PACKAGE` and an unsafe entry name, then `read` still exited 0 and wrote a body view. The slip marker and the external targets are not in that view. A markdown view of body text does not carry a zip entry. The name policy fired as a warning, not as a refusal of the command. Under the catch rule this is not a catch. If a named unsafe entry were enough to count as a catch, the rule would have to change. It was not changed. The level is `not-in-view`, with that warning stated in the detail.

On the corrupt package, layout named `INVALID_XML` because the comments part does not close a tag, and `read` still wrote the body view. The bad image marker is not in the view. Same shape: a named problem on a secondary part, a successful body view, not a catch, not sanitation.

## External relationships

The view is the body marker. The probe URL and the UNC target are not in it. Stderr does not show a connection. Localhost was allowed, so a connect to the probe would not have been blocked by the seatbelt. Nothing in the log shows one. Absence of a log line is not a measured block. The level is `not-in-view`. Catch is no.

## Active content

Stderr says the input has 1 validity error. The view keeps the body marker. It does not contain the hyperlink's visible word, the javascript target, or the script marker. The hyperlink paragraph is absent. The URL was not rewritten into a safe link. The level is `sanitation`. Catch is yes. This is the one clean drop in the ten.

## Layout bomb

The bomb's merged span is a million. The markdown reader caps a merged span at its grid constant, 64. The view records the cell as merged across 64. That is `bounded-delivery`: a declared cap, a written view, the hostile value absent.

The same view summarizes the empty field paragraphs as one range, `p2-p2001 empty`, and stderr names 2000 validity errors. The field markup is not in the view. The bibliography part is not in the view, which is the `not-in-view` half of this cell. The fidelity field stays `not-in-view` because the hostile strings are absent, and that is why the catch is no. The protection level is the clamp, not the catch bit. Those two answers are different on purpose.

No editor cell in Report D has `bounded-delivery` as its primary label. wordcraft's layout package clamped the span and still kept the fields and the bibliography, so that cell stays `preserved`.

## What this run does not show

The binary did not crash, hang, or leak on these ten packages. The decompression read was refused by the part ceiling. It did not hang in the layout pass. That is what this run showed. It does not say what a larger part, or a different command, would do.

`read` is not the redline comparer. The limits used here are the ones `read` uses when nobody passes an override. A comparer limit was not substituted in.
