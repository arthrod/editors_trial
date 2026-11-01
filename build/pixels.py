"""The one resolution every pixel measurement rasterises at (Report C's pixel
layers: Word's pages, LibreOffice's pages, the SmartArt band).

Release rule from v0.9.3: 200 dpi. Releases up to v0.9.2 used 110 dpi, so pixel
counts are not comparable across that line; percentages of the corpus's ink are
closer, but were re-measured, not converted.
"""
DPI = 200
