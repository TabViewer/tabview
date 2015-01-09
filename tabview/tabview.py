# -*- coding: utf-8 -*-
""" tabview.py -- View a tab-delimited file in a spreadsheet-like display.

  Scott Hansen <firecat four one five three at gmail dot com>
  Based on code contributed by A.M. Kuchling <amk at amk dot ca>

"""
from __future__ import print_function, division, unicode_literals

import csv
import curses
import locale
import os
import re
import sys
from operator import itemgetter
from subprocess import Popen, PIPE
from textwrap import wrap


if sys.version_info.major < 3:
    # Python 2.7 shim
    str = unicode

    def addstr(*args):
        scr, args = args[0], list(args[1:])
        x = 2 if len(args) > 2 else 0
        args[x] = args[x].encode(sys.stdout.encoding)
        return scr.addstr(*args)

    def insstr(*args):
        scr, args = args[0], list(args[1:])
        x = 2 if len(args) > 2 else 0
        args[x] = args[x].encode(sys.stdout.encoding)
        return scr.insstr(*args)

else:
    # Python 3 wrappers
    def addstr(*args):
        scr, args = args[0], args[1:]
        return scr.addstr(*args)

    def insstr(*args):
        scr, args = args[0], args[1:]
        return scr.insstr(*args)


class ReloadException(Exception):
    pass


class QuitException(Exception):
    pass


