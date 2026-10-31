# Report D — Safety, Resource Bombs and Hostile Input (2026)

## What was executed

Nothing in the ten-vector suite was executed. The recorder refuses to build a bomb unless the address-space limit can be lowered. On this machine it cannot. The lines below are the whole outcome log. A skip is the recorded result. It is not a crash, a leak, a bounded reject, or a preserved payload, because those words would describe a run that did not happen.

## Two axes

Fidelity and safety are different questions. Fidelity asks whether a hostile payload was preserved, dropped, or refused by the editor. Safety asks whether the editor crashed, hung, leaked, rejected the input inside a resource bound, or was not run. Preserving a hostile payload is not the same single result as a crash. This run has a safety result only, and that result is not-run. It has no fidelity result.

## Log

```
platform: macOS-27.0.1-arm64-arm-64bit-Mach-O
not-run: resource.setrlimit(RLIMIT_AS) raised ValueError: current limit exceeds maximum limit. platform=macOS-27.0.1-arm64-arm-64bit-Mach-O RLIMIT_AS soft=9223372036854775807 hard=9223372036854775807. The hostile suite was not executed.
taxonomy: preserving a hostile payload is not the same single result as a crash. This run recorded neither, because no vector was executed.
defect_survival.py classifies structural defects in outputs of fixture/complex_broken.docx. It is not this suite, and it did not run B1-B10.
B1 SKIP not-run: Zip decompression bomb (ratio / total size). not-run: resource.setrlimit(RLIMIT_AS) raised ValueError: current limit exceeds maximum limit. platform=macOS-27.0.1-arm64-arm-64bit-Mach-O RLIMIT_AS soft=9223372036854775807 hard=9223372036854775807. The hostile suite was not executed.
B2 SKIP not-run: Zip entry flood. not-run: resource.setrlimit(RLIMIT_AS) raised ValueError: current limit exceeds maximum limit. platform=macOS-27.0.1-arm64-arm-64bit-Mach-O RLIMIT_AS soft=9223372036854775807 hard=9223372036854775807. The hostile suite was not executed.
B3 SKIP not-run: XML attribute compression bomb. not-run: resource.setrlimit(RLIMIT_AS) raised ValueError: current limit exceeds maximum limit. platform=macOS-27.0.1-arm64-arm-64bit-Mach-O RLIMIT_AS soft=9223372036854775807 hard=9223372036854775807. The hostile suite was not executed.
B4 SKIP not-run: Deep nesting of w:sdt and w:tbl. not-run: resource.setrlimit(RLIMIT_AS) raised ValueError: current limit exceeds maximum limit. platform=macOS-27.0.1-arm64-arm-64bit-Mach-O RLIMIT_AS soft=9223372036854775807 hard=9223372036854775807. The hostile suite was not executed.
B5 SKIP not-run: Billion Laughs and XXE. not-run: resource.setrlimit(RLIMIT_AS) raised ValueError: current limit exceeds maximum limit. platform=macOS-27.0.1-arm64-arm-64bit-Mach-O RLIMIT_AS soft=9223372036854775807 hard=9223372036854775807. The hostile suite was not executed.
B6 SKIP not-run: Zip-Slip path traversal. not-run: resource.setrlimit(RLIMIT_AS) raised ValueError: current limit exceeds maximum limit. platform=macOS-27.0.1-arm64-arm-64bit-Mach-O RLIMIT_AS soft=9223372036854775807 hard=9223372036854775807. The hostile suite was not executed.
B7 SKIP not-run: SSRF / NTLM credential leak via external relationships. NTLM credential leak cannot be measured on macOS. not-run: resource.setrlimit(RLIMIT_AS) raised ValueError: current limit exceeds maximum limit. platform=macOS-27.0.1-arm64-arm-64bit-Mach-O RLIMIT_AS soft=9223372036854775807 hard=9223372036854775807. The hostile suite was not executed.
B8 SKIP not-run: XSS / active content. not-run: resource.setrlimit(RLIMIT_AS) raised ValueError: current limit exceeds maximum limit. platform=macOS-27.0.1-arm64-arm-64bit-Mach-O RLIMIT_AS soft=9223372036854775807 hard=9223372036854775807. The hostile suite was not executed.
B9 SKIP not-run: Layout and combinatorial bombs (gridSpan, fields, bibliography). not-run: resource.setrlimit(RLIMIT_AS) raised ValueError: current limit exceeds maximum limit. platform=macOS-27.0.1-arm64-arm-64bit-Mach-O RLIMIT_AS soft=9223372036854775807 hard=9223372036854775807. The hostile suite was not executed.
B10 SKIP not-run: Corrupt secondary parts and bad PNG magic. not-run: resource.setrlimit(RLIMIT_AS) raised ValueError: current limit exceeds maximum limit. platform=macOS-27.0.1-arm64-arm-64bit-Mach-O RLIMIT_AS soft=9223372036854775807 hard=9223372036854775807. The hostile suite was not executed.
```

## How to read the ten vectors

Each `B1` through `B10` line is a skip. The names are the vectors the suite would have built: a zip decompression bomb, a zip entry flood, an XML attribute bomb, deep `w:sdt` and `w:tbl` nesting, Billion Laughs and XXE, Zip-Slip, SSRF and NTLM via external relationships, XSS or other active content, layout bombs (`gridSpan`, fields, bibliography), and corrupt secondary parts including a bad PNG magic. `B7` also records that an NTLM credential leak cannot be measured on macOS.

`build/defect_survival.py` classifies structural defects in outputs of `fixture/complex_broken.docx`. The log says it is not this suite. Content variants elsewhere in the tree are not these vectors.
