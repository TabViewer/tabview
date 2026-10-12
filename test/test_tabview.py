import argparse
import curses
import io
import pathlib
import unittest
from unittest import mock
import tabview.cli as cli
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
# Windows-1252 is tried before Latin-1; it decodes Latin-1 text identically
# apart from the (rarely used) C1 control characters
data_2 = ('sample/test_latin-1.csv', 'cp1252', res2)
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
        res = t.process_data(self.data(fn))
        # Check that process_file returns a list of lists
        self.assertEqual(type(res), list)
        self.assertEqual(type(res[0]), list)
        for j, i in enumerate(sample_data):
            self.assertEqual(str(i), res[-1][j])

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
            self.assertEqual(i, res[0][j])

    def test_tabview_uri_parse(self):
        # Strip 'file://' from uri (three slashes)
        path = t.parse_path('file:///home/user/test.csv')
        self.assertEqual(path, '/home/user/test.csv')

        # Two slashes
        path = t.parse_path('file://localhost/test.csv')
        self.assertEqual(path, '/test.csv')

        # Don't change if no 'file://' in string
        path = t.parse_path('/home/user/test.csv')
        self.assertEqual(path, '/home/user/test.csv')

        # Don't change if relative path
        path = t.parse_path('../test.csv')
        self.assertEqual(path, '../test.csv')

        path = t.parse_path('test.csv')
        self.assertEqual(path, 'test.csv')

        # Plain filenames may contain URL special characters
        for fn in ('data#1.csv', 'what?.csv', 'a;b.csv', '100%.csv'):
            self.assertEqual(t.parse_path(fn), fn)

        # Percent escapes in URIs are decoded
        path = t.parse_path('file:///tmp/a%20b.csv')
        self.assertEqual(path, '/tmp/a b.csv')

    def test_clipboard_commands(self):
        with mock.patch.dict('os.environ', clear=True), \
                mock.patch('sys.platform', 'linux'):
            self.assertEqual(t.clipboard_commands(), [])
        with mock.patch.dict('os.environ', {'WAYLAND_DISPLAY': 'wayland-0',
                                            'DISPLAY': ':0'}, clear=True), \
                mock.patch('sys.platform', 'linux'):
            cmds = t.clipboard_commands()
            self.assertEqual(cmds[0], ['wl-copy'])
            self.assertIn(['xclip', '-selection', 'clipboard'], cmds)
        with mock.patch.dict('os.environ', clear=True), \
                mock.patch('sys.platform', 'darwin'):
            self.assertEqual(t.clipboard_commands(), [['pbcopy']])


class TestTabviewInput(unittest.TestCase):
    """Parsing of file data into rows"""

    def test_sniff_single_column(self):
        self.assertEqual(t.process_data([b'Name\n', b'Bob\n', b'Mary\n']),
                         [['Name'], ['Bob'], ['Mary']])

    def test_sniff_uses_several_lines(self):
        self.assertEqual(t.csv_sniff('Full Name,Age\nBob Smith,3\n'), ',')

    def test_sniff_blank_first_line(self):
        self.assertEqual(t.process_data(b'\na,b\n1,2\n')[1:],
                         [['a', 'b'], ['1', '2']])

    def test_sniff_control_char_delimiter(self):
        self.assertEqual(t.process_data(b'a\x01b c\n1\x012\n'),
                         [['a', 'b c'], ['1', '2']])

    def test_sniff_fallback(self):
        self.assertEqual(t.csv_sniff(''), ',')
        self.assertEqual(t.csv_sniff('a\tb\n'), '\t')

    def test_space_delim_quotes(self):
        res = t.process_data(b'name city\n"John Smith" NYC\nit\'s  LA\n')
        self.assertEqual(res, [['name', 'city'], ['John Smith', 'NYC'],
                               ["it's", 'LA']])

    def test_cr_newlines(self):
        self.assertEqual(t.process_data(b'a,b\r1,2\r'),
                         [['a', 'b'], ['1', '2']])

    def test_bom(self):
        self.assertEqual(t.detect_encoding(b'\xef\xbb\xbfa,b\n'),
                         'utf-8-sig')
        self.assertEqual(t.process_data(b'\xef\xbb\xbfa,b\n1,2\n'),
                         [['a', 'b'], ['1', '2']])
        # BOM is also removed when the encoding is given explicitly
        self.assertEqual(t.process_data(b'\xef\xbb\xbfa,b\n', enc='utf-8'),
                         [['a', 'b']])

    def test_utf16(self):
        data = 'a,é\n1,2\n'.encode('utf-16')
        self.assertEqual(t.detect_encoding(data), 'utf-16')
        self.assertEqual(t.process_data(data), [['a', 'é'], ['1', '2']])

    def test_cp1252(self):
        self.assertEqual(t.process_data('“q”,b\n'.encode('cp1252')),
                         [['“q”', 'b']])

    def test_input_types(self):
        expected = [['a', 'b'], ['1', '2']]
        self.assertEqual(t.process_data('a,b\n1,2\n'), expected)
        self.assertEqual(t.process_data(['a,b\n', '1,2\n']), expected)
        self.assertEqual(t.process_data(io.StringIO('a,b\n1,2\n').read()),
                         expected)

    def test_ragged_tuples(self):
        self.assertEqual(t.pad_data((('a', 'b'), ('c',))),
                         [['a', 'b'], ['c', '']])

    def test_empty(self):
        for data in ([], b'', '', b'\n\n', [[]]):
            self.assertFalse(t.has_data(t.process_data(data)), data)
        self.assertTrue(t.has_data(t.process_data(b'a\n')))

    def test_view_no_data(self):
        with mock.patch('sys.stderr', new_callable=io.StringIO) as err:
            self.assertEqual(t.view([[]]), 1)
            self.assertEqual(t.view(io.BytesIO(b'\n\n')), 1)
        self.assertIn('no data', err.getvalue())

    def test_view_path_types(self):
        # Opening and parsing happen before curses starts; stop there
        with mock.patch('curses.wrapper', side_effect=t.QuitException) as w:
            fn = data_1[0]
            for data in (fn, pathlib.Path(fn),
                         pathlib.Path(fn).resolve().as_uri()):
                self.assertEqual(t.view(data), 0)
                self.assertEqual(w.call_args.args[1][-1], res1)
                self.assertEqual(w.call_args.kwargs['info'], str(data))
            with open(fn, encoding='utf-8') as f:
                t.view(f)
            self.assertEqual(w.call_args.args[1][-1], res1)


class TestTabviewCli(unittest.TestCase):

    def test_char_arg(self):
        self.assertEqual(cli.char_arg('\\t'), '\t')
        self.assertEqual(cli.char_arg('\\x01'), '\x01')
        self.assertEqual(cli.char_arg(';'), ';')
        self.assertEqual(cli.char_arg('é'), 'é')
        for bad in ('', 'ab', '\\'):
            with self.assertRaises(argparse.ArgumentTypeError):
                cli.char_arg(bad)


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
