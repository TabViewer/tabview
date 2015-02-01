# -*- coding: utf-8 -*-
""" tabview.py -- View a tab-delimited file in a spreadsheet-like display.

  Scott Hansen <firecat four one five three at gmail dot com>
  Based on code contributed by A.M. Kuchling <amk at amk dot ca>

"""
from __future__ import print_function, division, unicode_literals

import csv
import _curses
import curses
import curses.ascii
import locale
import os
import re
import sys
from collections import Counter
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
    def __init__(self, width):
        self.column_width = width


class QuitException(Exception):
    pass


class TextBox:
    def __init__(self, scr, data='', title=None):
        self._running = False
        self.scr = scr
        self.data = self.orig_data = data
        self.title = title
        self.tdata = []    # transformed data
        self.hid_rows = 0  # number of hidden rows from the beginning
        self.cur_y = 0     # cursor Y coordinate
        self.cur_x = 0     # cursor X coordinate
        self.term_rows, self.term_cols = scr.getmaxyx()
        self.setup_handlers()

    def setup_handlers(self):
        self.handlers = {curses.ascii.NL:  self.close,
                         curses.ascii.CR:  self.close,
                         curses.KEY_ENTER: self.close,
                         curses.ascii.ESC: self.discard_and_close,
                         curses.KEY_UP:    self.move_up,
                         curses.KEY_DOWN:  self.move_down,
                         curses.KEY_LEFT:  self.move_left,
                         curses.KEY_RIGHT: self.move_right,
                         curses.KEY_HOME:  self.move_start,
                         curses.KEY_END:   self.move_end,
                         }

    def _calculate_layout(self):
        # transform raw data into list of lines ready to be printed
        chunk_size = self.term_cols - 2
        self.tdata = [self.data[i:i+chunk_size] 
                      for i in range(0, len(self.data), chunk_size)]
        # number of lines in the box
        self.nlines = min(len(self.tdata), int(self.term_rows/2 - 2))
        if self.nlines == 0:
            self.nlines = 1

    def run(self):
        self._running = True
        self._calculate_layout()
        self.move_end()
        while self._running:
            self.display()
            c = self.scr.getch()
            self.handle_key(c)

    def handle_key(self, inp):
        try:
            self.handlers[inp]()
        except KeyError:
            pass

    @property
    def line_end(self):
        if len(self.data) <= self.cur_y + self.hid_rows:
            return 0
        line_len = len(self.tdata[self.cur_y + self.hid_rows])
        if self.cur_y + self.hid_rows < len(self.tdata) - 1:
            line_len -= 1
        return line_len

    def move_start(self):
        self.cur_y = self.cur_x = self.hid_rows = 0

    def move_end(self):
        if len(self.tdata) == 0:
            self.move_start()
        else:
            self.hid_rows = len(self.tdata) - self.nlines
            self.cur_y = self.nlines - 1
            self.cur_x = len(self.tdata[-1])

    def discard_and_close(self):
        self.data = self.orig_data
        self.close()

    def close(self):
        self._running = False

    def move_up(self):
        if self.cur_y > 0:
            self.cur_y -= 1
        elif self.hid_rows > 0:
            self.hid_rows -= 1

    def move_right(self):
        if self.cur_x < self.line_end:
            self.cur_x += 1
        elif self.cur_y < self.nlines - 1:
            self.cur_y += 1
            self.cur_x = 0
        elif self.cur_y + self.hid_rows < len(self.tdata) - 1:
            self.hid_rows += 1
            self.cur_x = 0

    def move_down(self):
        if self.cur_y < self.nlines - 1:
            self.cur_y += 1
        elif self.cur_y + self.hid_rows + 1 == len(self.tdata) - 1:
            self.move_end()
        elif self.cur_y + self.hid_rows < len(self.tdata) - 1:
            self.hid_rows += 1

    def move_left(self):
        if self.cur_x > 0:
            self.cur_x -= 1
        elif self.cur_y > 0:
            self.cur_y -= 1
            self.cur_x = self.line_end
        elif self.hid_rows > 0:
            self.hid_rows -= 1
            self.cur_x = self.line_end

    def display(self):
        curses.curs_set(True)
        window = curses.newwin(self.nlines + 2, self.term_cols,
                               self.term_rows - self.nlines - 2, 0)
        visible_rows = self.tdata[self.hid_rows:self.hid_rows+self.nlines]
        addstr(window, 1, 1, '\n '.join(visible_rows))
        window.box()
        if self.title:
            addstr(window, 0, 2, self.title)
        window.move(self.cur_y + 1, self.cur_x + 1)
        self.scr.refresh()
        window.refresh()


