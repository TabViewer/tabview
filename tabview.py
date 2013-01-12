#!/usr/bin/env python

""" tabview.py -- View a tab-delimited file in a spreadsheet-like display.
  Scott Hansen <firecat four one five three at gmail dot com>
  Based on code contributed by A.M. Kuchling <amk at amk dot ca>

  Usage:
      From command line:  ./tabview.py <filename>
      From python command line to view an object:
          import tabview
          a = [["a","b","c"], ["d","e","f"]]
          tabview.view(a)
      From python command line to view a file:
          import tabview
          data = tabview.process_file(filename)
          tabview.view(data)

  Copyright (c) 2013, Scott Hansen
  Copyright (c) 2010, Andrew M. Kuchling

  Permission is hereby granted, free of charge, to any person obtaining a copy
  of this software and associated documentation files (the "Software"), to deal
  in the Software without restriction, including without limitation the rights
  to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
  copies of the Software, and to permit persons to whom the Software is
  furnished to do so, subject to the following conditions:

  The above copyright notice and this permission notice shall be included in
  all copies or substantial portions of the Software.

  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
  OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
  THE SOFTWARE.

"""
import argparse
import csv
import curses
import os.path
import re
import sys
import traceback
from textwrap import wrap

def csv_sniff(fn):
    """Given a filename or a list of lists, sniff the dialect of the
    file and return the delimiter. This should keep any errors from
    popping up with tab or comma delimited files.

    Args:
        fn - complete file path/name or list like
            ["col1,col2,col3","data1,data2,data3","data1...]
    Returns:
        delimiter - ',' or '\t' or other delimiter

    """
    try:
        # If fn is a filename
        with open(fn) as f:
            dialect = csv.Sniffer().sniff(f.readline())
            return dialect.delimiter
    except TypeError:
        # If fn is a list, check the first item in the list
        dialect = csv.Sniffer().sniff(fn[0])
        return dialect.delimiter

def process_file(fn):
    """Given a filename, return the file as a list of lists.

    """
    data = []
    with open(fn, 'r', encoding="latin-1") as f:
        csv_obj = csv.reader(f, delimiter=csv_sniff(fn))
        for row in csv_obj:
            data.append(row)
    return data