class Viewer:
    """The actual CSV viewer class.

    Args:
        scr: curses window object
        data: data (list of lists)
        column_width: fixed width for each column
        column_gap: gap inbetween columns
        trunc_char: character to delineate a truncated line

    """
    def __init__(self, scr, data, column_width=20, column_gap=2,
                 trunc_char='…'):
        self.scr = scr
        if sys.version_info.major < 3:
            self.data = [[j for j in i] for i in data]
        else:
            self.data = [[str(j) for j in i] for i in data]
        self.header_offset_orig = 3
        self.header = self.data[0]
        if len(self.data) > 1:
            del self.data[0]
            self.header_offset = self.header_offset_orig
        else:
            # Don't make one line file a header row
            self.header_offset = self.header_offset_orig - 1
        self.column_width = column_width
        self.column_gap = column_gap

        try:
            trunc_char.encode(sys.stdout.encoding or 'utf-8')
            self.trunc_char = trunc_char
        except (UnicodeDecodeError, UnicodeError):
            self.trunc_char = '>'

        self.x, self.y = 0, 0
        self.win_x, self.win_y = 0, 0
        self.max_y, self.max_x = 0, 0
        self.num_columns = 0
        self.vis_columns = 0
        self.res = []
        self.res_idx = 0
        self.modifier = str()
        self.keys()
        self.resize()
        self.display()

    def column_xw(self, x):
        """Return the position and width of the requested column"""
        xp = x * self.column_width + x * self.column_gap
        if x < self.num_columns:
            w = min(self.max_x, self.column_width)
        else:
            w = self.max_x - xp
        return xp, w

    def keys(self):
        """Define methods for each allowed key press.

        """
        def quit():
            raise QuitException

        def reload():
            raise ReloadException

        def down():
            end = len(self.data) - 1
            if self.win_y + self.y < end:
                if self.y < self.max_y - self.header_offset - 1:
                    self.y = self.y + 1
                else:
                    self.win_y = self.win_y + 1

        def up():
            if self.y == 0:
                if self.win_y > 0:
                    self.win_y = self.win_y - 1
            else:
                self.y = self.y - 1

        def left():
            if self.x == 0:
                if self.win_x > 0:
                    self.win_x = self.win_x - 1
            else:
                self.x = self.x - 1

        def right():
            yp = self.y + self.win_y
            if len(self.data) <= yp:
                return
            end = len(self.data[yp]) - 1
            if self.win_x + self.x >= end:
                pass
            elif self.x < self.num_columns - 1:
                self.x = self.x + 1
            else:
                self.win_x = self.win_x + 1

        def page_down():
            end = len(self.data) - 1
            if self.win_y <= end - self.max_y + self.header_offset:
                new_win_y = self.win_y + self.max_y - self.header_offset
                if new_win_y + self.y > end:
                    self.y = end - new_win_y
                self.win_y = new_win_y
            else:
                self.y = end - self.win_y

        def page_up():
            if self.win_y == 0:
                self.y = 0
            elif self.win_y < self.max_y - self.header_offset:
                self.win_y = 0
            else:
                self.win_y = self.win_y - self.max_y + self.header_offset

        def page_right():
            yp = self.y + self.win_y
            if len(self.data) <= yp:
                return
            end = len(self.data[yp]) - 1
            if self.win_x <= end - self.num_columns:
                new_win_x = self.win_x + self.num_columns
                if new_win_x + self.x > end:
                    self.x = end - new_win_x
                self.win_x = new_win_x
            else:
                self.x = end - self.win_x

        def page_left():
            if self.win_x == 0:
                self.x = 0
            elif self.win_x < self.num_columns:
                self.win_x = 0
            else:
                self.win_x = self.win_x - self.num_columns

        def mark():
            self.save_y, self.save_x = self.y + self.win_y, self.x + self.win_x

        def goto_mark():
            if hasattr(self, 'save_y'):
                goto_y(self.save_y + 1)
                goto_x(self.save_x + 1)

        def home():
            self.win_y = self.y = 0

        def goto_y(m):
            if m > 0 and m <= len(self.data):
                if self.win_y < m <= self.win_y + \
                        (self.max_y - self.header_offset):
                    # same screen, change y appropriately.
                    self.y = m - 1 - self.win_y
                elif m <= self.win_y:
                    # going back
                    self.y = 0
                    self.win_y = m - 1
                else:
                    # going forward
                    self.win_y = m - (self.max_y - self.header_offset)
                    self.y = (self.max_y - self.header_offset) - 1

        def goto_row():
            m = int(self.modifier) if len(self.modifier) else len(self.data)
            goto_y(m)
            self.modifier = str()

        def goto_x(m):
            if m > 0 and m <= len(self.data[self.y + self.win_y]):
                if self.win_x < m <= self.win_x + self.num_columns:
                    # same screen, change x value appropriately.
                    self.x = m - 1 - self.win_x
                elif m <= self.win_x:
                    # going back
                    self.x = 0
                    self.win_x = m - 1
                else:
                    # going forward
                    self.win_x = m - self.num_columns
                    self.x = self.num_columns - 1

        def goto_col():
            m = int(self.modifier) if len(self.modifier) else 1
            goto_x(m)
            self.modifier = str()

        def line_home():
            self.win_x = self.x = 0

        def line_end():
            end = len(self.data[self.y + self.win_y])
            goto_x(end)

        def show_cell():
            "Display current cell in a pop-up window"
            yp = self.y + self.win_y
            xp = self.x + self.win_x
            try:
                # Don't display popup if the cursor if somehow off the
                # end of the normal row, for example if the list has an
                # uneven number of columns
                s = self.data[yp][xp].splitlines()
                s = [wrap(i, 78, subsequent_indent="  ") for i in s]
                s = [i for j in s for i in j]
            except IndexError:
                return
            if not s:
                # Only display pop-up if cells have contents
                return
            lines = len(s) + 2
            scr2 = curses.newwin(lines, 80, 5, 5)
            scr2.move(0, 0)
            addstr(scr2, 1, 1, "\n".join(s))
            scr2.box()
            while not scr2.getch():
                pass

        def search():
            """Search (case independent) from the top for string and goto
            that spot"""
            scr2 = curses.newwin(4, 40, 15, 15)
            scr2.box()
            scr2.move(1, 1)
            addstr(scr2, "Search: ")
            curses.echo()
            search = scr2.getstr().decode(sys.stdout.encoding).lower()
            curses.noecho()
            if search:
                self.res = [(y, x) for y, line in enumerate(self.data) for
                            x, item in enumerate(line)
                            if search in item.lower()]
                self.res_idx = 0
                self.x = self.y = 0
            else:
                self.res = []
            if self.res:
                self.win_y, self.win_x = self.res[self.res_idx]

        def next_result():
            if self.res:
                if self.res_idx < len(self.res) - 1:
                    self.res_idx += 1
                else:
                    self.res_idx = 0
                self.x = self.y = 0
                self.win_y, self.win_x = self.res[self.res_idx]

        def prev_result():
            if self.res:
                if self.res_idx > 0:
                    self.res_idx -= 1
                else:
                    self.res_idx = len(self.res) - 1
                self.x = self.y = 0
                self.win_y, self.win_x = self.res[self.res_idx]

        def help():
            help_txt = readme()
            idx = help_txt.index('Keybindings:\n')
            help_txt = [i.replace('**', '') for i in help_txt[idx:]
                        if '=' not in i]
            lines = len(help_txt) + 2
            scr2 = curses.newwin(lines, 82, 5, 5)
            scr2.move(0, 0)
            addstr(scr2, 1, 1, " ".join(help_txt))
            scr2.box()
            while not scr2.getch():
                pass

        def toggle_header():
            if self.header_offset == self.header_offset_orig:
                # Turn off header row
                self.header_offset = self.header_offset - 1
                self.data.insert(0, self.header)
                self.y = self.y + 1
            else:
                if len(self.data) == 1:
                    return
                # Turn on header row
                self.header_offset = self.header_offset_orig
                del self.data[self.data.index(self.header)]
                if self.y > 0:
                    self.y = self.y - 1
                elif self.win_y > 0:
                    # Scroll down 1 to keep cursor on the same item
                    up()
                    down()
                    self.y = self.y - 1

        def column_gap_down():
            self.column_gap = max(0, self.column_gap - 1)
            self.recalculate_layout()

        def column_gap_up():
            self.column_gap += 1
            self.recalculate_layout()

        def column_width_down():
            step = max(1, int(self.column_width * 0.2))
            self.column_width = max(1, self.column_width - step)
            self.recalculate_layout()

        def column_width_up():
            step = int(self.column_width * 0.2)
            self.column_width += max(1, step)
            self.recalculate_layout()

        def sort_by_column():
            xp = self.x + self.win_x
            self.data = sorted(self.data, key=itemgetter(xp))

        def sort_by_column_reverse():
            xp = self.x + self.win_x
            self.data = sorted(self.data, key=itemgetter(xp), reverse=True)

        def sort_by_column_natural():
            xp = self.x + self.win_x
            self.data = sorted_nicely(self.data, itemgetter(xp))

        def sort_by_column_natural_reverse():
            xp = self.x + self.win_x
            self.data = sorted_nicely(self.data, itemgetter(xp), rev=True)

        def sorted_nicely(ls, key, rev=False):
            """ Sort the given iterable in the way that humans expect.

            From StackOverflow: http://goo.gl/nGBUrQ

            """
            def convert(text):
                return int(text) if text.isdigit() else text

            def alphanum_key(item):
                return [convert(c) for c in re.split('([0-9]+)', key(item))]

            return sorted(ls, key=alphanum_key, reverse=rev)

        def yank_cell():
            yp = self.y + self.win_y
            xp = self.x + self.win_x
            s = self.data[yp][xp]
            # Bail out if not running in X
            try:
                os.environ['DISPLAY']
            except KeyError:
                return
            for cmd in (['xclip', '-selection', 'clipboard'],
                        ['xsel', '-i']):
                try:
                    Popen(cmd, stdin=PIPE,
                          universal_newlines=True).communicate(input=s)
                except FileNotFoundError:
                    pass

        self.keys = {'j':   down,
                     'k':   up,
                     'h':   left,
                     'l':   right,
                     'J':   page_down,
                     'K':   page_up,
                     'm':   mark,
                     "'":   goto_mark,
                     'L':   page_right,
                     'H':   page_left,
                     'q':   quit,
                     'Q':   quit,
                     '$':   line_end,
                     '^':   line_home,
                     '0':   line_home,
                     'g':   home,
                     'G':   goto_row,
                     '|':   goto_col,
                     '\n':  show_cell,
                     '/':   search,
                     'n':   next_result,
                     'p':   prev_result,
                     't':   toggle_header,
                     '-':   column_gap_down,
                     '+':   column_gap_up,
                     '<':   column_width_down,
                     '>':   column_width_up,
                     'a':   sort_by_column_natural,
                     'A':   sort_by_column_natural_reverse,
                     's':   sort_by_column,
                     'S':   sort_by_column_reverse,
                     'y':   yank_cell,
                     'r':   reload,
                     '?':   help,
                     curses.KEY_F1:     help,
                     curses.KEY_UP:     up,
                     curses.KEY_DOWN:   down,
                     curses.KEY_LEFT:   left,
                     curses.KEY_RIGHT:  right,
                     curses.KEY_HOME:   line_home,
                     curses.KEY_END:    line_end,
                     curses.KEY_PPAGE:  page_up,
                     curses.KEY_NPAGE:  page_down,
                     curses.KEY_IC:     mark,
                     curses.KEY_DC:     goto_mark,
                     curses.KEY_ENTER:  show_cell,
                     }

    def run(self):
        # Clear the screen and display the menu of keys
        # Main loop:
        while True:
            self.display()
            self.handle_keys()

    def handle_keys(self):
        """Determine what method to call for each keypress.

        """
        c = self.scr.getch()  # Get a keystroke
        if c == curses.KEY_RESIZE:
            self.resize()
            return
        if 0 < c < 256:
            c = chr(c)
        # Digits are commands without a modifier
        try:
            found_digit = c.isdigit()
        except AttributeError:
            # Since .isdigit() doesn't exist if c > 256, we need to catch the
            # error for those keys.
            found_digit = False
        if found_digit and (len(self.modifier) > 0 or c not in self.keys):
            self.handle_modifier(c)
        elif c in self.keys:
            self.keys[c]()
        else:
            self.modifier = str()

    def handle_modifier(self, mod):
        """Append digits as a key modifier, clear the modifier if not
        a digit.

        Args:
            mod: potential modifier string
        """
        self.modifier += mod
        if not self.modifier.isdigit():
            self.modifier = str()

    def resize(self):
        """Handle terminal resizing"""
        # Check if screen was re-sized (True or False)
        resize = self.max_x == 0 or \
            curses.is_term_resized(self.max_y, self.max_x)
        if resize is True:
            self.recalculate_layout()
            curses.resizeterm(self.max_y, self.max_x)

    def recalculate_layout(self):
        """Recalulate the screen layout and cursor position"""
        self.max_y, self.max_x = self.scr.getmaxyx()
        self.num_columns = (1 + max(0, self.max_x - self.column_width)
                            // (self.column_width + self.column_gap))
        if (self.num_columns * self.column_width +
                self.num_columns * self.column_gap) < self.max_x - 3:
            self.vis_columns = self.num_columns + 1
        else:
            self.vis_columns = self.num_columns

        if self.x >= self.num_columns:
            # reposition x
            ox = self.win_x + self.x
            self.win_x = max(ox - self.num_columns + 1, 0)
            self.x = self.num_columns - 1
        if self.y >= self.max_y - self.header_offset:
            # reposition y
            oy = self.win_y + self.y
            self.win_y = max(oy - (self.max_y - self.header_offset) + 1, 0)
            self.y = self.max_y - self.header_offset - 1

    def display(self):
        """Refresh the current display"""
        yp = self.y + self.win_y
        xp = self.x + self.win_x
        # Print the current cursor cell in the top left corner
        self.scr.move(0, 0)
        self.scr.clrtoeol()
        s = "  {},{}  ".format(yp + 1, xp + 1)
        addstr(self.scr, s, curses.A_REVERSE)

        # Adds the current cell content after the 'current cell' display
        wc = self.max_x - len(s) - 2
        s = self.cellstr(yp, xp, wc)
        addstr(self.scr, "  " + s, curses.A_NORMAL)

        # Print a divider line
        self.scr.hline(1, 0, curses.ACS_HLINE, self.max_x)

        # Print the header if the correct offset is set
        if self.header_offset == self.header_offset_orig:
            self.scr.move(self.header_offset - 1, 0)
            self.scr.clrtoeol()
            for x in range(0, self.vis_columns):
                xc, wc = self.column_xw(x)
                s = self.hdrstr(x + self.win_x, wc)
                insstr(self.scr, self.header_offset - 1, xc, s, curses.A_BOLD)

        # Print the table data
        for y in range(0, self.max_y - self.header_offset):
            self.scr.move(y + self.header_offset, 0)
            self.scr.clrtoeol()
            for x in range(0, self.vis_columns):
                if x == self.x and y == self.y:
                    attr = curses.A_REVERSE
                else:
                    attr = curses.A_NORMAL
                xc, wc = self.column_xw(x)
                s = self.cellstr(y + self.win_y, x + self.win_x, wc)
                insstr(self.scr, y + self.header_offset, xc, s, attr)

        self.scr.refresh()

    def strpad(self, s, width):
        if '\n' in s:
            s = s.replace('\n', '\\n')
        if len(s) > width:
            s = s[0:(width - len(self.trunc_char))] \
                + self.trunc_char
        else:
            s = s.ljust(width)
        return s

    def hdrstr(self, x, width):
        "Format the content of the requested header for display"
        if len(self.header) <= x:
            s = ""
        else:
            s = self.header[x]
        return self.strpad(s, width)

    def cellstr(self, y, x, width):
        "Format the content of the requested cell for display"
        if len(self.data) <= y or len(self.data[y]) <= x:
            s = ""
        else:
            s = self.data[y][x]
        return self.strpad(s, width)


def csv_sniff(data, enc):
    """Given a list, sniff the dialect of the data and return it.

    Args:
        data - list like ["col1,col2,col3"]
        enc - python encoding value ('utf_8','latin-1','cp870', etc)
    Returns:
        csv.dialect

    """
    data = data.decode(enc)
    dialect = csv.Sniffer().sniff(data)
    return dialect.delimiter


def process_data(data, enc=None, delim=None):
    """Given a list of lists, check for the encoding and delimiter and return a
    list of CSV rows (normalized to a single length)

    """
    if enc is None:
        enc = detect_encoding(data)
    if delim is None:
        delim = csv_sniff(data[0], enc)
    csv_data = []
    if sys.version_info.major < 3:
        csv_obj = csv.reader(data, delimiter=delim.encode(enc))
        for row in csv_obj:
            row = [str(x, enc) for x in row]
            csv_data.append(row)
    else:
        data = [i.decode(enc) for i in data]
        csv_obj = csv.reader(data, delimiter=delim)
        for row in csv_obj:
            csv_data.append(row)
    return pad_data(csv_data)


def pad_data(d):
    """Pad data rows to the length of the longest row.

        Args: d - list of lists

    """
    max_len = set((len(i) for i in d))
    if len(max_len) == 1:
        return d
    else:
        max_len = max(max_len)
        return [i + [""] * (max_len - len(i)) for i in d]


def readme():
    path = os.path.dirname(os.path.realpath(__file__))
    fn = os.path.join(path, "README.rst")
    with open(fn, 'r') as f:
        return f.readlines()


def detect_encoding(data):
    """Return the default system encoding. If data is passed, try
    to decode the data with the default system encoding or from a short
    list of encoding types to test.

    Args:
        data - list of lists
    Returns:
        enc - system encoding

    """
    enc_list = ['utf-8', 'latin-1', 'iso8859-1', 'iso8859-2',
                'utf-16', 'cp720']
    code = locale.getpreferredencoding(False)
    if code.lower() not in enc_list:
        enc_list.insert(0, code.lower())
    for c in enc_list:
        try:
            for line in data:
                line.decode(c)
        except (UnicodeDecodeError, UnicodeError):
            continue
        return c
    print("Encoding not detected. Please pass encoding value manually")


def main(stdscr, *args, **kwargs):
    curses.use_default_colors()
    curses.curs_set(False)
    Viewer(stdscr, *args, **kwargs).run()


def view(data, enc=None):
    """The curses.wrapper passes stdscr as the first argument to main +
    passes to main any other arguments passed to wrapper. Initializes
    and then puts screen back in a normal state after closing or
    exceptions.

    Args:
        data: a filename OR list of lists, tuple of tuples, etc.
        enc: encoding for file/data

    """
    if sys.version_info.major < 3:
        lc_all = locale.getlocale(locale.LC_ALL)
        locale.setlocale(locale.LC_ALL, '')
    else:
        lc_all = None
    try:
        with open(data, 'rb') as f:
            data = f.readlines()
    except TypeError:
        pass
    try:
        while True:
            try:
                d = process_data(data, enc)
                curses.wrapper(main, d)
            except (QuitException, KeyboardInterrupt):
                return 0
            except ReloadException:
                continue
    finally:
        if lc_all is not None:
            locale.setlocale(locale.LC_ALL, lc_all)
