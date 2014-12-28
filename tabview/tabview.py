""" tabview.py -- View a tab-delimited file in a spreadsheet-like display.

  Scott Hansen <firecat four one five three at gmail dot com>
  Based on code contributed by A.M. Kuchling <amk at amk dot ca>

"""
import csv
import curses
import _curses
import locale
import os
import os.path
import re
import sys
from operator import itemgetter
from subprocess import Popen, PIPE
from textwrap import wrap


class Viewer:
    """The actual CSV viewer class.

    Args:
        scr: curses window object
        data: data (list of lists)
        column_width: fixed width for each column

    """
    def __init__(self, scr, data, column_width=20):
        self.scr = scr
        self.reload = False
        self.data = [[str(j) for j in i] for i in data]
        self.header = self.data[0]
        del self.data[0]
        self.header_offset = 3
        self.column_width = column_width
        self.coord_pat = re.compile('^(?P<x>[a-zA-Z]{1, 2})-(?P<y>\d+)$')
        self.x, self.y = 0, 0
        self.win_x, self.win_y = 0, 0
        self.max_y, self.max_x = self.scr.getmaxyx()
        self.num_columns = int(self.max_x / self.column_width)
        self.res = []
        self.res_idx = 0
        self.modifier = str()
        self.keys()
        self.scr.clear()
        self.display()

    def keys(self):
        """Define methods for each allowed key press.

        """
        def quit():
            sys.exit()

        def reload():
            self.reload = True

        def down():
            end = len(self.data) - 1
            if self.win_y + self.y < end:
                if self.y < self.max_y - 4:
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
            elif self.x < int(self.max_x / self.column_width) - 1:
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
                self.win_y = 0
            else:
                self.win_x = self.win_x - self.num_columns

        def mark():
            self.save_y, self.save_x = self.y + self.win_y, self.x + self.win_x

        def goto_mark():
            if hasattr(self, 'save_y'):
                self.x = self.y = 0
                self.win_y, self.win_x = self.save_y, self.save_x

        def home():
            self.win_y = self.y = 0

        def goto():
            end = len(self.data)
            if self.modifier == str():
                # Goto the bottom of the current column if no modifier
                # is present
                if self.win_y > end - self.max_y + self.header_offset:
                    # If on the last page already, just move self.y
                    self.y = end - self.win_y - 1
                else:
                    self.win_y = end - self.max_y + self.header_offset
                    self.y = self.max_y - self.header_offset - 1
            else:
                # Goto line number given if available
                m = int(self.modifier)
                if m > 0 and m <= end:
                    if self.win_y > end - self.max_y + self.header_offset:
                        if m <= self.win_y:
                            # If going back up off the last page:
                            self.y = 0
                            self.win_y = m - 1
                        else:
                            # If on the last page already and staying
                            # there, just move self.y
                            self.y = m - 1 - self.win_y
                    else:
                        self.y = 0
                        self.win_y = m - 1
                self.modifier = str()

        def line_home():
            self.win_x = self.x = 0

        def line_end():
            yp = self.y + self.win_y
            if len(self.data) <= yp:
                end = 0
            else:
                end = len(self.data[yp]) - 1

            # If the end column is on-screen, just change the
            # .x value appropriately.
            if self.win_x <= end < self.win_x + self.num_columns:
                self.x = end - self.win_x
            else:
                if end < self.num_columns:
                    self.win_x = 0
                    self.x = end
                else:
                    self.x = self.num_columns - 1
                    self.win_x = end - self.x

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
            scr2.addstr(1, 1, "\n".join(s))
            scr2.box()
            while not scr2.getch():
                pass

        def search():
            """Search (case independent) from the top for string and goto
            that spot"""
            scr2 = curses.newwin(4, 40, 15, 15)
            scr2.box()
            scr2.move(1, 1)
            scr2.addstr("Search: ")
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
            scr2.addstr(1, 1, " ".join(help_txt))
            scr2.box()
            while not scr2.getch():
                pass

        def toggle_header():
            if self.header_offset == 3:
                self.header_offset = 2
                self.data.insert(0, self.header)
                self.y = self.y + 1
            else:
                self.header_offset = 3
                del self.data[self.data.index(self.header)]
                self.y = self.y - 1

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
                     'G':   goto,
                     '\n':  show_cell,
                     '/':   search,
                     'n':   next_result,
                     'p':   prev_result,
                     't':   toggle_header,
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
        while not self.reload and True:
            self.display()
            self.scr.move(self.y + self.header_offset,
                          self.x * self.column_width)
            # Move the cursor back to the highlighted block, then wait
            # for a valid keypress
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
        has_modifier = not self.modifier == str()
        try:
            if found_digit and has_modifier:
                # Add the digit to the modifier rather than executing a command
                self.handle_modifier(c)
            else:
                self.keys[c]()
        except KeyError:
            # Ignore incorrect keys
            self.handle_modifier(c)
        else:
            if not found_digit:
                # Don't clear the modifier if we the last character was a digit
                self.modifier = str()

    def handle_modifier(self, mod):
        """Append digits as a key modifier, clear the modifier if not
        a digit.

        Args:
            mod: potential modifier key
        """
        self.scr.refresh()
        try:
            if mod.isdigit():
                self.modifier = "{}{}".format(self.modifier, mod)
            else:
                self.modifier = str()
        except AttributeError:
            # Ignore illegal keys
            self.modifier = str()

    def resize(self):
        """Handle terminal resizing

        """
        # Check if screen was re-sized (True or False)
        resize = curses.is_term_resized(self.max_y, self.max_x)
        if resize is True:
            self.max_y, self.max_x = self.scr.getmaxyx()
            self.scr.clear()
            curses.resizeterm(self.max_y, self.max_x)
            num_columns = max(int(self.max_x / self.column_width), 1)
            if num_columns < self.num_columns:
                self.num_columns = num_columns
                self.x = max(self.x - 1, 0)
            if self.y > self.max_y - self.header_offset - 1:
                self.y = max(self.max_y - self.header_offset - 1, 0)
            self.scr.refresh()

    def display(self):
        """Refresh the current display"""
        # Print the current cursor cell in the top left corner
        self.scr.move(0, 0)
        self.scr.clrtoeol()
        self.scr.addstr(0, 0, "  {}  ".format(
                        self.yx2str(self.y + self.win_y, self.x + self.win_x)),
                        curses.A_REVERSE)

        # Adds the current cell content after the 'current cell' display
        yp = self.y + self.win_y
        xp = self.x + self.win_x
        if len(self.data) <= yp or len(self.data[yp]) <= xp:
            s = ""
        else:
            s = str(self.data[yp][xp])
        if '\n' in s:
            s = s.replace('\n', '\\n')
        self.scr.move(0, 20)
        self.scr.clrtoeol()
        self.scr.addstr(s[0: self.max_x - 20], curses.A_NORMAL)

        # Print a divider line
        self.scr.move(1, 0)
        self.scr.clrtoeol()
        self.scr.hline(curses.ACS_HLINE, self.max_x)

        # Print the header if the correct offset is set
        if self.header_offset == 3:
            self.scr.move(2, 0)
            self.scr.clrtoeol()
            for x in range(0, int(self.max_x / self.column_width)):
                self.scr.attrset(curses.A_NORMAL)
                xp = x + self.win_x
                if len(self.header) <= xp:
                    s = ""
                else:
                    s = str(self.header[xp])
                s = s.ljust(15)[0:15]
                if '\n' in s:
                    s = s.replace('\n', '\\n')
                # Note: the string is offset right by 1 space in each
                # column to ensure the whole string is reverse video.
                self.scr.addstr(2, x * self.column_width, " {}".format(s),
                                curses.A_BOLD)

        # Print the table data
        for y in range(0, self.max_y - self.header_offset):
            self.scr.move(y + self.header_offset, 0)
            self.scr.clrtoeol()
            for x in range(0, int(self.max_x / self.column_width)):
                self.scr.attrset(curses.A_NORMAL)
                yp = y + self.win_y
                xp = x + self.win_x
                if len(self.data) <= yp or len(self.data[yp]) <= xp:
                    s = ""
                else:
                    s = str(self.data[yp][xp])
                s = s.ljust(15)[0:15]
                if x == self.x and y == self.y and self.y < len(self.data):
                    self.scr.attrset(curses.A_REVERSE)
                if '\n' in s:
                    s = s.replace('\n', '\\n')
                # Note: the string is offset right by 1 space in each
                # column to ensure the whole string is reverse video.
                self.scr.addstr(y + self.header_offset, x * self.column_width,
                                " {}".format(s))
                self.scr.attrset(curses.A_NORMAL)
        self.scr.refresh()

    def yx2str(self, y, x):
        "Convert a coordinate pair like 1,26 to AA2"
        if x < 26:
            s = chr(65 + x)
        else:
            x = x - 26
            s = chr(65 + (x // 26)) + chr(65 + (x % 26))
        s = s + '-' + str(y + 1)
        return s

    def str2yx(self, s):
        "Convert a string like A1 to a coordinate pair like 0,0"
        match = self.coord_pat.match(s)
        if not match:
            return None
        y, x = match.group('y', 'x')
        x = x.upper()
        if len(x) == 1:
            x = ord(x) - 65
        else:
            x = (ord(x[0]) - 65) * 26 + ord(x[1]) - 65 + 26
        return int(y) - 1, x


def csv_sniff(fn, enc):
    """Given a filename or a list of lists, sniff the dialect of the
    file and return the delimiter. This should keep any errors from
    popping up with tab or comma delimited files.

    Args:
        fn - complete file path/name or list like
            ["col1,col2,col3","data1,data2,data3","data1...]
        enc - python encoding value ('utf_8','latin-1','cp870', etc)
    Returns:
        delimiter - ',' or '\t' or other delimiter

    """
    try:
        # If fn is a filename
        with open(fn, 'r', encoding=enc) as f:
            dialect = csv.Sniffer().sniff(f.readline())
            return dialect.delimiter
    except TypeError:
        # If fn is a list, check the first item in the list
        dialect = csv.Sniffer().sniff(fn[0])
        return dialect.delimiter


def main(stdscr, data):
    curses.use_default_colors()
    Viewer(stdscr, data).run()


def process_file(fn, enc=None):
    """Given a filename, return the file as a list of lists.

    """
    if enc is None:
        enc = set_encoding(fn)
    data = []
    with open(fn, 'r', encoding=enc) as f:
        csv_obj = csv.reader(f, delimiter=csv_sniff(fn, enc))
        for row in csv_obj:
            data.append(row)
    return data


def readme():
    path = os.path.dirname(os.path.realpath(__file__))
    fn = os.path.join(path, "README.rst")
    with open(fn, 'r') as f:
        return f.readlines()


def set_encoding(fn=None):
    """Return the default system encoding. If a filename is passed, try
    to decode the file with the default system encoding or from a short
    list of encoding types to test.

    Args:
        fn(optional) - complete path to file

    Returns:
        enc - system encoding

    """
    enc_list = ['UTF-8', 'LATIN-1', 'iso8859-1', 'iso8859-2',
                'UTF-16', 'CP720']
    locale.setlocale(locale.LC_ALL, '')
    code = locale.getpreferredencoding()
    if code not in enc_list:
        enc_list.insert(0, code)
    if fn is not None:
        for c in enc_list:
            try:
                with open(fn, 'r', encoding=c) as f:
                    f.read()
            except (UnicodeDecodeError, UnicodeError):
                continue
            return c
        print("Encoding not detected. Please pass encoding value manually")
    else:
        return code


def view(data=None, fn=None, enc=None):
    """The curses.wrapper passes stdscr as the first argument to main +
    passes to main any other arguments passed to wrapper. Initializes
    and then puts screen back in a normal state after closing or
    exceptions.

    Args:
        data: list of lists, tuple of tuples, etc. Any tabular data.
            If 'data' is passed, 'fn' and 'enc' will be ignored
        fn: filename
        enc: encoding for file

    """
    while True:
        if data is not None:
            d = data
        elif fn is not None:
            d = process_file(fn, enc)
        try:
            curses.wrapper(main, d)
        except _curses.error:
            continue