class Viewer:
    """The actual CSV viewer class.

    Args:
        scr: curses window object
        data: data (list of lists). Should be normalized to equal row lengths
        start_pos: initial file position. Either a single integer for just y
            (row) position, or tuple/list (y,x)
        column_width: 'max' (max width for the column),
                      'mode' (uses arithmetic mode to compute width), or
                      int x (x characters wide). Default is 'mode'
        column_gap: gap between columns
        trunc_char: character to delineate a truncated line

    """
    def __init__(self, scr, data, start_pos, column_width='mode', column_gap=2,
                 trunc_char='…'):
        self.scr = scr
        if sys.version_info.major < 3:
            self.data = data
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
        self.num_data_columns = len(self.data[0])
        self.column_width_mode = column_width
        self._get_column_widths(column_width)
        self.column_gap = column_gap

        try:
            trunc_char.encode(sys.stdout.encoding or 'utf-8')
            self.trunc_char = trunc_char
        except (UnicodeDecodeError, UnicodeError):
            self.trunc_char = '>'

        self.x, self.y = 0, 0
        self.win_x, self.win_y = 0, 0
        self.max_y, self.max_x = 0, 0
        self.vis_columns = 0
        self.res = []
        self.res_idx = 0
        self.modifier = str()
        self.define_keys()
        self.resize()
        self.display()
        # Handle goto initial position (either (y,x), [y] or y)
        try:
            self.goto_y(start_pos[0])
        except TypeError:
            self.goto_y(start_pos)
        try:
            self.goto_x(start_pos[1])
        except (IndexError, TypeError):
            pass

    def column_xw(self, x):
        """Return the position and width of the requested column"""
        xp = sum(self.column_width[self.win_x:self.win_x + x]) \
            + x * self.column_gap
        if x < self.vis_columns:
            w = min(self.max_x, self.column_width[self.win_x + x])
        else:
            w = self.max_x - xp
        return xp, w

    def quit(self):
        raise QuitException

    def reload(self):
        raise ReloadException(self.column_width_mode)

    def down(self):
        end = len(self.data) - 1
        if self.win_y + self.y < end:
            if self.y < self.max_y - self.header_offset - 1:
                self.y = self.y + 1
            else:
                self.win_y = self.win_y + 1

    def up(self):
        if self.y == 0:
            if self.win_y > 0:
                self.win_y = self.win_y - 1
        else:
            self.y = self.y - 1

    def left(self):
        if self.x == 0:
            if self.win_x > 0:
                self.win_x = self.win_x - 1
                self.recalculate_layout()
        else:
            self.x = self.x - 1

    def right(self):
        yp = self.y + self.win_y
        if len(self.data) <= yp:
            return
        if self.x < self.vis_columns - 1:
            self.x = self.x + 1
        else:
            # Go right, unless we're on the last column of data
            # Keep going right until the entire last column is visible
            end = self.num_data_columns - 1
            width = sum(self.column_width[-(self.vis_columns):]) + \
                self.x * self.column_gap
            if self.win_x + self.x < end or width > self.max_x:
                self.win_x = self.win_x + 1
                self.recalculate_layout()

    def page_down(self):
        end = len(self.data) - 1
        if self.win_y <= end - self.max_y + self.header_offset:
            new_win_y = self.win_y + self.max_y - self.header_offset
            if new_win_y + self.y > end:
                self.y = end - new_win_y
            self.win_y = new_win_y
        else:
            self.y = end - self.win_y

    def page_up(self):
        if self.win_y == 0:
            self.y = 0
        elif self.win_y < self.max_y - self.header_offset:
            self.win_y = 0
        else:
            self.win_y = self.win_y - self.max_y + self.header_offset

    def page_right(self):
        yp = self.y + self.win_y
        if len(self.data) <= yp:
            return
        end = self.num_data_columns - 1
        if self.win_x <= end - self.vis_columns:
            new_win_x = self.win_x + self.vis_columns
            if new_win_x + self.x > end:
                self.x = end - new_win_x
            self.win_x = new_win_x
            self.recalculate_layout()
        else:
            self.x = end - self.win_x

    def page_left(self):
        if self.win_x == 0:
            self.x = 0
        elif self.win_x < self.vis_columns:
            self.win_x = 0
            self.recalculate_layout()
        else:
            self.win_x = self.win_x - self.vis_columns
            self.recalculate_layout()

    def mark(self):
        self.save_y, self.save_x = self.y + self.win_y, self.x + self.win_x

    def goto_mark(self):
        if hasattr(self, 'save_y'):
            self.goto_y(self.save_y + 1)
            self.goto_x(self.save_x + 1)

    def home(self):
        self.win_y = self.y = 0

    def goto_y(self, m):
        if m >= len(self.data):
            m = len(self.data)
        if m > 0:
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

    def goto_row(self):
        m = int(self.modifier) if len(self.modifier) else len(self.data)
        self.goto_y(m)
        self.modifier = str()

    def goto_x(self, m):
        if m >= len(self.data[self.y + self.win_y]):
            m = len(self.data[self.y + self.win_y])
        if m > 0:
            if self.win_x < m <= self.win_x + self.vis_columns:
                # same screen, change x value appropriately.
                self.x = m - 1 - self.win_x
            elif m <= self.win_x:
                # going back
                self.x = 0
                self.win_x = m - 1
                self.recalculate_layout()
            else:
                # going forward
                self.win_x = m - self.vis_columns
                self.recalculate_layout()
                self.x = self.vis_columns - 1

    def goto_col(self):
        m = int(self.modifier) if len(self.modifier) else 1
        self.goto_x(m)
        self.modifier = str()

    def line_home(self):
        self.win_x = self.x = 0
        self.recalculate_layout()

    def line_end(self):
        end = len(self.data[self.y + self.win_y])
        self.goto_x(end)

    def show_cell(self):
        "Display current cell in a pop-up window"
        yp = self.y + self.win_y
        xp = self.x + self.win_x
        try:
            win = TextBox(self.scr, self.data[yp][xp])
            win.run()
        except IndexError:
            pass

    def search(self):
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
            self.recalculate_layout()

    def next_result(self):
        if self.res:
            if self.res_idx < len(self.res) - 1:
                self.res_idx += 1
            else:
                self.res_idx = 0
            self.x = self.y = 0
            self.win_y, self.win_x = self.res[self.res_idx]
            self.recalculate_layout()

    def prev_result(self):
        if self.res:
            if self.res_idx > 0:
                self.res_idx -= 1
            else:
                self.res_idx = len(self.res) - 1
            self.x = self.y = 0
            self.win_y, self.win_x = self.res[self.res_idx]
            self.recalculate_layout()

    def help(self):
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

    def toggle_header(self):
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
                self.up()
                self.down()
                self.y = self.y - 1

    def column_gap_down(self):
        self.column_gap = max(0, self.column_gap - 1)
        self.recalculate_layout()

    def column_gap_up(self):
        self.column_gap += 1
        self.recalculate_layout()

    def column_width_down(self):
        self.column_width = [max(1, self.column_width[i] -
                                 max(1, int(self.column_width[i] * 0.2)))
                             for i in range(0, self.num_data_columns)]
        self.recalculate_layout()

    def column_width_up(self):
        self.column_width = [max(1, self.column_width[i] +
                                 max(1, int(self.column_width[i] * 0.2)))
                             for i in range(0, self.num_data_columns)]
        self.recalculate_layout()

    def sort_by_column(self):
        xp = self.x + self.win_x
        self.data = sorted(self.data, key=itemgetter(xp))

    def sort_by_column_reverse(self):
        xp = self.x + self.win_x
        self.data = sorted(self.data, key=itemgetter(xp), reverse=True)

    def sort_by_column_natural(self):
        xp = self.x + self.win_x
        self.data = self.sorted_nicely(self.data, itemgetter(xp))

    def sort_by_column_natural_reverse(self):
        xp = self.x + self.win_x
        self.data = self.sorted_nicely(self.data, itemgetter(xp), rev=True)

    def sorted_nicely(self, ls, key, rev=False):
        """ Sort the given iterable in the way that humans expect.

        From StackOverflow: http://goo.gl/nGBUrQ

        """
        def convert(text):
            return int(text) if text.isdigit() else text

        def alphanum_key(item):
            return [convert(c) for c in re.split('([0-9]+)', key(item))]

        return sorted(ls, key=alphanum_key, reverse=rev)

    def toggle_column_width(self):
        """Reload file and toggle column width mode between 'mode' and 'max'
        or set fixed column width mode if self.modifier is set.

        """
        try:
            self.column_width_mode = min(int(self.modifier), self.max_x)
        except ValueError:
            if self.column_width_mode == 'mode':
                self.column_width_mode = 'max'
            else:
                self.column_width_mode = 'mode'
        raise ReloadException(self.column_width_mode)

    def yank_cell(self):
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
            except IOError:
                pass

    def define_keys(self):
        self.keys = {'j':   self.down,
                     'k':   self.up,
                     'h':   self.left,
                     'l':   self.right,
                     'J':   self.page_down,
                     'K':   self.page_up,
                     'm':   self.mark,
                     "'":   self.goto_mark,
                     'L':   self.page_right,
                     'H':   self.page_left,
                     'q':   self.quit,
                     'Q':   self.quit,
                     '$':   self.line_end,
                     '^':   self.line_home,
                     '0':   self.line_home,
                     'g':   self.home,
                     'G':   self.goto_row,
                     '|':   self.goto_col,
                     '\n':  self.show_cell,
                     '/':   self.search,
                     'n':   self.next_result,
                     'p':   self.prev_result,
                     't':   self.toggle_header,
                     '-':   self.column_gap_down,
                     '+':   self.column_gap_up,
                     '<':   self.column_width_down,
                     '>':   self.column_width_up,
                     'a':   self.sort_by_column_natural,
                     'A':   self.sort_by_column_natural_reverse,
                     's':   self.sort_by_column,
                     'S':   self.sort_by_column_reverse,
                     'y':   self.yank_cell,
                     'r':   self.reload,
                     'c':   self.toggle_column_width,
                     '?':   self.help,
                     curses.KEY_F1:     self.help,
                     curses.KEY_UP:     self.up,
                     curses.KEY_DOWN:   self.down,
                     curses.KEY_LEFT:   self.left,
                     curses.KEY_RIGHT:  self.right,
                     curses.KEY_HOME:   self.line_home,
                     curses.KEY_END:    self.line_end,
                     curses.KEY_PPAGE:  self.page_up,
                     curses.KEY_NPAGE:  self.page_down,
                     curses.KEY_IC:     self.mark,
                     curses.KEY_DC:     self.goto_mark,
                     curses.KEY_ENTER:  self.show_cell,
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
        width = nb_cols = 0
        while self.win_x + nb_cols < self.num_data_columns \
                and width + self.column_width[self.win_x + nb_cols] \
                + self.column_gap < self.max_x:
            width += (self.column_width[self.win_x + nb_cols]
                      + self.column_gap)
            nb_cols += 1

        if self.win_x + nb_cols < self.num_data_columns:
            nb_cols += 1
        self.vis_columns = nb_cols

        if self.x >= self.vis_columns:
            # reposition x
            self.x = self.vis_columns - 1
        if self.y >= self.max_y - self.header_offset:
            # reposition y
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

    def _get_column_widths(self, width):
        """Compute column width array

        Args: width - 'max', 'mode', or an integer value
        Returns: [len of col 1, len of col 2, ....]

        """
        if width == 'max':
            self.column_width = self._get_column_widths_max(self.data)
        elif width == 'mode':
            self.column_width = self._get_column_widths_mode(self.data)
        else:
            try:
                width = int(width)
            except (TypeError, ValueError):
                width = 25
            self.column_width = [width for i in
                                 range(0, self.num_data_columns)]

    def _mode_len(self, x):
        """Compute arithmetic mode (most common value) of the length of each item
        in an iterator.

            Args: x - iterator (list, tuple, etc)
            Returns: mode - int. Minimum column width of 3

        """
        if len(x) > 500:  # 500 is just arbitrary choice for "long"
            # Check every 10th row for long columns
            lens = [len(i) for i in x[::10]]
        else:
            lens = [len(i) for i in x]
        m = Counter(lens).most_common()
        # If there are a lot of empty columns, use the 2nd most common length
        # besides 0
        try:
            mode = m[0][0] or m[1][0]
        except IndexError:
            mode = 0
        max_len = max(lens) or 1
        if (max(3, (abs(mode - max_len))/max_len)) > 0.1:
            return max(3, mode)
        else:
            return max(3, max_len)

    def _get_column_widths_mode(self, d):
        """Given a list of lists, return a list of the variable column width
        for each column using the arithmetic mode.

        Args: d - list of lists with x columns
        Returns: list of ints [len_1, len_2...len_x]

        Ignore first row (assume header row)

        """
        d = zip(*d[1:])
        return [self._mode_len(i) for i in d]

    def _get_column_widths_max(self, d):
        """Given a list of lists, return a list of the variable column width
        for each column using the max length. Minimum column width of 3.

        Args: d - list of lists with x columns
        Returns: list of ints [len_1, len_2...len_x]

        """
        d = zip(*d)
        return [max(3, min(250, max(set(len(j) for j in i)))) for i in d]


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
    with open(fn, 'rb') as f:
        h = f.readlines()
        return [i.decode('utf-8') for i in h]


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
    try:
        curses.curs_set(False)
    except (AttributeError, _curses.error):
        pass
    Viewer(stdscr, *args, **kwargs).run()


def view(data, enc=None, start_pos=(0, 0), column_width='mode'):
    """The curses.wrapper passes stdscr as the first argument to main +
    passes to main any other arguments passed to wrapper. Initializes
    and then puts screen back in a normal state after closing or
    exceptions.

    Args:
        data: a filename OR list of lists, tuple of tuples, etc.
        enc: encoding for file/data
        start_pos: initial file position. Either a single integer for just y
            (row) position, or tuple/list (y,x)
        column_width: 'max' (max width for the column),
                      'mode' (uses arithmetic mode to compute width), or
                      int x (x characters wide). Default is 'mode'

    """
    # reduce the delay after pressing ESC
    try:
        os.environ['ESCDELAY']
    except KeyError:
        os.environ['ESCDELAY'] = '25'

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
                curses.wrapper(main, d, start_pos, column_width)
            except (QuitException, KeyboardInterrupt):
                return 0
            except ReloadException as e:
                column_width = e.column_width
    finally:
        if lc_all is not None:
            locale.setlocale(locale.LC_ALL, lc_all)
