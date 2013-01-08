#!/usr/bin/env python

""" tabview.py -- View a tab-delimited file in a spreadsheet-like display.
  Contributed by A.M. Kuchling <amk@amk.ca>

  The tab-delimited file is displayed on screen.  The highlighted
  position is shown in the top-left corner of the screen; below it are
  shown the contents of that cell.

   Movement keys are:
     Cursor keys: Move the highlighted cell, scrolling if required.
     Q or q     : Quit
     TAB        : Page right a screen
     Home       : Move to the start of this line
     End        : Move to the end of this line
     PgUp/PgDn  : Move a page up or down
     Insert     : Memorize this position
     Delete     : Return to memorized position (if any)

  TODO: A 'G' for Goto: enter a cell like AA260 and move there
  TODO: A key to re-read the tab-delimited file
  TODO: Generalize to read a list-of-lists as a CSV object
  TODO: Encoding detection?
  TODO: Variable width columns

  Possible projects:
     Allow editing of cells, and then saving the modified data
     Add formula evaluation, and you've got a simple spreadsheet
  program.  (Actually, you should allow displaying both via curses and
  via a Tk widget.)

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


  3/16/2011
  Modified by Scott Hansen
  - Code cleanup and convert to python 3 compatible
  - Added a delimeter argument on the command line
  - Added default delimeter for .txt and .csv (TAB and ,)
  - Switched to CSV module for importing the file
  - Added vim-type navigation (h,j,k,l)

"""
import argparse
import csv
import curses
import re
import traceback

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

def process_data(fn):
    """Given a filename, return it as a list of lists.

    """
    data = []
    with open(fn, 'r', encoding="latin-1") as f:
        csv_obj = csv.reader(f, delimiter=csv_sniff(fn))
        for row in csv_obj:
            data.append(row)
    return data

