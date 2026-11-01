#!/usr/bin/env python3
"""
Reports as templates over the measurement.

A template is the report's Markdown with each measured figure replaced by a
placeholder, ``{{key}}`` or ``{{key:spec}}``. ``key`` names a value in
out/facts.json (build/facts.py); ``spec`` is a Python format spec, plus ``yn``
for a boolean written as yes/no. ``render`` fills the placeholders;
``templatize`` makes a template out of a finished report.

templatize is conservative. A figure is bound only when the facts, the
table column or the sentence around it identify one measurement; anything
else stays literal and is returned as *unbound*, so a person can decide. A
template must always render back to the text it came from - that is checked
by the caller (build/render_reports.py --templatize) before anything is
written.
"""
from __future__ import annotations

import re
from collections import Counter

PLACEHOLDER = re.compile(r"\{\{([A-Za-z0-9_.\-/]+)(?::([^{}]*))?\}\}")


def fmt(value, spec: str | None) -> str:
    if spec == "yn":
        return "yes" if value else "no"
    return format(value, spec or "")


def render(template: str, facts: dict) -> str:
    def sub(m: re.Match) -> str:
        key, spec = m.group(1), m.group(2)
        if key not in facts:
            raise KeyError(key)
        return fmt(facts[key], spec)

    return PLACEHOLDER.sub(sub, template)


# --------------------------------------------------------------------------
# templatize
# --------------------------------------------------------------------------

# Who a figure can be about. First match wins, so lane names come first.
SUBJECTS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"superdoc/docx-editor"), "superdoc"),
    (re.compile(r"stella/folio"), "folio"),
    (re.compile(r"genspark-ai/genoffice"), "genoffice"),
    (re.compile(r"storytold/wordcraft"), "wordcraft"),
    (re.compile(r"DemoMacro/docen"), "docen"),
    (re.compile(r"udecode/plate"), "plate"),
    (re.compile(r"fiduswriter/fiduswriter\b"), "fidus"),
    (re.compile(r"eigenpal(?:-| )editor"), "eigenpal-editor"),
    (re.compile(r"Folio(?:-| )editor"), "folio-editor"),
    (re.compile(r"(?<![/\w.\-])wordcraft(?![/\w.\-])"), "wordcraft"),
    (re.compile(r"SuperDoc"), "superdoc"),
    (re.compile(r"Docxodus"), "docxodus"),
    (re.compile(r"GenOffice"), "genoffice"),
    (re.compile(r"eigenpal"), "eigenpal"),
    (re.compile(r"Folio"), "folio"),
    (re.compile(r"office-open"), "officeopen"),
    (re.compile(r"Docen"), "docen"),
    (re.compile(r"WordCraft"), "wordcraft"),
    (re.compile(r"canvas-editor|\bcanvas\b"), "canvas"),
    (re.compile(r"Fidus(?: Writer)?"), "fidus"),
    (re.compile(r"docs\.plus"), "docsplus"),
    (re.compile(r"Plate(?:\.js)?\b"), "plate"),
    (re.compile(r"LibreOffice"), "lo_baseline"),
]

# The repository whose star count stands for each participant.
SLUG = {
    "superdoc": "superdoc/docx-editor", "docxodus": "JSv4/Docxodus", "genoffice": "genspark-ai/genoffice",
    "eigenpal": "eigenpal/docx-editor", "folio": "stella/folio", "officeopen": "DemoMacro/office-open",
    "docen": "DemoMacro/docen", "wordcraft": "storytold/wordcraft", "canvas": "Hufe921/canvas-editor",
    "fidus": "fiduswriter/fiduswriter", "docsplus": "docs-plus/docs.plus", "plate": "udecode/plate",
}

# Figures true of the whole trial, whoever the sentence is about.
GLOBAL_KW = {
    "checks.total": ("check",),
    "checks.critical": ("critical",),
    "fixture.parts": ("part",),
}

