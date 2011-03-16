#!/usr/bin/env python

# tabview.py -- View a tab-delimited file in a spreadsheet-like display.
# Contributed by A.M. Kuchling <amk@amk.ca>
#
# The tab-delimited file is displayed on screen.  The highlighted
# position is shown in the top-left corner of the screen; below it are
# shown the contents of that cell.
#
#  Movement keys are:
#    Cursor keys: Move the highlighted cell, scrolling if required.
#    Q or q     : Quit
#    TAB        : Page right a screen
#    Home       : Move to the start of this line
#    End        : Move to the end of this line
#    PgUp/PgDn  : Move a page up or down
#    Insert     : Memorize this position
#    Delete     : Return to memorized position (if any)
#
# TODO: A 'G' for Goto: enter a cell like AA260 and move there
# TODO: A key to re-read the tab-delimited file
#
# Possible projects:
#    Allow editing of cells, and then saving the modified data
#    Add formula evaluation, and you've got a simple spreadsheet
# program.  (Actually, you should allow displaying both via curses and
# via a Tk widget.)
#
# Copyright (c) 2010, Andrew M. Kuchling
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
#
# 3/16/2011
# Modified by Scott Hansen
# - Code cleanup and convert to python 3 compatible
# - Added a delimeter argument on the command line
# - Added default delimeter for .txt and .csv (TAB and ,)
# - Switched to CSV module for importing the file
# - Added vim-type navigation (h,j,k,l)

import sys, curses, re, string, csv, traceback
from os.path import splitext

def yx2str(y,x):
    "Convert a coordinate pair like 1,26 to AA2"
    if x < 26:
        s = chr(65 + x)
    else:
        x = x - 26
        s = chr(65 + (x//26) ) + chr(65 + (x % 26) )
    s = s + '-' + str(y + 1)
    return s

coord_pat = re.compile('^(?P<x>[a-zA-Z]{1,2})-(?P<y>\d+)$')

def str2yx(s):
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

class TabFile:
    def __init__(self, scr, filename, delim, column_width=20):
        self.scr = scr
        self.filename = filename
        self.column_width = column_width
        self.data = []
        rows = csv.reader(open(filename, 'r'), delimiter = delim)
        for i in rows:
            self.data.append(i)
        self.x, self.y = 0,0
        self.win_x, self.win_y = 0,0
        self.max_y, self.max_x = self.scr.getmaxyx()
        self.num_columns = int(self.max_x/self.column_width)
        self.scr.clear()
        self.display()

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
        self.scr.addstr(0, 0, yx2str(self.y + self.win_y, self.x + self.win_x)
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

def main(stdscr):
    filename = sys.argv[1]
    ext = splitext(filename)[1]
    try:
        delim = sys.argv[2]
    except IndexError:
        if ext.lower() == '.txt':
            delim = '\t' 
        else:
            delim = ','

    # Clear the screen and display the menu of keys
    stdscr.clear()
    file = TabFile(stdscr, filename, delim)

    # Main loop:
    while (1):
        stdscr.move(file.y + 2, file.x * file.column_width)     # Move the cursor
        c = stdscr.getch()                # Get a keystroke
        if 0 < c < 256:
            c = chr(c)
            # Q or q exits
            if c in 'Qq':
                break
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
                file.win_x = file.win_x + file.num_columns
                file.display()
            elif c == 'H':
                # TODO: page left
                pass
                #file.win_x = file.win_x - file.num_columns
                #file.display()
            elif c == 'm':
                c = curses.KEY_IC
            elif c == 'g':
                c = curses.KEY_DC
            else: 
                pass                  # Ignore incorrect keys

        # Cursor keys
        if c == curses.KEY_UP:
            if file.y  ==  0:
                if file.win_y > 0:
                    file.win_y = file.win_y - 1
            else:
                file.y=file.y - 1
            file.display()
        elif c == curses.KEY_DOWN:
            if file.y < file.max_y-3 - 1:
                file.y=file.y + 1
            else:
                file.win_y = file.win_y + 1
            file.display()
        elif c == curses.KEY_LEFT:
            if file.x == 0:
                if file.win_x > 0:
                    file.win_x = file.win_x - 1
            else:
                file.x=file.x - 1
            file.display()
        elif c == curses.KEY_RIGHT:
            if file.x < int(file.max_x/file.column_width) - 1:
                file.x=file.x + 1
            else:
                file.win_x = file.win_x + 1
            file.display()

        # Home key moves to the start of this line
        elif c == curses.KEY_HOME:
            file.win_x = file.x = 0
            file.display()
        # End key moves to the end of this line
        elif c == curses.KEY_END:
            file.move_to_end()
            file.display()

        # PageUp moves up a page
        elif c == curses.KEY_PPAGE:
            file.win_y = file.win_y - (file.max_y - 2)
            if file.win_y < 0:
                file.win_y = 0
            file.display()
        # PageDn moves down a page
        elif c == curses.KEY_NPAGE:
            file.win_y = file.win_y + (file.max_y - 2)
            if file.win_y < 0:
                file.win_y = 0
            file.display()

        # Insert or 'm' memorizes the current position
        elif c == curses.KEY_IC:
            file.save_y, file.save_x = file.y + file.win_y, file.x + file.win_x
        # Delete or 'g' restores a saved position
        elif c == curses.KEY_DC:
            if hasattr(file, 'save_y'):
                file.x = file.y = 0
                file.win_y, file.win_x = file.save_y, file.save_x
                file.display()
        else:
            #stdscr.addstr(0,50, curses.keyname(c)+ ' pressed')
            stdscr.refresh()
            pass                        # Ignore incorrect keys

if __name__ == '__main__':
    if len(sys.argv) == 1:
        print ("Usage: tabview.py <filename> <delimeter>\nDefault "
        "delimiter is , for *.csv and TAB for *.txt")
        sys.exit()
    try:
        # Initialize curses
        stdscr=curses.initscr()
        # Turn off echoing of keys, and enter cbreak mode,
        # where no buffering is performed on keyboard input
        curses.noecho()
        curses.cbreak()

        # In keypad mode, escape sequences for special keys
        # (like the cursor keys) will be interpreted and
        # a special value like curses.key_left will be returned
        stdscr.keypad(1)
        main(stdscr)                    # Enter the main loop
        # Set everything back to normal
        stdscr.keypad(0)
        curses.echo() 
        curses.nocbreak()
        curses.endwin()                 # Terminate curses
    except:
        # In the event of an error, restore the terminal
        # to a sane state.
        stdscr.keypad(0)
        curses.echo()
        curses.nocbreak()
        curses.endwin()
        traceback.print_exc()           # Print the exception
