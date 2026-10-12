""" tabview -- View a tab-delimited file in a spreadsheet-like display.
  Scott Hansen <firecat four one five three at gmail dot com>
  Based on code contributed by A.M. Kuchling <amk at amk dot ca>

  Usage:
      From command line:  tabview <filename>
      From python command line to view an object:
          import tabview as t
          a = [["a","b","c"], ["d","e","f"]]
          t.view(a)
      From python command line to view a file:
          import tabview as t
          t.view(<filename>[, enc=<encoding>])

"""
import argparse
import codecs
import csv
import os
import sys

from .tabview import view


def char_arg(value):
    """argparse type for a single character. Accepts backslash escapes such as
    '\\t' or '\\x01', since those are hard to type literally.

    """
    try:
        value = value.encode('latin-1', 'backslashreplace').decode(
            'unicode_escape')
    except UnicodeDecodeError:
        value = ''
    if len(value) != 1:
        raise argparse.ArgumentTypeError(
            "must be a single character (escapes like '\\t' are allowed)")
    return value


def build_parser():
    """Build the command line parser."""
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
    parser.add_argument('--delimiter', '-d', default=None, type=char_arg,
                        help="CSV delimiter. Not typically necessary since "
                        "automatic delimiter sniffing is used. Escapes like "
                        "'\\t' or '\\x01' are accepted.")
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
                        help="Specify column width. 'max' or 'mode' "
                        "for variable widths, or an integer value for "
                        "fixed column width (default: %(default)s).")
    parser.add_argument('--double_width', action='store_true', default=False,
                        help="Force full handling of double-width characters "
                        "for large files (with a performance penalty)")
    parser.add_argument('--quote-char', '-q', default='"', type=char_arg,
                        help="Quote character. Not typically necessary.")
    return parser


def start_position(start_norm, start_classic):
    """Given a string "[y, x, ...]" or a list of strings starting with
    "+[y]:[x]", return a tuple (y, x) for the start position. Missing values
    are 0.

    Args: start_norm - string [y,x, ...]
          start_classic - list of strings "+[y]:[x]"

    Returns: tuple (y, x)
    Raises: ValueError if a value isn't an integer

    """
    if start_norm is not None:
        parts = start_norm.split(',')
    elif start_classic:
        parts = start_classic[0].removeprefix('+').split(':')
    else:
        parts = []
    y, x = ([int(i) if i.strip() else 0 for i in parts[:2]] + [0, 0])[:2]
    return y, x


def fixup_stdin():
    """Return stdin as a binary file and reopen the terminal as stdin, so
    curses can read keys.

    Raises: OSError if there is no terminal

    """
    print("tabview: Reading from stdin...", file=sys.stderr)
    data = os.fdopen(os.dup(0), 'rb')
    os.dup2(os.open("/dev/tty", os.O_RDONLY), 0)
    return data


def main():
    parser = build_parser()
    args, extra = parser.parse_known_args()
    pos_plus = [i for i in extra if i.startswith('+')]
    unknown = [i for i in extra if not i.startswith('+')]
    if unknown:
        parser.error(f"unrecognized arguments: {' '.join(unknown)}")
    try:
        start_pos = start_position(args.start_pos, pos_plus)
    except ValueError:
        parser.error("start position must be integers, like '+5:10' or "
                     "'--start_pos 5,10'")
    if args.encoding is not None:
        try:
            codecs.lookup(args.encoding)
        except LookupError:
            parser.error(f"unknown encoding: {args.encoding}")
    if args.filename != '-':
        data = args.filename
    else:
        try:
            data = fixup_stdin()
        except OSError as e:
            print(f"tabview: can't open the terminal for input: {e}",
                  file=sys.stderr)
            return 1
    try:
        return view(data, enc=args.encoding, start_pos=start_pos,
                    column_width=args.width, double_width=args.double_width,
                    delimiter=args.delimiter, quoting=args.quoting,
                    quote_char=args.quote_char)
    except OSError as e:
        print(f"tabview: {e}", file=sys.stderr)
        return 1