# What a metric is called in a table header or a sentence.
METRIC_KW = {
    "weighted": ("weighted", "score", "fidelity", "round-trip", "round trip", "first pass", "second pass"),
    "critical_pct": ("critical",),
    "critical_passed": ("critical",),
    "critical_total": ("critical",),
    "critical_failed": ("critical",),
    "text_pct": ("text",),
    "text_tokens": ("token",),
    "text_lost": ("token",),
    "passed": ("check",),
    "total": ("check",),
    "failed": ("fail",),
    "bytes": ("byte",),
    "grade": ("grade",),
    "kept": ("part", "kept"),
    "out": ("part",),
    "passthrough": ("pass-through", "passthrough", "untouched", "byte-identical"),
    "rewritten": ("rewritten",),
    "reserialized": ("re-serial",),
    "changed": ("changed",),
    "dropped": ("drop", "lost"),
    "added": ("added",),
}
NUMERATOR = {"critical_passed", "passed", "kept"}
COUNTERPART = {"critical_passed": "critical_total", "passed": "total", "kept": "total",
               "critical_total": "critical_passed"}
DENOMINATOR = {"critical_total", "total"}
THRESHOLD = 3

NUMBER = re.compile(
    r"(?<![\w.§#@$`:+\-])"
    r"(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)"
    r"(?![\w@]|:\d|\.\d|-\d|,\d)"
)
# Spans that are never bound: code, links' targets, images, URLs, HTML.
PROTECT = re.compile(
    r"^\s*(?:#+\s*)?\d+[.)](?=\s)|`[^`\n]*`|!\[[^\]]*\]\([^)]*\)|\]\([^)]*\)|https?://\S+|<[^>\n]+>|\{\{[^}]*\}\}"
)
SENTENCE_END = re.compile(r"(?<=[.!?;])\s+(?=[*_(\[]*[A-Z])")


def _spec_for(literal: str) -> list[str]:
    if "," in literal:
        return [","]
    if "." in literal:
        return [f".{len(literal.split('.')[1])}f"]
    return ["", "g"]


def _formats_to(value, literal: str) -> str | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    for spec in _spec_for(literal):
        if spec == "" and not isinstance(value, int):
            continue
        if spec == "g" and isinstance(value, int):
            continue
        try:
            if format(value, spec) == literal:
                return spec
        except ValueError:
            continue
    return None


def _subjects_in(text: str) -> list[tuple[int, str]]:
    """Every editor named in ``text``, in order. Where two names overlap
    ("eigenpal editor" and "eigenpal") the longer one, the lane, wins."""
    found = []
    for rx, tool in SUBJECTS:
        for m in rx.finditer(text):
            found.append((m.start(), m.end(), tool))
    found.sort(key=lambda f: (f[0], -(f[1] - f[0])))
    kept, end = [], -1
    for a, b, tool in found:
        if a < end:
            continue
        kept.append((a, tool))
        end = b
    return kept


def _family_pref(context: str) -> str:
    c = context.lower()
    i_first, i_second = c.find("first"), c.find("second")
    if i_second >= 0 and (i_first < 0 or i_second < i_first):
        return "p2"
    return "rt"


def _role(text: str, start: int, end: int) -> str | None:
    if re.match(r"\s+of\s+\d", text[end:]):
        return "of"
    if re.match(r"\s*/\s*\d", text[end:]):
        return "num"
    if re.search(r"\d\s*/\s*$", text[:start]):
        return "den"
    return None


def _partner_matches(key: str, fam: str, metric: str, role: str, text: str, s: int, e: int, facts: dict) -> bool:
    """For "28/29": the 28 is a critical_passed only if the 29 is the same
    editor's critical_total, and the other way round."""
    if role == "num":
        m = re.match(r"\s*/\s*(\d[\d,.]*\d|\d)", text[e:])
        want = COUNTERPART.get(metric) if metric in NUMERATOR else None
    else:
        m = re.search(r"(\d[\d,.]*\d|\d)\s*/\s*$", text[:s])
        want = {"critical_total": "critical_passed", "total": "kept" if fam == "parts" else "passed"}.get(metric)
        if metric not in DENOMINATOR:
            want = None
    if not m or not want:
        return False
    other = key.rsplit(".", 1)[0] + "." + want
    return other in facts and _formats_to(facts[other], m.group(1)) is not None


def _gap_has_number(gap: str) -> bool:
    """True when another figure stands between a keyword and the token
    (a fraction partner such as the "/29" in "28/29" does not count)."""
    gap = re.sub(r"^\s*(?:/|of)\s*\d+", "", gap)
    gap = re.sub(r"\d+\s*/\s*$", "", gap)
    return bool(NUMBER.search(gap))


