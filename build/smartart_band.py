"""Locate the SmartArt band from the border control's own footprint.

The control (dgm_pic_border) is the corpus with a bordered picture put where the
diagram is. The band is where the CONTROL has ink and the CORPUS has none:
content both pages draw (the object below the band) is excluded even when its
anti-aliased edge moves by a pixel between the two renders. Until v0.9.3 the band
was the bounding box of every difference, which at 200 dpi swallowed that object.
"""
INK = 245  # a grey level below this is ink (smartart_verify.ink_count's threshold)


def footprint(width, height, corpus, control):
    """corpus, control: callables (x, y) -> grey level 0-255. Returns (x0, y0, x1, y1)
    with exclusive x1, y1, or None when the control adds no ink."""
    xs, ys = [], []
    for y in range(height):
        for x in range(width):
            if control(x, y) < INK and corpus(x, y) >= INK:
                xs.append(x)
                ys.append(y)
    if not xs:
        return None
    return (min(xs), min(ys), max(xs) + 1, max(ys) + 1)


def outside(width, height, differs, band):
    """differs: callable (x, y) -> bool. Count the differing pixels outside the band
    (x0, y0, x1, y1 exclusive) and return (count, their bounding box or None)."""
    x0, y0, x1, y1 = band
    xs, ys = [], []
    for y in range(height):
        for x in range(width):
            if differs(x, y) and not (x0 <= x < x1 and y0 <= y < y1):
                xs.append(x)
                ys.append(y)
    if not xs:
        return 0, None
    return len(xs), (min(xs), min(ys), max(xs) + 1, max(ys) + 1)
