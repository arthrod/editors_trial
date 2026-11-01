#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["pillow>=11"]
# ///
"""
Report C section 6.3: the A/B control, one construct removed at a time.

Each variant (build/ab_test.py) is the corpus with one construct deleted from
word/document.xml, exported to PDF by Word (out/ab/pdf/<variant>.pdf) and
rasterised at build/pixels.py's DPI (build/raster_controls.py, out/ab/png).
Each variant page is compared with Word's page of the corpus
(out/render/png_word/corpus-N.png) by build/page_diff.py's compare(): pixels
whose difference exceeds 8/255, and the bounding box of the difference.

The PDF byte column compares each variant with out/render/word/corpus.pdf,
the export the pixel pages come from.

LibreOffice's side (section 5.6) renders the corpus and every variant in this
run (lo_render_compare.render: a temporary profile, the release DPI), so both
come from one LibreOffice: a corpus rendered on another day once differed from
every variant by the same 4,536 pixels on page 2.

usage: uv run --script build/ab_table.py      # -> out/ab/ab_compare.json
facts.py publishes table() as {{ab.table}} and each variant as ab.<variant>.*
"""
import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_JSON = os.path.join(BASE, "out", "ab", "ab_compare.json")

# in the report's order: the largest byte delta first
VARIANTS = [
    ("no_w14", "the `w14:textOutline` run"),
    ("no_chart", "the chart"),
    ("no_math", "the OMML equation"),
    ("no_wps", "the `wps` text box"),
    ("no_ole", "the OLE object"),
    ("no_pic", "the picture"),
    ("no_dgm", "the SmartArt"),
]
# what section 5 proves about a row, appended to its pixel cell
NOTES = {"no_dgm": " — **all of it reflow**"}
# the colour Word draws the picture and the OLE object in (section 5.6 follows
# the OLE object from page 4 to page 3); the chart's bars, (68, 114, 196), are not it
BLUE = (31, 119, 180)


def is_blue(rgb, tol=12):
    return all(abs(a - b) <= tol for a, b in zip(rgb, BLUE))


def blue_count(path):
    from PIL import Image
    im = Image.open(path).convert("RGB")
    return sum(n for n, c in im.getcolors(maxcolors=1 << 24) if is_blue(c))


def _diffs(page_diff, ref_fmt, var_fmt):
    pages, n = {}, 1
    while os.path.exists(var_fmt % n):
        r = page_diff.compare(ref_fmt % n, var_fmt % n)
        if r.get("size_mismatch"):
            pages[str(n)] = {"size_mismatch": True}
        elif r["diff_px"]:
            pages[str(n)] = {"diff_px": r["diff_px"], "bbox": list(r["diff_bbox"])}
        n += 1
    return pages, n - 1


def measure():
    sys.path.insert(0, os.path.join(BASE, "build"))
    import page_diff
    import pixels
    ref = os.path.join(BASE, "out", "render", "png_word")
    var = os.path.join(BASE, "out", "ab", "png")
    data = {"dpi": pixels.DPI,
            "corpus_bytes": os.path.getsize(os.path.join(BASE, "out", "render", "word", "corpus.pdf")),
            "variants": {}}
    import lo_render_compare as lrc
    lrc.render("corpus", "fixture/complex.docx", os.path.join(BASE, "out", "render", "lo"),
               os.path.join(BASE, "out", "render", "lo_png"))
    lo_png = os.path.join(BASE, "out", "ab", "lo_png")
    os.makedirs(lo_png, exist_ok=True)
    for v, _ in VARIANTS:
        lrc.render(v, "out/ab/%s.docx" % v, os.path.join(BASE, "out", "ab", "lo"), lo_png)
    lo_ref = os.path.join(BASE, "out", "render", "lo_png", "corpus-%d.png")
    data["corpus_blue"] = {str(n): blue_count(os.path.join(ref, "corpus-%d.png" % n)) for n in (3, 4)}
    for v, _ in VARIANTS:
        pages, count = _diffs(page_diff, os.path.join(ref, "corpus-%d.png"), os.path.join(var, v + "-%d.png"))
        lo_pages, _ = _diffs(page_diff, lo_ref, os.path.join(BASE, "out", "ab", "lo_png", v + "-%d.png"))
        data["variants"][v] = {
            "bytes": os.path.getsize(os.path.join(BASE, "out", "ab", "pdf", v + ".pdf")),
            "page_count": count, "pages": pages, "lo_pages": lo_pages,
            "blue": {str(n): blue_count(os.path.join(var, "%s-%d.png" % (v, n))) for n in (3, 4)},
        }
    return data


def _num(n):
    return f"{n:,}"


def _delta(n):
    return ("−" if n < 0 else "+") + f"{abs(n):,}"


def _cell(v, row):
    pages = row["pages"]
    if any(p.get("size_mismatch") for p in pages.values()):
        return "page sizes differ"
    if not pages:
        return "0"
    if len(pages) == 1:
        (p, d), = pages.items()
        b = d["bbox"]
        cell = f"{_num(d['diff_px'])} on page {p}, bbox ({b[0]}, {b[1]}) – ({b[2]}, {b[3]})"
    else:
        cell = " + ".join(f"{_num(d['diff_px'])} on page {p}" for p, d in sorted(pages.items(), key=lambda x: int(x[0])))
    return cell + NOTES.get(v, "")


def table(data):
    rows = [(v, label, data["variants"][v]) for v, label in VARIANTS if v in data["variants"]]
    deltas = {v: r["bytes"] - data["corpus_bytes"] for v, _, r in rows}
    smallest = min(deltas, key=lambda v: abs(deltas[v])) if deltas else None
    out = ["| Variant | Construct removed | Word PDF bytes | Δ | Differing pixels at %d dpi |" % data["dpi"],
           "|---|---|---:|---:|---|",
           f"| corpus | — | {_num(data['corpus_bytes'])} | — | — |"]
    for v, label, r in rows:
        d = _delta(deltas[v])
        if v == smallest:
            d = f"**{d}**"
        out.append(f"| `{v}` | {label} | {_num(r['bytes'])} | {d} | {_cell(v, r)} |")
    return "\n".join(out)


def facts_into(data, facts):
    facts["ab.table"] = table(data)
    for p, n in data.get("corpus_blue", {}).items():
        facts[f"ab.corpus.blue.p{p}"] = _num(n)
    for v, r in data["variants"].items():
        px = [p["diff_px"] for p in r["pages"].values() if "diff_px" in p]
        facts[f"ab.{v}.px"] = _num(sum(px))
        facts[f"ab.{v}.delta"] = _delta(r["bytes"] - data["corpus_bytes"])
        facts[f"ab.{v}.page"] = " and ".join(sorted(r["pages"], key=int)) or "none"
        for p, d in r["pages"].items():
            if "bbox" in d:
                b = d["bbox"]
                facts[f"ab.{v}.p{p}.px"] = _num(d["diff_px"])
                facts[f"ab.{v}.p{p}.bbox"] = f"({b[0]}, {b[1]}) – ({b[2]}, {b[3]})"
        for p, d in r.get("lo_pages", {}).items():
            if "diff_px" in d:
                facts[f"ab.{v}.lo.p{p}.px"] = _num(d["diff_px"])
        for p, n in r.get("blue", {}).items():
            facts[f"ab.{v}.blue.p{p}"] = _num(n)


def main():
    data = measure()
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w") as fh:
        json.dump(data, fh, indent=1)
    print(table(data))
    return 0


if __name__ == "__main__":
    sys.exit(main())
