# Word experiment evidence (Reports D and E)

The run journal and raw logs from opening the hostile fixtures in Microsoft Word
for Mac and in jubarte.

- `LOG.md`: run journal.
- `results_word.tsv`, `results_jubarte*.tsv`: one row per fixture and run.
- `runs/ID/word.log`: the bench log for each Word run.
- `screen.log`: every Word dialog seen on screen, with its OCR text.
- `net.log`: every connection to the `127.0.0.1:18009` listener.
- `cmp_scale/`: `jubarte compare` timings at scale and the builder.
- `scripts/`: `build.py`, `build_cap.py`, `build_net.py`, `build_x4.py` and
  `build_x4c.py` rebuild all 33 fixtures into `fixtures/`; `listen.py` is the
  listener.

The fixtures themselves, which are hostile packages, are not published. Neither
are the jubarte run outputs (about 420 MB).

Absolute paths from the author's machine were rewritten as placeholders:
`<word_exp>` (this folder), `<editors_trial>` (this repository),
`<jubarte-loop>`, `<T>`, `~` and `$TMPDIR/`. `scripts/build.py` resolves the
repository's `build/` relative to itself.