class Viewer:
    """Create the viewer object

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
        self.scr.clear()
        self.display()

    def run(self):
        # Clear the screen and display the menu of keys
        # Main loop:
        while True:
            self.scr.move(self.y + 2, self.x * self.column_width)     # Move the cursor
            if self.handle_key() is False:
                break

    def handle_key(self):
        c = self.scr.getch()                # Get a keystroke
        if 0 < c < 256:
            c = chr(c)
            # Q or q exits
            if c in 'Qq':
                return False
            elif c == 'j':
                c = curses.KEY_DOWN
            elif c == 'k':
                c = curses.KEY_UP
            elif c == 'h':
                c = curses.KEY_LEFT
            elif c == 'l':
                c = curses.KEY_RIGHT
            elif c == 'J':
                c = curses.KEY_NPAGE
            elif c == 'K':
                c = curses.KEY_PPAGE
            # Tab or 'L' pages one screen to the right
            elif c == '\t' or c == 'L':
                self.win_x = self.win_x + self.num_columns
                self.display()
            elif c == 'H':
                # TODO: page left
                pass
                #self.win_x = self.win_x - self.num_columns
                #self.display()
            elif c == 'm':
                c = curses.KEY_IC
            elif c == 'g':
                c = curses.KEY_DC
            else:
                pass                  # Ignore incorrect keys

        # Cursor keys
        if c == curses.KEY_UP:
            if self.y  ==  0:
                if self.win_y > 0:
                    self.win_y = self.win_y - 1
            else:
                self.y=self.y - 1
            self.display()
        elif c == curses.KEY_DOWN:
            if self.y < self.max_y-3 - 1:
                self.y=self.y + 1
            else:
                self.win_y = self.win_y + 1
            self.display()
        elif c == curses.KEY_LEFT:
            if self.x == 0:
                if self.win_x > 0:
                    self.win_x = self.win_x - 1
            else:
                self.x=self.x - 1
            self.display()
        elif c == curses.KEY_RIGHT:
            if self.x < int(self.max_x/self.column_width) - 1:
                self.x=self.x + 1
            else:
                self.win_x = self.win_x + 1
            self.display()

        # Home key moves to the start of this line
        elif c == curses.KEY_HOME:
            self.win_x = self.x = 0
            self.display()
        # End key moves to the end of this line
        elif c == curses.KEY_END:
            self.move_to_end()
            self.display()

        # PageUp moves up a page
        elif c == curses.KEY_PPAGE:
            self.win_y = self.win_y - (self.max_y - 2)
            if self.win_y < 0:
                self.win_y = 0
            self.display()
        # PageDn moves down a page
        elif c == curses.KEY_NPAGE:
            self.win_y = self.win_y + (self.max_y - 2)
            if self.win_y < 0:
                self.win_y = 0
            self.display()

        # Insert or 'm' memorizes the current position
        elif c == curses.KEY_IC:
            self.save_y, self.save_x = self.y + self.win_y, self.x + self.win_x
        # Delete or 'g' restores a saved position
        elif c == curses.KEY_DC:
            if hasattr(self, 'save_y'):
                self.x = self.y = 0
                self.win_y, self.win_x = self.save_y, self.save_x
                self.display()
        else:
            #stdscr.addstr(0,50, curses.keyname(c)+ ' pressed')
            self.scr.refresh()
            pass                        # Ignore incorrect keys

    def move_to_end(self):
        """Move the highlighted location to the end of the current line."""

        # This is a method because I didn't want to have the code to
        # handle the End key be aware of the internals of the TabFile object.
        yp = self.y + self.win_y
        xp=self.x + self.win_x
        if len(self.data) <= yp:
            end = 0
        else:
            end=len(self.data[yp]) - 1

        # If the end column is on-screen, just change the
        # .x value appropriately.
        if self.win_x <= end < self.win_x + self.num_columns:
            self.x = end - self.win_x
        else:
            if end<self.num_columns:
                self.win_x = 0
                self.x = end
            else:
                self.x = self.num_columns - 1
                self.win_x = end - self.x

    def display(self):
        """Refresh the current display"""
        self.scr.addstr(0, 0,
                        self.yx2str(self.y + self.win_y, self.x + self.win_x)
                        + '    ', curses.A_REVERSE)

        for y in range(0, self.max_y - 3):
            self.scr.move(y + 2, 0)
            self.scr.clrtoeol()
            for x in range(0, int(self.max_x / self.column_width) ):
                self.scr.attrset(curses.A_NORMAL)
                yp = y + self.win_y
                xp=x + self.win_x
                if len(self.data) <= yp:
                    s = ""
                elif len(self.data[yp]) <= xp:
                    s = ""
                else:
                    s = self.data[yp][xp]
                s = s.ljust(15)[0:15]
                if x == self.x and y == self.y:
                    self.scr.attrset(curses.A_STANDOUT)
                self.scr.addstr(y + 2, x * self.column_width, s)

        yp = self.y + self.win_y
        xp = self.x+self.win_x
        if len(self.data) <= yp:
            s = ""
        elif len(self.data[yp]) <= xp:
            s = ""
        else:
            s = self.data[yp][xp]

        self.scr.move(1,0)
        self.scr.clrtoeol()
        self.scr.addstr(s[0:self.max_x])
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

def main(stdscr, fn):
    Viewer(stdscr, process_data(fn)).run()

def curses_init(fn):
    """The curses.wrapper passes stdscr as the first argument to main +
    passes to main any other arguments passed to wrapper. Initializes
    and then puts screen back in a normal state after closing or
    exceptions.

    """
    curses.wrapper(main, fn)

def help():
    """Open README file and return as a string.

    """
    with open("README", 'r') as f:
        txt = f.readlines()
    return "".join(txt)

def arg_parse():
    """Parse filename and show help

    """
    parser = argparse.ArgumentParser(formatter_class=
                                     argparse.RawDescriptionHelpFormatter,
                                     description=help())
    parser.add_argument('filename')
    return parser.parse_args()

if __name__ == '__main__':
    args = arg_parse()
    fn = args.filename
    curses_init(fn)
