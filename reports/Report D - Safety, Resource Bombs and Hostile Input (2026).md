# Report D — Safety, Resource Bombs and Hostile Input (2026)

## What was executed

Nothing in the ten-vector suite was built or opened. The vectors are recorded to run later, sandboxed. On this machine the address-space limit cannot be lowered, and no stronger sandbox was used. The lines below are the whole outcome log. Not-run is the recorded value on both axes. It is not a crash, a leak, a bounded reject, or a preserved, dropped, or refused payload, because those words would describe a run that did not happen.

## Two axes

Fidelity and safety are separate fields on every row. Fidelity is one of preserved, dropped, refused, or not-run. Safety is one of crash, hang, leak, bounded reject, or not-run. Preserving a hostile payload is not the same single result as a crash. Word and LibreOffice are reference rows with the same two fields. This session did not feed a hostile package to either program, or to an editor. For B1 through B10, and for both reference rows, fidelity is not-run and safety is not-run.

## Log

```
platform: macOS-27.0.1-arm64-arm-64bit-Mach-O
not-run: resource.setrlimit(RLIMIT_AS) raised ValueError: current limit exceeds maximum limit. platform=macOS-27.0.1-arm64-arm-64bit-Mach-O RLIMIT_AS soft=9223372036854775807 hard=9223372036854775807. The hostile suite was not executed.
scheduled: run later, sandboxed. This session did not build or open a hostile package.
taxonomy: preserving a hostile payload is not the same single result as a crash. This run recorded neither, because no vector was executed.
defect_survival.py classifies structural defects in outputs of fixture/complex_broken.docx. It is not this suite, and it did not run B1-B10.
reference Word fidelity: not-run safety: not-run Word was not opened on a hostile package. not-run: resource.setrlimit(RLIMIT_AS) raised ValueError: current limit exceeds maximum limit. platform=macOS-27.0.1-arm64-arm-64bit-Mach-O RLIMIT_AS soft=9223372036854775807 hard=9223372036854775807. The hostile suite was not executed.
reference LibreOffice fidelity: not-run safety: not-run LibreOffice was not opened on a hostile package. not-run: resource.setrlimit(RLIMIT_AS) raised ValueError: current limit exceeds maximum limit. platform=macOS-27.0.1-arm64-arm-64bit-Mach-O RLIMIT_AS soft=9223372036854775807 hard=9223372036854775807. The hostile suite was not executed.
B1 SKIP not-run: Zip decompression bomb (ratio / total size). fidelity: not-run safety: not-run not-run: resource.setrlimit(RLIMIT_AS) raised ValueError: current limit exceeds maximum limit. platform=macOS-27.0.1-arm64-arm-64bit-Mach-O RLIMIT_AS soft=9223372036854775807 hard=9223372036854775807. The hostile suite was not executed.
B2 SKIP not-run: Zip entry flood. fidelity: not-run safety: not-run not-run: resource.setrlimit(RLIMIT_AS) raised ValueError: current limit exceeds maximum limit. platform=macOS-27.0.1-arm64-arm-64bit-Mach-O RLIMIT_AS soft=9223372036854775807 hard=9223372036854775807. The hostile suite was not executed.
B3 SKIP not-run: XML attribute compression bomb. fidelity: not-run safety: not-run not-run: resource.setrlimit(RLIMIT_AS) raised ValueError: current limit exceeds maximum limit. platform=macOS-27.0.1-arm64-arm-64bit-Mach-O RLIMIT_AS soft=9223372036854775807 hard=9223372036854775807. The hostile suite was not executed.
B4 SKIP not-run: Deep nesting of w:sdt and w:tbl. fidelity: not-run safety: not-run not-run: resource.setrlimit(RLIMIT_AS) raised ValueError: current limit exceeds maximum limit. platform=macOS-27.0.1-arm64-arm-64bit-Mach-O RLIMIT_AS soft=9223372036854775807 hard=9223372036854775807. The hostile suite was not executed.
B5 SKIP not-run: Billion Laughs and XXE. fidelity: not-run safety: not-run not-run: resource.setrlimit(RLIMIT_AS) raised ValueError: current limit exceeds maximum limit. platform=macOS-27.0.1-arm64-arm-64bit-Mach-O RLIMIT_AS soft=9223372036854775807 hard=9223372036854775807. The hostile suite was not executed.
B6 SKIP not-run: Zip-Slip path traversal. fidelity: not-run safety: not-run not-run: resource.setrlimit(RLIMIT_AS) raised ValueError: current limit exceeds maximum limit. platform=macOS-27.0.1-arm64-arm-64bit-Mach-O RLIMIT_AS soft=9223372036854775807 hard=9223372036854775807. The hostile suite was not executed.
B7 SKIP not-run: SSRF / NTLM credential leak via external relationships. NTLM credential leak cannot be measured on macOS. fidelity: not-run safety: not-run not-run: resource.setrlimit(RLIMIT_AS) raised ValueError: current limit exceeds maximum limit. platform=macOS-27.0.1-arm64-arm-64bit-Mach-O RLIMIT_AS soft=9223372036854775807 hard=9223372036854775807. The hostile suite was not executed.
B8 SKIP not-run: XSS / active content. fidelity: not-run safety: not-run not-run: resource.setrlimit(RLIMIT_AS) raised ValueError: current limit exceeds maximum limit. platform=macOS-27.0.1-arm64-arm-64bit-Mach-O RLIMIT_AS soft=9223372036854775807 hard=9223372036854775807. The hostile suite was not executed.
B9 SKIP not-run: Layout and combinatorial bombs (gridSpan, fields, bibliography). fidelity: not-run safety: not-run not-run: resource.setrlimit(RLIMIT_AS) raised ValueError: current limit exceeds maximum limit. platform=macOS-27.0.1-arm64-arm-64bit-Mach-O RLIMIT_AS soft=9223372036854775807 hard=9223372036854775807. The hostile suite was not executed.
B10 SKIP not-run: Corrupt secondary parts and bad PNG magic. fidelity: not-run safety: not-run not-run: resource.setrlimit(RLIMIT_AS) raised ValueError: current limit exceeds maximum limit. platform=macOS-27.0.1-arm64-arm-64bit-Mach-O RLIMIT_AS soft=9223372036854775807 hard=9223372036854775807. The hostile suite was not executed.
```

## How to read the ten vectors

Each `B1` through `B10` line is a skip with its own fidelity field and its own safety field. Both fields are not-run. Word and LibreOffice are reference rows. Both of those fields are not-run on each reference row, because neither program was opened on a hostile package. The names are the vectors a later sandboxed run would build: a zip decompression bomb, a zip entry flood, an XML attribute bomb, deep `w:sdt` and `w:tbl` nesting, Billion Laughs and XXE, Zip-Slip, SSRF and NTLM via external relationships, XSS or other active content, layout bombs (`gridSpan`, fields, bibliography), and corrupt secondary parts including a bad PNG magic. `B7` also records that an NTLM credential leak cannot be measured on macOS. That reason is separate from the missing sandbox.

`build/defect_survival.py` classifies structural defects in outputs of `fixture/complex_broken.docx`. The log says it is not this suite. Content variants elsewhere in the tree are not these vectors.
