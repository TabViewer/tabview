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

    def test_strpad(self):
        v = mock.Mock(trunc_char='>')
        self.assertEqual(t.Viewer.strpad(v, 'a\tb\x00c', 9), 'a\\tb\\x00c')
        self.assertEqual(t.Viewer.strpad(v, 'a\nb', 6), 'a\\nb  ')
        # Double width characters take two cells: 2 + 2 + '>'
        self.assertEqual(t.Viewer.strpad(v, '日本語', 5), '日本>')
        self.assertEqual(t.Viewer.strpad(v, 'ab', 0), '')

    def test_help_text(self):
        text = t.help_text()
        self.assertIn('Show this list of keybindings', text)
        self.assertIn('[num]}', text)
        self.assertNotIn('```', text)
        self.assertNotIn('## ', text)

    def test_wrap_cells(self):
        def cells(line):
            return sum(t.char_width(c) for c in line)
        text = 'Camera摄影机早早就在美式战斗机的机枪枪管上方安扎下来，用于捕捉目标' * 3
        lines = t.wrap_cells(text, 20)
        self.assertTrue(all(cells(i) <= 20 for i in lines))
        self.assertEqual(''.join(i.removeprefix(' ') for i in lines), text)
        # Plain text wraps at spaces like textwrap
        self.assertEqual(t.wrap_cells('aaa bbb ccc', 8), ['aaa bbb', ' ccc'])
        self.assertEqual(t.wrap_cells('', 8), [''])

    def test_char_width(self):
        self.assertEqual(t.char_width('a'), 1)
        self.assertEqual(t.char_width('日'), 2)
        self.assertEqual(t.char_width('Ａ'), 2)  # fullwidth


class TestTabviewSort(unittest.TestCase):

    def sort(self, method, column):
        v = mock.Mock(data=[[i] for i in column], x=0, win_x=0)
        v.sorted_nicely = lambda *a, **k: t.Viewer.sorted_nicely(v, *a, **k)
        v.float_string_key = lambda i: t.Viewer.float_string_key(v, i)
        getattr(t.Viewer, method)(v)
        return [i[0] for i in v.data]

    def test_natural(self):
        col = ['a10', 'a2', 'b1', 'a1', '²', '٣', '']
        self.assertEqual(self.sort('sort_by_column_natural', col),
                         ['', 'a1', 'a2', 'a10', 'b1', '²', '٣'])
        self.assertEqual(self.sort('sort_by_column_natural_reverse', col),
                         ['٣', '²', 'b1', 'a10', 'a2', 'a1', ''])

    def test_numeric(self):
        col = ['0', 'nan', '-1', 'NaN', '1e3', 'abc', '2.5']
        self.assertEqual(self.sort('sort_by_column_numeric', col),
                         ['-1', '0', '2.5', '1e3', 'nan', 'NaN', 'abc'])
        self.assertEqual(self.sort('sort_by_column_numeric_reverse', col),
                         ['abc', 'nan', 'NaN', '1e3', '2.5', '0', '-1'])

    def test_plain(self):
        col = ['b', 'a', 'B', '10', '9']
        self.assertEqual(self.sort('sort_by_column', col),
                         ['10', '9', 'B', 'a', 'b'])
        self.assertEqual(self.sort('sort_by_column_reverse', col),
                         ['b', 'a', 'B', '9', '10'])