def _globals(facts: dict) -> dict[str, tuple[str, ...]]:
    """Trial-wide figures and the words that name them."""
    g = {k: v for k, v in GLOBAL_KW.items() if k in facts}
    for k in facts:
        if k.startswith("bomb.count."):
            g[k] = (k[len("bomb.count."):],)
    if "bomb.cells" in facts:
        g["bomb.cells"] = ("cell",)
    return g


def _kw_header(kws, header: str) -> int:
    h = header.lower()
    return 3 if any(kw in h for kw in kws) else 0


def _kw_weight(kws, text: str, s: int, e: int) -> int:
    """How strongly the words around text[s:e] name a metric: a keyword just
    after the figure (\"100% text\") is strongest, just before (\"scores
    97.5%\") next, a table header always strong, anything else in the
    sentence weak. A keyword with another figure in between is not ours."""
    best = 0
    low = text.lower()
    for kw in kws:
        for m in re.finditer(re.escape(kw), low):
            if m.start() >= e:
                gap = text[e:m.start()]
                if _gap_has_number(gap):
                    continue
                best = max(best, 3 if len(gap) <= 14 else 2 if len(gap) <= 28 else 1)
            elif m.end() <= s:
                gap = text[m.end():s]
                if _gap_has_number(gap):
                    continue
                best = max(best, 3 if gap.strip(" *_") == "" and len(gap) <= 3 else 2 if len(gap) <= 14 else 1 if len(gap) <= 40 else 0)
    return best


def _choose(literal: str, subject: str | None, text: str, s: int, e: int, header: str,
            facts: dict) -> tuple[str, str] | None:
    window = header + " " + text[max(0, s - 60): e + 40]
    family = _family_pref(window)
    role = _role(text, s, e)
    percent = bool(re.match(r"\s?%", text[e:]))
    cands: list[tuple[int, str, str]] = []
    keys = []
    if subject:
        for fam in ("rt", "p2", "parts", "bomb"):
            pre = f"{fam}.{subject}."
            keys += [k for k in facts if k.startswith(pre) and k.count(".") == 2]
    glob = _globals(facts)
    keys += list(glob)
    scored = []
    for k in keys:
        spec = _formats_to(facts[k], literal)
        if spec is None:
            continue
        if k in glob:
            fam, metric, kws = "global", k, glob[k]
        else:
            fam, _, metric = k.split(".", 2)
            kws = METRIC_KW.get(metric, ())
        scored.append((k, spec, fam, metric, kws, _kw_weight(kws, text, s, e)))
    # The column header decides only when no word beside the figure does.
    use_header = not any(local for *_, local in scored)
    for k, spec, fam, metric, kws, local in scored:
        score = _kw_header(kws, header) if use_header else local
        if fam in ("rt", "p2"):
            score += 2 if fam == family else 0
            if fam == "p2" and family != "p2":
                score -= 3
        if fam != "global" and role is None and metric in NUMERATOR | DENOMINATOR:
            score -= 4
        if role == "of":
            score += -4 if metric in DENOMINATOR or fam == "global" else 0
            role_for_bonus = None
        else:
            role_for_bonus = role
        if role_for_bonus in ("num", "den") and metric in NUMERATOR | DENOMINATOR:
            score += 4 if _partner_matches(k, fam, metric, role_for_bonus, text, s, e, facts) else -8
        if role_for_bonus and metric not in NUMERATOR | DENOMINATOR:
            score -= 4
        if percent:
            score += 2 if metric == "weighted" else 1 if metric.endswith("pct") else -3
        if isinstance(facts[k], int) and facts[k] >= 1000:
            score += 3
        cands.append((score, k, spec))
    if not cands:
        return None
    cands.sort(key=lambda c: -c[0])
    best = cands[0]
    if best[0] < THRESHOLD:
        return None
    if len(cands) > 1 and cands[1][0] == best[0] and cands[1][1] != best[1]:
        return None
    return best[1], best[2]


def _protected(text: str) -> list[tuple[int, int]]:
    return [(m.start(), m.end()) for m in PROTECT.finditer(text)]


