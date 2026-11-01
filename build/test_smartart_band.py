#!/usr/bin/env python3
"""The SmartArt band is the control's own footprint, not every difference between
the two pages (at 200 dpi an object below the band differs by an anti-aliased edge)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import smartart_band  # noqa: E402

W, H = 40, 40


def page(frame=False, box_top=30):
    def px(x, y):
        if frame and (x in (5, 30) or y in (5, 20)) and 5 <= x <= 30 and 5 <= y <= 20:
            return 0          # the control's border
        if box_top <= y < 38 and 5 <= x < 15:
            return 100        # the grey object below the band, on both pages
        if y == box_top - 1 and 5 <= x < 15:
            return 200        # its anti-aliased top edge
        return 255
    return px


class Footprint(unittest.TestCase):
    def test_the_band_is_the_control_border_only(self):
        # the object below is shifted by one pixel in the control, as at 200 dpi
        self.assertEqual(smartart_band.footprint(W, H, page(), page(frame=True, box_top=31)), (5, 5, 31, 21))

    def test_no_added_ink_is_no_band(self):
        self.assertIsNone(smartart_band.footprint(W, H, page(), page()))


class Outside(unittest.TestCase):
    def test_differences_outside_the_band_are_counted_with_their_box(self):
        band = (5, 5, 31, 21)
        differs = lambda x, y: (x, y) in {(10, 10), (12, 25), (12, 26), (12, 27)}  # noqa: E731
        self.assertEqual(smartart_band.outside(W, H, differs, band), (3, (12, 25, 13, 28)))

    def test_nothing_outside_is_zero_and_no_box(self):
        self.assertEqual(smartart_band.outside(W, H, lambda x, y: x == 10 and y == 10, (5, 5, 31, 21)), (0, None))


if __name__ == "__main__":
    unittest.main()
