""" tabview.py -- View a tab-delimited file in a spreadsheet-like display.

  Scott Hansen <firecat four one five three at gmail dot com>
  Based on code contributed by A.M. Kuchling <amk at amk dot ca>

"""
import codecs
import csv
import curses
import curses.ascii
import io
import locale
import math
import os
import re
import string
import sys
import unicodedata
from collections import Counter
from curses.textpad import Textbox
from importlib import resources
from operator import itemgetter
from subprocess import DEVNULL, CalledProcessError, run
from textwrap import wrap
from urllib.parse import urlparse
from urllib.request import url2pathname

# Minimum terminal size for the main view
MIN_ROWS, MIN_COLS = 6, 20

# Control characters can't be drawn by curses (NUL raises ValueError, tabs and
# others move the cursor), so display them as Python-style escapes.
CONTROL_ESCAPES = {c: repr(chr(c))[1:-1]
                   for c in (*range(0x20), *range(0x7f, 0xa0))}
# Same, but keep newlines for multi-line pop-ups
CONTROL_ESCAPES_ML = {c: v for c, v in CONTROL_ESCAPES.items()
                      if c != ord('\n')}


def wrap_cells(text, width, indent=' '):
    """Wrap text to lines of at most width terminal cells, counting double
    width characters as two. Continuation lines are indented with indent.

    """
    width = max(width, len(indent) + 2)
    lines = []
    for line in wrap(text, width, subsequent_indent=indent) or ['']:
        # textwrap counts characters, so split lines with double width
        # characters (which often have no spaces to break at) further
        while sum(char_width(c) for c in line) > width:
            cut = used = 0
            while used + char_width(line[cut]) <= width:
                used += char_width(line[cut])
                cut += 1
            lines.append(line[:cut])
            line = indent + line[cut:]
        lines.append(line)
    return lines


def KEY_CTRL(key):
    return curses.ascii.ctrl(key)


def char_width(c):
    """Number of terminal cells used by character c"""
    return 2 if unicodedata.east_asian_width(c) in ('W', 'F') else 1


class ReloadException(Exception):
    def __init__(self, start_pos, column_width, column_gap, column_widths,
                 search_str):
        self.start_pos = start_pos
        self.column_width_mode = column_width
        self.column_gap = column_gap
        self.column_widths = column_widths
        self.search_str = search_str


class QuitException(Exception):
    pass


