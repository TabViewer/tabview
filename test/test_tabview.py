# -*- coding: utf-8 -*-
import curses
import unittest
import tabview.tabview as t

res1 = ["Yugoslavia (Latin)", "Djordje Balasevic", "Jugoslavija",
        "Đorđe Balašević"]
res2 = ["ALP", "B34130005", "Ladies' 7 oz. ComfortSoft® Cotton "
        "Piqué Polo - WHITE - L",
        "100% ComfortSoft&#174; cotton; Welt-knit collar; "
        "Tag-free neck label; High-stitch density for superior "
        "embellishment platform; "
        "Ash is 99% cotton, 1% polyester; Light Steel is "
        "90% cotton, 10% polyester; Hemmed sleeves; "
        "Sideseamed for a feminine fit; "
        "Narrow, feminine, clean-finished placket with four "
        "dyed-to-match buttons; ",
        "8.96", "7.51", "5.78", "035", "L",
        "28", "5", "WHITE", "FFFFFF", "00", ".58",
        "http://www.alphabroder.com",
        "/images/alp/prodDetail/035_00_p.jpg",
        "/images/alp/prodGallery/035_00_g.jpg", 17.92, "035",
        "00766369145683", "100", "no", "Hanes", "6",
        "36", "1007", "no", "/images/alp/prodDetail/035_00_p.jpg",
        "/images/alp/backDetail/035_bk_00_p.jpg",
        "/images/alp/sideDetail/035_sd_00_p.jpg"]
res3 = [["A", "B", "C", "D"],
        ["-0.000103903949401458218", "-0.687995654231882803", "+3",
        "+40.9029683683568948"]]

data_1 = ('sample/unicode-example-utf8.txt', 'utf-8', res1)
data_2 = ('sample/test_latin-1.csv', 'latin-1', res2)
data_3 = ('sample/commented_annotated_numeric.txt', 'utf-8', res3[1])

list_1 = [['a', 'b', 'c'], ['d', 'e', 'f'], [1, 2, 3]]

win_newlines = ('sample/windows_newlines.csv')


class TestTabviewUnits(unittest.TestCase):
    """Unit tests for tabview

    """
    def setUp(self):
        pass

    def data(self, fn):
        with open(fn, 'rb') as f:
            return f.readlines()

    def tabview_encoding(self, info):
        """Test that correct encoding is returned for encoded data.

        """
        fn, enc, _ = info
        d = self.data(fn)
        r = t.detect_encoding(d)
        self.assertEqual(r, enc)

    def test_tabview_encoding_utf8(self):
        """Test that correct encoding is returned for utf-8 encoded file.

        """
        self.tabview_encoding(data_1)

    def test_tabview_encoding_latin1(self):
        """Test that correct encoding is returned for latin-1 encoded file.

        """
        self.tabview_encoding(data_2)

    def tabview_file(self, info):
        """Test that data processed from a unicode file matches the sample data
        above

        """
        fn, _, sample_data = info
        code = 'utf-8'  # Per top line of file
        res = t.process_data(self.data(fn))
        # Check that process_file returns a list of lists
        self.assertEqual(type(res), list)
        self.assertEqual(type(res[0]), list)
        # Have to decode res1 and res2 from utf-8 so they can be compared to
        # the results from the file, which are unicode (py2) or string (py3)
        for j, i in enumerate(sample_data):
            try:
                i = i.decode(code)
            except AttributeError:
                i = str(i)
            self.assertEqual(i, res[-1][j])

    def test_tabview_file_unicode(self):
        self.tabview_file(data_1)

    def test_tabview_file_latin1(self):
        self.tabview_file(data_2)

    def test_tabview_file_annotated_comment(self):
        self.tabview_file(data_3)
        # Test removal of comment mark in first line
        sample_data = res3[0]
        res = t.process_data(self.data(data_3[0]))
        for j, i in enumerate(sample_data):
            try:
                i = i.decode('utf-8')
            except AttributeError:
                i = str(i)
            self.assertEqual(i, res[0][j])


class TestTabviewIntegration(unittest.TestCase):
    """Integration tests for tabview. Run through the curses routines and some
    of the non-interactive movements.

    """
    def setUp(self):
        pass

    def main(self, stdscr, *args, **kwargs):
        curses.use_default_colors()
        curses.curs_set(False)
        v = t.Viewer(stdscr, *args, **kwargs)
        v.display()
        for key in v.keys:
            if key not in ('q', 'Q', 'r', '?', '/', '\n', 'a', 'A', 's', 'S',
                           '#', '@', 'y', curses.KEY_F1, curses.KEY_ENTER,
                           t.KEY_CTRL('g')):
                v.keys[key]()
            elif key in ('q', 'Q', 'r'):
                self.assertRaises((t.ReloadException, t.QuitException),
                                  v.keys[key])

    def data(self, fn):
        with open(fn, 'rb') as f:
            return f.readlines()

    def test_tabview_unicode(self):
        curses.wrapper(self.main, t.process_data(self.data(data_1[0])),
                       start_pos=(5, 5), column_width='mode', column_gap=2,
                       column_widths=None, trunc_char='…', search_str=None)

    def test_tabview_latin1(self):
        curses.wrapper(self.main, t.process_data(self.data(data_2[0])),
                       start_pos=5, column_width='max', column_gap=0,
                       column_widths=None, trunc_char='…', search_str='36')

    def test_tabview_list(self):
        curses.wrapper(self.main, t.process_data(list_1),
                       start_pos=0, column_width=5, column_gap=10,
                       column_widths=[4, 5, 1], trunc_char='>',
                       search_str=None)

    def test_tabview_windows_newlines(self):
        curses.wrapper(self.main, t.process_data(self.data(win_newlines)),
                       start_pos=(0, 1), column_width='mode', column_gap=5,
                       column_widths=None, trunc_char='…', search_str=None)

    def test_tabview_annotated_comment(self):
        curses.wrapper(self.main, t.process_data(self.data(data_3[0])),
                       start_pos=(0, 1), column_width='mode', column_gap=2,
                       column_widths=None, trunc_char='…', search_str=None)


if __name__ == '__main__':
    unittest.main()
