#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" tabview -- View a tab-delimited file in a spreadsheet-like display.
  Scott Hansen <firecat four one five three at gmail dot com>
  Based on code contributed by A.M. Kuchling <amk at amk dot ca>

  Usage:
      From command line:  tabview <filename>
      From python command line to view an object:
          import tabview.tabview as t
          a = [["a","b","c"], ["d","e","f"]]
          t.view(a)
      From python command line to view a file:
          import tabview.tabview as t
          t.view(fn=<filename>[, enc=<encoding>])

"""
from __future__ import print_function, unicode_literals
import argparse
import csv
import os
import sys
from tabview.tabview import view


def arg_parse():
    """Parse filename and show help."""
    parser = argparse.ArgumentParser(description="View a tab-delimited file "
                                     "in a spreadsheet-like display. "
                                     "Press F1 or '?' while running for a "
                                     "list of available keybindings.")
    parser.add_argument('filename', help="File to read. Use '-' to read from "
                        "the standard input instead.")
    parser.add_argument('--encoding', '-e', help="Encoding, if required.  "
                        "If the file is UTF-8, Latin-1(iso8859-1) or a few "
                        "other common encodings, it should be detected "
                        "automatically. If not, you can pass "
                        "'CP720', or 'iso8859-2', for example.")
    parser.add_argument('--delimiter', '-d', default=None,
                        help="CSV delimiter. Not typically necessary since "
                        "automatic delimiter sniffing is used.")
    parser.add_argument('--quoting', default=None,
                        choices=[i for i in dir(csv) if i.startswith("QUOTE")],
                        help="CSV quoting style. Not typically required.")
    parser.add_argument('--start_pos', '-s',
                        help="Initial cursor display position. "
                        "Single number for just y (row) position, or two "
                        "comma-separated numbers (--start_pos 2,3) for both. "
                        "Alternatively, you can pass the numbers in the more "
                        "classic +y:[x] format without the --start_pos label. "
                        "Like 'tabview <fn> +5:10'")
    parser.add_argument('--width', '-w', default=20,
                        help="Specify column width. 'max' or 'mode' (default) "
                        "for variable widths, or an integer value for "
                        "fixed column width.")
    parser.add_argument('--double_width', action='store_true', default=False,
                        help="Force full handling of double-width characters "
                        "for large files (with a performance penalty)")
    parser.add_argument('--quote-char', '-q', default=str('"'),
                        help="Quote character. Not typically necessary.")
    return parser.parse_known_args()


def start_position(start_norm, start_classic):
    """Given a string "[y, x, ...]" or a string "+[y]:[x]", return a tuple (y, x)
    for the start position

    Args: start_norm - string [y,x, ...]
          start_classic - string "+[y]:[x]"

    Returns: tuple (y, x)

    """
    if start_norm is not None:
        start_pos = start_norm.split(',')[:2]
        if not start_pos[0]:
            start_pos[0] = 0
        start_pos = [int(i) for i in start_pos]
    elif start_classic:
        sp = start_classic[0].strip('+').split(':')
        if not sp[0]:
            sp[0] = 0
        try:
            start_pos = (int(sp[0]), int(sp[1]))
        except IndexError:
            start_pos = (int(sp[0]), 0)
    else:
        start_pos = (0, 0)
    return start_pos


def fixup_stdin():
    print("tabview: Reading from stdin...", file=sys.stderr)
    data = os.fdopen(os.dup(0), 'rb')
    os.dup2(os.open("/dev/tty", os.O_RDONLY), 0)
    return data


def tabview_cli():
    args, extra = arg_parse()
    pos_plus = [i for i in extra if i.startswith('+')]
    start_pos = start_position(args.start_pos, pos_plus)
    if args.filename != '-':
        data = args.filename
    else:
        data = fixup_stdin()
    view(data, enc=args.encoding, start_pos=start_pos,
         column_width=args.width, double_width=args.double_width,
         delimiter=args.delimiter, quoting=args.quoting, quote_char=args.quote_char)


if __name__ == '__main__':
    tabview_cli()