class Viewer:
    """The actual CSV viewer class.

    Args:
        args: other positional arguments. See view() for descriptions.
            stdscr, data
        kwargs: dict of other keyword arguments.
            start_pos, column_width, column_gap, trunc_char, column_widths,
            search_str, double_width

    """
    def __init__(self, *args, **kwargs):
        self.scr = args[0]
        self.data = [[str(j) for j in i] for i in args[1]]
        self.info = kwargs.get('info')
        self.header_offset_orig = 3
        self.header = self.data[0]
        if len(self.data) > 1 and \
                not any(self._is_num(cell) for cell in self.header):
            del self.data[0]
            self.header_offset = self.header_offset_orig
        else:
            # Don't make one line file a header row
            # If any of the header line cells are all digits, assume that the
            # first line is NOT a header
            self.header_offset = self.header_offset_orig - 1
        self.num_data_columns = len(self.data[0])
        self._init_double_width(kwargs.get('double_width'))
        self.column_width_mode = kwargs.get('column_width')
        self.column_gap = kwargs.get('column_gap')
        self._init_column_widths(kwargs.get('column_width'),
                                 kwargs.get('column_widths'))
        try:
            kwargs.get('trunc_char').encode(sys.stdout.encoding or 'utf-8')
            self.trunc_char = kwargs.get('trunc_char')
        except (UnicodeDecodeError, UnicodeError):
            self.trunc_char = '>'

        self.x, self.y = 0, 0
        self.win_x, self.win_y = 0, 0
        self.max_y, self.max_x = 0, 0
        self.num_columns = 0
        self.vis_columns = 0
        self.init_search = self.search_str = kwargs.get('search_str')
        self._search_win_open = 0
        self.modifier = ''
        self.define_keys()
        self.resize()
        self.display()
        # Handle goto initial position (either (y,x), [y] or y)
        try:
            self.goto_y(kwargs.get('start_pos')[0])
        except TypeError:
            self.goto_y(kwargs.get('start_pos'))
        try:
            self.goto_x(kwargs.get('start_pos')[1])
        except (IndexError, TypeError):
            pass

    def _is_num(self, cell):
        try:
            float(cell)
            return True
        except ValueError:
            return False

    def _init_double_width(self, dw):
        """Initialize self._cell_len to determine if double width characters
        are taken into account when calculating cell widths.

        """
        self.double_width = dw
        # Enable double with character processing for small files
        if self.double_width is False:
            self.double_width = len(self.data) * self.num_data_columns < 65000
        if self.double_width is True:
            self._cell_len = self.__cell_len_dw
        else:
            self._cell_len = len

    def _init_column_widths(self, cw, cws):
        """Initialize column widths

        Args: - cw: column_width mode
                cws: list of column widths

        """
        if cws is None or len(self.data[0]) != len(cws):
            self._get_column_widths(cw)
        else:
            self.column_width = cws

    def column_xw(self, x):
        """Return the position and width of the requested column"""
        xp = sum(self.column_width[self.win_x:self.win_x + x]) \
            + x * self.column_gap
        w = max(0, min(self.max_x - xp, self.column_width[self.win_x + x]))
        return xp, w

    def quit(self):
        raise QuitException

    def reload(self):
        start_pos = (self.y + self.win_y + 1, self.x + self.win_x + 1)
        raise ReloadException(start_pos, self.column_width_mode,
                              self.column_gap, self.column_width,
                              self.search_str)

    def consume_modifier(self, default=1):
        m = int(self.modifier) if len(self.modifier) else default
        self.modifier = ''
        return m

    def down(self):
        m = self.consume_modifier()
        yp = self.y + self.win_y
        self.goto_y(yp + 1 + m)

    def up(self):
        m = self.consume_modifier()
        yp = self.y + self.win_y
        self.goto_y(yp + 1 - m)

    def left(self):
        m = self.consume_modifier()
        xp = self.x + self.win_x
        self.goto_x(xp + 1 - m)

    def right(self):
        m = self.consume_modifier()
        xp = self.x + self.win_x
        self.goto_x(xp + 1 + m)

    def page_down(self):
        m = self.consume_modifier()
        row_shift = (self.max_y - self.header_offset) * m
        end = len(self.data) - 1
        if self.win_y <= end - row_shift:
            new_win_y = self.win_y + row_shift
            if new_win_y + self.y > end:
                self.y = end - new_win_y
            self.win_y = new_win_y
        else:
            self.y = end - self.win_y

    def page_up(self):
        m = self.consume_modifier()
        row_shift = (self.max_y - self.header_offset) * m
        if self.win_y == 0:
            self.y = 0
        elif self.win_y < row_shift:
            self.win_y = 0
        else:
            self.win_y = self.win_y - row_shift

    def page_right(self):
        for _ in range(self.consume_modifier()):
            end = self.num_data_columns - 1
            if self.win_x <= end - self.num_columns:
                cols = self.num_columns_fwd(self.win_x + self.x)
                new_win_x = self.win_x + cols
                if new_win_x + self.x > end:
                    self.x = end - new_win_x
                self.win_x = new_win_x
                self.recalculate_layout()
            else:
                self.x = end - self.win_x
                break

    def page_left(self):
        for _ in range(self.consume_modifier()):
            if self.win_x == 0:
                self.x = 0
                break
            cols = self.num_columns_rev(self.win_x + self.x)
            if self.win_x < cols:
                self.win_x = 0
                self.recalculate_layout()
            else:
                self.win_x = self.win_x - cols
                self.recalculate_layout()

    def mark(self):
        self.save_y, self.save_x = self.y + self.win_y, self.x + self.win_x

    def goto_mark(self):
        if hasattr(self, 'save_y'):
            self.goto_yx(self.save_y + 1, self.save_x + 1)

    def home(self):
        self.goto_y(1)

    def goto_y(self, y):
        y = max(min(len(self.data), y), 1)
        if self.win_y < y <= self.win_y + \
                (self.max_y - self.header_offset - self._search_win_open):
            # same screen, change y appropriately.
            self.y = y - 1 - self.win_y
        elif y <= self.win_y:
            # going back
            self.y = 0
            self.win_y = y - 1
        else:
            # going forward
            self.win_y = y - (self.max_y - self.header_offset -
                              self._search_win_open)
            self.y = (self.max_y - self.header_offset -
                      self._search_win_open) - 1

    def goto_row(self):
        m = self.consume_modifier(len(self.data))
        self.goto_y(m)

    def goto_x(self, x):
        x = max(min(self.num_data_columns, x), 1)
        if self.win_x < x <= self.win_x + self.num_columns:
            # same screen, change x value appropriately.
            self.x = x - 1 - self.win_x
        elif x <= self.win_x:
            # going back
            self.x = 0
            self.win_x = x - 1
            self.recalculate_layout()
        else:
            # going forward
            cols = self.num_columns_rev(x - 1)
            self.win_x = x - cols
            self.x = cols - 1
            self.recalculate_layout()

    def goto_col(self):
        m = self.consume_modifier()
        self.goto_x(m)

    def goto_yx(self, y, x):
        self.goto_y(y)
        self.goto_x(x)

    def line_home(self):
        self.goto_x(1)

    def line_end(self):
        end = len(self.data[self.y + self.win_y])
        self.goto_x(end)

    def show_cell(self):
        "Display current cell in a pop-up window"
        yp = self.y + self.win_y
        xp = self.x + self.win_x
        s = self.data[yp][xp]
        if not s:
            # Only display pop-up if cells have contents
            return
        TextBox(self.scr, data="\n" + s,
                title=self.location_string(yp, xp))()
        self.resize()

    def show_info(self):
        """Display data information in a pop-up window

        """
        fn = self.info
        yp = self.y + self.win_y
        xp = self.x + self.win_x
        location = self.location_string(yp, xp)

        def sizeof_fmt(num, suffix='B'):
            for unit in ['', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi']:
                if abs(num) < 1024.0:
                    return f"{num:3.1f}{unit}{suffix}"
                num /= 1024.0
            return f"{num:.1f}Yi{suffix}"
        size = sizeof_fmt(sys.getsizeof(self.data))
        rows_cols = str((len(self.data), self.num_data_columns))
        info = [("Filename/Data Info:", fn),
                ("Current Location:", location),
                ("Total Rows/Columns:", rows_cols),
                ("Data Size:", size)]
        display = "\n\n".join(f"{i:<20}{j}" for i, j in info)
        TextBox(self.scr, data=display)()
        self.resize()

    def _search_validator(self, ch):
        """Fix Enter and backspace for textbox.

        Used as an aux function for the textpad.edit method

        """
        if ch == curses.ascii.NL:  # Enter
            return curses.ascii.BEL
        elif ch == 127:  # Backspace
            self.search_str = self.textpad.gather().strip().lower()[:-1]
            return 8
        else:
            if 0 < ch < 256:
                c = chr(ch)
                if c in string.printable:
                    res = self.textpad.gather().strip().lower()
                    self.search_str = res + chr(ch)
                    self.search_results(look_in_cur=True)
                    self.display()
            return ch

    def search(self):
        """Open search window, get input and set the search string."""
        if self.max_y < MIN_ROWS or self.max_x < MIN_COLS:
            return
        scr2 = curses.newwin(3, self.max_x, self.max_y - 3, 0)
        scr3 = scr2.derwin(1, self.max_x - 12, 1, 9)
        scr2.box()
        scr2.move(1, 1)
        scr2.addstr("Search: ")
        scr2.refresh()
        curses.curs_set(1)
        self._search_win_open = 3
        self.textpad = Textbox(scr3, insert_mode=True)
        self.search_str = self.textpad.edit(self._search_validator)
        self.search_str = self.search_str.lower().strip()
        try:
            curses.curs_set(0)
        except curses.error:
            pass
        if self.search_str:
            self.init_search = None
        self._search_win_open = 0

    def search_results(self, rev=False, look_in_cur=False):
        """Given self.search_str or self.init_search, find next result after
        current position and reposition the cursor there.

        Args: rev - True/False search backward if true
              look_in_cur - True/False start search in current cell

        """
        if not self.search_str and not self.init_search:
            return
        self.search_str = self.search_str or self.init_search
        needle = self.search_str.lower()
        yp, xp = self.y + self.win_y, self.x + self.win_x
        for y, x in self._cell_positions(yp, xp, rev, look_in_cur):
            row = self.data[y]
            if x < len(row) and needle in row[x].lower():
                self.goto_yx(y + 1, x + 1)
                return

    def search_results_prev(self, rev=False, look_in_cur=False):
        """Search backwards"""
        self.search_results(rev=True, look_in_cur=look_in_cur)

    def _cell_positions(self, yp, xp, rev=False, look_in_cur=False):
        """Yield every (y, x) cell position once, in reading order (or
        reverse), starting after (or at, with look_in_cur) cell yp, xp and
        wrapping around. Without look_in_cur, the current cell comes last.

        """
        cols = self.num_data_columns
        total = len(self.data) * cols
        start = yp * cols + xp
        step = -1 if rev else 1
        first = 0 if look_in_cur else 1
        for i in range(first, first + total):
            yield divmod((start + step * i) % total, cols)

    def help(self):
        TextBox(self.scr, data=help_text(), title="Keybindings")()
        self.resize()

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

    def column_width_all_down(self):
        self.column_width = [max(1, self.column_width[i] -
                                 max(1, int(self.column_width[i] * 0.2)))
                             for i in range(0, self.num_data_columns)]
        self.recalculate_layout()

    def column_width_all_up(self):
        self.column_width = [max(1, self.column_width[i] +
                                 max(1, int(self.column_width[i] * 0.2)))
                             for i in range(0, self.num_data_columns)]
        self.recalculate_layout()

    def column_width_down(self):
        xp = self.x + self.win_x
        self.column_width[xp] = max(1, self.column_width[xp] - max(
            1, int(self.column_width[xp] * 0.2)))
        self.recalculate_layout()

    def column_width_up(self):
        xp = self.x + self.win_x
        self.column_width[xp] += max(1, int(self.column_width[xp] * 0.2))
        self.recalculate_layout()

    def sort_by_column_numeric(self):
        xp = self.x + self.win_x
        self.data = sorted(self.data, key=lambda x:
                           self.float_string_key(itemgetter(xp)(x)))

    def sort_by_column_numeric_reverse(self):
        xp = self.x + self.win_x
        self.data = sorted(self.data, key=lambda x:
                           self.float_string_key(itemgetter(xp)(x)),
                           reverse=True)

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
        def alphanum_key(item):
            # Odd items are the ASCII digit runs. str.isdigit() would also
            # accept characters like '²' that int() rejects.
            return [int(c) if i % 2 else c
                    for i, c in enumerate(re.split('([0-9]+)', key(item)))]

        return sorted(ls, key=alphanum_key, reverse=rev)

    def float_string_key(self, value):
        """Sort by data type first and by floating point value second,
        if possible. NaN sorts after the other numbers, since it doesn't
        compare. Used for numeric sorting

        """
        try:
            value = float(value)
        except ValueError:
            return 'str', False, value
        if math.isnan(value):
            return 'float', True, 0.0
        return 'float', False, value

    def toggle_column_width(self):
        """Toggle column width mode between 'mode' and 'max' or set fixed
        column width mode if self.modifier is set.

        """
        try:
            self.column_width_mode = max(1, min(int(self.modifier),
                                                self.max_x))
            self.modifier = ''
        except ValueError:
            if self.column_width_mode == 'mode':
                self.column_width_mode = 'max'
            else:
                self.column_width_mode = 'mode'
        self._get_column_widths(self.column_width_mode)
        self.recalculate_layout()

    def set_current_column_width(self):
        xs = self.win_x + self.x
        if len(self.modifier):
            width = max(1, int(self.modifier))
            self.modifier = ''
        else:
            width = 0
            for y in range(0, len(self.data)):
                width = max(width, self._cell_len(self.data[y][xs]))
            width = min(250, width)
        self.column_width[xs] = width
        self.recalculate_layout()

    def yank_cell(self):
        yp = self.y + self.win_y
        xp = self.x + self.win_x
        s = self.data[yp][xp]
        # Use the first clipboard tool that works
        for cmd in clipboard_commands():
            try:
                run(cmd, input=s, text=True, check=True,
                    stdout=DEVNULL, stderr=DEVNULL)
                return
            except (OSError, CalledProcessError):
                continue

    def define_keys(self):
        self.keys = {'j': self.down,
                     'k': self.up,
                     'h': self.left,
                     'l': self.right,
                     'J': self.page_down,
                     'K': self.page_up,
                     'm': self.mark,
                     "'": self.goto_mark,
                     'L': self.page_right,
                     'H': self.page_left,
                     'q': self.quit,
                     'Q': self.quit,
                     '$': self.line_end,
                     '^': self.line_home,
                     'g': self.home,
                     'G': self.goto_row,
                     '|': self.goto_col,
                     '\n': self.show_cell,
                     '/': self.search,
                     'n': self.search_results,
                     'p': self.search_results_prev,
                     't': self.toggle_header,
                     '-': self.column_gap_down,
                     '+': self.column_gap_up,
                     '<': self.column_width_all_down,
                     '>': self.column_width_all_up,
                     ',': self.column_width_down,
                     '.': self.column_width_up,
                     'a': self.sort_by_column_natural,
                     'A': self.sort_by_column_natural_reverse,
                     '#': self.sort_by_column_numeric,
                     '@': self.sort_by_column_numeric_reverse,
                     's': self.sort_by_column,
                     'S': self.sort_by_column_reverse,
                     'y': self.yank_cell,
                     'r': self.reload,
                     'c': self.toggle_column_width,
                     'C': self.set_current_column_width,
                     ']': self.skip_to_row_change,
                     '[': self.skip_to_row_change_reverse,
                     '}': self.skip_to_col_change,
                     '{': self.skip_to_col_change_reverse,
                     '?': self.help,
                     curses.KEY_F1: self.help,
                     curses.KEY_UP: self.up,
                     curses.KEY_DOWN: self.down,
                     curses.KEY_LEFT: self.left,
                     curses.KEY_RIGHT: self.right,
                     curses.KEY_HOME: self.line_home,
                     curses.KEY_END: self.line_end,
                     curses.KEY_PPAGE: self.page_up,
                     curses.KEY_NPAGE: self.page_down,
                     curses.KEY_IC: self.mark,
                     curses.KEY_DC: self.goto_mark,
                     curses.KEY_ENTER: self.show_cell,
                     KEY_CTRL('a'): self.line_home,
                     KEY_CTRL('e'): self.line_end,
                     KEY_CTRL('l'): self.scr.redrawwin,
                     KEY_CTRL('g'): self.show_info,
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
            self.modifier = ''

    def handle_modifier(self, mod):
        """Append digits as a key modifier, clear the modifier if not
        a digit.

        Args:
            mod: potential modifier string
        """
        self.modifier += mod
        if not self.modifier.isdigit():
            self.modifier = ''

    def resize(self):
        """Handle terminal resizing"""
        # Check if screen was re-sized (True or False)
        resize = self.max_x == 0 or \
            curses.is_term_resized(self.max_y, self.max_x)
        if resize is True:
            self.recalculate_layout()
            curses.resizeterm(self.max_y, self.max_x)

    def num_columns_fwd(self, x):
        """Count number of fully visible columns starting at x,
        going forward.

        """
        width = cols = 0
        while (x + cols) < self.num_data_columns \
                and width + self.column_width[x + cols] <= self.max_x:
            width += self.column_width[x + cols] + self.column_gap
            cols += 1
        return max(1, cols)

    def num_columns_rev(self, x):
        """Count number of fully visible columns starting at x,
        going reverse.

        """
        width = cols = 0
        while x - cols >= 0 \
                and width + self.column_width[x - cols] <= self.max_x:
            width += self.column_width[x - cols] + self.column_gap
            cols += 1
        return max(1, cols)

    def recalculate_layout(self):
        """Recalulate the screen layout and cursor position"""
        self.max_y, self.max_x = self.scr.getmaxyx()
        self.vis_columns = self.num_columns = self.num_columns_fwd(self.win_x)
        if self.win_x + self.num_columns < self.num_data_columns:
            xc, wc = self.column_xw(self.num_columns)
            if wc > len(self.trunc_char):
                self.vis_columns += 1
        if self.x >= self.num_columns:
            self.goto_x(self.win_x + self.x + 1)
        if self.y >= self.max_y - self.header_offset:
            self.goto_y(self.win_y + self.y + 1)

    def location_string(self, yp, xp):
        """Create (y,x) col_label string. Max 30% of screen width. (y,x) is
        padded to the max possible length it could be. Label string gets
        trunc_char appended if it's longer than the allowed width.

        """
        yx_str = "({},{}) "
        label_str = "{},{}"
        max_y = str(len(self.data))
        max_x = str(len(self.data[0]))
        max_yx = yx_str.format(max_y, max_x)
        max_label = label_str.format('-', max(self.header, key=len))
        if self.header_offset != self.header_offset_orig:
            # Hide column labels if header row disabled
            label = ""
            max_width = min(int(self.max_x * .3), len(max_yx))
        else:
            label = label_str.format(
                '-', self.header[xp].translate(CONTROL_ESCAPES))
            max_width = min(int(self.max_x * .3), len(max_yx + max_label))
        yx = yx_str.format(yp + 1, xp + 1)
        pad = " " * (max_width - len(yx) - len(label))
        loc = f"{yx}{label}{pad}"
        if len(loc) > max_width:
            loc = loc[:max_width - 1] + self.trunc_char
        return loc

    def display(self):
        """Refresh the current display"""
        if self.max_y < MIN_ROWS or self.max_x < MIN_COLS:
            self.scr.erase()
            try:
                self.scr.addstr(0, 0, "Terminal too small"[:self.max_x - 1])
            except curses.error:
                pass
            self.scr.refresh()
            return
        yp = self.y + self.win_y
        xp = self.x + self.win_x

        # Print the current cursor cell in the top left corner
        self.scr.move(0, 0)
        self.scr.clrtoeol()
        info = f" {self.location_string(yp, xp)}"
        self.scr.addstr(info, curses.A_REVERSE)

        # Adds the current cell content after the 'current cell' display
        wc = self.max_x - len(info) - 2
        s = self.cellstr(yp, xp, wc)
        self.scr.addstr("  " + s, curses.A_NORMAL)

        # Print a divider line
        self.scr.hline(1, 0, curses.ACS_HLINE, self.max_x)

        # Print the header if the correct offset is set
        if self.header_offset == self.header_offset_orig:
            self.scr.move(self.header_offset - 1, 0)
            self.scr.clrtoeol()
            for x in range(0, self.vis_columns):
                xc, wc = self.column_xw(x)
                if wc < 1:
                    continue
                s = self.hdrstr(x + self.win_x, wc)
                self.scr.addstr(self.header_offset - 1, xc, s, curses.A_BOLD)

        # Print the table data
        for y in range(0, self.max_y - self.header_offset -
                       self._search_win_open):
            yc = y + self.header_offset
            self.scr.move(yc, 0)
            self.scr.clrtoeol()
            for x in range(0, self.vis_columns):
                if x == self.x and y == self.y:
                    attr = curses.A_REVERSE
                else:
                    attr = curses.A_NORMAL
                xc, wc = self.column_xw(x)
                if wc < 1:
                    continue
                s = self.cellstr(y + self.win_y, x + self.win_x, wc)
                if yc == self.max_y - 1 and x == self.vis_columns - 1:
                    # Prevents a curses error when filling in the bottom right
                    # character
                    self.scr.insstr(yc, xc, s, attr)
                else:
                    self.scr.addstr(yc, xc, s, attr)

        self.scr.refresh()

    def strpad(self, s, width):
        if width < 1:
            return ''
        s = s.translate(CONTROL_ESCAPES)

        # take into account double-width characters
        buf = ''
        buf_width = 0
        for c in s:
            w = char_width(c)
            if buf_width + w > width:
                break
            buf_width += w
            buf += c

        if len(buf) < len(s):
            # truncation occurred
            while buf_width + len(self.trunc_char) > width:
                w = char_width(buf[-1])
                buf = buf[0:-1]
                buf_width -= w
            buf += ' ' * (width - buf_width - len(self.trunc_char))
            buf += self.trunc_char
        elif buf_width < width:
            # padding required
            buf += ' ' * (width - buf_width)

        return buf

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
                width = max(1, int(width))
            except (TypeError, ValueError):
                width = 25
            self.column_width = [width for i in
                                 range(0, self.num_data_columns)]

    @staticmethod
    def __cell_len_dw(s):
        """Return the number of character cells a string will take
        (double-width aware). Defined as self._cell_len in __init__

        """
        return sum(char_width(c) for c in s)

    def _mode_len(self, x):
        """Compute arithmetic mode (most common value) of the length of each item
        in an iterator.

            Args: x - iterator (list, tuple, etc)
            Returns: mode - int.

        """
        lens = [self._cell_len(i) for i in x]
        m = Counter(lens).most_common()
        # If there are a lot of empty columns, use the 2nd most common length
        # besides 0
        try:
            mode = m[0][0] or m[1][0]
        except IndexError:
            mode = 0
        max_len = max(lens) or 1
        diff = abs(mode - max_len)
        if diff > (self.column_gap * 2) and diff / max_len > 0.1:
            return max(max(1, self.column_gap), mode)
        else:
            return max(max(1, self.column_gap), max_len)

    def _get_column_widths_mode(self, d):
        """Given a list of lists, return a list of the variable column width
        for each column using the arithmetic mode.

        Args: d - list of lists with x columns
        Returns: list of ints [len_1, len_2...len_x]

        """
        # Rows are padded to the same length by process_data
        d = zip(*d, strict=True)
        return [self._mode_len(i) for i in d]

    def _get_column_widths_max(self, d):
        """Given a list of lists, return a list of the variable column width
        for each column using the max length.

        Args: d - list of lists with x columns
        Returns: list of ints [len_1, len_2...len_x]

        """
        # Rows are padded to the same length by process_data
        d = zip(*d, strict=True)
        return [max(1, min(250, max(self._cell_len(j) for j in i)))
                for i in d]

    def _skip_to_value_change(self, x_inc, y_inc):
        m = self.consume_modifier()
        for _ in range(m):
            x = self.win_x + self.x
            y = self.win_y + self.y
            v = self.data[y][x]
            y += y_inc
            x += x_inc
            while y >= 0 and y < len(self.data) \
                    and x >= 0 and x < self.num_data_columns \
                    and self.data[y][x] == v:
                y += y_inc
                x += x_inc
            self.goto_yx(y + 1, x + 1)

    def skip_to_row_change(self):
        self._skip_to_value_change(0, 1)

    def skip_to_row_change_reverse(self):
        self._skip_to_value_change(0, -1)

    def skip_to_col_change(self):
        self._skip_to_value_change(1, 0)

    def skip_to_col_change_reverse(self):
        self._skip_to_value_change(-1, 0)


class TextBox:
    """Display a scrollable text box in the bottom half of the screen.

    """
    def __init__(self, scr, data='', title=""):
        self._running = False
        self.scr = scr
        self.data = data.translate(CONTROL_ESCAPES_ML)
        self.title = title.translate(CONTROL_ESCAPES)
        self.tdata = []    # transformed data
        self.hid_rows = 0  # number of hidden rows from the beginning
        self.setup_handlers()

    def __call__(self):
        self.run()

    def setup_handlers(self):
        self.handlers = {'\n': self.close,
                         curses.KEY_ENTER: self.close,
                         'q': self.close,
                         curses.KEY_RESIZE: self.close,
                         curses.KEY_DOWN: self.scroll_down,
                         'j': self.scroll_down,
                         curses.KEY_UP: self.scroll_up,
                         'k': self.scroll_up,
                         }

    def _calculate_layout(self):
        """Setup popup window and format data. """
        self.scr.touchwin()
        self.term_rows, self.term_cols = self.scr.getmaxyx()
        # The window is the bottom half of the screen
        self.box_height = self.term_rows // 2
        self.win = curses.newwin(self.box_height, self.term_cols,
                                 self.term_rows - self.box_height, 0)
        try:
            curses.curs_set(False)
        except curses.error:
            pass
        # transform raw data into list of lines ready to be printed
        s = self.data.splitlines()
        s = [wrap_cells(i, self.term_cols - 3) for i in s]
        self.tdata = [i for j in s for i in j]
        # -3 -- 2 for the box lines and 1 for the title row
        self.nlines = min(len(self.tdata), self.box_height - 3)
        self.scr.refresh()

    def run(self):
        self._running = True
        self._calculate_layout()
        while self._running:
            self.display()
            c = self.scr.getch()
            self.handle_key(c)

    def handle_key(self, key):
        if 0 < key < 256:
            key = chr(key)
        try:
            self.handlers[key]()
        except KeyError:
            pass

    def close(self):
        self._running = False

    def scroll_down(self):
        if self.box_height - 3 + self.hid_rows <= len(self.tdata):
            self.hid_rows += 1
        self.hid_rows = min(len(self.tdata), self.hid_rows)

    def scroll_up(self):
        self.hid_rows -= 1
        self.hid_rows = max(0, self.hid_rows)

    def display(self):
        self.win.erase()
        visible_rows = self.tdata[self.hid_rows:self.hid_rows +
                                  self.nlines]
        try:
            self.win.addstr(1, 1, self.title[:self.term_cols - 3],
                            curses.A_STANDOUT)
            self.win.addstr(2, 1, '\n '.join(visible_rows))
            self.win.box()
        except curses.error:
            # Terminal too small for the pop-up
            pass
        self.win.refresh()


# Characters considered when sniffing the delimiter. Without this list the
# sniffer happily picks letters, e.g. 'm' for a single "Name" column.
SNIFF_DELIMITERS = ',\t;| :\x01\x1f'


def csv_sniff(text):
    """Guess the delimiter of CSV text.

    Sniff the first lines together, then the first line alone (aligned,
    space-delimited data with a commented header isn't consistent across
    lines), then fall back to tab or comma.

    Args:
        text - decoded file contents
    Returns:
        delimiter character

    """
    lines = [i for i in re.split(r'\r\n|\r|\n', text, maxsplit=50)[:50]
             if i.strip()]
    sniffer = csv.Sniffer()
    for sample in ('\n'.join(lines), lines[0] if lines else ''):
        try:
            return sniffer.sniff(sample, delimiters=SNIFF_DELIMITERS).delimiter
        except csv.Error:
            continue
    return '\t' if '\t' in text else ','


def clean_space_delim(lines):
    """Prepare space delimited lines for csv.reader: strip leading and
    trailing whitespace so alignment padding doesn't create empty cells.

    Additionally, if (and only if) the first line begins with '#' or '%',
    strip that off. Common pattern in Matlab and Numpy

    """
    if lines and lines[0][:1] in ('#', '%'):
        lines[0] = lines[0][1:]
    return [i.strip() for i in lines]


def process_data(data, enc=None, delim=None, quoting=None, quote_char='"'):
    """Given the data, check for the encoding, quoting and delimiter and
    return a list of CSV rows (normalized to a single length)

    Args:
        data - bytes or str file contents, a list of bytes or str lines (e.g.
               from readlines()), or a list of rows (list of lists)

    """
    if isinstance(data, (bytes, str)):
        text = data
    elif not data:
        return []
    elif data_list_or_file(data) == 'list':
        # If data is from an object (list of lists) instead of a file
        return pad_data(data)
    else:
        text = data[0][:0].join(data)
    if isinstance(text, bytes):
        text = text.decode(enc or detect_encoding(text))
    # A UTF-8 BOM survives decoding when the encoding was passed in
    text = text.removeprefix('﻿')
    if delim is None:
        delim = csv_sniff(text)
    quoting = getattr(csv, quoting) if quoting else csv.QUOTE_MINIMAL
    # newline='' splits lines on \n, \r\n and \r without translating them,
    # which is what csv.reader expects
    lines = io.StringIO(text, newline='').readlines()
    if delim == ' ':
        lines = clean_space_delim(lines)
        csv_obj = csv.reader(lines, delimiter=delim, quoting=quoting,
                             quotechar=quote_char, skipinitialspace=True)
    else:
        csv_obj = csv.reader(lines, delimiter=delim, quoting=quoting,
                             quotechar=quote_char)
    return pad_data(list(csv_obj))


def data_list_or_file(data):
    """Determine if 'data' is a list of lists or list of strings/bytes

    Reading a file returns a list of byte strings, while a list of lists
    is just a list

    Returns: 'file' if data was from a file, 'list' if from a python list/tuple

    """
    f = isinstance(data[0], (str, bytes))
    return 'file' if f is True else 'list'


def pad_data(d):
    """Pad data rows to the length of the longest row.

        Args: d - list of lists (or other sequences)

    """
    lens = {len(i) for i in d}
    if len(lens) <= 1:
        return d
    max_len = max(lens)
    return [list(i) + [""] * (max_len - len(i)) for i in d]


def has_data(d):
    """True if there is at least one row with at least one column"""
    return bool(d) and any(len(i) for i in d)


def clipboard_commands():
    """Return the clipboard copy commands to try, in order of preference, for
    the current platform and display server.

    """
    cmds = []
    if sys.platform == 'darwin':
        cmds.append(['pbcopy'])
    if os.environ.get('WAYLAND_DISPLAY'):
        cmds.append(['wl-copy'])
    if os.environ.get('DISPLAY'):
        cmds.extend([['xclip', '-selection', 'clipboard'],
                     ['xsel', '--input', '--clipboard']])
    return cmds


def readme():
    """Return the lines of the README shipped with the package"""
    text = resources.files(__package__).joinpath('README.md').read_text(
        encoding='utf-8')
    return text.splitlines(keepends=True)


def help_text():
    """Return the README's keybindings section (a fenced plain text block)
    for the help screen

    """
    lines = readme()
    start = lines.index('## Keybindings\n') + 1
    return ''.join(i for i in lines[start:] if not i.startswith('```'))


def detect_encoding(data=None):
    """Return the locale encoding. If data is passed, guess its encoding: a
    byte order mark if present, otherwise the first of UTF-8, the locale
    encoding and Windows-1252 that decodes it, falling back to Latin-1 (which
    decodes anything).

    Args:
        data - bytes, or a list of bytes lines
    Returns:
        enc - encoding name

    """
    code = locale.getencoding()
    if data is None:
        return code
    if not isinstance(data, bytes):
        data = b''.join(data)
    for bom, enc in ((codecs.BOM_UTF32_LE, 'utf-32'),
                     (codecs.BOM_UTF32_BE, 'utf-32'),
                     (codecs.BOM_UTF8, 'utf-8-sig'),
                     (codecs.BOM_UTF16_LE, 'utf-16'),
                     (codecs.BOM_UTF16_BE, 'utf-16')):
        if data.startswith(bom):
            return enc
    tried = set()
    for enc in ('utf-8', code, 'cp1252'):
        try:
            name = codecs.lookup(enc).name
        except LookupError:
            continue
        if name in tried:
            continue
        tried.add(name)
        try:
            data.decode(enc)
        except UnicodeDecodeError:
            continue
        return enc
    return 'latin-1'


def main(stdscr, *args, **kwargs):
    try:
        curses.use_default_colors()
    except (AttributeError, curses.error):
        pass
    try:
        curses.curs_set(False)
    except (AttributeError, curses.error):
        pass
    Viewer(stdscr, *args, **kwargs).run()


def view(data, enc=None, start_pos=(0, 0), column_width=20, column_gap=2,
         trunc_char='…', column_widths=None, search_str=None,
         double_width=False, delimiter=None, quoting=None, info=None,
         quote_char='"'):
    """The curses.wrapper passes stdscr as the first argument to main +
    passes to main any other arguments passed to wrapper. Initializes
    and then puts screen back in a normal state after closing or
    exceptions.

    Args:
        data: data (filename, path-like, file:// URI, binary or text file
              object, list of lists or tuple of tuples).
              Should be normalized to equal row lengths
        enc: encoding for file/data
        start_pos: initial file position. Either a single integer for just y
            (row) position, or tuple/list (y,x)
        column_width: 'max' (max width for the column),
                      'mode' (uses arithmetic mode to compute width), or
                      int x (x characters wide). Default is 20
        column_gap: gap between columns
        column_widths: list of widths for each column [len1, len2, lenxxx...]
        trunc_char: character to indicate continuation of too-long columns
        search_str: string to search for
        double_width: boolean indicating whether double-width characters
                      should be handled (defaults to False for large files)
        delimiter: CSV delimiter. Typically needed only if the automatic
                   delimiter detection doesn't work. None => automatic
        quoting: CSV quoting. None => automatic. This can be useful when
                 csv.QUOTE_NONE isn't automatically detected, for example when
                 using as a MySQL pager. Allowed values are per the Python
                 documentation:
                     QUOTE_MINIMAL
                     QUOTE_NONNUMERIC
                     QUOTE_ALL
                     QUOTE_NONE
        info: Data information to be displayed on ^g. For example a variable
              name or description of the current data. Defaults to the filename
              or "" if input was not from a file

    """
    if info is None:
        info = ""
    # curses uses LINES/COLUMNS over the real terminal size if they are set
    # (https://bugs.python.org/issue2675), so drop them before initscr
    os.environ.pop('LINES', None)
    os.environ.pop('COLUMNS', None)
    buf = None
    while True:
        try:
            if isinstance(data, (str, os.PathLike)):
                path = os.fspath(data)
                with open(parse_path(path), 'rb') as fd:
                    new_data = fd.read()
                if info == "":
                    info = path
            elif hasattr(data, 'read'):
                new_data = data.read()
            else:
                new_data = data

            new_buf = process_data(new_data, enc, delimiter, quoting,
                                   quote_char)
            if has_data(new_buf):
                buf = new_buf
            elif buf is None:
                print("tabview: no data to display", file=sys.stderr)
                return 1
            # else: the reloaded data is empty, keep showing the old data

            curses.wrapper(main, buf,
                           start_pos=start_pos,
                           column_width=column_width,
                           column_gap=column_gap,
                           trunc_char=trunc_char,
                           column_widths=column_widths,
                           search_str=search_str,
                           double_width=double_width,
                           info=info)
        except QuitException:
            return 0
        except KeyboardInterrupt:
            return 130
        except ReloadException as e:
            start_pos = e.start_pos
            column_width = e.column_width_mode
            column_gap = e.column_gap
            column_widths = e.column_widths
            search_str = e.search_str
            continue


def parse_path(path):
    """Convert a file:// URI to a local path. Anything else is returned
    unchanged, so plain filenames may contain '#', '?', etc.

    """
    if path.startswith('file://'):
        return url2pathname(urlparse(path).path)
    return path