def _star_key(text: str, s: int, e: int) -> str | None:
    """"1,117★ (SuperDoc)" or "WordCraft 16,875★": the editor right beside the stars."""
    after = re.match(r"★[*_]*\s*\(([^)]*)\)", text[e:])
    if after:
        found = _subjects_in(after.group(1))
    else:
        found = _subjects_in(text[max(0, s - 60):s])[-1:]
    tools = {t for _, t in found}
    return f"stars.{SLUG[tools.pop()]}" if len(tools) == 1 and next(iter(tools), None) in SLUG else None


def _bind_segment(text: str, subject_at, header: str, facts: dict, unbound: list, lineno: int,
                  star_slug: str | None = None) -> str:
    """Replace every bindable number in ``text``. ``subject_at(i)`` gives the
    subject for a token; ``header`` is its table column header, if any."""
    spans = _protected(text)
    out, last = [], 0
    for m in NUMBER.finditer(text):
        s, e = m.span(1)
        if any(a <= s < b for a, b in spans):
            continue
        literal = m.group(1)
        if text[e:e + 1] == "★" or star_slug:
            key = star_slug or _star_key(text, s, e)
            spec = None if not key or key not in facts else _formats_to(facts[key], literal)
            if spec is None:
                unbound.append({"line": lineno, "literal": literal, "subject": None,
                                "context": text[max(0, s - 60): e + 30].strip()})
                continue
            out.append(text[last:s])
            out.append("{{%s%s}}" % (key, f":{spec}" if spec else ""))
            last = e
            continue
        subject = subject_at(s)
        percent = bool(re.match(r"\s?%", text[e:]))
        choice = _choose(literal, subject, text, s, e, header, facts)
        if choice is None:
            if subject or percent:
                unbound.append({"line": lineno, "literal": literal, "subject": subject,
                                "context": text[max(0, s - 60): e + 30].strip()})
            continue
        key, spec = choice
        out.append(text[last:s])
        out.append("{{%s%s}}" % (key, f":{spec}" if spec else ""))
        last = e
    out.append(text[last:])
    return "".join(out)


def _prose(line: str, facts: dict, unbound: list, lineno: int, default: str | None = None) -> str:
    # Split into sentences; bind each against its own nearest subject.
    bounds = [0] + [m.end() for m in SENTENCE_END.finditer(line)] + [len(line)]
    parts = []
    for a, b in zip(bounds, bounds[1:]):
        sent = line[a:b]
        subs = _subjects_in(sent)

        def subject_at(i, subs=subs):
            before = [t for p, t in subs if p < i]
            if before:
                return before[-1]
            return None if subs else default

        parts.append(_bind_segment(sent, subject_at, "", facts, unbound, lineno))
    return "".join(parts)


def _split_cells(row: str) -> list[str]:
    cells, cur, tick = [], [], False
    for i, ch in enumerate(row):
        if ch == "`":
            tick = not tick
        if ch == "|" and not tick and (i == 0 or row[i - 1] != "\\"):
            cells.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    cells.append("".join(cur))
    return cells


def _identical_word(cell: str, subject: str | None, facts: dict) -> str:
    key = f"p2.{subject}.identical"
    if not subject or key not in facts:
        return cell
    m = re.fullmatch(r"(\s*[*_]*)(yes|no)([*_]*\s*)", cell)
    if not m or (m.group(2) == "yes") != bool(facts[key]):
        return cell
    return f"{m.group(1)}{{{{{key}:yn}}}}{m.group(3)}"


def _table(rows: list[str], facts: dict, unbound: list, first_lineno: int) -> list[str]:
    header = _split_cells(rows[0])
    col_subject = []
    for h in header:
        named = {t for _, t in _subjects_in(h)}
        col_subject.append(named.pop() if len(named) == 1 else None)
    out = rows[:2]
    grid: list[list[str]] = []
    subjects: list[list[str | None]] = []
    for n, row in enumerate(rows[2:], start=2):
        cells = _split_cells(row)
        first = _subjects_in(cells[1]) if len(cells) > 1 else []
        row_subject = first[0][1] if first else None
        new, subs = [], []
        for ci, cell in enumerate(cells):
            head = header[ci] if ci < len(header) else ""
            fallback = (col_subject[ci] if ci < len(col_subject) else None) or row_subject
            own = _subjects_in(cell)

            def subject_at(i, own=own, fallback=fallback):
                before = [t for p, t in own if p < i]
                if before:
                    return before[-1]
                return own[0][1] if own else fallback

            subs.append(fallback)
            if "identical" in head.lower():
                cell = _identical_word(cell, subject_at(len(cell)), facts)
            if ci == 1 and row_subject and not col_subject[ci]:
                new.append(cell)  # the row label names the subject; it is not a figure
                continue
            star = None
            if "★" in head:
                slug = re.search(r"`([\w.\-]+/[\w.\-]+)`", cells[1]) if len(cells) > 1 else None
                star = f"stars.{slug.group(1)}" if slug and f"stars.{slug.group(1)}" in facts else None
                if not star:
                    new.append(cell)
                    continue
            new.append(_bind_segment(cell, subject_at, head, facts, unbound, first_lineno + n, star))
        grid.append(new)
        subjects.append(subs)
    _fill_columns(grid, subjects, facts)
    out.extend("|".join(cells) for cells in grid)
    return out