class Viewer:
    """The actual CSV viewer class.

    Args:
        scr: curses window object
        data: data (list of lists)
        column_width: fixed width for each column

    """
    def __init__(self, scr, data, column_width=20):
        self.scr = scr
        self.data = data
        self.column_width = column_width
        self.coord_pat = re.compile('^(?P<x>[a-zA-Z]{1,2})-(?P<y>\d+)$')
        self.x, self.y = 0,0
        self.win_x, self.win_y = 0,0
        self.max_y, self.max_x = self.scr.getmaxyx()
        self.num_columns = int(self.max_x/self.column_width)
        self.keys()
        self.scr.clear()
        self.display()

    def keys(self):
        """Define methods for each allowed key press.

        """
        def quit():
            sys.exit()

        def down():
            end = len(self.data) - 1
            if self.win_y + self.y < end:
                if self.y < self.max_y - 4:
                    self.y = self.y + 1
                else:
                    self.win_y = self.win_y + 1

        def up():
            if self.y  ==  0:
                if self.win_y > 0:
                    self.win_y = self.win_y - 1
            else:
                self.y=self.y - 1

        def left():
            if self.x == 0:
                if self.win_x > 0:
                    self.win_x = self.win_x - 1
            else:
                self.x=self.x - 1

        def right():
            yp = self.y + self.win_y
            end = len(self.data[yp]) - 1
            if self.win_x + self.x >= end:
                pass
            elif self.x < int(self.max_x/self.column_width) - 1:
                self.x=self.x + 1
            else:
                self.win_x = self.win_x + 1

        def page_down():
            end = len(self.data) - 1
            if self.win_y + self.max_y - 2 > end:
                pass
            else:
                self.win_y = self.win_y + (self.max_y - 2)

        def page_up():
            self.win_y = self.win_y - (self.max_y - 2)
            if self.win_y < 0:
                self.win_y = 0

        def page_right():
            yp = self.y + self.win_y
            end = len(self.data[yp]) - 1
            if self.win_x + self.num_columns > end:
                pass
            else:
                self.win_x = self.win_x + self.num_columns

        def page_left ():
            self.win_x = self.win_x - self.num_columns
            if self.win_x < 0:
                self.win_x = 0

        def mark():
            self.save_y, self.save_x = self.y + self.win_y, self.x + self.win_x

        def goto_mark():
            if hasattr(self, 'save_y'):
                self.x = self.y = 0
                self.win_y, self.win_x = self.save_y, self.save_x

        def home():
            self.win_x = self.x = self.win_y = self.y = 0

        def end():
            end = len(self.data) + 3
            self.win_y = end - self.max_y
            self.y = self.max_y - 4

        def line_home():
            self.win_x = self.x = 0

        def line_end():
            yp = self.y + self.win_y
            xp = self.x + self.win_x
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
            s = wrap(str(self.data[yp][xp]), 58, subsequent_indent="  ")
            lines = len(s) + 2
            scr2 = curses.newwin(lines,60,15,15)
            scr2.move(0,0)
            scr2.addstr(1, 1, "\n".join(s))
            scr2.box()
            while not scr2.getch():
                pass

        self.keys = {
                     'j':   down,
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
                     'g':   home,
                     'G':   end,
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
                     '\n':  show_cell,
                    }

    def run(self):
        # Clear the screen and display the menu of keys
        # Main loop:
        while True:
            # Move the cursor back to the highlighted block, then wait
            # for a valid keypress
            self.scr.move(self.y + 2, self.x * self.column_width)
            self.handle_keys()

    def handle_keys(self):
        """Determine what method to call for each keypress.

        """
        c = self.scr.getch()  # Get a keystroke
        if 0 < c < 256:
            c = chr(c)
        try:
            self.keys[c]()
            self.display()
        except KeyError:
            # Ignore incorrect keys
            self.scr.refresh()
            pass

    def display(self):
        """Refresh the current display"""
        # Print the current cursor cell in the top left corner
        self.scr.move(0,0)
        self.scr.clrtoeol()
        self.scr.addstr(0, 0, "  {}  ".format(
                        self.yx2str(self.y + self.win_y, self.x + self.win_x)),
                        curses.A_REVERSE)

        # Adds the current cell content into row 2
        yp = self.y + self.win_y
        xp = self.x+self.win_x
        if len(self.data) <= yp or len(self.data[yp]) <= xp:
            s = ""
        else:
            s = str(self.data[yp][xp])
        self.scr.move(0,20)
        self.scr.clrtoeol()
        self.scr.addstr(s[0:self.max_x-20], curses.A_NORMAL)

        # Print a divider line
        self.scr.move(1,0)
        self.scr.clrtoeol()
        self.scr.hline(curses.ACS_HLINE, self.max_x)

        # Print the table data
        for y in range(0, self.max_y - 3):
            self.scr.move(y + 2, 0)
            self.scr.clrtoeol()
            for x in range(0, int(self.max_x / self.column_width) ):
                self.scr.attrset(curses.A_NORMAL)
                yp = y + self.win_y
                xp = x + self.win_x
                if len(self.data) <= yp or len(self.data[yp]) <= xp:
                    s = ""
                else:
                    s = str(self.data[yp][xp])
                s = s.ljust(15)[0:15]
                if x == self.x and y == self.y:
                    self.scr.attrset(curses.A_REVERSE)
                # Note: the string is offset right by 1 space in each
                # column to ensure the whole string is reverse video.
                self.scr.addstr(y + 2, x * self.column_width, " {}".format(s))
        self.scr.refresh()

    def yx2str(self,y,x):
        "Convert a coordinate pair like 1,26 to AA2"
        if x < 26:
            s = chr(65 + x)
        else:
            x = x - 26
            s = chr(65 + (x//26) ) + chr(65 + (x % 26) )
        s = s + '-' + str(y + 1)
        return s

    def str2yx(self,s):
        "Convert a string like A1 to a coordinate pair like 0,0"
        match = coord_pat.match(s)
        if not match:
            return None
        y, x = match.group('y', 'x')
        x = x.upper()
        if len(x) == 1:
            x = ord(x) - 65
        else:
            x = (ord(x[0]) - 65) * 26 + ord(x[1]) - 65 + 26
        return int(y) - 1, x

def main(stdscr, data):
    Viewer(stdscr, data).run()

def view(data):
    """The curses.wrapper passes stdscr as the first argument to main +
    passes to main any other arguments passed to wrapper. Initializes
    and then puts screen back in a normal state after closing or
    exceptions.

    Args:
        data: list of lists, tuple of tuples, etc. Any tabular data.

    """
    curses.wrapper(main, data)

def arg_parse():
    """Parse filename and show help. Assumes README is in the same
    directory as tabview.py

    """
    script_dir = os.path.dirname(os.path.realpath(__file__))
    fn = os.path.join(script_dir, "README")
    with open(fn, 'r') as f:
        help_txt = "".join(f.readlines())
    parser = argparse.ArgumentParser(formatter_class=
                                     argparse.RawDescriptionHelpFormatter,
                                     description=help_txt)
    parser.add_argument('filename')
    return parser.parse_args()

if __name__ == '__main__':
    args = arg_parse()
    data = process_file(args.filename)
    view(data)