class TestTabviewSearch(unittest.TestCase):
    """search_results() on a Viewer built without curses. Positions are
    0-based (y, x) data coordinates.

    """
    grid = [['apple', 'banana', 'cherry'],
            ['date', 'Apple pie', 'fig'],
            ['grape', 'kiwi', 'crabapple']]

    def viewer(self, pos=(0, 0), search='apple', data=None, win=(0, 0)):
        v = t.Viewer.__new__(t.Viewer)
        v.data = [list(i) for i in (data or self.grid)]
        v.num_data_columns = len(v.data[0])
        v.win_y, v.win_x = win
        v.y, v.x = pos[0] - win[0], pos[1] - win[1]
        v.search_str = search
        v.init_search = None

        def goto_yx(y, x):
            v.y, v.x = y - 1 - v.win_y, x - 1 - v.win_x
        v.goto_yx = goto_yx
        return v

    def pos(self, v):
        return v.y + v.win_y, v.x + v.win_x

    def press(self, v, key, times=1):
        res = []
        for _ in range(times):
            if key == 'n':
                v.search_results()
            else:
                v.search_results_prev()
            res.append(self.pos(v))
        return res

    def test_next(self):
        v = self.viewer()
        self.assertEqual(self.press(v, 'n', 4),
                         [(1, 1), (2, 2), (0, 0), (1, 1)])

    def test_prev(self):
        v = self.viewer()
        self.assertEqual(self.press(v, 'p', 4),
                         [(2, 2), (1, 1), (0, 0), (2, 2)])

    def test_next_then_prev(self):
        v = self.viewer()
        self.assertEqual(self.press(v, 'n', 2), [(1, 1), (2, 2)])
        self.assertEqual(self.press(v, 'p', 2), [(1, 1), (0, 0)])

    def test_same_row(self):
        # Matches later in the current row come first, earlier ones last
        data = [['x', 'a', 'x', 'a'], ['x', 'x', 'x', 'x']]
        v = self.viewer(pos=(0, 2), search='a', data=data)
        self.assertEqual(self.press(v, 'n', 2), [(0, 3), (0, 1)])
        v = self.viewer(pos=(0, 2), search='a', data=data)
        self.assertEqual(self.press(v, 'p', 2), [(0, 1), (0, 3)])

    def test_wraps_from_end(self):
        v = self.viewer(pos=(2, 2), search='banana')
        self.assertEqual(self.press(v, 'n'), [(0, 1)])
        v = self.viewer(pos=(0, 0), search='fig')
        self.assertEqual(self.press(v, 'p'), [(1, 2)])

    def test_end_of_row(self):
        v = self.viewer(pos=(0, 2), search='date')
        self.assertEqual(self.press(v, 'n'), [(1, 0)])
        v = self.viewer(pos=(1, 0), search='cherry')
        self.assertEqual(self.press(v, 'p'), [(0, 2)])

    def test_only_match_is_current_cell(self):
        v = self.viewer(pos=(1, 2), search='fig')
        self.assertEqual(self.press(v, 'n'), [(1, 2)])
        self.assertEqual(self.press(v, 'p'), [(1, 2)])

    def test_no_match(self):
        v = self.viewer(pos=(1, 1), search='zzz')
        v.goto_yx = mock.Mock()
        v.search_results()
        v.search_results_prev()
        v.goto_yx.assert_not_called()

    def test_no_search_string(self):
        v = self.viewer(search='')
        v.goto_yx = mock.Mock()
        v.search_results()
        v.goto_yx.assert_not_called()

    def test_init_search(self):
        v = self.viewer(search=None)
        v.init_search = 'kiwi'
        self.assertEqual(self.press(v, 'n'), [(2, 1)])
        self.assertEqual(v.search_str, 'kiwi')

    def test_init_search_case(self):
        # The initial search string isn't lowercased by the search box
        v = self.viewer(search=None)
        v.init_search = 'KIWI'
        self.assertEqual(self.press(v, 'n'), [(2, 1)])

    def test_ragged_rows(self):
        data = [['a', 'b', 'c'], ['d'], ['e', 'f', 'x']]
        v = self.viewer(search='x', data=data)
        self.assertEqual(self.press(v, 'n'), [(2, 2)])
        self.assertEqual(self.press(v, 'p'), [(2, 2)])

    def test_look_in_current(self):
        v = self.viewer(pos=(1, 1))
        v.search_results(look_in_cur=True)
        self.assertEqual(self.pos(v), (1, 1))
        v = self.viewer(pos=(1, 2))
        v.search_results(look_in_cur=True)
        self.assertEqual(self.pos(v), (2, 2))

    def test_scrolled_window(self):
        # Cursor position is win + offset within the window
        v = self.viewer(pos=(1, 1), win=(1, 1))
        self.assertEqual(self.press(v, 'n'), [(2, 2)])
        v = self.viewer(pos=(1, 1), win=(1, 1))
        self.assertEqual(self.press(v, 'p'), [(0, 0)])

    def test_data_unchanged(self):
        v = self.viewer()
        rows = list(v.data)
        self.press(v, 'p', 3)
        self.press(v, 'n', 3)
        self.assertEqual(v.data, self.grid)
        self.assertTrue(all(a is b for a, b in zip(v.data, rows, strict=True)))


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

    def test_start_position(self):
        sp = cli.start_position
        self.assertEqual(sp(None, []), (0, 0))
        self.assertEqual(sp('5,3', []), (5, 3))
        self.assertEqual(sp('5,', []), (5, 0))
        self.assertEqual(sp(',3', []), (0, 3))
        self.assertEqual(sp('5', []), (5, 0))
        self.assertEqual(sp(None, ['+6:5']), (6, 5))
        self.assertEqual(sp(None, ['+5:']), (5, 0))
        self.assertEqual(sp(None, ['+:4']), (0, 4))
        self.assertEqual(sp(None, ['+7']), (7, 0))
        with self.assertRaises(ValueError):
            sp('a', [])

    def run_main(self, *argv):
        with mock.patch('sys.argv', ['tabview', *argv]), \
                mock.patch.object(cli, 'view', return_value=0) as view, \
                mock.patch('sys.stderr', new_callable=io.StringIO) as err:
            try:
                res = cli.main()
            except SystemExit as e:
                res = e.code
        return res, view, err.getvalue()

    def test_main(self):
        res, view, _ = self.run_main('f.csv', '+6:5', '-d', '\\t')
        self.assertEqual(res, 0)
        self.assertEqual(view.call_args.args, ('f.csv',))
        self.assertEqual(view.call_args.kwargs['start_pos'], (6, 5))
        self.assertEqual(view.call_args.kwargs['delimiter'], '\t')
        self.assertEqual(view.call_args.kwargs['column_width'], 20)

    def test_main_errors(self):
        for argv, msg in ((('f.csv', '--widht', '5'), 'unrecognized'),
                          (('f.csv', '+a'), 'start position'),
                          (('f.csv', '-e', 'bogus'), 'unknown encoding'),
                          (('f.csv', '-q', ''), 'single character')):
            res, view, err = self.run_main(*argv)
            self.assertEqual(res, 2, argv)
            self.assertIn(msg, err)
            view.assert_not_called()

    def test_main_missing_file(self):
        with mock.patch('sys.argv', ['tabview', 'no/such/file.csv']), \
                mock.patch('sys.stderr', new_callable=io.StringIO) as err:
            self.assertEqual(cli.main(), 1)
        self.assertIn('No such file', err.getvalue())


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
            if key not in ('q', 'Q', 'r', '?', '/', '\n', 'y', curses.KEY_F1,
                           curses.KEY_ENTER, t.KEY_CTRL('g')):
                v.keys[key]()
                v.display()
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

    def keys(self, stdscr, data, keys):
        """Press keys (digits are modifiers) and redraw after each"""
        v = t.Viewer(stdscr, data, start_pos=(0, 0), column_width='mode',
                     column_gap=2, column_widths=None, trunc_char='…',
                     search_str=None)
        v.display()
        for key in keys:
            if key.isdigit():
                v.handle_modifier(key)
            else:
                v.keys[key]()
                v.display()
        return v

    def test_control_chars(self):
        data = [['a\x00', 'b'], ['x\x00y', 'z\tq\tq\tq\tq\tq\tq\tq\tq\r\x1b']]
        curses.wrapper(self.main, data, start_pos=(0, 0),
                       column_width='mode', column_gap=2, column_widths=None,
                       trunc_char='…', search_str=None)

    def test_column_width_min(self):
        data = t.process_data(self.data(data_2[0]))
        for keys in (',' * 30 + 'l' * 30 + ',' * 30, '++0cLLLHHH', '0CLL'):
            v = curses.wrapper(self.keys, data, keys)
            self.assertGreaterEqual(min(v.column_width), 1, keys)

    def test_tabview_annotated_comment(self):
        curses.wrapper(self.main, t.process_data(self.data(data_3[0])),
                       start_pos=(0, 1), column_width='mode', column_gap=2,
                       column_widths=None, trunc_char='…', search_str=None)


if __name__ == '__main__':
    unittest.main()