def _fill_columns(grid: list[list[str]], subjects: list[list[str | None]], facts: dict) -> None:
    """A figure left literal because two facts tie binds the way the rest of
    its column bound, when every bound cell of the column agrees."""
    width = max(len(r) for r in grid)
    for ci in range(width):
        metrics = set()
        for r in grid:
            if ci < len(r):
                found = re.findall(r"\{\{(\w+)\.[\w\-]+\.(\w+)(?::([^}]*))?\}\}", r[ci])
                if len(found) > 1:
                    metrics.add(None)
                metrics.update(found)
        if len(metrics) != 1 or None in metrics:
            continue
        fam, metric, spec = metrics.pop()
        for ri, r in enumerate(grid):
            if ci >= len(r) or "{{" in r[ci]:
                continue
            subject = subjects[ri][ci]
            key = f"{fam}.{subject}.{metric}"
            if not subject or key not in facts:
                continue
            nums = [m for m in NUMBER.finditer(r[ci])
                    if not any(a <= m.start(1) < b for a, b in _protected(r[ci]))]
            if len(nums) != 1 or _formats_to(facts[key], nums[0].group(1)) is None:
                continue
            m = nums[0]
            fmt_spec = _formats_to(facts[key], m.group(1))
            ph = "{{%s%s}}" % (key, f":{fmt_spec}" if fmt_spec else "")
            r[ci] = r[ci][:m.start(1)] + ph + r[ci][m.end(1):]


def templatize(text: str, facts: dict) -> tuple[str, list[dict]]:
    lines = text.split("\n")
    out: list[str] = []
    unbound: list[dict] = []
    i, fence, section = 0, False, None
    while i < len(lines):
        line = lines[i]
        if line.lstrip().startswith(("```", "~~~")):
            fence = not fence
            out.append(line)
            i += 1
            continue
        if fence:
            out.append(line)
            i += 1
            continue
        if line.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:|-]+\|?\s*$", lines[i + 1]):
            j = i
            while j < len(lines) and lines[j].startswith("|"):
                j += 1
            out.extend(_table(lines[i:j], facts, unbound, i + 1))
            i = j
            continue
        if line.startswith("#"):
            named = {t for _, t in _subjects_in(line)}
            section = named.pop() if len(named) == 1 else None
        out.append(_prose(line, facts, unbound, i + 1, None if line.startswith("#") else section))
        i += 1
    return "\n".join(out), unbound


def stale(template: str, old: dict, new: dict) -> list[dict]:
    """Literal figures in ``template`` that read as one of the OLD facts which
    has a different value now: the numbers an update would leave behind.
    Placeholders are protected, so only the template's literals are read."""
    rebound, _ = templatize(template, old)
    hits = []
    for line_no, (before, after) in enumerate(zip(template.split("\n"), rebound.split("\n")), start=1):
        if before == after:
            continue
        mine = Counter(m.group(0) for m in PLACEHOLDER.finditer(before))
        for m in PLACEHOLDER.finditer(after):
            if mine[m.group(0)] > 0:
                mine[m.group(0)] -= 1
                continue
            key = m.group(1)
            if new.get(key) != old.get(key):
                hits.append({"line": line_no, "key": key, "literal": fmt(old[key], m.group(2)),
                             "now": None if key not in new else fmt(new[key], m.group(2)),
                             "context": after[max(0, m.start() - 60): m.end() + 30]})
    return hits
